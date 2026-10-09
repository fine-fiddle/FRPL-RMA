import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_minnesota import (DOCUMENTARY, EXTRACT, INCOME_COUNT, INCOME_FLAG,
    income, normalize, outcome, profile_cohort, school_id)
from state_snapshot import import_snapshot


class MinnesotaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(EXTRACT.read_text())
        cls.payload = normalize(cls.raw)
        cls.output = json.loads((ROOT / 'data/minnesota/schools.json').read_text())
        cls.profiles = {p['id']: p for p in cls.raw['profiles']}
        cls.complete = next(s for s in cls.payload['schools'] if s['income'] is not None and
            all(o['proficiency'] is not None for o in s['outcomes'].values()))

    def test_authoritative_three_component_same_year_identity(self):
        self.assertEqual(school_id({'District Number': 1, 'District Type': 1, 'School Number': 2}), '0001-01-002')
        self.assertNotEqual(school_id({'District Number': 1, 'District Type': 1, 'School Number': 2}),
                            school_id({'District Number': 1, 'District Type': 3, 'School Number': 2}))
        for value in [True, 1.5, 'A01', '0000']:
            with self.assertRaises(ValueError):
                school_id({'District Number': value, 'District Type': 1, 'School Number': 2})
        for field, value in [('Data Year', '23-24'), ('District Type', '04')]:
            bad = copy.deepcopy(self.raw)
            bad['profiles'][0]['rows'][0]['raw'][field] = value
            with self.assertRaises(ValueError): normalize(bad)

    def test_complete_grades_and_no_mixed_populations(self):
        self.assertEqual(len(self.raw['profiles']), 2431)
        self.assertEqual(len(self.payload['schools']), 1776)
        self.assertEqual(sum(s['cohort'] == 'grade' for s in self.payload['schools']), 1275)
        self.assertEqual(sum(s['cohort'] == 'high' for s in self.payload['schools']), 501)
        for s in self.payload['schools']:
            rows = self.profiles[s['id']]['rows']
            expected, _ = profile_cohort(rows)
            self.assertEqual(expected, s['cohort'])
            grades = {int(e['raw']['Grade']) for e in rows if e['raw']['Grade'].isdigit() and e['raw']['Total Enrollment'] > 0}
            self.assertFalse(grades & set(range(9, 13)) if expected == 'grade' else grades & set(range(3, 9)))
            if expected == 'high':
                self.assertTrue(all(e['raw']['Grade'] in ['All Grades', '9', '10', '11', '12'] or e['raw']['Total Enrollment'] == 0 for e in rows))
        bad = copy.deepcopy(self.profiles[self.complete['id']]['rows'])
        next(e for e in bad if e['raw']['Grade'] != 'All Grades')['raw']['Total Enrollment'] = None
        self.assertIsNone(profile_cohort(bad)[0])
        self.assertEqual(self.payload['source_audit']['exclusions']['Mixed tested grade-school and high-school enrollment'], 417)
        self.assertEqual(self.payload['source_audit']['exclusions']['Native test grades establish mixed scope beyond fall grade profile'], 22)
        self.assertEqual(self.payload['source_audit']['exclusions']['High-school ID shares primary or early-childhood enrollment'], 1)
        tribal = [p for p in self.raw['profiles'] if p['id'].split('-')[1] == '34']
        self.assertEqual(len(tribal), 4)
        self.assertEqual(self.payload['source_audit']['exclusions']['Tribal/BIE District Type 34 outside state-public jurisdiction'], 4)
        self.assertFalse(any(s['id'].split('-')[1] == '34' for s in self.payload['schools']))
        high = next(s for s in self.payload['schools'] if s['cohort'] == 'high')
        for grade in ['ECSE', 'PK', 'KG', '1', '2']:
            rows = copy.deepcopy(self.profiles[high['id']]['rows'])
            total = next(e for e in rows if e['raw']['Grade'] == 'All Grades')
            total['raw']['Total Enrollment'] += 1
            extra = copy.deepcopy(total); extra['raw'].update(Grade=grade)
            extra['raw']['Total Enrollment'] = 1
            rows.append(extra)
            self.assertIsNone(profile_cohort(rows)[0])

    def test_native_school_totals_use_published_valid_counts(self):
        for s in self.payload['schools']:
            for subject, o in s['outcomes'].items():
                if o['proficiency'] is None: continue
                r = o['raw']; n = r['Total Tested']
                self.assertEqual(r['Grade'], 0)
                self.assertEqual(o['tested'], n)
                self.assertAlmostEqual(o['proficiency'], 100 * (r['Count Level M'] + r['Count Level E']) / n)
                self.assertEqual(n, r['Count Valid Scores MCA'] + r['Count Valid Scores MTAS'])
                self.assertIn('valid score', o['valid_score_evidence'])
        for subject in ['math', 'reading']:
            definition = dict(self.raw['metadata'][subject]['definitions'][1:])
            self.assertEqual(definition['Total Tested'], 'Number of students receiving a valid score.')
        self.assertIn('School Year 2024–25', DOCUMENTARY['alternate_application_2024_25']['verified'])

    def test_component_suppression_never_uses_complements(self):
        entry = dict(raw=copy.deepcopy(self.complete['outcomes']['math']['raw']), source_row=1)
        entry['raw']['Count Level M'] = None
        self.assertIsNone(outcome(entry, 'math')['proficiency'])
        self.assertIsNone(outcome(entry, 'math')['tested'])
        entry['raw']['Count Level M'] = 0
        entry['raw']['Count Level E'] = 0
        entry['raw']['Count Level D'] = entry['raw']['Total Tested']
        entry['raw']['Count Level P'] = 0
        entry['raw']['Percent Proficient'] = 0
        self.assertEqual(outcome(entry, 'math')['proficiency'], 0)
        entry['raw']['Filter All'] = 'Y'
        self.assertIsNone(outcome(entry, 'math')['proficiency'])
        entry['raw']['Filter All'] = 'N'
        entry['raw']['Count Valid Scores MCA'] += 1
        with self.assertRaises(ValueError): outcome(entry, 'math')

    def test_individual_income_and_all_native_privacy_flags(self):
        for s in self.payload['schools']:
            if s['income'] is not None:
                self.assertAlmostEqual(s['income'], 100*s['low_income']/s['enrollment'])
                self.assertEqual(s['income_raw']['total']['raw'][INCOME_FLAG], 'N')
        r = copy.deepcopy(self.complete['income_raw']['total']['raw'])
        r[INCOME_COUNT] = None
        self.assertIsNone(income(r)[2])
        r[INCOME_COUNT] = 0
        r['Total Students Eligible for Free or Reduced Priced Meals Percent'] = '0.00%'
        self.assertEqual(income(r)[2], 0)
        for flag in ['Filter Groups', INCOME_FLAG]:
            bad = dict(r); bad[flag] = 'Y'
            self.assertIsNone(income(bad)[2])
        bad = copy.deepcopy(self.raw); bad['documentary_evidence'] = {}
        with self.assertRaises(ValueError): normalize(bad)
        self.assertIn('actual eligibility', DOCUMENTARY['cep_guidance']['verified'])

    def test_duplicate_or_contrary_assessment_identity_rejected(self):
        for mutation in ['duplicate', 'year', 'native_grade']:
            bad = copy.deepcopy(self.raw)
            if mutation == 'duplicate': bad['assessments']['math'].append(bad['assessments']['math'][0])
            elif mutation == 'year': bad['assessments']['math'][0]['raw']['Data Year'] = '25-26'
            else: bad['assessments']['math'][0]['raw']['Grade'] = 9
            with self.assertRaises(ValueError): normalize(bad)

    def test_independent_deleted_school_models_and_interval_propagation(self):
        outputs = {s['id']: s for s in self.output['schools']}
        expected = {'ES': {'math':1129, 'reading':1128, 'combined':1128},
                    'HS': {'math':266, 'reading':240, 'combined':235}}
        for model in self.output['history_models']:
            values = {}
            for s in self.payload['schools']:
                if s['cohort'] != ('grade' if model['level'] == 'ES' else 'high') or s['income'] is None: continue
                metrics = s['outcomes']; rates = {k:o['proficiency'] for k,o in metrics.items()}
                variances = {}
                for subject, o in metrics.items():
                    if o['proficiency'] is None: continue
                    n = o['tested']; p = (o['proficiency']/100*n+.5)/(n+1)
                    variances[subject] = 10000*p*(1-p)/n
                if all(v is not None for v in rates.values()):
                    rates['combined'] = (rates['math']+rates['reading'])/2
                    variances['combined'] = (np.sqrt(variances['math'])+np.sqrt(variances['reading']))**2/4
                if rates.get(model['subject']) is not None:
                    values[s['id']] = (s['income'],rates[model['subject']],variances[model['subject']])
            self.assertEqual(model['n'],expected[model['level']][model['subject']])
            keys = list(values); x,y,v = np.array(list(values.values())).T
            design = np.column_stack([np.ones(len(x)),x]); beta = np.linalg.lstsq(design,y,rcond=None)[0]
            self.assertAlmostEqual(model['slope'],beta[1],places=9)
            inv = np.linalg.inv(design.T@design)
            for i in [0,len(x)//2,len(x)-1]:
                keep = np.arange(len(x)) != i
                deleted = np.linalg.lstsq(design[keep],y[keep],rcond=None)[0]
                errors = y[keep]-design[keep]@deleted
                variance = errors@errors/(len(x)-3)
                hatrow = design[i]@inv@design.T; denominator = np.sqrt(variance*(1-hatrow[i]))
                expected_t = (y[i]-design[i]@beta)/denominator
                residual_row = -hatrow; residual_row[i] += 1
                expected_se = np.sqrt((residual_row**2)@v)/denominator
                metric = outputs[keys[i]]['metrics'][model['subject']]
                self.assertAlmostEqual(metric['studentized'],expected_t,places=8)
                self.assertAlmostEqual(metric['low'],expected_t-1.96*expected_se,places=8)
                self.assertAlmostEqual(metric['high'],expected_t+1.96*expected_se,places=8)

    def test_repeat_import_preserves_other_datasets(self):
        db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
        self.addCleanup(db.close)
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db,self.payload,EXTRACT)
        tables = ['dataset','source','school','economic_definition','economic_observation','assessment_definition','assessment_observation']
        before = {t:sorted([tuple(r) for r in db.execute(f'SELECT * FROM {t}')],key=repr) for t in tables}
        import_snapshot(db,self.payload,EXTRACT)
        self.assertEqual(before,{t:sorted([tuple(r) for r in db.execute(f'SELECT * FROM {t}')],key=repr) for t in tables})
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0],'Unrelated')


if __name__ == '__main__': unittest.main()
