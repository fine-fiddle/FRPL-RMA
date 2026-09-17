import sys
import unittest
import json
from pathlib import Path
import numpy as np
import polars as pl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_data import fit_model, sampling_variance, build_history

class ModelsTest(unittest.TestCase):
    def test_studentization_matches_explicit_leave_one_out(self):
        x=np.array([3,8,20,35,55,65,88,96.])
        y=np.array([75,61,66,48,21,32,18,4.])
        model,results=fit_model(x,y,np.ones(len(x)))
        for i,r in enumerate(results):
            keep=np.arange(len(x))!=i
            X=np.column_stack([np.ones(keep.sum()),x[keep]])
            beta=np.linalg.lstsq(X,y[keep],rcond=None)[0]
            variance=np.sum((y[keep]-X@beta)**2)/(len(x)-3)
            expected=r['residual']/np.sqrt(variance*(1-r['leverage']))
            self.assertAlmostEqual(expected,r['studentized'],places=10)
        self.assertAlmostEqual(sum(r['residual'] for r in results),0,places=9)
    def test_sampling_intervals_respond_to_tested_count(self):
        x=[10,25,40,60,75,90]; y=[65,70,40,35,30,9]
        _,small=fit_model(x,y,[sampling_variance(p,20) for p in y])
        _,large=fit_model(x,y,[sampling_variance(p,200) for p in y])
        for a,b in zip(small,large):
            self.assertAlmostEqual(a['studentized'],b['studentized'])
            self.assertGreater(a['high']-a['low'],b['high']-b['low'])
    def test_boundary_rates_have_positive_variance(self):
        self.assertGreater(sampling_variance(0,100),0)
        self.assertGreater(sampling_variance(100,100),0)
    def test_degenerate_cohort_rejected(self):
        with self.assertRaises(ValueError):fit_model([1,1,1,1],[4,3,2,1],[1]*4)

    def test_history_snapshot_keeps_assessment_gap_explicit(self):
        with open(Path(__file__).resolve().parents[1] / 'data/schools.json') as source:
            data = json.load(source)
        self.assertEqual(data['history_years'], [2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024])
        school = next(s for s in data['schools'] if s['history'])
        years = [record['year'] for record in school['history']]
        self.assertNotIn(2020, years)
        self.assertTrue(any('math' in r['subjects'] for r in school['history']))

    def test_every_historical_model_matches_same_year_inputs(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads((root/'data/history.json').read_text())
        incomes = pl.read_csv(root/'data/source/income-history.csv').to_dicts()
        income = {(str(r['school_id']),r['year']):r for r in incomes}
        assessments = pl.read_csv(root/'data/source/assessments-history.csv', infer_schema=False).to_dicts()
        actuals = {(r['school_id'],int(r['year']),r['level'],r['assessment'],r['subject']):r for r in assessments}
        self.assertEqual({r['year'] for r in incomes},set(range(2015,2025)))
        for model in data['models']:
            subject=model['subject']
            records=[r for r in data['records'] if (r['year'],r['level'],r['assessment']) == (model['year'],model['level'],model['assessment']) and subject in r['subjects']]
            self.assertEqual(len(records),model['n'])
            for r in records:
                source=income[(r['school_id'],r['year'])]
                self.assertAlmostEqual(r['income'],100*source['low_income']/source['enrollment'])
                self.assertEqual(r['income_year'],r['year'])
                for part in (['math','reading'] if subject=='combined' else [subject]):
                    a=actuals[(r['school_id'],r['year'],r['level'],r['assessment'],part)]
                    self.assertAlmostEqual(r['subjects'][part]['actual'],float(a['proficiency']))
            x=np.array([r['income'] for r in records]); y=np.array([r['subjects'][subject]['actual'] for r in records])
            X=np.column_stack([np.ones(len(x)),x]); beta=np.linalg.lstsq(X,y,rcond=None)[0]
            residual=y-X@beta
            h=np.einsum('ij,jk,ik->i',X,np.linalg.inv(X.T@X),X)
            t=residual/np.sqrt(((residual@residual-residual**2/(1-h))/(len(x)-3))*(1-h))
            np.testing.assert_allclose([r['subjects'][subject]['studentized'] for r in records],t,atol=1e-8)
            self.assertAlmostEqual(model['slope'],beta[1])
            for r in records:
                m=r['subjects'][subject]
                self.assertLessEqual(m['low'],m['studentized']); self.assertGreaterEqual(m['high'],m['studentized'])
        snapshot=json.loads((root/'data/schools.json').read_text())
        for school in snapshot['schools']:
            current=next((r for r in school['history'] if r['year']==2024),None)
            self.assertEqual(school['metrics'],current['subjects'] if current else {})
        current_ids={s['id'] for s in snapshot['schools']}
        self.assertTrue(any(r['school_id'] not in current_ids and r['subjects'] for r in data['records']))

    def test_missing_income_is_not_backfilled_and_duplicate_keys_fail(self):
        a=pl.DataFrame([dict(school_id='1',year='2015',level='ES',assessment='IAR',subject='math',proficiency='50',tested='40')])
        income=pl.DataFrame([dict(school_id='1',year='2024',name='School',enrollment='100',low_income='50',income_label='FRPL')])
        records,models=build_history(a,income)
        self.assertIsNone(records[0]['income'])
        self.assertEqual(records[0]['subjects'],{})
        self.assertEqual(models,[])
        self.assertIn('same-year income',records[0]['exclusions']['math'])
        with self.assertRaises(ValueError):build_history(pl.concat([a,a]),income)
        with self.assertRaises(ValueError):build_history(a,pl.concat([income,income]))

if __name__=='__main__':unittest.main()
