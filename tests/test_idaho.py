import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_idaho import EXTRACT, grade_school, income, indexed, normalize, outcome, school_id
from state_snapshot import import_snapshot


class IdahoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(EXTRACT.read_text())
        cls.payload = normalize(cls.raw)
        cls.output = json.loads((ROOT / 'data/idaho/schools.json').read_text())
        cls.complete = next(indexed(p) for p in cls.raw['profiles'] if grade_school(p['directory']) and
            income(indexed(p))[2] is not None and outcome(indexed(p), 'math')[0] is not None)

    def test_individual_income_no_blur_or_complement_reconstruction(self):
        records = copy.deepcopy(self.complete)
        n, low, pct, reason = income(records)
        self.assertIsNone(reason)
        self.assertAlmostEqual(pct, 100 * low / n)
        native = records[('Pct Enrollment', 'Students Economically Disadvantaged')]
        native['Student Count'] = '*'
        self.assertIsNone(income(records)[2])
        native['Student Count'] = str(low)
        native['Suppression Type'] = 'BlurredDynamic'
        self.assertIsNone(income(records)[2])
        native['Suppression Type'] = 'None'
        native['NSize'] = str(n + 1)
        with self.assertRaises(ValueError):
            income(records)
        for school in self.payload['schools']:
            if school['income'] is not None:
                self.assertAlmostEqual(school['income'], 100 * school['low_income'] / school['enrollment'])

    def test_complete_valid_score_proof_and_95_percent_rejection(self):
        records = copy.deepcopy(self.complete)
        pct, valid, raw, reason = outcome(records, 'math')
        self.assertIsNone(reason)
        self.assertEqual(valid, sum(int(r['Student Count']) for r in raw['levels']))
        self.assertEqual(valid, int(raw['participation']['Student Count']))
        self.assertAlmostEqual(pct, 100 * int(raw['proficiency']['Student Count']) / valid)
        records[('Math Level Below Basic', 'All Students')]['Student Count'] = '*'
        self.assertIsNone(outcome(records, 'math')[0])
        records = copy.deepcopy(self.complete)
        for name in ['Math Proficiency', 'Math Level Below Basic', 'Math Level Basic', 'Math Level Proficient', 'Math Level Advanced']:
            records[(name, 'All Students')]['NSize'] = str(valid + 2)
        result = outcome(records, 'math')
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertIn('95%', result[3])
        records = copy.deepcopy(self.complete)
        records[('Math Participation', 'All Students')]['Student Count'] = str(valid - 1)
        self.assertIsNone(outcome(records, 'math')[0])
        records[('Math Participation', 'All Students')]['Student Count'] = '*'
        self.assertIsNone(outcome(records, 'math')[0])
        for school in self.payload['schools']:
            for observation in school['outcomes'].values():
                if observation['tested'] is not None:
                    levels = observation['raw']['levels']
                    self.assertTrue(all(r['Suppression Type'] == 'None' for r in levels))
                    self.assertEqual(observation['tested'], sum(int(r['Student Count']) for r in levels))
                    self.assertEqual(observation['tested'], int(observation['raw']['participation']['Student Count']))
                    self.assertTrue(observation['valid_score_evidence'])

    def test_same_year_directory_overrides_current_presentation(self):
        self.assertEqual(school_id('002', '0010'), '002-0010')
        self.assertEqual(len(self.payload['schools']), 480)
        ids = {s['id'] for s in self.payload['schools']}
        self.assertNotIn('493-1371', ids)  # Current presentation K–8; 2024–25 directory K–12.
        self.assertNotIn('532-1424', ids)  # Current presentation K–6; 2024–25 directory K–11.
        directory = copy.deepcopy(next(p['directory'] for p in self.raw['profiles'] if grade_school(p['directory'])))
        directory['G_9_OFFERED'] = 'Yes'
        self.assertFalse(grade_school(directory))
        directory['G_9_OFFERED'] = 'Unknown'
        self.assertFalse(grade_school(directory))
        directory['SCHOOL_YEAR'] = '2023-2024'
        with self.assertRaises(ValueError):
            grade_school(directory)
        for school in self.output['schools']:
            self.assertEqual(school['level'], 'ES')
            self.assertEqual(school['history'][0]['income_year'], 2025)
            self.assertIsNone(school['latitude'])
            self.assertIsNone(school['longitude'])
            if 'combined' in school['metrics']:
                self.assertAlmostEqual(school['metrics']['combined']['actual'],
                    (school['metrics']['math']['actual'] + school['metrics']['reading']['actual']) / 2)

    def test_models_against_independent_deleted_school_regressions(self):
        profiles = {p['id']: p for p in self.payload['schools']}
        schools = {s['id']: s for s in self.output['schools']}
        for model in self.output['history_models']:
            expected = {}
            for key, profile in profiles.items():
                rates = {s: o['proficiency'] for s, o in profile['outcomes'].items()}
                if all(v is not None for v in rates.values()):
                    rates['combined'] = (rates['math'] + rates['reading']) / 2
                if profile['income'] is not None and rates.get(model['subject']) is not None:
                    expected[key] = (profile['income'], rates[model['subject']])
            self.assertEqual(model['n'], len(expected))
            self.assertEqual(model['n'], dict(math=345, reading=357, combined=336)[model['subject']])
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
                metric = schools[list(expected)[i]]['metrics'][model['subject']]
                self.assertAlmostEqual(metric['studentized'], value, places=8)
                self.assertIsNotNone(metric['low'])
                self.assertLess(metric['low'], metric['high'])

    def test_repeat_import_identity_and_year_validation(self):
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
        bad = copy.deepcopy(self.raw)
        bad['year'] = 2024
        with self.assertRaises(ValueError):
            normalize(bad)
        bad = copy.deepcopy(self.raw)
        bad['profiles'][0]['id'] = '000-0000'
        with self.assertRaises(ValueError):
            normalize(bad)
        bad = copy.deepcopy(self.raw)
        bad['profiles'][0]['records'][0]['School Year'] = '2025-2026'
        with self.assertRaises(ValueError):
            normalize(bad)


if __name__ == '__main__':
    unittest.main()
