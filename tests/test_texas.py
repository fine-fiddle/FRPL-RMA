import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from database import ROOT
from prepare_texas import EXTRACT, GRADES, grade_school, income, normalize, outcome, sid
from state_snapshot import import_snapshot


class TexasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads(EXTRACT.read_text());cls.payload=normalize(cls.raw)
        cls.output=json.loads((ROOT/'data/texas/schools.json').read_text())

    def test_native_exact_rates_and_no_mask_reconstruction(self):
        self.assertEqual(outcome(['100','33','33']),(33,100,None))
        self.assertAlmostEqual(outcome(['101','33','33'])[0],100*33/101)
        for r in [['-1','-1','-1'],['100','-3','33'],['0','0','']]:self.assertIsNone(outcome(r)[0])
        for r in [['101','33','40'],['100','101','100'],['4','4','100'],['100.5','30','30']]:
            with self.assertRaises(ValueError):outcome(r)
        for p in self.raw['profiles']:
            for r in p['outcomes'].values():
                pct,n,_=outcome(r)
                if pct is not None:self.assertAlmostEqual(pct,100*int(r[1])/int(r[0]))

    def test_same_year_income_enrolled_scope_and_exact_ids(self):
        self.assertEqual(sid(self.raw['profiles'][0]['profile']),'001902001')
        bad=copy.deepcopy(self.raw['profiles'][0]['profile']);bad['DISTRICT']='999999'
        with self.assertRaises(ValueError):sid(bad)
        self.assertEqual(len(self.raw['profiles']),9084)
        self.assertEqual(len(self.payload['schools']),6573)
        for p in self.raw['profiles']:
            row=p['profile'];total,low,pct=income(row)
            self.assertEqual(low+int(row['CPNTNEDC']),total)
            self.assertAlmostEqual(pct,100*low/total)
            self.assertEqual(grade_school(row),not any(int(row[k]) for k in GRADES[-4:]))
        self.assertIn('universal meals do not make all',self.payload['income_definition']['definition'].lower())

    def test_models_independent_deleted_school_regression(self):
        profiles={s['id']:s for s in self.payload['schools']}
        schools={s['id']:s for s in self.output['schools']}
        for model in self.output['history_models']:
            expected={}
            for key,p in profiles.items():
                rates={s:o['proficiency'] if o['tested'] is not None and o['tested']>=10 else None for s,o in p['outcomes'].items()}
                if all(v is not None for v in rates.values()):rates['combined']=(rates['math']+rates['reading'])/2
                if p['income'] is not None and rates.get(model['subject']) is not None:expected[key]=(p['income'],rates[model['subject']])
            self.assertEqual(model['n'],len(expected))
            self.assertEqual(model['n'],6118 if model['subject']=='math' else 6117)
            x,y=np.array(list(expected.values())).T;design=np.column_stack([np.ones(len(x)),x])
            beta=np.linalg.lstsq(design,y,rcond=None)[0];self.assertAlmostEqual(model['slope'],beta[1],places=9)
            for i in [0,len(x)//2,len(x)-1]:
                keep=np.arange(len(x))!=i;deleted=np.linalg.lstsq(design[keep],y[keep],rcond=None)[0]
                errors=y[keep]-design[keep]@deleted;variance=errors@errors/(len(x)-3)
                h=design[i]@np.linalg.inv(design.T@design)@design[i]
                value=(y[i]-design[i]@beta)/np.sqrt(variance*(1-h))
                metric=schools[list(expected)[i]]['metrics'][model['subject']]
                self.assertAlmostEqual(metric['studentized'],value,places=8)
                self.assertIsNotNone(metric['low']);self.assertIsNotNone(metric['high'])

    def test_grade_filter_and_coordinate_independence(self):
        for s in self.output['schools']:
            self.assertEqual(s['level'],'ES');self.assertIsNone(s['latitude']);self.assertIsNone(s['longitude'])
            self.assertEqual(s['history'][0]['income_year'],2025)
            if 'combined' in s['metrics']:
                self.assertAlmostEqual(s['metrics']['combined']['actual'],(s['metrics']['math']['actual']+s['metrics']['reading']['actual'])/2)
            else:self.assertTrue(s['exclusions']['combined'])

    def test_repeat_import_preserves_unrelated_and_rejects_wrong_year(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db,self.payload,EXTRACT)
        tables=['source','school','economic_observation','assessment_observation']
        before={t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        import_snapshot(db,self.payload,EXTRACT)
        self.assertEqual(before,{t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0],'Unrelated')
        bad=copy.deepcopy(self.raw);bad['year']=2024
        with self.assertRaises(ValueError):normalize(bad)


if __name__=='__main__':unittest.main()
