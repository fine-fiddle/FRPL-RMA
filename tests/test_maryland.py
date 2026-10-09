import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT, connect
from prepare_maryland import EXTRACT, OUTPUT, validate, percentage, income_value
from state_snapshot import import_snapshot


class MarylandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((OUTPUT / 'schools.json').read_text())

    def test_native_totals_and_independent_income_denominator(self):
        validate(self.payload)
        for value in ['*', '<=5', '>=95', '-', '', 'NaN']:
            self.assertIsNone(percentage(value))
        self.assertEqual(percentage('0'), 0)
        for school in self.payload['schools']:
            raw = school['income_raw']
            if school['income'] is not None:
                self.assertEqual(school['income'], 100 * int(raw['Economically Disadvantaged Cnt']) / int(raw['Total Student Cnt']))
            for native in school['outcomes'].values():
                self.assertIsNone(native['tested'])
                self.assertTrue(native['raw']['Assessment'].strip().endswith('All Grades'))
        # Early Attendance and September enrollment are different collections.
        school = next(s for s in self.payload['schools'] if s['id'] == '01-0301')
        september = next(r for r in school['grades_raw'] if r['Grade'] == 'All Grades')
        self.assertNotEqual(school['enrollment'], int(september['Enrolled Count']))

    def test_grade_high_school_foreign_ids_and_years_cannot_enter(self):
        base = next(i for i, s in enumerate(self.payload['schools']) if s['outcomes'])
        for change in ['income_year', 'income_id', 'directory_id', 'nces', 'grade_span', 'high_grade', 'adjusted_ccd', 'assessment_year', 'grade_rate', 'tested']:
            payload = copy.deepcopy(self.payload)
            school = payload['schools'][base]
            native = next(iter(school['outcomes'].values()))
            if change == 'income_year': school['income_rows_raw'][0]['Academic Year'] = '2024'
            elif change == 'income_id': school['income_rows_raw'][0]['School Number'] = '9999'
            elif change == 'directory_id': school['directory_raw']['School'] = '9999'
            elif change == 'nces': school['directory_raw']['NCES Number'] = '999999999999'
            elif change == 'grade_span': school['directory_raw']['Grade Span'] = 'EMH'
            elif change == 'high_grade': school['grades_raw'].append(dict(school['grades_raw'][0], Grade='Grade 9', **{'Enrolled Cnt': '*'}))
            elif change == 'adjusted_ccd': school['ccd_raw']['IGOFFERED'] = 'Adjusted'
            elif change == 'assessment_year': native['raw']['Year'] = 2024
            elif change == 'grade_rate': native['raw']['Assessment'] = 'Mathematics Grade 3'
            else: native['tested'] = 100
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(payload)

    def test_suppression_and_whole_school_income_are_preserved(self):
        raw = dict(self.payload['schools'][0]['income_raw'])
        raw.update({'School Type': 'All', 'Total Student Cnt': '100', 'Economically Disadvantaged Cnt': '99', 'Economically Disadvantaged Pct': '>=95'})
        self.assertIsNone(income_value([raw])[2])
        bands = [dict(raw, **{'School Type': 'Elementary', 'Economically Disadvantaged Pct': '99'}), dict(raw, **{'School Type': 'Middle', 'Economically Disadvantaged Pct': '99'})]
        self.assertIsNone(income_value(bands)[2])
        self.assertIsNone(income_value(bands + [raw])[2])
        with self.assertRaises(ValueError): income_value([raw, raw])
        self.assertFalse(any(m['tested'] is not None or m['low'] is not None or m['high'] is not None
            for s in self.output['schools'] for m in s['metrics'].values()))

    def test_independent_deleted_school_models(self):
        self.assertEqual(set(self.output['levels']), {'ES'})
        for subject, model in self.output['models']['ES'].items():
            schools = [s for s in self.output['schools'] if subject in s['metrics']]
            x = np.array([s['income'] for s in schools]); y = np.array([s['metrics'][subject]['actual'] for s in schools])
            X = np.column_stack([np.ones(len(x)), x]); beta = np.linalg.lstsq(X, y, rcond=None)[0]
            self.assertEqual(model['n'], len(schools)); self.assertAlmostEqual(model['slope'], beta[1], places=9)
            for i in [0, len(x)//2, len(x)-1]:
                keep = np.arange(len(x)) != i; deleted = np.linalg.lstsq(X[keep], y[keep], rcond=None)[0]
                errors = y[keep] - X[keep] @ deleted; variance = errors @ errors / (len(x)-3)
                leverage = X[i] @ np.linalg.inv(X.T @ X) @ X[i]
                t = (y[i] - X[i] @ beta) / np.sqrt(variance * (1-leverage))
                self.assertAlmostEqual(schools[i]['metrics'][subject]['studentized'], t, places=8)

    def test_repeat_import_preserves_unrelated_data(self):
        db = connect(':memory:'); db.executescript((ROOT / 'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db, self.payload, EXTRACT)
        before = {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')]
            for t in ['source', 'school', 'economic_observation', 'assessment_observation']}
        import_snapshot(db, self.payload, EXTRACT)
        self.assertEqual(before, {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in before})
        self.assertIsNotNone(db.execute("SELECT * FROM dataset WHERE id='keep'").fetchone())
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        db.close()


if __name__ == '__main__': unittest.main()
