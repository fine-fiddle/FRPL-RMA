import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT, connect
from prepare_oregon import EXTRACT, OUTPUT, validate, exact_percent, grade_cohort
from state_snapshot import import_snapshot


class OregonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((OUTPUT/'schools.json').read_text())

    def test_native_rates_and_individual_spring_income(self):
        validate(self.payload)
        for marker in ['*', '--', '-', '< 5.0%', '>95', '0*', '5-10', '', 'nan']:
            self.assertIsNone(exact_percent(marker))
        for school in self.payload['schools']:
            raw = school['income_raw']
            self.assertEqual(school['income'], raw['Percentage Students Experiencing Poverty'])
            self.assertEqual(school['enrollment'], raw['Total Number of Students'])
            self.assertEqual(school['low_income'], raw['Students Experiencing Poverty'])
            for outcome in school['outcomes'].values():
                self.assertIsNone(outcome['tested'])
                self.assertEqual(outcome['proficiency'], exact_percent(outcome['raw']['Percent Proficient']))

    def test_same_year_native_ids_and_separate_grade_cohorts(self):
        self.assertEqual(grade_cohort('Grade(s) K-8'), 'grade')
        self.assertEqual(grade_cohort('Grade(s) 9-12'), 'high')
        self.assertIsNone(grade_cohort('Grade(s) K-12'))
        self.assertIsNone(grade_cohort('Grade(s) K-2'))
        self.assertIsNone(grade_cohort('Grade(s) unknown'))
        for change in ['income_year', 'test_year', 'district_id', 'school_id', 'mixed', 'income_subgroup', 'grade_total', 'subject']:
            payload = copy.deepcopy(self.payload)
            school = payload['schools'][0]
            raw = school['outcomes']['math']['raw']
            if change == 'income_year': school['income_raw']['Report Year'] = 20232024
            elif change == 'test_year': raw['Academic Year'] = '2023-2024'
            elif change == 'district_id': raw['District ID'] = 99999
            elif change == 'school_id': raw['School ID'] = 99999
            elif change == 'mixed': school['directory_raw']['Grades'] = 'Grade(s) K-12'
            elif change == 'income_subgroup': raw['Student Group'] = 'Students Experiencing Poverty'
            elif change == 'grade_total': raw['Grade Level'] = 'Grade 3'
            else: raw['Subject'] = 'Science'
            with self.subTest(change=change), self.assertRaises(ValueError): validate(payload)

    def test_never_infer_suppressed_rates_or_tested_counts(self):
        for change in ['rate', 'tested', 'income', 'count']:
            payload = copy.deepcopy(self.payload)
            school = payload['schools'][0]
            outcome = school['outcomes']['math']
            if change == 'rate': outcome['raw']['Percent Proficient'] = '< 5.0%'; outcome['proficiency'] = 5
            elif change == 'tested': outcome['tested'] = outcome['raw_tested']; outcome['valid_score_evidence'] = 'Participation is not performance'
            elif change == 'income': school['income_raw']['Percentage Students Experiencing Poverty'] = '<5'; school['income'] = 5
            else: school['low_income'] = school['enrollment']*school['income']/100
            with self.subTest(change=change), self.assertRaises(ValueError): validate(payload)
        for school in self.output['schools']:
            for metric in school['metrics'].values():
                self.assertIsNone(metric['tested'])
                self.assertIsNone(metric['low'])
                self.assertIsNone(metric['high'])
        # Participants and proficiency denominators differ in the official rows.
        self.assertTrue(any(isinstance(o['raw_tested'],int) and
            all(isinstance(o['raw'][f'Number Level {i}'],int) for i in range(1,5)) and
            o['raw_tested'] != sum(o['raw'][f'Number Level {i}'] for i in range(1,5))
            for s in self.payload['schools'] for o in s['outcomes'].values()))

    def test_independent_deleted_school_models_and_combined(self):
        self.assertEqual(set(self.output['levels']), {'ES','HS'})
        for level, models in self.output['models'].items():
            for subject, model in models.items():
                schools = [s for s in self.output['schools'] if s['level']==level and subject in s['metrics']]
                x = np.array([s['income'] for s in schools]); y = np.array([s['metrics'][subject]['actual'] for s in schools])
                X = np.column_stack([np.ones(len(x)),x]); beta = np.linalg.lstsq(X,y,rcond=None)[0]
                self.assertEqual(model['n'],len(x)); self.assertAlmostEqual(model['slope'],beta[1],places=9)
                for i in [0,len(x)//2,len(x)-1]:
                    keep = np.arange(len(x)) != i
                    deleted = np.linalg.lstsq(X[keep],y[keep],rcond=None)[0]
                    errors = y[keep]-X[keep]@deleted
                    variance = errors@errors/(len(x)-3)
                    h = X[i]@np.linalg.inv(X.T@X)@X[i]
                    t = (y[i]-X[i]@beta)/np.sqrt(variance*(1-h))
                    self.assertAlmostEqual(schools[i]['metrics'][subject]['studentized'],t,places=8)
        for school in self.output['schools']:
            if 'combined' in school['metrics']:
                self.assertEqual(school['metrics']['combined']['actual'],
                    (school['metrics']['math']['actual']+school['metrics']['reading']['actual'])/2)

    def test_repeat_import_preserves_other_datasets(self):
        db = connect(':memory:'); db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db,self.payload,EXTRACT)
        before = {t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')]
            for t in ['source','school','economic_observation','assessment_observation']}
        import_snapshot(db,self.payload,EXTRACT)
        self.assertEqual(before,{t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in before})
        self.assertIsNotNone(db.execute("SELECT * FROM dataset WHERE id='keep'").fetchone())
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        db.close()


if __name__ == '__main__': unittest.main()
