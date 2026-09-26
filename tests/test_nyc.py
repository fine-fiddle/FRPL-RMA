import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from database import ROOT
from prepare_nyc import import_data, number, validated_rate


class NYCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((ROOT/'data/source/nyc.json').read_text())
        cls.output=json.loads((ROOT/'data/nyc/schools.json').read_text())
        cls.history=json.loads((ROOT/'data/nyc/history.json').read_text())

    def test_suppression_and_denominators(self):
        for token in ['s','Above 95%','Below 5%',None]:
            self.assertIsNone(number(token))
        self.assertEqual(number(0),0)
        self.assertEqual(validated_rate(dict(tested=100,proficient=0,rate=0)),(0,100))
        self.assertEqual(validated_rate(dict(tested=100,proficient='s',rate='s')),(None,100))
        with self.assertRaises(ValueError):
            validated_rate(dict(tested=100,proficient=70,rate=71))
        with self.assertRaises(ValueError):
            validated_rate(dict(tested=4.5,proficient=2,rate=44.44))

    def test_annual_model_matches_original_counts_and_income(self):
        income={(r['school_id'],r['year']):r for r in self.source['income']}
        grouped={}
        for r in self.source['assessments']:
            p=income.get((r['school_id'],r['year']))
            fraction=number(p['fraction']) if p else None
            rate,n=validated_rate(r)
            if fraction is None or rate is None or n is None or n<10:
                continue
            key=(r['year'],r['level'],r['assessment'],r['subject'])
            grouped.setdefault(key,{})[r['school_id']]=(100*fraction,rate)
        for year,level,assessment,subject in list(grouped):
            if subject!='math':continue
            math=grouped[(year,level,assessment,'math')]
            ela=grouped[(year,level,assessment,'reading')]
            grouped[(year,level,assessment,'combined')]={sid:(x,(y+ela[sid][1])/2) for sid,(x,y) in math.items() if sid in ela}
        results={(r['year'],r['level'],r['assessment'],r['school_id']):r for r in self.history['records']}
        for model in self.history['models']:
            key=tuple(model[k] for k in ['year','level','assessment','subject'])
            values=grouped[key]; n=len(values)
            self.assertEqual(model['n'],n)
            x=np.array([v[0] for v in values.values()]); y=np.array([v[1] for v in values.values()])
            design=np.column_stack([np.ones(n),x]); beta=np.linalg.lstsq(design,y,rcond=None)[0]
            residual=y-design@beta
            leverage=np.sum((design@np.linalg.inv(design.T@design))*design,axis=1)
            deleted_var=(residual@residual-residual**2/(1-leverage))/(n-3)
            expected=residual/np.sqrt(deleted_var*(1-leverage))
            self.assertAlmostEqual(model['slope'],beta[1],places=9)
            for sid,value in zip(values,expected):
                record=results[(*key[:3],sid)]; result=record['subjects'][key[3]]
                self.assertEqual(record['income_year'],key[0])
                self.assertAlmostEqual(result['studentized'],value,places=8)
                self.assertLess(result['low'],result['studentized'])
                self.assertGreater(result['high'],result['studentized'])

    def test_repeat_import_and_new_york_definitions(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        import_data(db,self.source)
        before=[tuple(r) for r in db.execute('SELECT * FROM assessment_observation ORDER BY school_id,definition_id,subject')]
        import_data(db,self.source)
        self.assertEqual(before,[tuple(r) for r in db.execute('SELECT * FROM assessment_observation ORDER BY school_id,definition_id,subject')])
        self.assertEqual({r[0] for r in db.execute('SELECT state FROM assessment_definition')},{'NY'})
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        db.close()

    def test_snapshot_years_scope_and_missing_income(self):
        self.assertEqual(self.output['levels']['ES']['year'],2026)
        self.assertEqual(self.output['levels']['HS']['year'],2023)
        self.assertEqual(len(self.output['schools']),len({s['id'] for s in self.output['schools']}))
        for s in self.output['schools']:
            self.assertEqual(s['program'],'Unclassified')
            year=self.output['levels'][s['level']]['year']
            current=next((r for r in s['history'] if r['year']==year),None)
            self.assertEqual(s['metrics'],current['subjects'] if current else {})
            if s['income'] is None:self.assertFalse(s['metrics'])
            if s['latitude'] is not None:
                self.assertTrue(40.4<=s['latitude']<=41)
                self.assertTrue(-74.3<=s['longitude']<=-73.65)
        assessments={r['year']:r['assessment'] for r in self.history['records'] if r['level']=='ES'}
        self.assertNotEqual(assessments[2022],assessments[2023])


if __name__=='__main__':unittest.main()
