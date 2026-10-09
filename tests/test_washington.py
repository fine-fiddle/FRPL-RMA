import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from database import connect
from prepare_washington import DATASET, EXTRACT, YEAR, assessment_values, count, income_values, import_data, level_for, sid


class WashingtonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((ROOT/'data/washington/schools.json').read_text())
        cls.history = json.loads((ROOT/'data/washington/history.json').read_text())

    def test_tested_only_rate_never_uses_expected_or_participation_counts(self):
        row = dict(dat='None', percent_consistent_tested='.6', count_of_students_expected='100',
                   count_of_students_expected_1='125', count_consistent_grade_level='60',
                   percent_consistent_grade='48%', percent_participation='.8')
        self.assertEqual(assessment_values(row), (60, None, None))
        row['percent_consistent_tested'] = '0'
        self.assertEqual(assessment_values(row), (0, None, None))
        row.pop('percent_consistent_tested')
        self.assertEqual(assessment_values(row)[:2], (None, None))

    def test_privacy_flags_exclude_even_numeric_assessment_fields(self):
        for dat in ['N<10', '<5%', '>98%', 'Cross Grade Level - N<10', 'Cross OrganizatiON - N<10', 'No Students']:
            self.assertEqual(assessment_values(dict(dat=dat, percent_consistent_tested='.9'))[:2], (None, None))
        for fraction in ['1.1', '-.1', 'nan']:
            with self.assertRaises(ValueError):
                assessment_values(dict(dat='None', percent_consistent_tested=fraction))

    def test_protected_enrollment_zeros_are_not_zero_eligibility(self):
        row = dict(all_students='107', low_income='0', non_low_income='0', dat='DAT Applied: > 95%')
        self.assertEqual(income_values(row), (107, None, None))
        row.update(all_students='0', dat='DAT Applied: N < 10')
        self.assertEqual(income_values(row), (None, None, None))
        row.update(all_students='100', low_income='41', non_low_income='59', dat='DAT Applied: Foster Care - N < 10')
        self.assertEqual(income_values(row), (100, 41, 41))
        row.update(low_income='0', non_low_income='100', dat='')
        self.assertEqual(income_values(row), (100, 0, 0))
        row['non_low_income'] = '99'
        with self.assertRaises(ValueError):
            income_values(row)

    def test_grade_presence_keeps_mixed_and_small_high_school_grades_out_of_es(self):
        entry = dict(grade_membership=[dict(gradelevel='3rd Grade', all_students='100')])
        self.assertEqual(level_for(entry), 'ES')
        entry['grade_membership'].append(dict(gradelevel='9th Grade', all_students='0', dat='DAT Applied: N < 10'))
        self.assertEqual(level_for(entry), 'HS')
        self.assertIsNone(level_for(dict(grade_membership=[dict(gradelevel='Kindergarten')])) )
        with self.assertRaises(ValueError):
            count('10.2')

    def test_identity_year_and_assessment_population_are_required(self):
        row = dict(schoolorganizationid='100333', schoolyear='2024-25', organizationlevel='School')
        self.assertEqual(sid(row), '100333')
        for altered in [dict(row, schoolorganizationid=100333), dict(row, schoolyear='2023-24'), dict(row, organizationlevel='District')]:
            with self.assertRaises(ValueError):
                sid(altered)
        db = connect(':memory:'); db.executescript((ROOT/'scripts/schema.sql').read_text())
        entry = copy.deepcopy(self.payload['assessments'][0])
        with self.assertRaises(ValueError):
            import_data(db, dict(self.payload, assessments=[entry, entry]))
        entry['raw']['testadministration'] = 'AIM'
        with self.assertRaises(ValueError):
            import_data(db, dict(self.payload, assessments=[entry]))
        db.close()

    def test_importer_twice_preserves_unrelated_data_and_has_no_manufactured_counts(self):
        db = connect(':memory:'); db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Keep','Keep','ready')")
        import_data(db, self.payload)
        tables = ['source', 'school', 'economic_observation', 'assessment_observation']
        first = [db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables]
        import_data(db, self.payload)
        self.assertEqual(first, [db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0], 'Keep')
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=? AND tested IS NOT NULL', (DATASET,)).fetchone()[0], 0)
        db.close()

    def test_output_uses_native_appropriate_grade_rows_and_same_year_individual_income(self):
        profiles = {e['school_id']: e for e in self.payload['profiles']}
        raw = {(e['school_id'], e['raw']['gradelevel'], e['raw']['testsubject']): e['raw'] for e in self.payload['assessments']}
        for school in self.output['schools']:
            p = profiles[school['id']]
            self.assertEqual(school['level'], level_for(p))
            self.assertEqual(school['income'], income_values(p['raw'])[2])
            for subject, source_subject in [('math', 'Math'), ('reading', 'ELA')]:
                if subject in school['metrics']:
                    source = raw[(school['id'], 'All Grades' if school['level']=='ES' else '10', source_subject)]
                    self.assertEqual(source['dat'], 'None')
                    self.assertEqual(school['metrics'][subject]['actual'], 100*float(source['percent_consistent_tested']))
                    self.assertIsNone(school['metrics'][subject]['tested'])
            if 'combined' in school['metrics']:
                self.assertEqual(school['metrics']['combined']['actual'],
                                 (school['metrics']['math']['actual']+school['metrics']['reading']['actual'])/2)

    def test_all_models_match_independent_studentization_without_intervals(self):
        for model in self.history['models']:
            rows = [r for r in self.history['records'] if r['level']==model['level'] and model['subject'] in r['subjects']]
            x = np.array([r['income'] for r in rows]); y = np.array([r['subjects'][model['subject']]['actual'] for r in rows])
            X = np.column_stack([np.ones(len(x)), x]); beta = np.linalg.lstsq(X, y, rcond=None)[0]
            errors = y-X@beta; h = np.einsum('ij,jk,ik->i', X, np.linalg.inv(X.T@X), X)
            expected = errors/np.sqrt((errors@errors-errors**2/(1-h))/(len(x)-3)*(1-h))
            np.testing.assert_allclose([r['subjects'][model['subject']]['studentized'] for r in rows], expected, atol=1e-8)
            self.assertEqual(model['n'], len(rows))
            for r in rows:
                self.assertEqual(r['year'], YEAR); self.assertEqual(r['income_year'], YEAR)
                metric = r['subjects'][model['subject']]
                for field in ['tested', 'low', 'high']:
                    self.assertIsNone(metric[field])
        self.assertEqual(len(self.history['models']), 6)


if __name__ == '__main__':
    unittest.main()
