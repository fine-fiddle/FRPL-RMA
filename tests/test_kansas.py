import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT, connect
from prepare_kansas import EXTRACT, OUTPUT, validate, exact_percent, native_outcome, native_income, ccd_key
from state_snapshot import import_snapshot


class KansasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((OUTPUT/'schools.json').read_text())

    def test_published_school_category_sum_and_individual_income(self):
        validate(self.payload)
        for marker in ['*', '--', '-', '<5', '>95', '0*', '5-10', '', 'nan', True]:
            self.assertIsNone(exact_percent(marker))
        for school in self.payload['schools']:
            self.assertEqual(school['income'], native_income(school['income_raw']))
            self.assertIsNone(school['low_income'])
            self.assertEqual(school['id'], ccd_key(school['directory_raw']['ST_SCHID']))
            for outcome in school['outcomes'].values():
                self.assertIsNone(outcome['tested'])
                raw = outcome['raw']
                self.assertEqual(outcome['proficiency'], round(raw['Pct. Level 3']+raw['Pct. Level 4'],10))
        audit = self.payload['source_audit']
        self.assertIn('1:41:37', audit['assessment_scope_evidence'])
        self.assertIn('DLM', audit['native_population'])
        self.assertIn('KAP', audit['native_population'])

    def test_suppressed_levels_never_reconstructed(self):
        row = dict(self.payload['schools'][0]['outcomes']['math']['raw'])
        # Complementary levels and an exact total do not authorize reconstructing
        # an individually masked proficient category or a count.
        for column in ['Pct. Level 3','Pct. Level 4']:
            masked = {**row,column:'*','Pct. Level 1':10,'Pct. Level 2':10}
            self.assertIsNone(native_outcome(masked,1,'math')['proficiency'])
        payload = copy.deepcopy(self.payload)
        outcome = payload['schools'][0]['outcomes']['math']
        outcome['raw']['Pct. Level 3'] = '*'
        outcome['proficiency'] = 100-outcome['raw']['Pct. Level 1']-outcome['raw']['Pct. Level 2']
        with self.assertRaises(ValueError): validate(payload)

    def test_year_identity_population_and_count_mutations_rejected(self):
        for change in ['income_year','assessment_year','district','school','mixed','grade','subgroup','income_type','tested','low_income']:
            payload = copy.deepcopy(self.payload)
            school = payload['schools'][0]
            outcome = school['outcomes']['math']
            raw = outcome['raw']
            if change=='income_year': school['income_raw']['year']=2024
            elif change=='assessment_year': raw['School Year']=2024
            elif change=='district': raw['Org. No.']='D9999'
            elif change=='school': raw['Bldg. No.']='9999'
            elif change=='mixed': school['directory_raw']['G_9_OFFERED']='Yes'
            elif change=='grade': raw['Grade']='3rd Grade'
            elif change=='subgroup': raw['Student Subgroup']='Free/Reduced Lunch'
            elif change=='income_type': school['income_raw']['url']=school['income_raw']['url'].replace('demoType=3','demoType=4')
            elif change=='tested': outcome['tested']=school['enrollment'];outcome['valid_score_evidence']='Not a valid-score denominator'
            else: school['low_income']=round(school['income']*school['enrollment']/100)
            with self.subTest(change=change), self.assertRaises(ValueError): validate(payload)
        for school in self.output['schools']:
            for metric in school['metrics'].values():
                self.assertIsNone(metric['tested']);self.assertIsNone(metric['low']);self.assertIsNone(metric['high'])

    def test_independent_deleted_school_models_and_combined(self):
        self.assertEqual(set(self.output['levels']), {'ES','HS'})
        for level,models in self.output['models'].items():
            for subject,model in models.items():
                schools=[s for s in self.output['schools'] if s['level']==level and subject in s['metrics']]
                x=np.array([s['income'] for s in schools]);y=np.array([s['metrics'][subject]['actual'] for s in schools])
                X=np.column_stack([np.ones(len(x)),x]);beta=np.linalg.lstsq(X,y,rcond=None)[0]
                self.assertEqual(model['n'],len(x));self.assertAlmostEqual(model['slope'],beta[1],places=9)
                for i in [0,len(x)//2,len(x)-1]:
                    keep=np.arange(len(x))!=i;deleted=np.linalg.lstsq(X[keep],y[keep],rcond=None)[0]
                    errors=y[keep]-X[keep]@deleted;variance=errors@errors/(len(x)-3)
                    h=X[i]@np.linalg.inv(X.T@X)@X[i]
                    t=(y[i]-X[i]@beta)/np.sqrt(variance*(1-h))
                    self.assertAlmostEqual(schools[i]['metrics'][subject]['studentized'],t,places=8)
        for school in self.output['schools']:
            if 'combined' in school['metrics']:
                self.assertEqual(school['metrics']['combined']['actual'],
                    (school['metrics']['math']['actual']+school['metrics']['reading']['actual'])/2)

    def test_repeat_import_preserves_other_datasets(self):
        db=connect(':memory:');db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db,self.payload,EXTRACT)
        before={t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')]
            for t in ['source','school','economic_observation','assessment_observation']}
        import_snapshot(db,self.payload,EXTRACT)
        self.assertEqual(before,{t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in before})
        self.assertIsNotNone(db.execute("SELECT * FROM dataset WHERE id='keep'").fetchone())
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall());db.close()


if __name__=='__main__':unittest.main()
