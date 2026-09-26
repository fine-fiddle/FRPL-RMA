import json
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_cps_crosswalk import validate


class IllinoisExpansionTests(unittest.TestCase):
    def test_2017_models_against_original_school_aggregates(self):
        source = json.loads((ROOT/'data/source/illinois-history-2017.json').read_text())
        output = json.loads((ROOT/'data/illinois/schools.json').read_text())
        for test in ['PARCC','SAT']:
            for subject in ['math','reading','combined']:
                points = {}
                for row in source['observations']:
                    try:
                        income = float(row['profile']['% Student Enrollment - Low Income'])
                        subjects = ['math','reading'] if subject=='combined' else [subject]
                        actual = np.mean([float(row['proficiency'][test][s]) for s in subjects])
                    except ValueError:
                        continue
                    points[row['profile']['RCDTS']] = (income,actual)
                ids=list(points)
                x,y=np.array(list(points.values())).T
                X=np.column_stack([np.ones(len(x)),x])
                beta=np.linalg.lstsq(X,y,rcond=None)[0]
                e=y-X@beta
                h=np.einsum('ij,jk,ik->i',X,np.linalg.inv(X.T@X),X)
                t=e/np.sqrt((e@e-e**2/(1-h))/(len(x)-3)*(1-h))
                expected=dict(zip(ids,t))
                model=next(m for m in output['history_models'] if m['year']==2017 and m['assessment']==test and m['subject']==subject)
                self.assertEqual(model['n'],len(points))
                self.assertAlmostEqual(model['slope'],beta[1])
                for school in output['schools']:
                    for row in school['history']:
                        if row['year']==2017 and row['assessment']==test and subject in row['subjects']:
                            self.assertEqual(row['income'],points[school['id']][0])
                            self.assertAlmostEqual(row['subjects'][subject]['studentized'],expected[school['id']],places=8)
                            self.assertIsNone(row['subjects'][subject]['low'])

    def test_crosswalk_excludes_ambiguous_and_disagreeing_ids(self):
        rows=[dict(schoolid='A',isbe_id='state1',nces_id='101'),
              dict(schoolid='B',isbe_id='state2',nces_id='102'),
              dict(schoolid='C',isbe_id='state2',nces_id='102'),
              dict(schoolid='D',isbe_id='state3',nces_id='103'),
              dict(schoolid='E',isbe_id='state4')]
        locations={f'state{i}':dict(nces_id=str(100+i)) for i in range(1,5)}
        locations['state3']['nces_id']='changed'
        matches,rejected=validate(rows,dict.fromkeys('ABCDE'),locations)
        self.assertEqual([r['cps_id'] for r in matches],['A'])
        self.assertEqual(len(rejected),4)
        self.assertEqual(sum(r['reason']=='Ambiguous historical mapping' for r in rejected),2)

    def test_programs_only_transfer_via_verified_crosswalk(self):
        crosswalk=json.loads((ROOT/'data/source/cps-illinois-crosswalk.json').read_text())
        matches={r['school_id']:r['cps_id'] for r in crosswalk['matches']}
        self.assertEqual(len(matches),len(crosswalk['matches']))
        self.assertEqual(len(set(matches.values())),len(matches))
        cps={s['id']:s for s in json.loads((ROOT/'data/schools.json').read_text())['schools']}
        data=json.loads((ROOT/'data/illinois/schools.json').read_text())
        classified=0
        for school in data['schools']:
            if school['program']!='Unclassified':
                classified+=1
                self.assertEqual(school['cps_id'],matches[school['id']])
                if school['cps_id'] in cps:
                    self.assertEqual(school['program'],cps[school['cps_id']]['program'])
            if school['id'] not in matches:
                self.assertEqual(school['program'],'Unclassified')
        self.assertGreater(classified,400)
