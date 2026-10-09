import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_oklahoma import EXTRACT, aggregate, count, identity, income, normalize
from state_snapshot import import_snapshot


class OklahomaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(EXTRACT.read_text())
        cls.payload = normalize(cls.raw)
        cls.output = json.loads((ROOT / 'data/oklahoma/schools.json').read_text())
        cls.complete = next(p for p in cls.raw['profiles'] if p['id'] == '05I006125')

    def test_visible_valid_counts_and_whole_subject_suppression(self):
        self.assertEqual(aggregate(self.complete, 'ELA')[:2], (100 * 50 / 145, 145))
        self.assertEqual(aggregate(self.complete, 'Mathematics')[:2], (100 * 62 / 145, 145))
        for value in ['***', '', '*', '<10', '10-19', '---', 'N/A', None]:
            self.assertIsNone(count(value))
        self.assertEqual(count('0'), 0)
        for value in [20, '-1', 'nan', '11.5']:
            with self.assertRaises(ValueError):count(value)
        p = copy.deepcopy(self.complete)
        p['records'][0]['ELA - Advanced No.'] = '***'
        self.assertIsNone(aggregate(p, 'ELA')[0])
        p = copy.deepcopy(self.complete)
        p['records'][0]['ELA - Valid N'] = '***'
        # A visible total cannot substitute for a protected valid denominator.
        self.assertIsNone(aggregate(p, 'ELA')[0])
        p = copy.deepcopy(self.complete)
        p['directory']['G_4_OFFERED'] = 'Yes'
        self.assertIsNone(aggregate(p, 'ELA')[0])
        p = copy.deepcopy(self.complete)
        p['records'][0]['ELA - Below Basic No.'] = '***'
        self.assertEqual(aggregate(p, 'ELA')[:2], (100 * 50 / 145, 145))
        self.assertEqual(p['records'][0]['ELA - Below Basic No.'], '***')
        for s in self.payload['schools']:
            for subject, o in s['outcomes'].items():
                if o['tested'] is not None:
                    native = 'Mathematics' if subject == 'math' else 'ELA'
                    n = sum(int(r[native + ' - Valid N']) for r in o['raw'])
                    p = sum(int(r[native + ' - Proficient No.']) + int(r[native + ' - Advanced No.']) for r in o['raw'])
                    self.assertEqual(o['tested'], n)
                    self.assertAlmostEqual(o['proficiency'], 100 * p / n)
                    self.assertTrue(o['valid_score_evidence'])

    def test_individual_income_exact_authoritative_identity_year(self):
        p = copy.deepcopy(self.complete)
        n, low, pct, reason = income(p)
        self.assertEqual((n, low), (729, 460))
        self.assertAlmostEqual(pct, 100 * low / n)
        self.assertIsNone(reason)
        self.assertEqual(identity(p['id']), ('05-I006', 'OK-05-I006-05-I006-125'))
        with self.assertRaises(ValueError):identity('5I006125')
        p['direct_certification']['DMS_FLAG'] = 'Not reported'
        self.assertIsNone(income(p)[2])
        p = copy.deepcopy(self.complete)
        p['direct_certification']['STUDENT_COUNT'] = str(n + 1)
        self.assertIsNone(income(p)[2])
        for field, value in [('DATA_GROUP', 'Free and Reduced Lunch'), ('SCHOOL_YEAR', '2023-2024'), ('ST_SCHID', 'wrong')]:
            p = copy.deepcopy(self.complete)
            p['direct_certification'][field] = value
            with self.assertRaises(ValueError):income(p)

    def test_standards_reset_year_scope_and_intervals(self):
        self.assertEqual(len(self.payload['schools']), 1205)
        self.assertIn('restored the 2023 cuts', self.payload['cohorts'][0]['standard'])
        self.assertIn('2025 reset', self.payload['cohorts'][0]['assessment'])
        p = copy.deepcopy(self.raw)
        p['administration'] = '2526'
        with self.assertRaises(ValueError):normalize(p)
        p = copy.deepcopy(self.raw)
        p['profiles'][0]['records'][0]['Administration'] = '2324'
        with self.assertRaises(ValueError):normalize(p)
        p = copy.deepcopy(self.raw)
        p['profiles'][0]['records'].append(copy.deepcopy(p['profiles'][0]['records'][0]))
        with self.assertRaises(ValueError):normalize(p)
        for s in self.output['schools']:
            self.assertEqual(s['level'], 'ES')
            self.assertEqual(s['history'][0]['income_year'], 2025)
            self.assertIsNone(s['latitude'])
            for m in s['metrics'].values():
                self.assertIsNotNone(m['low'])
                self.assertIsNotNone(m['high'])
        for s in self.payload['schools']:
            self.assertTrue(all(s['directory_raw'][f'G_{g}_OFFERED'] == 'No' for g in range(9, 14)))

    def test_models_against_independent_deleted_school_regressions(self):
        profiles = {p['id']: p for p in self.payload['schools']}
        schools = {s['id']: s for s in self.output['schools']}
        for model in self.output['history_models']:
            expected = {}
            for key, p in profiles.items():
                rates = {s: o['proficiency'] for s, o in p['outcomes'].items()}
                if all(v is not None for v in rates.values()):rates['combined'] = (rates['math'] + rates['reading']) / 2
                if p['income'] is not None and rates.get(model['subject']) is not None:
                    expected[key] = (p['income'], rates[model['subject']])
            self.assertEqual(model['n'], len(expected))
            self.assertEqual(model['n'], dict(math=344, reading=169, combined=148)[model['subject']])
            x, y = np.array(list(expected.values())).T
            design = np.column_stack([np.ones(len(x)), x])
            beta = np.linalg.lstsq(design, y, rcond=None)[0]
            self.assertAlmostEqual(model['slope'], beta[1], places=9)
            for i in [0, len(x)//2, len(x)-1]:
                keep = np.arange(len(x)) != i
                deleted = np.linalg.lstsq(design[keep], y[keep], rcond=None)[0]
                errors = y[keep] - design[keep] @ deleted
                variance = errors @ errors / (len(x)-3)
                h = design[i] @ np.linalg.inv(design.T @ design) @ design[i]
                value = (y[i] - design[i] @ beta) / np.sqrt(variance * (1-h))
                self.assertAlmostEqual(schools[list(expected)[i]]['metrics'][model['subject']]['studentized'], value, places=8)

    def test_repeat_import_preserves_unrelated_records(self):
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
        db.close()


if __name__ == '__main__':unittest.main()
