import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from database import connect
from prepare_colorado import DATASET, EXTRACT, YEAR, assessment_values, count, income_values, import_data, number, sid


class ColoradoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((ROOT/'data/colorado/schools.json').read_text())
        cls.history = json.loads((ROOT/'data/colorado/history.json').read_text())

    def test_native_school_total_uses_valid_scores_and_exact_proficient_count(self):
        row = {'Number of Valid Scores': ' 1,000', 'Number Met or Exceeded Expectations': '123',
               '2025': '12.3', 'Number of Total Records': '1,500', 'Number of No Scores': '500'}
        self.assertEqual(assessment_values(row, 'ES'), (12.3, 1000, None))
        row['Number Met or Exceeded Expectations'] = '0'
        row['2025'] = '0.0'
        self.assertEqual(assessment_values(row, 'ES'), (0, 1000, None))

    def test_suppression_and_bounded_counts_remain_unavailable(self):
        for raw in ['*', '- -', '< 16', 'N/A', None]:
            self.assertIsNone(number(raw))
            row = {'Number of Valid Scores': raw, 'Number Met or Exceeded Expectations': '2', '2025': '20'}
            self.assertEqual(assessment_values(row, 'ES')[:2], (None, None))
        with self.assertRaises(ValueError):
            count('16.5')
        with self.assertRaises(ValueError):
            assessment_values({'Number of Valid Scores': '100', 'Number Met or Exceeded Expectations': '110', '2025': '110'}, 'ES')

    def test_published_income_rounding_and_suppression_are_preserved(self):
        row = {'K-12 Count': 393, 'Free and Reduced Count': 272, '% Free and Reduced': .692}
        self.assertEqual(income_values(row), (393, 272, 69.19999999999999))
        self.assertNotEqual(income_values(row)[2], 100*272/393)
        row['% Free and Reduced'] = '*'
        self.assertIsNone(income_values(row)[2])
        row['% Free and Reduced'] = .8
        with self.assertRaises(ValueError):
            income_values(row)

    def test_exact_identity_and_same_year_scope_are_required(self):
        self.assertEqual(sid({'Organization Code': '0010', 'School Code': '0501'}), '00100501')
        with self.assertRaises(ValueError):
            sid({'Organization Code': '0010', 'School Code': 501})
        with self.assertRaises(ValueError):
            sid({'Organization Code': '0010', 'School Code': '501'})
        db = connect(':memory:'); db.executescript((ROOT/'scripts/schema.sql').read_text())
        payload = dict(self.payload, academic_year='2025-2026')
        with self.assertRaises(ValueError):
            import_data(db, payload)
        db.close()

    def test_duplicate_records_and_psat_or_summary_substitution_are_rejected(self):
        db = connect(':memory:'); db.executescript((ROOT/'scripts/schema.sql').read_text())
        entry = next(e for e in self.payload['assessments'] if e['level'] == 'HS')
        payload = dict(self.payload, assessments=[entry, entry])
        with self.assertRaises(ValueError):
            import_data(db, payload)
        for replacement in ['PSAT Grade 9', 'All Grades']:
            entry = copy.deepcopy(entry)
            entry['raw']['Grade'] = replacement
            with self.assertRaises(ValueError):
                import_data(db, dict(self.payload, assessments=[entry]))
        db.close()

    def test_importer_twice_preserves_unrelated_data(self):
        db = connect(':memory:'); db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Keep','Keep','ready')")
        import_data(db, self.payload)
        tables = ['source', 'school', 'economic_observation', 'assessment_observation']
        first = [db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables]
        import_data(db, self.payload)
        self.assertEqual(first, [db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0], 'Keep')
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=? AND proficiency IS NOT NULL AND tested IS NULL', (DATASET,)).fetchone()[0], 0)
        db.close()

    def test_export_reconciles_to_raw_native_totals_and_same_year_income(self):
        income = {e['school_id']: e['raw'] for e in self.payload['incomes']}
        profiles = {e['school_id']: e['raw'] for e in self.payload['profiles']}
        raw = {(e['school_id'], e['level'], e['subject']): e['raw'] for e in self.payload['assessments']}
        for school in self.output['schools']:
            p = profiles[school['id']]
            self.assertEqual(school['level'], 'HS' if any(p[g] > 0 for g in ['9th', '10th', '11th', '12th']) else 'ES')
            self.assertEqual(school['income'], income_values(income[school['id']])[2] if school['id'] in income else None)
            for subject in ['math', 'reading']:
                if subject in school['metrics']:
                    pct, tested, reason = assessment_values(raw[(school['id'], school['level'], subject)], school['level'])
                    self.assertIsNone(reason)
                    self.assertEqual(school['metrics'][subject]['actual'], pct)
                    self.assertEqual(school['metrics'][subject]['tested'], tested)
            if 'combined' in school['metrics']:
                self.assertEqual(school['metrics']['combined']['actual'],
                                 (school['metrics']['math']['actual']+school['metrics']['reading']['actual'])/2)

    def test_all_models_match_independent_studentization_and_have_verified_intervals(self):
        for model in self.history['models']:
            rows = [r for r in self.history['records'] if r['level'] == model['level'] and model['subject'] in r['subjects']]
            x = np.array([r['income'] for r in rows]); y = np.array([r['subjects'][model['subject']]['actual'] for r in rows])
            X = np.column_stack([np.ones(len(x)), x]); beta = np.linalg.lstsq(X, y, rcond=None)[0]
            errors = y-X@beta; h = np.einsum('ij,jk,ik->i', X, np.linalg.inv(X.T@X), X)
            expected = errors/np.sqrt((errors@errors-errors**2/(1-h))/(len(x)-3)*(1-h))
            np.testing.assert_allclose([r['subjects'][model['subject']]['studentized'] for r in rows], expected, atol=1e-8)
            self.assertEqual(model['n'], len(rows))
            for r in rows:
                self.assertEqual(r['year'], YEAR); self.assertEqual(r['income_year'], YEAR)
                self.assertIsNotNone(r['subjects'][model['subject']]['low'])
                self.assertIsNotNone(r['subjects'][model['subject']]['high'])
        self.assertEqual(len(self.history['models']), 6)


if __name__ == '__main__':
    unittest.main()
