import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from database import connect
from prepare_utah import DATASET, EXTRACT, YEAR, ASSESSMENTS, RELEASE_STATUS, assessment_values, income_values, income_exclusion, import_data, level_for, sid, site_code


class UtahTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((ROOT/'data/utah/schools.json').read_text())
        cls.history = json.loads((ROOT/'data/utah/history.json').read_text())

    def test_suppression_ranges_and_numeric_codes_are_never_reconstructed(self):
        for raw in ['n<10', '40-49%', '≤5%', '>95%', None, '']:
            self.assertEqual(assessment_values({'Percent Proficient':raw})[:2], (None,None))
        self.assertEqual(assessment_values({'Percent Proficient':0}), (0,None,None))
        self.assertEqual(assessment_values({'Percent Proficient':.5}), (50,None,None))
        for raw in [1.2,-.1,float('nan')]:
            with self.assertRaises(ValueError):assessment_values({'Percent Proficient':raw})
        self.assertEqual(site_code(' 01-104'), ('1','104'))
        self.assertEqual(site_code(' 4K-300'), ('4K','300'))
        self.assertIsNone(site_code(3e-100))
        self.assertIsNone(site_code('01-104,105'))

    def test_individual_eligibility_excludes_program_flags_roster_and_ambiguous_units(self):
        row = {'Site Name':'School','Enrollment':100,'Free %':.2,'Reduced %':.1,'Free and Reduced %':.3}
        self.assertEqual(income_values({'raw':row,'exclusion':None}), (100,None,30))
        for name in ['School*','School**']:
            self.assertIsNotNone(income_exclusion(dict(row,**{'Site Name':name}),('1','100'),set(),False))
        reason = income_exclusion(row,('1','100'),{('1','100')},False)
        self.assertIsNotNone(reason)
        self.assertEqual(income_values({'raw':row,'exclusion':reason}), (100,None,None))
        self.assertIsNotNone(income_exclusion(row,('1','100'),set(),True))
        self.assertIsNone(income_exclusion(row,('1','100'),set(),False))
        with self.assertRaises(ValueError):income_values({'raw':dict(row,**{'Free and Reduced %':.5}),'exclusion':None})

    def test_school_identity_requires_district_number_and_internal_school_id(self):
        self.assertEqual(sid({'District ID':480,'SchoolNumber':102}), '480-102')
        self.assertNotEqual(sid({'District ID':480,'SchoolNumber':102}), sid({'District ID':122,'SchoolNumber':102}))
        db=connect(':memory:');db.executescript((ROOT/'scripts/schema.sql').read_text())
        try:
            bad=copy.deepcopy(self.payload);bad['profiles'][0]['cactus']['schoolId']+=1
            with self.assertRaises(ValueError):import_data(db,bad)
            bad=copy.deepcopy(self.payload);bad['incomes'][0]['raw']['Site Number']='01-999'
            with self.assertRaises(ValueError):import_data(db,bad)
            bad=copy.deepcopy(self.payload);bad['incomes'][0]['exclusion']='invented'
            with self.assertRaises(ValueError):import_data(db,bad)
            bad=copy.deepcopy(self.payload);bad['academic_year']='2023-24'
            with self.assertRaises(ValueError):import_data(db,bad)
        finally:db.close()

    def test_high_and_mixed_schools_never_enter_the_grade_school_model(self):
        entry={'school_id':'480-102','raw':{'SchoolLevel':'K8','IsSplitSchool':'0'}}
        self.assertEqual(level_for(entry,set()),'ES')
        self.assertEqual(level_for(entry,{'480-102'}),'HS')
        entry['raw']['IsSplitSchool']='1';self.assertEqual(level_for(entry,set()),'HS')
        entry['raw']['SchoolLevel']='HS';self.assertEqual(level_for(entry,set()),'HS')

    def test_duplicate_assessments_and_overall_results_are_rejected(self):
        db=connect(':memory:');db.executescript((ROOT/'scripts/schema.sql').read_text())
        try:
            entry=copy.deepcopy(self.payload['assessments'][0])
            with self.assertRaises(ValueError):import_data(db,dict(self.payload,assessments=[entry,entry]))
            entry['raw']['Assessment Type']='Overall Results'
            with self.assertRaises(ValueError):import_data(db,dict(self.payload,assessments=[entry]))
        finally:db.close()

    def test_second_import_is_identical_and_preserves_unrelated_rows(self):
        db=connect(':memory:');db.executescript((ROOT/'scripts/schema.sql').read_text())
        try:
            db.execute("INSERT INTO dataset VALUES ('keep','IL','Keep','Keep','ready')")
            import_data(db,self.payload)
            tables=['source','school','economic_observation','assessment_observation']
            before={t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY 1,2')] for t in tables}
            import_data(db,self.payload)
            self.assertEqual(before,{t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY 1,2')] for t in tables})
            self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0],'Keep')
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=? AND tested IS NOT NULL',(DATASET,)).fetchone()[0],0)
            self.assertEqual(RELEASE_STATUS, 'audit_pending')
            self.assertEqual(db.execute('SELECT status FROM dataset WHERE id=?',(DATASET,)).fetchone()[0], 'audit_pending')
            self.assertEqual(self.payload['release_status'], 'audit_pending')
            self.assertEqual(json.loads((ROOT/'data/utah/catalog.json').read_text())['regions'][0]['status'], 'audit_pending')
        finally:db.close()

    def test_export_matches_exact_native_sources_and_restricted_income_cohort(self):
        profiles={e['school_id']:e for e in self.payload['profiles']};incomes={e['school_id']:e for e in self.payload['incomes']}
        raw={(e['school_id'],e['raw']['Assessment Type'],e['raw']['Subject Area']):e['raw'] for e in self.payload['assessments']}
        high={e['school_id'] for e in self.payload['assessments'] if e['raw']['Assessment Type']=='Utah Aspire Plus (Grades 9-10)'}
        for school in self.output['schools']:
            key=school['id'];self.assertEqual(school['level'],level_for(profiles[key],high))
            expected_income=income_values(incomes[key])[2] if key in incomes else None
            self.assertEqual(school['income'],expected_income)
            for subject,source_subject in [('math','Mathematics'),('reading','English Language Arts')]:
                if subject not in school['metrics']:continue
                typ='RISE (Grades 3-8)' if school['level']=='ES' else 'Utah Aspire Plus (Grades 9-10)'
                self.assertEqual(school['metrics'][subject]['actual'],100*raw[(key,typ,source_subject)]['Percent Proficient'])
                self.assertIsNone(incomes[key]['exclusion'])
                self.assertNotIn('*',incomes[key]['raw']['Site Name'])
                self.assertEqual(profiles[key]['raw']['schoolyearendyear'],str(YEAR))
            if 'combined' in school['metrics']:
                self.assertEqual(school['metrics']['combined']['actual'],(school['metrics']['math']['actual']+school['metrics']['reading']['actual'])/2)

    def test_models_match_independent_studentization_without_counts_or_intervals(self):
        for model in self.history['models']:
            rows=[r for r in self.history['records'] if r['level']==model['level'] and model['subject'] in r['subjects']]
            x=np.array([r['income'] for r in rows]);y=np.array([r['subjects'][model['subject']]['actual'] for r in rows])
            X=np.column_stack([np.ones(len(x)),x]);beta=np.linalg.lstsq(X,y,rcond=None)[0]
            errors=y-X@beta;h=np.einsum('ij,jk,ik->i',X,np.linalg.inv(X.T@X),X)
            expected=errors/np.sqrt((errors@errors-errors**2/(1-h))/(len(x)-3)*(1-h))
            np.testing.assert_allclose([r['subjects'][model['subject']]['studentized'] for r in rows],expected,atol=1e-8)
            self.assertEqual(model['n'],len(rows));self.assertEqual(model['assessment'],ASSESSMENTS[model['level']])
            for row in rows:
                self.assertEqual(row['year'],YEAR);self.assertEqual(row['income_year'],YEAR)
                for field in ['tested','low','high']:self.assertIsNone(row['subjects'][model['subject']][field])
        self.assertEqual(len(self.history['models']),6)


if __name__=='__main__':unittest.main()
