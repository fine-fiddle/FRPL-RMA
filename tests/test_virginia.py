import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from database import connect
from prepare_virginia import (ACADEMIC_YEAR,BANDS,DATASET,EXTRACT,YEAR,assessment_value,band_for,
    import_data,income_values,number,school_id)


def fixture():
    return dict(division_number='128',school_number='980',name='Test',district='Test district',category='Elementary',
        enrollment_subgroups={'5':dict(sch_yr='2024',subgroup_type_id='5',cnt='100',pct='100'),
            '3':dict(sch_yr='2024',subgroup_type_id='3',cnt='30',pct='30'),
            '18':dict(sch_yr='2024',subgroup_type_id='18',cnt='70',pct='70')},
        grade_table=dict(years=['2023-2024',ACADEMIC_YEAR,'2025-2026'],rows=[
            dict(label='Grade 3',values=['50','50','50']),dict(label='Grade 4',values=['50','50','50']),
            dict(label='Total Enrollment',values=['100','100','100'])]),
        assessments={s:dict(population='All Students',test='Mathematics' if s=='math' else 'English Reading',
            years=['2023-2024',ACADEMIC_YEAR,'2025-2026'],school_values=['42','71','98'],
            table_columns=['Advanced','Proficient','Passed','Failed'],table_all_students=['2','40','42','58','5','66','71','29','8','90','98','2'])
            for s in ['math','reading']})


class VirginiaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload=json.loads(EXTRACT.read_text())
        cls.outputs=[json.loads((ROOT/'data/virginia'/folder/'schools.json').read_text()) for folder in ['', 'mixed']]
        cls.histories=[json.loads((ROOT/'data/virginia'/folder/'history.json').read_text()) for folder in ['', 'mixed']]

    def test_native_counts_override_only_a_demonstrably_stale_display_percentage(self):
        raw=fixture();raw['enrollment_subgroups']['3']['pct']='31.5';raw['enrollment_subgroups']['5']['pct']='105'
        self.assertEqual(income_values(raw),(100,30,30))
        raw['grade_table']['rows'][0]['values'][1]='51'
        self.assertEqual(income_values(raw),(100,None,None))
        raw=fixture();raw['enrollment_subgroups']['18']['cnt']='69'
        self.assertEqual(income_values(raw),(100,None,None))
        raw=fixture();raw['grade_table']['rows'][0]['values'][1]='<'
        self.assertEqual(income_values(raw),(100,None,None))

    def test_suppression_never_becomes_zero_or_a_reconstructed_complement(self):
        for field in ['cnt','pct']:
            raw=fixture();raw['enrollment_subgroups']['3'][field]='<'
            self.assertEqual(income_values(raw),(100,None,None))
        raw=fixture();raw['enrollment_subgroups']['3'].update(cnt='0',pct='0');raw['enrollment_subgroups']['18']['cnt']='100'
        self.assertEqual(income_values(raw),(100,0,0))
        for value in ['nan','-1','1.5']:
            with self.assertRaises(ValueError):number(value,integral=True)

    def test_same_year_native_grade_membership_partitions_mixed_schools(self):
        raw=fixture();self.assertEqual(band_for(raw),'grade')
        raw['grade_table']['rows'].append(dict(label='Grade 9',values=['0','<','0']))
        self.assertEqual(band_for(raw),'mixed')
        raw['grade_table']['rows']=raw['grade_table']['rows'][-1:]
        self.assertEqual(band_for(raw),'high')
        raw['grade_table']['rows']=[dict(label='Kindergarten',values=['40','40','40'])]
        self.assertIsNone(band_for(raw))
        raw=fixture();raw['grade_table']['years']=['2025-2026']
        self.assertIsNone(band_for(raw))

    def test_identity_year_and_published_subject_totals_are_required(self):
        raw=fixture();self.assertEqual(school_id(raw),'1280980');self.assertEqual(assessment_value(raw,'math'),71)
        for changed in [dict(raw,school_number=980),dict(raw,division_number='0')]:
            with self.assertRaises(ValueError):school_id(changed)
        raw=fixture();raw['enrollment_subgroups']['3']['sch_yr']='2023'
        with self.assertRaises(ValueError):income_values(raw)
        for altered in ['population','test','years']:
            raw=fixture();raw['assessments']['math'][altered]={'population':'Economically Disadvantaged','test':'Grade 3 Mathematics','years':['2023-2024']}[altered]
            with self.assertRaises(ValueError):assessment_value(raw,'math')
        raw=fixture();raw['assessments']['math']['school_values'][1]='<'
        self.assertIsNone(assessment_value(raw,'math'))

    def test_importer_is_repeatable_preserves_other_data_and_does_not_invent_tested_counts(self):
        db=connect(':memory:');db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Keep','Keep','ready')")
        import_data(db,self.payload)
        tables=['source','school','economic_observation','assessment_observation']
        before=[db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables]
        import_data(db,self.payload)
        self.assertEqual(before,[db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0],'Keep')
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=? AND tested IS NOT NULL',(DATASET,)).fetchone()[0],0)
        broken=copy.deepcopy(self.payload);broken['profiles'].append(broken['profiles'][0])
        with self.assertRaises(ValueError):import_data(db,broken)
        db.close()

    def test_directory_rates_and_income_are_native_single_year_values(self):
        native={e['school_id']:e['raw'] for e in self.payload['profiles']}
        all_ids=set()
        for output in self.outputs:
            for school in output['schools']:
                self.assertNotIn(school['id'],all_ids);all_ids.add(school['id'])
                raw=native[school['id']];band=band_for(raw)
                self.assertEqual(school['level'],BANDS[band][0])
                self.assertEqual(school['income'],income_values(raw)[2])
                for subject in ['math','reading']:
                    if subject in school['metrics']:
                        self.assertEqual(school['metrics'][subject]['actual'],assessment_value(raw,subject))
                        self.assertIsNone(school['metrics'][subject]['tested'])
                if 'combined' in school['metrics']:
                    self.assertEqual(school['metrics']['combined']['actual'],
                        (school['metrics']['math']['actual']+school['metrics']['reading']['actual'])/2)
                self.assertEqual([r['year'] for r in school['history']],[YEAR])
        self.assertEqual(self.payload['inventory']['total_schools'],len(native))

    def test_independent_studentization_and_strict_cohort_separation_without_intervals(self):
        for history in self.histories:
            for model in history['models']:
                rows=[r for r in history['records'] if r['level']==model['level'] and r['assessment']==model['assessment'] and model['subject'] in r['subjects']]
                x=np.array([r['income'] for r in rows]);y=np.array([r['subjects'][model['subject']]['actual'] for r in rows])
                X=np.column_stack([np.ones(len(x)),x]);beta=np.linalg.lstsq(X,y,rcond=None)[0]
                e=y-X@beta;h=np.einsum('ij,jk,ik->i',X,np.linalg.inv(X.T@X),X)
                expected=e/np.sqrt((e@e-e**2/(1-h))/(len(x)-3)*(1-h))
                np.testing.assert_allclose([r['subjects'][model['subject']]['studentized'] for r in rows],expected,atol=1e-8)
                self.assertEqual(model['n'],len(rows))
                for row in rows:
                    self.assertEqual(row['year'],YEAR);self.assertEqual(row['income_year'],YEAR)
                    for field in ['tested','low','high']:self.assertIsNone(row['subjects'][model['subject']][field])
        self.assertEqual({m['assessment'] for h in self.histories for m in h['models']},{v[1] for v in BANDS.values()})
        self.assertEqual(len([m for h in self.histories for m in h['models']]),9)

    def test_stale_display_audit_contains_only_verified_count_ratios(self):
        audit=json.loads((ROOT/'data/virginia/audit.json').read_text())
        native={e['school_id']:e['raw'] for e in self.payload['profiles']}
        mismatches=[key for key,raw in native.items() if income_values(raw)[2] is not None and abs(float(raw['enrollment_subgroups']['3']['pct'])-income_values(raw)[2])>.00051]
        self.assertEqual(audit['stale_income_display_percentages'],len(mismatches))
        self.assertGreater(len(mismatches),0)
        for example in audit['stale_income_display_examples']:
            self.assertEqual(example['verified_count_percentage'],income_values(native[example['school_id']])[2])


if __name__=='__main__':unittest.main()
