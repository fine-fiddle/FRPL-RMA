import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_hawaii import EXTRACT, ccd_id, cohort, income, native_id, normalize, rate
from state_snapshot import import_snapshot


class HawaiiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(EXTRACT.read_text())
        cls.payload = normalize(cls.raw)
        cls.output = json.loads((ROOT / 'data/hawaii/schools.json').read_text())
        cls.complete = next(p for p in cls.raw['profiles'] if p['id'] == cls.payload['schools'][0]['id'])

    def test_exact_native_ids_and_historical_grade_scope(self):
        self.assertEqual(len(self.raw['profiles']), 296)
        self.assertEqual(len(self.payload['schools']), 225)
        for p in self.raw['profiles']:
            self.assertEqual(ccd_id(p['directory']), p['id'])
        for s in self.payload['schools']:
            self.assertEqual(s['cohort'], 'grade')
            self.assertTrue(all(s['directory_raw'][f'G_{g}_OFFERED'] == 'No' for g in range(9, 14)))
        for value in ['001', '1000', 'HI-100', 100]:
            with self.assertRaises(ValueError): native_id(value)
        bad = copy.deepcopy(self.complete)
        bad['directory']['G_9_OFFERED'] = 'Yes'
        self.assertIsNone(cohort(bad))
        bad = copy.deepcopy(self.complete)
        bad['directory']['G_UG_OFFERED'] = 'Yes'
        bad['membership_grades']['Ungraded'] = {'DMS_FLAG': 'Reported', 'STUDENT_COUNT': '1'}
        self.assertIsNone(cohort(bad))
        for field, value in [('SCHOOL_YEAR','2023-2024'),('ST_SCHID','HI-001-4-999')]:
            bad = copy.deepcopy(self.raw)
            bad['profiles'][0]['directory'][field] = value
            with self.assertRaises(ValueError): normalize(bad)

    def test_suppression_native_totals_and_no_counts(self):
        self.assertIsNone(rate('--'))
        self.assertIsNone(rate(''))
        self.assertEqual(rate('0'), 0)
        for value in ['95-100', '<5', '*', '101', 'nan', 59]:
            with self.assertRaises(ValueError): rate(value)
        self.assertIn('less than 11', self.raw['native_advisory'])
        for s in self.payload['schools']:
            for subject, field in [('math','Math Proficiency (%)'),('reading','LA Proficiency (%)')]:
                o = s['outcomes'][subject]
                self.assertEqual(o['proficiency'], rate(o['raw'][field]))
                self.assertIsNone(o['tested'])
        for s in self.output['schools']:
            for metric in s['metrics'].values():
                self.assertIsNone(metric['tested'])
                self.assertIsNone(metric['low'])
                self.assertIsNone(metric['high'])

    def test_individual_income_flags_identity_and_year(self):
        for s in self.payload['schools']:
            self.assertAlmostEqual(s['income'], 100*s['low_income']/s['enrollment'])
        p = copy.deepcopy(self.complete)
        p['direct_certification']['DMS_FLAG'] = 'Suppressed'
        self.assertIsNone(income(p)[2])
        for field, value in [('SCHOOL_YEAR','2023-2024'),('NCESSCH','159999999999'),('DATA_GROUP','Free and Reduced Lunch')]:
            p = copy.deepcopy(self.complete)
            p['direct_certification'][field] = value
            with self.assertRaises(ValueError): income(p)
        p = copy.deepcopy(self.complete)
        p['direct_certification']['STUDENT_COUNT'] = str(int(p['membership']['STUDENT_COUNT'])+1)
        self.assertIsNone(income(p)[2])

    def test_independent_deleted_school_models(self):
        outputs = {s['id']: s for s in self.output['schools']}
        for model in self.output['history_models']:
            values = {}
            for s in self.payload['schools']:
                rates = {k:o['proficiency'] for k,o in s['outcomes'].items()}
                if all(v is not None for v in rates.values()): rates['combined'] = (rates['math']+rates['reading'])/2
                if s['income'] is not None and rates.get(model['subject']) is not None:
                    values[s['id']] = (s['income'],rates[model['subject']])
            self.assertEqual(model['n'],224)
            x,y = np.array(list(values.values())).T
            design = np.column_stack([np.ones(len(x)),x])
            beta = np.linalg.lstsq(design,y,rcond=None)[0]
            self.assertAlmostEqual(model['slope'],beta[1],places=9)
            for i in [0,len(x)//2,len(x)-1]:
                keep = np.arange(len(x)) != i
                deleted = np.linalg.lstsq(design[keep],y[keep],rcond=None)[0]
                errors = y[keep]-design[keep]@deleted
                variance = errors@errors/(len(x)-3)
                h = design[i]@np.linalg.inv(design.T@design)@design[i]
                expected = (y[i]-design[i]@beta)/np.sqrt(variance*(1-h))
                self.assertAlmostEqual(outputs[list(values)[i]]['metrics'][model['subject']]['studentized'],expected,places=8)

    def test_repeat_import_preserves_other_datasets(self):
        db = sqlite3.connect(':memory:');db.row_factory = sqlite3.Row
        self.addCleanup(db.close)
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db,self.payload,EXTRACT)
        tables = ['source','school','economic_observation','assessment_observation']
        before = {t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        import_snapshot(db,self.payload,EXTRACT)
        self.assertEqual(before,{t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0],'Unrelated')


if __name__ == '__main__': unittest.main()
