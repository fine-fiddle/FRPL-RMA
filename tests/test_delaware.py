import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT, connect
from prepare_delaware import EXTRACT, OUTPUT, validate, unique, income_value
from state_snapshot import import_snapshot


class DelawareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((OUTPUT / 'schools.json').read_text())

    def test_native_school_totals_and_actual_valid_scores(self):
        validate(self.payload)
        for school in self.payload['schools']:
            raw = school['income_raw']
            if school['income'] is not None:
                self.assertEqual(school['income'], 100 * int(raw['students']) / int(raw['eoyenrollment']))
                self.assertEqual(school['enrollment'], int(raw['eoyenrollment']))
            for native in school['outcomes'].values():
                self.assertEqual(native['raw']['grade'], 'All Students')
                if native['tested'] is not None:
                    self.assertEqual(native['tested'], int(native['raw']['tested']))
                    self.assertIn('valid scores', native['valid_score_evidence'])
        self.assertTrue(all(m['low'] is not None and m['high'] is not None
            for s in self.output['schools'] for m in s['metrics'].values()))

    def test_foreign_ids_years_assessments_and_grade_scope_are_rejected(self):
        i = next(i for i,s in enumerate(self.payload['schools']) if s['outcomes'] and s['income'] is not None)
        for change in ['income_year', 'income_id', 'outcome_id', 'alternate', 'grade_total', 'directory_year', 'high_grade', 'fall_income', 'count', 'cohort']:
            payload = copy.deepcopy(self.payload); school = payload['schools'][i]
            native = next(iter(school['outcomes'].values()))
            if change == 'income_year': school['income_raw']['schoolyear'] = '2024'
            elif change == 'income_id': school['income_raw']['schoolcode'] = '9999'
            elif change == 'outcome_id': native['raw']['schoolcode'] = '9999'
            elif change == 'alternate': native['raw']['assessmentname'] = 'DeSSA Alternate Assessment'
            elif change == 'grade_total': native['raw']['grade'] = '3rd Grade'
            elif change == 'directory_year': school['directory_raw']['schoolyear'] = '2024'
            elif change == 'high_grade': school['directory_raw']['highestgrade'] = '12'
            elif change == 'fall_income': school['enrollment'] = int(school['income_raw']['fallenrollment'])
            elif change == 'count': native['tested'] = native['tested'] + 1
            else: payload['cohorts'][0]['assessment'] = 'Pooled national achievement'
            with self.subTest(change=change), self.assertRaises(ValueError): validate(payload)

    def test_redaction_cannot_be_recovered_from_native_other_fields(self):
        row = dict(next(s['income_raw'] for s in self.payload['schools'] if s['income'] is not None))
        row['rowstatus'] = 'REDACTED'
        self.assertIsNone(income_value(row)[2])
        payload = copy.deepcopy(self.payload)
        school = next(s for s in payload['schools'] if s['outcomes'] and s['income'] is not None)
        native = next(iter(school['outcomes'].values())); native['raw']['rowstatus'] = 'REDACTED'
        with self.assertRaises(ValueError): validate(payload)

    def test_only_identical_duplicates_collapse_and_conflicts_remain_excluded(self):
        a = dict(districtcode='10', schoolcode='100', students='50')
        self.assertEqual(len(unique([a, a])), 1)
        self.assertEqual(len(unique([a, dict(a, students='51')])), 2)
        ambiguous = {s['id'] for s in self.payload['excluded'] if 'Conflicting' in s['reason']}
        self.assertTrue(ambiguous)
        self.assertFalse(ambiguous & {s['id'] for s in self.payload['schools']})

    def test_independent_deleted_school_models_and_combined(self):
        for level, models in self.output['models'].items():
            for subject, model in models.items():
                schools = [s for s in self.output['schools'] if s['level'] == level and subject in s['metrics']]
                x = np.array([s['income'] for s in schools]); y = np.array([s['metrics'][subject]['actual'] for s in schools])
                X = np.column_stack([np.ones(len(x)), x]); beta = np.linalg.lstsq(X, y, rcond=None)[0]
                self.assertEqual(model['n'], len(schools)); self.assertAlmostEqual(model['slope'], beta[1], places=9)
                for i in [0, len(x)//2, len(x)-1]:
                    keep = np.arange(len(x)) != i; deleted = np.linalg.lstsq(X[keep], y[keep], rcond=None)[0]
                    e = y[keep] - X[keep] @ deleted; v = e @ e / (len(x)-3)
                    h = X[i] @ np.linalg.inv(X.T @ X) @ X[i]
                    self.assertAlmostEqual(schools[i]['metrics'][subject]['studentized'], (y[i]-X[i]@beta)/np.sqrt(v*(1-h)), places=8)
        for school in self.output['schools']:
            if 'combined' in school['metrics']:
                self.assertEqual(school['metrics']['combined']['actual'],
                    (school['metrics']['math']['actual'] + school['metrics']['reading']['actual']) / 2)

    def test_repeat_import_preserves_other_datasets(self):
        db = connect(':memory:'); self.addCleanup(db.close)
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db, self.payload, EXTRACT)
        tables = ['source', 'school', 'economic_observation', 'assessment_observation']
        before = {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        import_snapshot(db, self.payload, EXTRACT)
        self.assertEqual(before, {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertIsNotNone(db.execute("SELECT * FROM dataset WHERE id='keep'").fetchone())
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())


if __name__ == '__main__': unittest.main()
