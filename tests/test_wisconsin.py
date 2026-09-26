import json
from pathlib import Path
import re
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_wisconsin import aggregate, ending_year, GRADE_FIELDS, import_data, number


class WisconsinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT / 'data/source/wisconsin.json').read_text())
        cls.output = json.loads((ROOT / 'data/wisconsin/schools.json').read_text())
        cls.history = json.loads((ROOT / 'data/wisconsin/history.json').read_text())

    def test_extract_structure_and_denominators(self):
        enrollment = {}
        for r in self.source['enrollment']:
            key = (r['school_id'], r['year'])
            self.assertNotIn(key, enrollment)
            enrollment[key] = r
            self.assertRegex(r['school_id'], r'^S\d{8}$')
            if r['econ'] is not None and r['enrollment'] is not None:
                self.assertLessEqual(r['econ'], r['enrollment'])
                self.assertAlmostEqual(r['percentage'], 100 * r['econ'] / r['enrollment'], places=9)
            else:
                self.assertIsNone(r['percentage'])
        keys = set()
        for r in self.source['assessments']:
            key = (r['school_id'], r['year'], r['level'], r['subject'])
            self.assertNotIn(key, keys)
            keys.add(key)
            self.assertIn(r['level'], {'ES', 'HS'})
            self.assertRegex(r['school_id'], r'^S\d{8}$')
            self.assertTrue(r['assessment'].endswith('(pre-2023-24 levels)')
                            or r['assessment'].endswith('(2023-24 levels)'))
            for grade, counts in r['grades'].items():
                self.assertIn(grade, GRADE_FIELDS + ['11'])
                self.assertTrue(counts is None or
                                (len(counts) == 5 and all(c is None or (int(c) == c and c >= 0)
                                                          for c in counts)))

    def test_annual_models_match_extracted_counts_and_income(self):
        enrollment = {(r['school_id'], ending_year(r['year'])): r for r in self.source['enrollment']}
        grouped = {}
        for r in self.source['assessments']:
            year = ending_year(r['year'])
            profile = enrollment.get((r['school_id'], year))
            if profile is None:
                continue
            if r['level'] == 'ES':
                expected = [g for g in GRADE_FIELDS if (number(profile['grades'].get(g)) or 0) > 0]
            else:
                expected = ['11']
            tested, pct = aggregate(r, expected)
            if pct is None or tested is None or tested < 10 or profile['percentage'] is None:
                continue
            grouped.setdefault((year, r['level'], r['assessment'], r['subject']), {})[
                r['school_id']] = (profile['percentage'], pct)
        for key in [k for k in grouped if k[3] == 'math']:
            reading = grouped[(key[0], key[1], key[2], 'reading')]
            grouped[(key[0], key[1], key[2], 'combined')] = {
                sid: (x, (y + reading[sid][1]) / 2) for sid, (x, y) in grouped[key].items()
                if sid in reading}
        results = {(r['year'], r['level'], r['assessment'], r['school_id']): r
                   for r in self.history['records']}
        self.assertEqual(len(self.history['models']), 60)
        for model in self.history['models']:
            subject = model['subject']
            values = grouped[(model['year'], model['level'], model['assessment'], subject)]
            self.assertEqual(model['n'], len(values), (model['year'], model['level'], model['assessment'], subject))
            x = np.array([v[0] for v in values.values()])
            y = np.array([v[1] for v in values.values()])
            design = np.column_stack([np.ones(len(x)), x])
            beta = np.linalg.lstsq(design, y, rcond=None)[0]
            self.assertAlmostEqual(model['slope'], beta[1], places=9)
            residual = y - design @ beta
            leverage = np.sum((design @ np.linalg.inv(design.T @ design)) * design, axis=1)
            deleted_var = (residual @ residual - residual ** 2 / (1 - leverage)) / (len(x) - 3)
            expected = residual / np.sqrt(deleted_var * (1 - leverage))
            for sid, value in zip(values, expected):
                record = results[(model['year'], model['level'], model['assessment'], sid)]
                result = record['subjects'][subject]
                self.assertEqual(record['income_year'], model['year'])
                self.assertAlmostEqual(result['studentized'], value, places=8)

    def test_repeat_import_and_wisconsin_definitions(self):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        import_data(db, self.source)
        before = [tuple(r) for r in db.execute(
            'SELECT * FROM assessment_observation ORDER BY school_id, definition_id, subject')]
        import_data(db, self.source)
        self.assertEqual(before, [tuple(r) for r in db.execute(
            'SELECT * FROM assessment_observation ORDER BY school_id, definition_id, subject')])
        self.assertEqual({r[0] for r in db.execute('SELECT state FROM assessment_definition')}, {'WI'})
        self.assertEqual({r[0] for r in db.execute('SELECT state FROM dataset')}, {'WI'})
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        db.close()

    def test_boundary_is_shoreline_clipped(self):
        # The TIGERweb jurisdictional State layer extends into Lake Michigan (max longitude
        # about -86.25), which leaves a school-less band over the lake and hides Door County's
        # coastline. The Census cartographic boundary is clipped to the shoreline.
        boundary = json.loads((ROOT / 'data/wisconsin/boundary.geojson').read_text())
        geometry = boundary['features'][0]['geometry']
        self.assertEqual(geometry['type'], 'Polygon')
        self.assertGreater(len(geometry['coordinates']), 5)
        points = [p for ring in geometry['coordinates'] for p in ring]
        self.assertLess(max(p[0] for p in points), -86.7)
        self.assertGreater(max(p[1] for p in points), 47.0)
        self.assertLess(min(p[1] for p in points), 42.6)

    def test_snapshot_scope_and_standard_break(self):
        self.assertEqual(self.output['levels']['ES']['year'], 2025)
        self.assertEqual(self.output['levels']['HS']['year'], 2025)
        self.assertEqual(len(self.output['schools']), len({s['id'] for s in self.output['schools']}))
        self.assertTrue(all(s['programs'] == ['Unclassified'] for s in self.output['schools']))
        for s in self.output['schools']:
            self.assertIn(s['level'], {'ES', 'HS'})
            self.assertTrue(set(r['level'] for r in s['history']) <= {s['level']})
            year = self.output['levels'][s['level']]['year']
            current = next((r for r in s['history'] if r['year'] == year), None)
            self.assertEqual(s['metrics'], current['subjects'] if current else {})
            if s['income'] is None:
                self.assertFalse(s['metrics'])
            if s['latitude'] is not None:
                self.assertTrue(42.4 <= s['latitude'] <= 47.1)
                self.assertTrue(-92.9 <= s['longitude'] <= -86.2)
        assessments = {r['assessment'] for r in self.history['records']}
        self.assertIn('Forward (pre-2023-24 levels)', assessments)
        self.assertIn('Forward (2023-24 levels)', assessments)
        self.assertIn('ACT (pre-2023-24 levels)', assessments)
        self.assertIn('ACT (2023-24 levels)', assessments)
        self.assertFalse([r for r in self.history['records']
                          if r['level'] == 'ES' and r['year'] == 2020])


if __name__ == '__main__':
    unittest.main()
