import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from database import connect
from prepare_new_jersey import EXTRACT, GRADES, INCOME_FIELD, cohort, count, identity, outcome, percentage
from state_snapshot import import_snapshot


class NewJerseyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload=json.loads(EXTRACT.read_text())
        cls.output=json.loads((ROOT/'data/new-jersey/schools.json').read_text())
        cls.history=json.loads((ROOT/'data/new-jersey/history.json').read_text())

    def test_rates_ranges_and_counts_keep_distinct_meanings(self):
        for token in ['<10%','>90%','Fewer than 10 valid scores','*',None]:
            self.assertIsNone(percentage(token))
            self.assertIsNone(count(token))
        self.assertEqual(count('1,234'),1234)
        self.assertEqual(percentage('0%'),0)
        self.assertIsNone(count('100.5'))
        with self.assertRaises(ValueError): percentage('101%')
        row={'MetExceededExpectations_School':'60.0%','ValidScores_School':'80',
             'FederalProficiencyRate_School':'48.0%','ParticipationRate_School':'80.0%'}
        result=outcome(row,'math',False)
        self.assertEqual((result['proficiency'],result['tested']),(60,80))
        row['ValidScores_School']='9'
        with self.assertRaises(ValueError): outcome(row,'math',False)

    def test_county_district_school_and_grade_scope_are_authoritative(self):
        row={'CountyCode':'01','DistrictCode':'0010','SchoolCode':'050'}
        self.assertEqual(identity(row),'010010050')
        row['CountyCode']=1
        with self.assertRaises(ValueError): identity(row)
        grades=[0]*14
        grades[4]=100
        self.assertEqual(cohort(grades),'ES')
        grades[10]=100
        self.assertIsNone(cohort(grades))  # Grade9 alone is not a grade11 NJGPA cohort.
        grades[12]=100
        self.assertEqual(cohort(grades),'HS')
        grades[10]='*'
        self.assertIsNone(cohort(grades))

    def test_all_exports_match_native_values_and_same_year_ids(self):
        raw={p['id']:p for p in self.payload['schools']}
        differing=0
        for school in self.output['schools']:
            p=raw[school['id']]
            self.assertEqual(school['id'],identity(p['grades_raw']))
            self.assertEqual(school['level'],cohort([p['grades_raw'][g] for g in GRADES]))
            self.assertEqual(p['income_raw']['SchoolYear'],'2024-25')
            self.assertEqual(school['income'],percentage(p['income_raw'][INCOME_FIELD]))
            if school['level']=='ES': self.assertTrue(all(count(p['grades_raw'][g])==0 for g in GRADES[10:]))
            for subject in ['math','reading']:
                source=p['outcomes'].get(subject)
                actual=school['metrics'].get(subject)
                if actual:
                    self.assertEqual(source['raw']['SchoolYear'],'2024-25')
                    self.assertEqual(identity(source['raw']),school['id'])
                    self.assertEqual(actual['actual'],source['proficiency'])
                    self.assertEqual(actual['tested'],source['tested'])
                    self.assertGreaterEqual(actual['tested'],10)
                    self.assertIsNotNone(actual['low'])
                if source and school['level']=='ES' and source['proficiency'] is not None:
                    if source['proficiency'] != percentage(source['raw']['FederalProficiencyRate_School']): differing+=1
            if school['metrics'].get('combined'):
                self.assertAlmostEqual(school['metrics']['combined']['actual'],
                    (school['metrics']['math']['actual']+school['metrics']['reading']['actual'])/2)
        self.assertGreater(differing,50)

    def test_repeat_import_preserves_other_datasets_and_requires_count_evidence(self):
        db=connect(':memory:')
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Keep','Keep','ready')")
        import_snapshot(db,self.payload,EXTRACT)
        tables=['source','school','economic_observation','assessment_observation']
        first={t:db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables}
        import_snapshot(db,self.payload,EXTRACT)
        self.assertEqual(first,{t:db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables})
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0],'Keep')
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        invalid=copy.deepcopy(self.payload)
        for school in invalid['schools']:
            for result in school['outcomes'].values():
                if result['tested']:
                    result.pop('valid_score_evidence')
                    with self.assertRaises(ValueError): import_snapshot(db,invalid,EXTRACT)
                    db.close()
                    return
        self.fail('No verified valid-score source was tested')

    def test_six_models_match_independent_deleted_residual_calculation(self):
        self.assertEqual(len(self.history['models']),6)
        for model in self.history['models']:
            subject=model['subject']
            rows=[r for r in self.history['records'] if r['level']==model['level'] and subject in r['subjects']]
            X=np.column_stack([np.ones(len(rows)),[r['income'] for r in rows]])
            y=np.array([r['subjects'][subject]['actual'] for r in rows])
            beta=np.linalg.lstsq(X,y,rcond=None)[0]
            residual=y-X@beta
            hat=np.einsum('ij,jk,ik->i',X,np.linalg.inv(X.T@X),X)
            deleted=(residual@residual-residual**2/(1-hat))/(len(rows)-3)
            studentized=residual/np.sqrt(deleted*(1-hat))
            np.testing.assert_allclose([model['intercept'],model['slope']],beta,rtol=1e-10,atol=1e-10)
            np.testing.assert_allclose([r['subjects'][subject]['studentized'] for r in rows],studentized,rtol=1e-10,atol=1e-10)
            self.assertEqual(model['n'],len(rows))


if __name__=='__main__': unittest.main()
