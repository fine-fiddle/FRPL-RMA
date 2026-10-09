import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_indiana import BANDS, DATASET, EXTRACT, band_for, import_data, public_id, result


class IndianaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.profiles = {r['school_id']: r for r in cls.payload['schools']}
        cls.assessments = {(r['school_id'], r['subject']): r for r in cls.payload['assessments']}
        cls.outputs = {band: json.loads((ROOT / 'data/indiana' /
            ('mixed' if band == 'mixed' else '') / 'schools.json').read_text()) for band in BANDS}

    def test_native_total_denominator_and_suppression(self):
        self.assertEqual(result([3, 2, 4, 1, 5, 10, .5]), (50, 10))
        self.assertEqual(result(['***'] * 7), (None, None))
        self.assertEqual(result([None] * 7), (None, None))
        for values in [[3, 2, 4, 1, 4, 10, .4], [3, 2, 4, 1, 5, 11, .5],
                       [3, 2, 4, 1, 5, 10, .51], [3, 2, 4, 1, 5, 10, 50],
                       [3, 2, 4, 1, 5, None, .5]]:
            with self.assertRaises(ValueError):
                result(values)
        # A suppression marker cannot become zero, even if some counts are published.
        self.assertEqual(result([3, 2, 4, 1, 5, 10, '***']), (None, None))
        for record in self.payload['assessments']:
            pct, tested = result(record['raw'])
            if pct is not None:
                self.assertEqual(sum(record['raw'][:4]), tested)
                self.assertAlmostEqual(pct, 100 * record['raw'][4] / tested, places=6)

    def test_same_year_grade_scope_and_public_registry(self):
        self.assertEqual(public_id(13), '0013')
        self.assertEqual(public_id('C460'), 'C460')
        for value in ['13', '0013.0', '0000', '../0013', None]:
            with self.assertRaises(ValueError):
                public_id(value)
        self.assertEqual(band_for([0] * 4 + [5] + [0] * 10), 'grade')
        self.assertEqual(band_for([0] * 4 + [5] + [0] * 5 + [5] + [0] * 4), 'mixed')
        self.assertEqual(band_for([0] * 10 + [5] + [0] * 4), 'high')
        self.assertEqual(len(self.profiles), 1891)
        # Alphanumeric codes do not by themselves mean private: state institutions are public.
        self.assertIn('C460', self.profiles)
        self.assertIn('C695', self.profiles)
        self.assertNotIn('A425', self.profiles)
        self.assertNotIn('6811', self.profiles)  # No same-year enrollment; never backfilled.
        for profile in self.profiles.values():
            self.assertEqual(profile['band'], band_for(profile['grades']))
            self.assertEqual(sum(profile['grades']), profile['income_raw'][2])
            self.assertEqual(sum(profile['income_raw'][:2]), profile['income_raw'][2])

    def test_models_against_independent_deleted_school_regressions(self):
        for band, output in self.outputs.items():
            schools = {s['id']: s for s in output['schools']}
            for model in output['history_models']:
                expected = {}
                for key, profile in self.profiles.items():
                    if profile['band'] != band:
                        continue
                    free, _, total = profile['income_raw']
                    rates = {s: result(self.assessments.get((key, s), {}).get('raw', [None] * 7))[0]
                             for s in ['math', 'reading']}
                    if all(v is not None for v in rates.values()):
                        rates['combined'] = (rates['math'] + rates['reading']) / 2
                    value = rates.get(model['subject'])
                    if total and value is not None:
                        expected[key] = (100 * free / total, value)
                self.assertEqual(model['n'], len(expected))
                x, y = np.array(list(expected.values())).T
                design = np.column_stack([np.ones(len(x)), x])
                beta = np.linalg.lstsq(design, y, rcond=None)[0]
                self.assertAlmostEqual(model['slope'], beta[1], places=9)
                for i in [0, len(x) // 2, len(x) - 1]:
                    other = np.arange(len(x)) != i
                    deleted = np.linalg.lstsq(design[other], y[other], rcond=None)[0]
                    errors = y[other] - design[other] @ deleted
                    variance = errors @ errors / (len(x) - 3)
                    leverage = design[i] @ np.linalg.inv(design.T @ design) @ design[i]
                    external = (y[i] - design[i] @ beta) / np.sqrt(variance * (1 - leverage))
                    key = list(expected)[i]
                    self.assertAlmostEqual(schools[key]['metrics'][model['subject']]['studentized'], external, places=8)
            for school in schools.values():
                profile = self.profiles[school['id']]
                self.assertEqual(profile['band'], band)
                self.assertEqual(school['level'], BANDS[band][0])
                self.assertEqual(school['history'][0]['income_year'], 2025)
                for subject, metric in school['metrics'].items():
                    self.assertIsNotNone(metric['low'])
                    self.assertIsNotNone(metric['high'])
                    self.assertGreaterEqual(metric['tested'], 10)
                if 'combined' in school['metrics']:
                    self.assertAlmostEqual(school['metrics']['combined']['actual'],
                        (school['metrics']['math']['actual'] + school['metrics']['reading']['actual']) / 2)

    def test_coverage_and_coordinates_never_control_model_membership(self):
        expected = {'grade': (1416, 1328, 1392), 'mixed': (187, 169, 177)}
        for band, output in self.outputs.items():
            directory, eligible, mapped = expected[band]
            self.assertEqual(len(output['schools']), directory)
            self.assertEqual(sum('combined' in s['metrics'] for s in output['schools']), eligible)
            self.assertEqual(sum(s['latitude'] is not None for s in output['schools']), mapped)
            self.assertTrue(any(s['latitude'] is None and 'combined' in s['metrics'] for s in output['schools']))
            for school in output['schools']:
                if 'combined' not in school['metrics']:
                    self.assertTrue(school['exclusions']['combined'])
                if school['latitude'] is not None:
                    self.assertEqual(school['latitude'], self.profiles[school['id']]['directory']['latitude'])
            if band == 'grade':
                self.assertTrue(all(not any(self.profiles[s['id']]['grades'][10:]) for s in output['schools']))
        self.assertEqual(self.payload['ambiguous_directory_ids'], ['6864'])
        self.assertEqual(self.profiles['6864']['directory'], {})

    def test_repeat_import_and_validation_preserve_other_datasets(self):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_data(db, self.payload)
        tables = ['source', 'school', 'economic_observation', 'assessment_observation']
        before = {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                  for table in tables}
        import_data(db, self.payload)
        for table in tables:
            self.assertEqual(before[table], [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0], 'Unrelated')
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        bad = copy.deepcopy(self.payload)
        bad['schools'][0]['grades'][10] = 1
        with self.assertRaises(ValueError):
            import_data(db, bad)
        db.close()


if __name__ == '__main__':
    unittest.main()
