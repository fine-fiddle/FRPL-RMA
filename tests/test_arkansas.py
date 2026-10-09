import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_arkansas import EXTRACT, income, normalize, rate, school_id
from state_snapshot import import_snapshot


class ArkansasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(EXTRACT.read_text())
        cls.payload = normalize(cls.raw)
        cls.output = json.loads((ROOT / 'data/arkansas/schools.json').read_text())
        cls.complete = next(p for p in cls.raw['profiles'] if p['id'] == cls.payload['schools'][0]['id'])

    def test_individual_dc_income_and_reporting_flags(self):
        p = copy.deepcopy(self.complete)
        n, dc, pct, reason = income(p)
        self.assertIsNone(reason)
        self.assertAlmostEqual(pct, 100 * dc / n)
        p['direct_certification']['DMS_FLAG'] = 'Not reported'
        self.assertIsNone(income(p)[2])
        p = copy.deepcopy(self.complete)
        p['direct_certification']['STUDENT_COUNT'] = str(n + 1)
        self.assertIsNone(income(p)[2])
        p = copy.deepcopy(self.complete)
        p['direct_certification']['DATA_GROUP'] = 'Free and Reduced Lunch'
        with self.assertRaises(ValueError):
            income(p)
        for s in self.payload['schools']:
            self.assertAlmostEqual(s['income'], 100 * s['low_income'] / s['enrollment'])

    def test_suppression_and_point_only_native_totals(self):
        for value in ['*', 'RV', '', 'N/A', 'N<10', '---', '<5%', '95-100%']:
            self.assertIsNone(rate(value))
        self.assertEqual(rate('0.0%'), 0)
        self.assertEqual(rate('100.0%'), 100)
        for value in ['-1%', '101%', 'nan%', '50', 50]:
            with self.assertRaises(ValueError):
                rate(value)
        for s in self.payload['schools']:
            for subject, o in s['outcomes'].items():
                self.assertIsNone(o['tested'])
                native = 'Math' if subject == 'math' else 'ELA'
                self.assertEqual(o['proficiency'], rate(o['raw'][native + ' % Level 3 & 4']))
        for s in self.output['schools']:
            for m in s['metrics'].values():
                self.assertIsNone(m['low'])
                self.assertIsNone(m['high'])
        self.assertEqual(self.raw['unused_native_dc']['numeric_zero'], 1060)
        self.assertEqual(self.raw['unused_native_dc']['unavailable'], 15)
        # Reading and Math Combined are distinct native responses, not aliases.
        p = next(p for p in self.raw['profiles'] if p['id'] == '0101003')
        row = p['record']
        self.assertNotEqual(row['ELA % Level 3 & 4'], row['Reading % Level 3 & 4'])
        self.assertNotEqual(p['record']['Math % Level 3 & 4'], p['record']['Math Combined % Level 3 & 4'])

    def test_native_grade_scope_and_authoritative_same_year_ids(self):
        self.assertEqual(len(self.payload['schools']), 654)
        self.assertEqual([r['Grade'] for r in self.raw['state_grade_rows']], [str(g).zfill(2) for g in range(3, 13)])
        bad = copy.deepcopy(self.raw)
        bad['year'] = 2024
        with self.assertRaises(ValueError):
            normalize(bad)
        row = copy.deepcopy(self.complete['record'])
        self.assertEqual(school_id(row), self.complete['id'])
        row['School LEA'] = row['School LEA'][1:]
        with self.assertRaises(ValueError):
            school_id(row)
        for field, value in [('SCHOOL_YEAR', '2023-2024'), ('ST_SCHID', 'AR-9999999-9999999')]:
            bad = copy.deepcopy(self.raw)
            bad['profiles'][0]['directory'][field] = value
            with self.assertRaises(ValueError):
                normalize(bad)
        for school in self.output['schools']:
            self.assertEqual(school['level'], 'ES')
            self.assertEqual(school['history'][0]['income_year'], 2025)
            self.assertIsNone(school['latitude'])
        for s in self.payload['schools']:
            self.assertTrue(all(s['directory_raw'][f'G_{g}_OFFERED'] == 'No' for g in range(9, 14)))

    def test_models_against_independent_deleted_school_regressions(self):
        profiles = {p['id']: p for p in self.payload['schools']}
        schools = {s['id']: s for s in self.output['schools']}
        for model in self.output['history_models']:
            expected = {}
            for key, p in profiles.items():
                rates = {s: o['proficiency'] for s, o in p['outcomes'].items()}
                if all(v is not None for v in rates.values()):
                    rates['combined'] = (rates['math'] + rates['reading']) / 2
                if p['income'] is not None and rates.get(model['subject']) is not None:
                    expected[key] = (p['income'], rates[model['subject']])
            self.assertEqual(model['n'], len(expected))
            self.assertEqual(model['n'], dict(math=653, reading=653, combined=653)[model['subject']])
            x, y = np.array(list(expected.values())).T
            design = np.column_stack([np.ones(len(x)), x])
            beta = np.linalg.lstsq(design, y, rcond=None)[0]
            self.assertAlmostEqual(model['slope'], beta[1], places=9)
            for i in [0, len(x) // 2, len(x) - 1]:
                keep = np.arange(len(x)) != i
                deleted = np.linalg.lstsq(design[keep], y[keep], rcond=None)[0]
                errors = y[keep] - design[keep] @ deleted
                variance = errors @ errors / (len(x) - 3)
                h = design[i] @ np.linalg.inv(design.T @ design) @ design[i]
                value = (y[i] - design[i] @ beta) / np.sqrt(variance * (1 - h))
                self.assertAlmostEqual(schools[list(expected)[i]]['metrics'][model['subject']]['studentized'], value, places=8)

    def test_repeat_import_and_wrong_economic_identity(self):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db, self.payload, EXTRACT)
        tables = ['source', 'school', 'economic_observation', 'assessment_observation']
        before = {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        import_snapshot(db, self.payload, EXTRACT)
        self.assertEqual(before, {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0], 'Unrelated')
        p = copy.deepcopy(self.complete)
        p['direct_certification']['NCESSCH'] = '019999999999'
        with self.assertRaises(ValueError):
            income(p)
        p = copy.deepcopy(self.complete)
        p['membership']['SCHOOL_YEAR'] = '2023-2024'
        with self.assertRaises(ValueError):
            income(p)


if __name__ == '__main__':
    unittest.main()
