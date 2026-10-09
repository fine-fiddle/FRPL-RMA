import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_iowa import DATASET, EXTRACT, aggregate, grade_school, import_data, income_result, school_id


class IowaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.profiles = {r['school_id']: r for r in cls.payload['schools']}
        cls.results = {(r['school_id'], r['subject']): r for r in cls.payload['assessments']}
        cls.output = json.loads((ROOT / 'data/iowa/schools.json').read_text())

    def test_complete_valid_score_aggregation_never_drops_masked_grade(self):
        zero = [0, 0, 0, '']
        raw = [[6, 4, 10, 40], [9, 21, 30, 70]] + [zero] * 4
        self.assertEqual(aggregate(raw), (62.5, 40, None))
        self.assertNotEqual(aggregate(raw)[0], (40 + 70) / 2)
        self.assertIsNone(aggregate([['small N'] * 4] + raw[1:])[0])
        self.assertIsNone(aggregate([[6, 4, 10, 'small N']] + raw[1:])[0])
        self.assertIsNone(aggregate([zero] * 6)[0])
        for first in [[6, 5, 10, 50], [6, 4, 10, 41], [6, 4, 10, None], [0, 0, 0, 0]]:
            with self.assertRaises(ValueError):
                aggregate([first] + [zero] * 5)
        for result in self.payload['assessments']:
            pct, tested, _ = aggregate(result['raw'])
            if tested is not None:
                self.assertEqual(tested, sum(r[2] for r in result['raw']))
                self.assertAlmostEqual(pct, 100 * sum(r[1] for r in result['raw']) / tested)

    def test_income_eligibility_masks_same_year_and_composite_ids(self):
        self.assertEqual(school_id(9, 409), '0009-0409')
        self.assertNotEqual(school_id('0009', '0409'), school_id('0018', '0409'))
        self.assertEqual(income_result([200, 80, 20, 100, 50]), (200, 100, 50, None))
        for marker in ['≤ 10', '≥ 90', '***']:
            self.assertIsNone(income_result([200, '***', '***', '***', marker])[2])
        with self.assertRaises(ValueError):
            income_result([200, 80, 20, 99, 49.5])
        self.assertEqual(len(self.profiles), 1550)
        self.assertEqual(len(self.payload['excluded_enrollment']), 7)
        self.assertTrue(all(not s.endswith('-0000') for s in self.profiles))
        for p in self.profiles.values():
            self.assertEqual(p['grade_school'], grade_school(p['grades']))
            if p['income_raw']:
                self.assertEqual(p['income_raw'][0], sum(p['grades'][1:]))
        # CEP is a source flag; it does not force the individual rate to 100%.
        eligible_cep = [p for p in self.profiles.values() if p['grade_school'] and p['cep'] == 'Y' and income_result(p['income_raw'])[2] is not None]
        self.assertTrue(eligible_cep)
        self.assertTrue(all(10 < income_result(p['income_raw'])[2] < 90 for p in eligible_cep))

    def test_independent_deleted_school_regressions(self):
        rendered = {s['id']: s for s in self.output['schools']}
        for model in self.output['history_models']:
            expected = {}
            for key, p in self.profiles.items():
                if not p['grade_school']:
                    continue
                income = income_result(p['income_raw'])[2]
                rates = {s: aggregate(self.results.get((key, s), {}).get('raw'))[0] for s in ['math', 'reading']}
                if all(v is not None for v in rates.values()):
                    rates['combined'] = (rates['math'] + rates['reading']) / 2
                outcome = rates.get(model['subject'])
                if income is not None and outcome is not None:
                    expected[key] = (income, outcome)
            self.assertEqual(model['n'], len(expected))
            self.assertEqual(model['n'], 795)
            x, y = np.array(list(expected.values())).T
            design = np.column_stack([np.ones(len(x)), x])
            beta = np.linalg.lstsq(design, y, rcond=None)[0]
            self.assertAlmostEqual(model['slope'], beta[1], places=9)
            for i in [0, len(x)//2, len(x)-1]:
                other = np.arange(len(x)) != i
                deleted = np.linalg.lstsq(design[other], y[other], rcond=None)[0]
                errors = y[other] - design[other] @ deleted
                variance = errors @ errors / (len(x)-3)
                leverage = design[i] @ np.linalg.inv(design.T @ design) @ design[i]
                external = (y[i] - design[i] @ beta) / np.sqrt(variance * (1-leverage))
                metric = rendered[list(expected)[i]]['metrics'][model['subject']]
                self.assertAlmostEqual(metric['studentized'], external, places=8)
                self.assertIsNotNone(metric['low'])
                self.assertIsNotNone(metric['high'])

    def test_output_scope_coverage_and_no_invented_locations(self):
        self.assertEqual(len(self.output['schools']), 1186)
        self.assertEqual(sum('combined' in s['metrics'] for s in self.output['schools']), 795)
        for s in self.output['schools']:
            self.assertEqual(s['level'], 'ES')
            self.assertFalse(any(self.profiles[s['id']]['grades'][10:]))
            self.assertIsNone(s['latitude'])
            self.assertIsNone(s['longitude'])
            self.assertEqual(s['history'][0]['income_year'], 2025)
            if 'combined' not in s['metrics']:
                self.assertTrue(s['exclusions']['combined'])
            else:
                self.assertAlmostEqual(s['metrics']['combined']['actual'], (s['metrics']['math']['actual'] + s['metrics']['reading']['actual'])/2)

    def test_repeat_import_and_identity_validation(self):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_data(db, self.payload)
        tables = ['source', 'school', 'economic_observation', 'assessment_observation']
        before = {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        import_data(db, self.payload)
        self.assertEqual(before, {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0], 'Unrelated')
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        bad = copy.deepcopy(self.payload)
        p = next(p for p in bad['schools'] if p['grade_school'] and p['income_raw'])
        p['income_identity_raw'][4] = '9999'
        with self.assertRaises(ValueError):
            import_data(db, bad)
        bad = copy.deepcopy(self.payload)
        bad['school_year'] = '2023-24'
        with self.assertRaises(ValueError):
            import_data(db, bad)


if __name__ == '__main__':
    unittest.main()
