import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from database import ROOT
from prepare_florida import EXTRACT,income,normalize,outcome,scope,sid
from state_snapshot import import_snapshot


class FloridaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads(EXTRACT.read_text());cls.payload=normalize(cls.raw)
        cls.output=json.loads((ROOT/'data/florida/schools.json').read_text())

    def test_individual_income_ignores_multiplier_and_excludes_provision2(self):
        row=[1,'District',31,'School',514,0,0,0,213,340,340,.661]
        self.assertEqual(sid(row),'01-0031')
        self.assertAlmostEqual(income(row)[2],100*213/514)
        row[9:]=[514,514,1];self.assertAlmostEqual(income(row)[2],100*213/514)
        row[7]=1;self.assertIsNone(income(row)[2])
        row[7]='*';self.assertIsNone(income(row)[2])
        row[7]=0;row[8]=515
        with self.assertRaises(ValueError):income(row)
        for p in self.raw['profiles']:
            total,low,pct,_=income(p['income_raw'])
            if pct is not None:
                self.assertEqual(p['income_raw'][7],0)
                self.assertEqual(low,sum(p['income_raw'][i] for i in [5,6,8]))
                self.assertAlmostEqual(pct,100*low/total)

    def test_native_achievement_no_collocated_or_provider_inference(self):
        row=copy.deepcopy(self.raw['assessments'][0]['raw'])
        self.assertEqual(outcome(row,'reading')[0],row[6])
        row[47]='Y';self.assertIsNone(outcome(row,'math')[0])
        row[47]='N';row[3]='302';self.assertIsNone(outcome(row,'reading')[0])
        row[3]='';row[6]=None;self.assertIsNone(outcome(row,'reading')[0])
        row[6]=101
        with self.assertRaises(ValueError):outcome(row,'reading')
        self.assertTrue(all(o['tested'] is None for p in self.payload['schools'] for o in p['outcomes'].values()))

    def test_grade_scope_preserves_protected_counts_and_excludes_high_schools(self):
        row=copy.deepcopy(next(p['grades'] for p in self.raw['profiles'] if scope(p['grades'])))
        row[14]='*';self.assertFalse(scope(row))
        row[14]=1;self.assertFalse(scope(row))
        self.assertEqual(len(self.payload['schools']),2885)
        self.assertEqual(len(self.raw['unmatched_income']),12)
        self.assertEqual(self.payload['source_audit']['unmatched_native_assessment_ids'],['26-0018'])
        for s in self.output['schools']:
            self.assertEqual(s['level'],'ES');self.assertIsNone(s['latitude']);self.assertIsNone(s['longitude'])
            self.assertEqual(s['history'][0]['income_year'],2025)
            for m in s['metrics'].values():self.assertIsNone(m['low']);self.assertIsNone(m['high'])
            if 'combined' in s['metrics']:
                self.assertAlmostEqual(s['metrics']['combined']['actual'],(s['metrics']['math']['actual']+s['metrics']['reading']['actual'])/2)
            else:self.assertTrue(s['exclusions']['combined'])

    def test_models_against_independent_deleted_school_regressions(self):
        profiles={p['id']:p for p in self.payload['schools']};schools={s['id']:s for s in self.output['schools']}
        for model in self.output['history_models']:
            expected={}
            for key,p in profiles.items():
                rates={s:o['proficiency'] for s,o in p['outcomes'].items()}
                if all(v is not None for v in rates.values()):rates['combined']=(rates['math']+rates['reading'])/2
                if p['income'] is not None and rates.get(model['subject']) is not None:expected[key]=(p['income'],rates[model['subject']])
            self.assertEqual(model['n'],len(expected));self.assertEqual(model['n'],2742)
            x,y=np.array(list(expected.values())).T;design=np.column_stack([np.ones(len(x)),x])
            beta=np.linalg.lstsq(design,y,rcond=None)[0];self.assertAlmostEqual(model['slope'],beta[1],places=9)
            for i in [0,len(x)//2,len(x)-1]:
                keep=np.arange(len(x))!=i;deleted=np.linalg.lstsq(design[keep],y[keep],rcond=None)[0]
                errors=y[keep]-design[keep]@deleted;variance=errors@errors/(len(x)-3)
                h=design[i]@np.linalg.inv(design.T@design)@design[i]
                value=(y[i]-design[i]@beta)/np.sqrt(variance*(1-h))
                self.assertAlmostEqual(schools[list(expected)[i]]['metrics'][model['subject']]['studentized'],value,places=8)

    def test_repeat_import_and_wrong_year_identity_rejected(self):
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
        bad=copy.deepcopy(self.raw);bad['profiles'][0]['id']='99-9999'
        with self.assertRaises(ValueError):normalize(bad)


if __name__=='__main__':unittest.main()
