import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from database import ROOT, connect
from prepare_montana import EXTRACT, OUTPUT, validate, native_income, native_outcome, raw_count
from state_snapshot import import_snapshot


class MontanaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload=json.loads(EXTRACT.read_text())
        cls.output=json.loads((OUTPUT/'schools.json').read_text())

    def test_exact_same_year_individual_income_and_native_rates(self):
        validate(self.payload)
        self.assertEqual(self.payload['source_audit']['program_year_crosscheck'],
            dict(numeric_non_cep_rows=492,mismatches=0,claim_period='2024-10-01T00:00:00'))
        for school in self.payload['schools']:
            raw=school['income_raw'];gems=raw['gems'];claim=raw['october_claim']
            self.assertEqual(school['income'],100*claim['Lunch Free or Reduced Eligible']/claim['Lunch Enrollment'])
            self.assertEqual(gems['NCES_Code'],school['directory_raw']['NCESSCH'])
            self.assertEqual(school['enrollment'],int(school['membership_raw']['STUDENT_COUNT']))
            self.assertIsNone(school['low_income'])
            self.assertFalse(gems['CEP_Base_Year'])
            self.assertEqual(claim['Site Participates In'],'Participates in Regular Program')
            for subject,outcome in school['outcomes'].items():
                raw=outcome['raw'];self.assertEqual(raw['GradeLevel'],'G38')
                self.assertIsNone(outcome['tested'])
                if outcome['proficiency'] is not None:
                    self.assertEqual(outcome['proficiency'],100*float(raw['ProficientOrAbove_percent']))

    def test_no_cep_claiming_or_meal_served_fallback(self):
        example=copy.deepcopy(self.payload['schools'][0]['income_raw'])
        for flag in ['CEP','PROV2','Not Participating',None]:
            raw=copy.deepcopy(example);raw['october_claim']['Site Participates In']=flag
            self.assertIsNone(native_income(raw))
        raw=copy.deepcopy(example);raw['gems']['CEP_Base_Year']='2024'
        self.assertIsNone(native_income(raw))
        for column in ['Students_Eligible_for_Free_Reduced_Count','Total_Students_Enrolled']:
            for value in ['*','--','','<10','10-20',True]:
                raw=copy.deepcopy(example);raw['gems'][column]=value
                raw['october_claim']['Lunch Free or Reduced Served']=500
                self.assertIsNone(native_income(raw))
        self.assertIsNone(raw_count(True));self.assertIsNone(raw_count('5-10'))

    def test_no_rate_or_tested_count_reconstruction(self):
        row=copy.deepcopy(self.payload['schools'][0]['outcomes']['math']['raw'])
        for value in ['*','--','','<.05','.20-.30','nan']:
            changed={**row,'ProficientOrAbove_percent':value,'ProficientOrAbove_count':'99',
                'StudentSubGroup_TotalTested':'100','ParticipationRate':'1'}
            outcome=native_outcome(changed,1,'math')
            self.assertIsNone(outcome['proficiency']);self.assertIsNone(outcome['tested'])
        changed={**row,'StudentSubGroup_TotalTested':'9999','ProficientOrAbove_count':'9999','ParticipationRate':'0'}
        self.assertEqual(native_outcome(changed,1,'math')['proficiency'],native_outcome(row,1,'math')['proficiency'])
        for school in self.output['schools']:
            for metric in school['metrics'].values():
                for field in ['tested','low','high']:self.assertIsNone(metric[field])

    def test_wrong_year_identity_grade_population_and_counts_rejected(self):
        for change in ['claimyear','programyear','sponsor','nces','mixed','assessyear','grade','alternate','cutscore','tested','income','claimcount','lowincome']:
            p=copy.deepcopy(self.payload);s=p['schools'][0];r=s['outcomes']['math']['raw']
            if change=='claimyear':s['income_raw']['october_claim']['Claim Period']='2025-10-01T00:00:00'
            elif change=='programyear':s['income_raw']['program_year']=2024
            elif change=='sponsor':s['income_raw']['october_claim']['Sponsor ID']='9999'
            elif change=='nces':r['NCESSchoolID']='309999999999'
            elif change=='mixed':s['directory_raw']['G_9_OFFERED']='Yes'
            elif change=='assessyear':r['SchYear']='2023-24'
            elif change=='grade':r['GradeLevel']='G03'
            elif change=='alternate':r['AssmtType']='Alt'
            elif change=='cutscore':r['Flag_CutScoreChange_math']='N'
            elif change=='tested':s['outcomes']['math']['tested']=s['enrollment']
            elif change=='income':s['income']=100
            elif change=='claimcount':s['income_raw']['october_claim']['Lunch Free or Reduced Eligible']+=1
            else:s['low_income']=10
            with self.subTest(change=change),self.assertRaises(ValueError):validate(p)

    def test_independent_deleted_school_models(self):
        self.assertEqual(set(self.output['levels']),{'ES'})
        for subject,model in self.output['models']['ES'].items():
            schools=[s for s in self.output['schools'] if subject in s['metrics']]
            x=np.array([s['income'] for s in schools]);y=np.array([s['metrics'][subject]['actual'] for s in schools])
            X=np.column_stack([np.ones(len(x)),x]);beta=np.linalg.lstsq(X,y,rcond=None)[0]
            self.assertEqual(model['n'],len(x));self.assertAlmostEqual(model['slope'],beta[1],places=9)
            for i in [0,len(x)//2,len(x)-1]:
                keep=np.arange(len(x))!=i;deleted=np.linalg.lstsq(X[keep],y[keep],rcond=None)[0]
                error=y[keep]-X[keep]@deleted;variance=error@error/(len(x)-3)
                h=X[i]@np.linalg.inv(X.T@X)@X[i]
                expected=(y[i]-X[i]@beta)/np.sqrt(variance*(1-h))
                self.assertAlmostEqual(schools[i]['metrics'][subject]['studentized'],expected,places=8)
        for s in self.output['schools']:
            if 'combined' in s['metrics']:
                self.assertEqual(s['metrics']['combined']['actual'],(s['metrics']['math']['actual']+s['metrics']['reading']['actual'])/2)

    def test_repeat_import_preserves_unrelated_datasets(self):
        db=connect(':memory:');db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Keep','Keep','ready')")
        import_snapshot(db,self.payload,EXTRACT)
        tables=['source','school','economic_observation','assessment_observation']
        before={t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        import_snapshot(db,self.payload,EXTRACT)
        self.assertEqual(before,{t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertIsNotNone(db.execute("SELECT * FROM dataset WHERE id='keep'").fetchone())
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall());db.close()
