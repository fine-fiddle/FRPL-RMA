import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_south_carolina import EXTRACT, count, income, normalize, outcome, school_id
from state_snapshot import import_snapshot


class SouthCarolinaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(EXTRACT.read_text())
        cls.payload = normalize(cls.raw)
        cls.output = json.loads((ROOT / 'data/south-carolina/schools.json').read_text())
        cls.complete = next(p for p in cls.raw['profiles'] if p['id'] == '0160019')

    def test_actual_scored_fraction_and_protected_bin_preservation(self):
        row = copy.deepcopy(self.complete['records'][0])
        self.assertEqual(outcome(row, 'E')[:2], (100 * 87 / 123, 123))
        self.assertEqual(row['E_NbrTOT'], 124)
        self.assertEqual(row['E_NbrNotTest'], 1)
        self.assertNotEqual(outcome(row, 'E')[0], row['E_PctME'])
        row['E_NbrNotTest'] = '*'
        self.assertEqual(outcome(row, 'E')[:2], (100 * 87 / 123, 123))
        self.assertEqual(row['E_NbrNotTest'], '*')
        row['E_NbrInNeedOfSupport'] = '*'
        self.assertIsNone(outcome(row, 'E')[0])
        for value in ['*', '***', '', '<10', '10-19', None]:self.assertIsNone(count(value))
        self.assertEqual(count(0), 0)
        for value in ['20', -1, 11.5, True]:
            with self.assertRaises(ValueError):count(value)
        row = copy.deepcopy(self.complete['records'][0])
        row['E_NbrME'] += 1
        with self.assertRaises(ValueError):outcome(row, 'E')
        for p in self.payload['schools']:
            for subject, o in p['outcomes'].items():
                if o['tested'] is not None:
                    prefix = 'M' if subject == 'math' else 'E'
                    valid = sum(o['raw'][prefix + '_' + f] for f in ['NbrExceeding','NbrReady','NbrClose','NbrInNeedOfSupport'])
                    self.assertEqual(o['tested'], valid)
                    self.assertAlmostEqual(o['proficiency'], 100 * o['raw'][prefix + '_NbrME'] / valid)
                    self.assertTrue(o['valid_score_evidence'])

    def test_individual_same_day_income_reconciles_identity(self):
        p = copy.deepcopy(self.complete)
        n, low, pct, reason = income(p)
        self.assertEqual((n, low), (251, 176))
        self.assertAlmostEqual(pct, 100 * low / n)
        self.assertIsNone(reason)
        self.assertEqual(school_id(160019), '0160019')
        with self.assertRaises(ValueError):school_id('160019')
        p['income_record'][15] = n + 1
        self.assertIsNone(income(p)[2])
        p = copy.deepcopy(self.complete)
        p['income_record'][3] += 1
        self.assertIsNone(income(p)[2])
        p = copy.deepcopy(self.complete)
        p['income_record'][0] = '0160020'
        with self.assertRaises(ValueError):income(p)
        p = copy.deepcopy(self.raw)
        p['income_headers'][1][0] = '2023–2024 135-Day Headcount'
        with self.assertRaises(ValueError):normalize(p)
        self.assertEqual(self.payload['source_audit']['income_unavailable'], 9)
        self.assertIn('three years', self.payload['income_definition']['definition'])

    def test_fay_general_alternate_scope_and_no_band_combination(self):
        self.assertEqual(len(self.payload['schools']), 831)
        self.assertEqual(self.payload['source_audit']['excluded']['Separate E/M report cards require complete grade-band union audit'], 64)
        self.assertNotIn('0601003', {p['id'] for p in self.payload['schools']})
        self.assertEqual(len(next(p for p in self.raw['profiles'] if p['id'] == '0601003')['records']), 2)
        self.assertIn('SC READY + SC-Alt', self.payload['cohorts'][0]['assessment'])
        self.assertIn('day45 through day160', self.payload['cohorts'][0]['standard'])
        p = copy.deepcopy(self.raw)
        p['profiles'][0]['records'][0]['ReportCardYear'] = 2024
        with self.assertRaises(ValueError):normalize(p)
        p = copy.deepcopy(self.raw)
        p['profiles'][0]['records'].append(copy.deepcopy(p['profiles'][0]['records'][0]))
        with self.assertRaises(ValueError):normalize(p)
        for p in self.payload['schools']:
            self.assertTrue(all(p['directory_raw'][f'G_{g}_OFFERED'] == 'No' for g in range(9,14)))
        for p in self.output['schools']:
            self.assertEqual(p['level'], 'ES')
            self.assertEqual(p['history'][0]['income_year'], 2025)
            self.assertIsNone(p['latitude'])
            for metric in p['metrics'].values():
                self.assertIsNotNone(metric['low'])
                self.assertIsNotNone(metric['high'])

    def test_models_against_independent_deleted_school_regressions(self):
        profiles = {p['id']:p for p in self.payload['schools']}
        schools = {p['id']:p for p in self.output['schools']}
        for model in self.output['history_models']:
            expected = {}
            for key, p in profiles.items():
                rates = {s:o['proficiency'] for s,o in p['outcomes'].items()}
                if all(v is not None for v in rates.values()):rates['combined'] = (rates['math']+rates['reading'])/2
                if p['income'] is not None and rates.get(model['subject']) is not None:expected[key] = (p['income'], rates[model['subject']])
            self.assertEqual(model['n'], len(expected))
            self.assertEqual(model['n'], dict(math=819,reading=821,combined=818)[model['subject']])
            x,y = np.array(list(expected.values())).T
            design = np.column_stack([np.ones(len(x)),x]);beta = np.linalg.lstsq(design,y,rcond=None)[0]
            self.assertAlmostEqual(model['slope'], beta[1], places=9)
            for i in [0,len(x)//2,len(x)-1]:
                keep = np.arange(len(x)) != i
                deleted = np.linalg.lstsq(design[keep],y[keep],rcond=None)[0]
                errors = y[keep]-design[keep]@deleted;variance = errors@errors/(len(x)-3)
                h = design[i]@np.linalg.inv(design.T@design)@design[i]
                value = (y[i]-design[i]@beta)/np.sqrt(variance*(1-h))
                self.assertAlmostEqual(schools[list(expected)[i]]['metrics'][model['subject']]['studentized'],value,places=8)

    def test_repeat_import_preserves_unrelated_records(self):
        db = sqlite3.connect(':memory:');db.row_factory = sqlite3.Row
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db,self.payload,EXTRACT)
        tables = ['source','school','economic_observation','assessment_observation']
        before = {t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        import_snapshot(db,self.payload,EXTRACT)
        self.assertEqual(before,{t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0],'Unrelated')
        db.close()


if __name__ == '__main__':unittest.main()
