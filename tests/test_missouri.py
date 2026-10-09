import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from database import connect
from prepare_missouri import EXTRACT, DATASET, aggregate, count, eligible_grades, income, normalize, school_id, validate_assessment
from state_snapshot import import_snapshot


class MissouriTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(EXTRACT.read_text())
        cls.normalized = normalize(cls.raw)
        cls.output = json.loads((ROOT / 'data/missouri/schools.json').read_text())
        cls.history = json.loads((ROOT / 'data/missouri/history.json').read_text())

    def test_authoritative_identity_rejects_ambiguous_or_cross_year_inputs(self):
        self.assertEqual(school_id(1091, 4050), '001091-4050')
        for value in [True, 1.5, 'Kirksville', 0]:
            with self.assertRaises(ValueError): school_id(value, 4050)
        p = copy.deepcopy(self.raw)
        p['profiles'][0]['directory']['YEAR'] = 2024
        with self.assertRaises(ValueError): normalize(p)
        p = copy.deepcopy(self.raw)
        p['profiles'][0]['income']['BLDG. NO.'] = 9999
        with self.assertRaises(ValueError): normalize(p)

    def test_exact_count_weights_differ_from_average_of_grade_percentages(self):
        rows = [dict(GradeLevel='G03', StudentSubGroup_TotalTested='10', Lev1_count='1',
                     Lev2_count='2', Lev3_count='5', Lev4_count='2'),
                dict(GradeLevel='G04', StudentSubGroup_TotalTested='90', Lev1_count='30',
                     Lev2_count='33', Lev3_count='20', Lev4_count='7')]
        self.assertEqual(aggregate(rows, {'G03', 'G04'}), (34, 100, None))
        self.assertNotEqual(34, (70 + 30) / 2)
        with self.assertRaises(ValueError): aggregate(rows + rows[:1], {'G03', 'G04'})

    def test_suppression_is_not_recovered_by_third_party_top_two_or_complements(self):
        r = dict(GradeLevel='G03', StudentSubGroup_TotalTested='31', Lev1_count='18',
                 Lev2_count='7', Lev3_count='*', Lev4_count='*',
                 ProficientOrAbove_count='6', ProficientOrAbove_percent='0.1935')
        self.assertEqual(aggregate([r], {'G03'})[:2], (None, None))
        self.assertIsNone(count('*'))
        for value in ['30 - 35', 1.1, -1, True]:
            with self.assertRaises(ValueError): count(value)

    def test_complete_grade_coverage_and_native_high_school_exclusions(self):
        p = next(p for p in self.raw['profiles'] if p['id']=='001091-4050')
        self.assertEqual(eligible_grades(p), {'G03', 'G04', 'G05'})
        rows = [r for r in p['assessments'] if r['Subject']=='ela']
        self.assertEqual(aggregate(rows[:-1], {'G03', 'G04', 'G05'})[:2], (None, None))
        q = copy.deepcopy(p)
        q['directory']['END_GRADE'] = 12
        self.assertIsNone(eligible_grades(q))
        q = copy.deepcopy(p)
        q['enrollment']['ENROLLMENT_GRADES_09'] = 8
        self.assertIsNone(eligible_grades(q))

    def test_cep_exclusion_and_fractional_fte_preserve_published_percentage(self):
        raw = next(p['income'] for p in self.raw['profiles'] if p['id']=='001091-1050')
        self.assertEqual(income(raw), (36.7, None))
        self.assertNotEqual(income(raw)[0], 100 * raw['January State FTE F&RL Count'] / raw['January Membership'])
        q = dict(raw, **{'Community Eligiblity Provision (CEP) Participating Building':'Yes'})
        self.assertIsNone(income(q)[0])
        self.assertTrue(all(s['low_income'] is None for s in self.normalized['schools']))
        self.assertEqual(self.normalized['source_audit']['native_cep_records'], 513)

    def test_native_audit_agrees_and_assessment_population_fails_closed(self):
        self.assertEqual(self.raw['native_audit']['comparison_cells'], 130)
        self.assertEqual(self.raw['native_audit']['differences'], 0)
        r = next(p['assessments'][0] for p in self.raw['profiles'] if p['assessments'])
        for field, value in [('SchYear','2023-24'),('AssmtType','Alternate'),('Subject','sci'),
                             ('StateAssignedDistID','999999'),('ProficiencyCriteria','Levels 2-4')]:
            q = dict(r, **{field:value})
            with self.assertRaises(ValueError): validate_assessment(q, r['StateAssignedSchID'])

    def test_import_twice_preserves_unrelated_dataset_and_exact_native_counts(self):
        db = connect(':memory:')
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Keep','Keep','ready')")
        import_snapshot(db, self.normalized, EXTRACT)
        tables = ['source','school','economic_observation','assessment_observation']
        before = [db.execute(f'SELECT * FROM {t} ORDER BY 1,2').fetchall() for t in tables]
        import_snapshot(db, self.normalized, EXTRACT)
        self.assertEqual(before, [db.execute(f'SELECT * FROM {t} ORDER BY 1,2').fetchall() for t in tables])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0], 'Keep')
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertTrue(all(r[0] is None for r in db.execute('SELECT low_income FROM economic_observation WHERE dataset_id=?',(DATASET,))))
        db.close()

    def test_models_match_independent_studentization_and_all_intervals_have_counts(self):
        self.assertEqual(len(self.history['models']), 3)
        expected_sizes = {'math':620,'reading':580,'combined':469}
        for model in self.history['models']:
            rows = [r for r in self.history['records'] if model['subject'] in r['subjects']]
            x = np.array([r['income'] for r in rows])
            y = np.array([r['subjects'][model['subject']]['actual'] for r in rows])
            X = np.column_stack([np.ones(len(x)), x])
            errors = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
            h = np.einsum('ij,jk,ik->i', X, np.linalg.inv(X.T @ X), X)
            expected = errors / np.sqrt((errors @ errors-errors**2/(1-h))/(len(x)-3)*(1-h))
            np.testing.assert_allclose([r['subjects'][model['subject']]['studentized'] for r in rows], expected, atol=1e-8)
            self.assertEqual(model['n'], expected_sizes[model['subject']])
            for r in rows:
                self.assertEqual((r['year'],r['income_year'],r['level']), (2025,2025,'ES'))
                m = r['subjects'][model['subject']]
                self.assertIsNotNone(m['low'])
                self.assertIsNotNone(m['high'])
                if model['subject']!='combined': self.assertGreater(m['tested'], 0)


if __name__=='__main__': unittest.main()
