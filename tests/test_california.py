import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from database import connect
from prepare_california import (
    ACADEMIC_YEAR, DATASET, EXTRACT, FIELDS, YEAR, aggregate, cds, grade,
    import_data, income_values, normalized, profile_span, validate_grade,
)


def grade_row(g=3, n=100, met=20, participation=190):
    return {'Grade': str(g), 'Overall Total': str(n),
            'Total Students Tested with Scores': str(n),
            'Total Students Tested': str(participation),
            'Count Standard Met and Above': str(met),
            'Percentage Standard Met and Above': f'{100*met/n:.2f}'}


class CaliforniaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((ROOT/'data/california/schools.json').read_text())
        cls.history = json.loads((ROOT/'data/california/history.json').read_text())
        cls.profiles = {e['school_id']: e['raw'] for e in cls.payload['profiles']}

    def test_exact_valid_scores_weight_grade_aggregation(self):
        rows = [grade_row(3, 100, 50), grade_row(4, 200, 20)]
        pct, n, reason = aggregate(rows, [3, 4])
        self.assertEqual(n, 300)
        self.assertAlmostEqual(pct, 100*70/300)
        self.assertIsNone(reason)
        self.assertNotEqual(pct, (50+10)/2)
        self.assertEqual(validate_grade(rows[0])[0], (100, 50))

    def test_suppressed_and_missing_grades_cannot_be_reconstructed_from_school_total(self):
        rows = [grade_row(3, 100, 50), grade_row(4, 200, 20), grade_row(13, 300, 70)]
        rows[1]['Count Standard Met and Above'] = '*'
        self.assertEqual(aggregate(rows, [3, 4])[:2], (None, None))
        self.assertIn('suppressed', aggregate(rows, [3, 4])[2])
        self.assertEqual(aggregate([rows[0], rows[2]], [3, 4])[:2], (None, None))
        self.assertIn('expected tested grade', aggregate([rows[0]], [3, 4])[2])

    def test_denominator_must_reconcile_and_counts_must_be_integral(self):
        for field, value in [('Overall Total', '99'), ('Overall Total', '100.5'),
                             ('Count Standard Met and Above', '101'),
                             ('Percentage Standard Met and Above', '21.00')]:
            row = grade_row()
            row[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_grade(row)
        row = grade_row(n=10, met=1)
        self.assertIsNone(validate_grade(row)[0])

    def test_identifiers_same_year_income_and_school_spans_are_explicit(self):
        p = copy.deepcopy(next(e['raw'] for e in self.payload['profiles'] if profile_span(e['raw'])))
        self.assertEqual(len(cds(p)), 14)
        self.assertTrue(cds(p).startswith('01'))
        p['Academic Year'] = '2025-2026'
        with self.assertRaises(ValueError):
            income_values(p)
        p['Academic Year'] = ACADEMIC_YEAR
        p['County Code'] = 1
        with self.assertRaises(ValueError):
            cds(p)
        p['School Type'] = 'N/A'
        self.assertIsNone(profile_span(p))

    def test_duplicate_raw_assessment_keys_are_rejected(self):
        payload = dict(self.payload, assessments=[self.payload['assessments'][0], self.payload['assessments'][0]])
        with self.assertRaises(ValueError):
            normalized(payload)

    def test_importer_is_repeatable_and_preserves_other_datasets(self):
        db = connect(':memory:')
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('unrelated','IL','Keep','Keep','ready')")
        import_data(db, self.payload)
        first = {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                 for table in ['source', 'school', 'economic_observation', 'assessment_observation']}
        import_data(db, self.payload)
        self.assertEqual(first, {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in first})
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='unrelated'").fetchone()[0], 'Keep')
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=? AND proficiency IS NOT NULL AND tested IS NULL', (DATASET,)).fetchone()[0], 0)
        db.close()

    def test_export_rates_reconcile_to_original_grade_counts_and_income(self):
        raw = {}
        for values in self.payload['assessments']:
            r = dict(zip(FIELDS, values[1:]))
            raw[(cds(r), r['Test ID'], int(r['Grade']))] = r
        checked = 0
        for school in self.output['schools']:
            p = self.profiles[school['id']]
            if p['Enrollment (K-12)']:
                self.assertAlmostEqual(school['income'], 100*p['FRPM Count (K-12)']/p['Enrollment (K-12)'])
            else:
                self.assertIsNone(school['income'])
            self.assertEqual(school['level'], 'HS' if grade(p['High Grade']) >= 9 else 'ES')
            for subject, test in [('math', '2'), ('reading', '1')]:
                result = school['metrics'].get(subject)
                if not result or checked >= 60:
                    continue
                lo, hi = profile_span(p)
                expected = [11] if school['level'] == 'HS' else list(range(max(lo, 3), min(hi, 8)+1))
                rows = [raw[(school['id'], test, g)] for g in expected]
                denominator = sum(int(r['Overall Total']) for r in rows)
                numerator = sum(int(r['Count Standard Met and Above']) for r in rows)
                self.assertEqual(result['tested'], denominator)
                self.assertAlmostEqual(result['actual'], 100*numerator/denominator)
                checked += 1
        self.assertEqual(checked, 60)

    def test_statewide_studentization_matches_independent_regression(self):
        for model in self.history['models']:
            rows = [r for r in self.history['records'] if r['level'] == model['level'] and model['subject'] in r['subjects']]
            x = np.array([r['income'] for r in rows])
            y = np.array([r['subjects'][model['subject']]['actual'] for r in rows])
            X = np.column_stack([np.ones(len(x)), x])
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            errors = y-X@beta
            h = np.einsum('ij,jk,ik->i', X, np.linalg.inv(X.T@X), X)
            expected = errors/np.sqrt((errors@errors-errors**2/(1-h))/(len(x)-3)*(1-h))
            np.testing.assert_allclose([r['subjects'][model['subject']]['studentized'] for r in rows], expected, atol=1e-8)
            self.assertEqual(model['n'], len(rows))
            for r in rows:
                self.assertEqual(r['income_year'], YEAR)
                result = r['subjects'][model['subject']]
                self.assertIsNotNone(result['low'])
                self.assertIsNotNone(result['high'])
        self.assertEqual(len(self.history['models']), 6)


if __name__ == '__main__':
    unittest.main()
