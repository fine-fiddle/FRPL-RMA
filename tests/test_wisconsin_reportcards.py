import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_wisconsin_reportcards import (
    BANDS, EXTRACT, RATE_FIELDS, band_for, import_data, published_percentage, school_id,
)


class WisconsinReportCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(EXTRACT.read_text())
        cls.wise = json.loads((ROOT / 'data/source/wisconsin.json').read_text())
        cls.outputs = [json.loads((ROOT / f'data/wisconsin/{folder}/schools.json').read_text())
                       for folder in ['reportcards', 'reportcards-mixed']]
        cls.incomes = {r['school_id']: r for r in cls.wise['enrollment'] if r['year'] == '2024-25'}

    def test_source_values_and_grade_span_partitions(self):
        self.assertEqual(published_percentage(0), 0)
        self.assertEqual(published_percentage(1), 100)
        self.assertEqual(published_percentage(.183), 18.3)
        for value in [None, '*', 'NA', '[Data Suppressed]']:
            self.assertIsNone(published_percentage(value))
        for value in [-.1, 18.3, float('nan')]:
            with self.assertRaises(ValueError):
                published_percentage(value)
        for low, high, band in [('K4', 8, 'grade'), (9, 12, 'high'), (6, 12, 'mixed')]:
            self.assertEqual(band_for({'Lowest Grade Level': low, 'Highest Grade Level': high}), band)
        with self.assertRaises(ValueError):
            band_for({'Lowest Grade Level': 9, 'Highest Grade Level': 8})
        keys = set()
        for entry in self.source['schools']:
            row = entry['raw']
            self.assertEqual(row['Report Card Type'], 'Public - All Students')
            self.assertEqual(row['School Year'], '2024-25')
            self.assertEqual(school_id(row), entry['school_id'])
            self.assertNotIn(entry['school_id'], keys)
            keys.add(entry['school_id'])
            self.assertEqual(band_for(row), entry['band'])
        self.assertEqual(len(keys), 2061)

    def test_models_reproduce_published_rates_and_deleted_residuals(self):
        expected = {}
        for entry in self.source['schools']:
            key, band, row = entry['school_id'], entry['band'], entry['raw']
            income = self.incomes.get(key, {}).get('percentage')
            if income is None:
                continue
            rates = {s: published_percentage(row[f]) for s, f in RATE_FIELDS.items()}
            if all(v is not None for v in rates.values()):
                rates['combined'] = (rates['math'] + rates['reading']) / 2
            for subject, rate in rates.items():
                if rate is not None:
                    expected.setdefault((BANDS[band][1], subject), {})[key] = (income, rate)
        for output in self.outputs:
            schools = {s['id']: s for s in output['schools']}
            for model in output['history_models']:
                values = expected[(model['assessment'], model['subject'])]
                self.assertEqual(model['n'], len(values))
                x, y = np.array(list(values.values())).T
                design = np.column_stack([np.ones(len(x)), x])
                beta = np.linalg.lstsq(design, y, rcond=None)[0]
                self.assertAlmostEqual(model['slope'], beta[1], places=9)
                # Independent literal leave-one-out refits verify externally studentized residuals.
                for i in [0, len(x) // 2, len(x) - 1]:
                    other = np.arange(len(x)) != i
                    deleted_beta = np.linalg.lstsq(design[other], y[other], rcond=None)[0]
                    deleted_errors = y[other] - design[other] @ deleted_beta
                    deleted_variance = (deleted_errors @ deleted_errors) / (len(x) - 3)
                    h = design[i] @ np.linalg.inv(design.T @ design) @ design[i]
                    residual = (y[i] - design[i] @ beta) / np.sqrt(deleted_variance * (1 - h))
                    key = list(values)[i]
                    self.assertAlmostEqual(schools[key]['metrics'][model['subject']]['studentized'], residual, places=8)
            for school in schools.values():
                annual = school['history'][0]
                self.assertEqual(annual['year'], 2025)
                self.assertEqual(school['metrics'], annual['subjects'])
                self.assertEqual(school['income'], self.incomes.get(school['id'], {}).get('percentage'))
                for subject, metric in school['metrics'].items():
                    self.assertIsNone(metric['tested'])
                    self.assertIsNone(metric['low'])
                    self.assertIsNone(metric['high'])
                    self.assertAlmostEqual(metric['actual'], expected[(annual['assessment'], subject)][school['id']][1])

    def test_coverage_gain_retains_unavailable_schools(self):
        all_schools = [s for output in self.outputs for s in output['schools']]
        self.assertEqual(len(all_schools), 2061)
        self.assertEqual(len({s['id'] for s in all_schools}), 2061)
        self.assertEqual(sum('combined' in s['metrics'] for s in all_schools), 1890)
        audit = json.loads((ROOT / 'data/wisconsin/coverage-comparison.json').read_text())
        self.assertEqual(audit['published_combined'], 1890)
        self.assertEqual(len(audit['added_ids']), 625)
        self.assertEqual(len(audit['original_only_ids']), 1)
        for school in all_schools:
            if 'combined' not in school['metrics']:
                self.assertTrue(school['exclusions']['combined'])
        suppressed = next(s for s in all_schools if s['id'] == 'S11830110')
        self.assertIn('DPI suppressed', suppressed['exclusions']['combined'])
        self.assertEqual(suppressed['metrics'], {})

    def test_repeat_import_preserves_other_datasets_and_rejects_bad_identity(self):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('unrelated','IL','Keep','Keep','ready')")
        import_data(db, self.source, self.wise)
        before = [tuple(r) for r in db.execute(
            'SELECT * FROM assessment_observation ORDER BY school_id, definition_id, subject')]
        import_data(db, self.source, self.wise)
        self.assertEqual(before, [tuple(r) for r in db.execute(
            'SELECT * FROM assessment_observation ORDER BY school_id, definition_id, subject')])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='unrelated'").fetchone()[0], 'Keep')
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        bad = copy.deepcopy(self.source)
        bad['schools'][0]['school_id'] = 'S99999999'
        with self.assertRaises(ValueError):
            import_data(db, bad, self.wise)
        db.close()


if __name__ == '__main__':
    unittest.main()
