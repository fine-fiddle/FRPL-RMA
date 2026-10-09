import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from database import ROOT
from prepare_pennsylvania import EXTRACT, grade_school, import_data, income_result, result, school_id


class PennsylvaniaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload=json.loads(EXTRACT.read_text())
        cls.profiles={p['school_id']:p for p in cls.payload['schools']}
        cls.results={(r['school_id'],r['subject']):r for r in cls.payload['assessments']}
        cls.output=json.loads((ROOT/'data/pennsylvania/schools.json').read_text())

    def test_native_rates_and_scored_denominators_preserve_suppression(self):
        self.assertEqual(result([100,20,30,25,25,50]),(50,100,None))
        self.assertIsNone(result([10,None,None,None,None,None])[0])
        self.assertIsNone(result(None)[0])
        for raw in [[10,20,30,25,25,50],[100,20,30,25,25,51],[100,20,30,25,30,50],[None,20,30,25,25,50]]:
            with self.assertRaises(ValueError):result(raw)
        for r in self.results.values():
            rate,tested,_=result(r['raw'])
            if rate is not None:
                self.assertEqual(rate,r['raw'][5])
                self.assertEqual(tested,r['raw'][0])
                self.assertGreaterEqual(tested,11)

    def test_individual_income_exact_counts_and_authoritative_ids(self):
        self.assertEqual(school_id(112011103,7302),'112011103-000007302')
        self.assertEqual(school_id('112011103','000007302'),'112011103-000007302')
        with self.assertRaises(ValueError):school_id('112011103',0)
        # Published proportions are truncated; use source count ratio, not that approximation.
        self.assertAlmostEqual(income_result([996,71,.0712])[2],100*71/996)
        with self.assertRaises(ValueError):income_result([996,71,.08])
        with self.assertRaises(ValueError):income_result([100,101,1])
        self.assertEqual(len(self.profiles),3389)
        self.assertEqual(len(self.payload['excluded_enrollment']),27)
        self.assertEqual(self.payload['unmatched_assessments'],[])
        for p in self.profiles.values():
            self.assertEqual(p['grade_school'],grade_school(p['grades']))
            if p['income_raw'] is not None:
                self.assertEqual(p['income_raw'][0],sum(p['grades']))

    def test_models_against_independent_deleted_school_regressions(self):
        schools={s['id']:s for s in self.output['schools']}
        for model in self.output['history_models']:
            expected={}
            for key,p in self.profiles.items():
                if not p['grade_school']:continue
                income=income_result(p['income_raw'])[2]
                rates={s:result(self.results.get((key,s),{}).get('raw'))[0] for s in ['math','reading']}
                if all(v is not None for v in rates.values()):rates['combined']=(rates['math']+rates['reading'])/2
                rate=rates.get(model['subject'])
                if income is not None and rate is not None:expected[key]=(income,rate)
            self.assertEqual(model['n'],2008)
            self.assertEqual(model['n'],len(expected))
            x,y=np.array(list(expected.values())).T
            design=np.column_stack([np.ones(len(x)),x])
            beta=np.linalg.lstsq(design,y,rcond=None)[0]
            self.assertAlmostEqual(model['slope'],beta[1],places=9)
            for i in [0,len(x)//2,len(x)-1]:
                other=np.arange(len(x))!=i
                deleted=np.linalg.lstsq(design[other],y[other],rcond=None)[0]
                errors=y[other]-design[other]@deleted
                variance=errors@errors/(len(x)-3)
                leverage=design[i]@np.linalg.inv(design.T@design)@design[i]
                external=(y[i]-design[i]@beta)/np.sqrt(variance*(1-leverage))
                metric=schools[list(expected)[i]]['metrics'][model['subject']]
                self.assertAlmostEqual(metric['studentized'],external,places=8)
                self.assertIsNotNone(metric['low'])
                self.assertIsNotNone(metric['high'])

    def test_grade_school_filter_excludes_high_schools_and_missing_locations_do_not_exclude(self):
        self.assertEqual(len(self.output['schools']),2172)
        self.assertEqual(sum('combined' in s['metrics'] for s in self.output['schools']),2008)
        for s in self.output['schools']:
            self.assertEqual(s['level'],'ES')
            self.assertFalse(any(self.profiles[s['id']]['grades'][17:]))
            self.assertIsNone(s['latitude'])
            self.assertIsNone(s['longitude'])
            self.assertEqual(s['history'][0]['income_year'],2025)
            if 'combined' in s['metrics']:
                self.assertAlmostEqual(s['metrics']['combined']['actual'],(s['metrics']['math']['actual']+s['metrics']['reading']['actual'])/2)
            else:self.assertTrue(s['exclusions']['combined'])

    def test_repeat_import_and_invalid_identity_year(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_data(db,self.payload)
        tables=['source','school','economic_observation','assessment_observation']
        before={t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        import_data(db,self.payload)
        self.assertEqual(before,{t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0],'Unrelated')
        bad=copy.deepcopy(self.payload);bad['assessments'][0]['identity_raw'][8]=3
        with self.assertRaises(ValueError):import_data(db,bad)
        bad=copy.deepcopy(self.payload);bad['year']=2024
        with self.assertRaises(ValueError):import_data(db,bad)


if __name__=='__main__':unittest.main()
