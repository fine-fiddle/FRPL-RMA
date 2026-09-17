import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_data import fit_model, sampling_variance

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

if __name__=='__main__':unittest.main()
