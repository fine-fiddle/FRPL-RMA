import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT, connect
from prepare_ccd_states import EXTRACT, STATES, SLUGS, exact_rate, nces_id, validate_snapshot
from state_snapshot import import_snapshot


class CCDStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.outputs = {state: json.loads((ROOT / 'data' / SLUGS[state] / 'schools.json').read_text())
                       for state in STATES}

    def test_exact_published_rates_and_official_identity_width(self):
        for raw in ['*', '0.2-0.3', '<0.05', '>0.95', '--', '', '-1', 'NaN', '1.01']:
            self.assertIsNone(exact_rate(raw))
        self.assertEqual(exact_rate('.1234'), .1234)
        self.assertEqual(nces_id('20005000023', 'AK'), '020005000023')
        with self.assertRaises(ValueError):
            nces_id('320039000282', 'AK')
        for snapshot in self.payload['states']:
            validate_snapshot(snapshot)
            for school in snapshot['schools']:
                for subject, outcome in school['outcomes'].items():
                    rate = exact_rate(outcome['raw']['ProficientOrAbove_percent'])
                    self.assertEqual(outcome['proficiency'], None if rate is None else 100*rate)
                    self.assertIsNone(outcome['tested'])
                dc = int(school['income_raw']['direct_certification']['STUDENT_COUNT'])
                membership = int(school['income_raw']['membership']['STUDENT_COUNT'])
                self.assertEqual(school['income'], 100*dc/membership)
                self.assertEqual(school['income_raw']['membership']['DMS_FLAG'], 'Reported')
                self.assertEqual(school['income_raw']['direct_certification']['DMS_FLAG'], 'Reported')
                self.assertEqual(sum(int(r['STUDENT_COUNT']) for r in school['membership_grades_raw'].values()), membership)

    def test_point_only_outputs_and_independent_deleted_school_models(self):
        expected = dict(AK=189, GA=1714, LA=834, ME=374, NM=534, NV=511, RI=214, TN=1297)
        for state, output in self.outputs.items():
            self.assertEqual(output['models']['ES']['combined']['n'], expected[state])
            self.assertEqual(set(output['levels']), {'ES'})
            for school in output['schools']:
                self.assertEqual(school['level'], 'ES')
                for metric in school['metrics'].values():
                    self.assertIsNone(metric['tested'])
                    self.assertIsNone(metric['low'])
                    self.assertIsNone(metric['high'])
                if 'combined' in school['metrics']:
                    self.assertEqual(school['metrics']['combined']['actual'],
                        (school['metrics']['math']['actual'] + school['metrics']['reading']['actual'])/2)
            for subject, model in output['models']['ES'].items():
                schools = [s for s in output['schools'] if subject in s['metrics']]
                x = np.array([s['income'] for s in schools])
                y = np.array([s['metrics'][subject]['actual'] for s in schools])
                X = np.column_stack([np.ones(len(x)), x])
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                self.assertEqual(model['n'], len(schools))
                self.assertAlmostEqual(model['slope'], beta[1], places=9)
                for i in [0, len(x)//2, len(x)-1]:
                    keep = np.arange(len(x)) != i
                    deleted = np.linalg.lstsq(X[keep], y[keep], rcond=None)[0]
                    errors = y[keep] - X[keep]@deleted
                    variance = errors@errors / (len(x)-3)
                    leverage = X[i] @ np.linalg.inv(X.T@X) @ X[i]
                    t = (y[i] - X[i]@beta) / np.sqrt(variance*(1-leverage))
                    self.assertAlmostEqual(schools[i]['metrics'][subject]['studentized'], t, places=8)

    def test_raw_tested_never_becomes_a_model_weight_or_interval(self):
        for snapshot in self.payload['states']:
            bad = copy.deepcopy(snapshot)
            bad['schools'][0]['outcomes']['math']['raw_tested'] = '999999999'
            bad['schools'][0]['outcomes']['math']['raw']['StudentSubGroup_TotalTested'] = '999999999'
            validate_snapshot(bad)  # Raw provenance is not a model denominator.
            bad['schools'][0]['outcomes']['math']['tested'] = 100
            bad['schools'][0]['outcomes']['math']['valid_score_evidence'] = 'Fabricated'
            with self.assertRaises(ValueError):
                validate_snapshot(bad)

    def test_invalid_scope_or_reconstructed_suppression_rejected(self):
        for change in ['year', 'grade', 'income_flag', 'income_year', 'income_scope', 'native_grade', 'rate']:
            bad = copy.deepcopy(self.payload['states'][0])
            school = bad['schools'][0]
            if change == 'year':
                bad['year'] = 2024
            elif change == 'grade':
                school['directory_raw']['G_9_OFFERED'] = 'Yes'
            elif change == 'income_flag':
                school['income_raw']['direct_certification']['DMS_FLAG'] = 'Missing'
            elif change == 'income_year':
                school['income_raw']['direct_certification']['SCHOOL_YEAR'] = '2023-2024'
            elif change == 'income_scope':
                school['membership_grades_raw']['Ungraded'] = {'STUDENT_COUNT': '1', 'DMS_FLAG': 'Reported'}
            elif change == 'native_grade':
                school['outcomes']['math']['raw']['GradeLevel'] = 'G03'
            else:
                school['outcomes']['math']['raw']['ProficientOrAbove_percent'] = '*'
                school['outcomes']['math']['proficiency'] = 50
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_snapshot(bad)
        ri = next(s for s in self.payload['states'] if s['state']['id']=='RI')
        self.assertFalse(any(s['district_id']=='4400150' for s in ri['schools']))

    def test_cohort_metadata_cannot_relabel_approved_grade_population(self):
        changes = dict(id='high', level='HS', grades='9–12',
            assessment='2024 alternate high-school total', standard='Different threshold',
            source='ccd_lunch_2025', source_url='https://example.invalid/', allow_point_only=False)
        for field, value in changes.items():
            with self.subTest(field=field):
                bad = copy.deepcopy(self.payload['states'][0])
                bad['cohorts'][0][field] = value
                with self.assertRaisesRegex(ValueError, 'approved 2025 ES native G38 cohort'):
                    validate_snapshot(bad)

    def test_metadata_and_provenance_require_approved_state_year_release(self):
        mutations = {
            'region': lambda p: p.update(region='georgia'),
            'state_name': lambda p: p['state'].update(name='Georgia'),
            'audit_year': lambda p: p['source_audit'].update(school_year='2023-24'),
            'audit_threshold': lambda p: p['source_audit'].update(proficiency_criteria='Levels 4-5'),
            'edc_year': lambda p: p['sources']['edc_2025'].update(
                url='https://www.eddatacenter.org/api/data/3.1?state=AK&year=2024'),
            'lunch_release': lambda p: p['sources']['ccd_lunch_2025'].update(
                path='data/raw/ccd_sch_033_2425_l_1a_073025.zip'),
            'membership_year': lambda p: p['sources']['ccd_membership_2025'].update(
                url='https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2324_l_1a.zip'),
            'income_source': lambda p: p['schools'][0].update(income_source='edc_2025'),
            'outcome_source': lambda p: p['schools'][0]['outcomes']['math'].update(source='ccd_lunch_2025'),
        }
        for name, mutate in mutations.items():
            with self.subTest(change=name):
                bad = copy.deepcopy(self.payload['states'][0])
                mutate(bad)
                with self.assertRaises(ValueError):
                    validate_snapshot(bad)

    def test_repeat_import_preserves_other_datasets_and_never_stores_tested(self):
        db = connect(':memory:')
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        for snapshot in self.payload['states']:
            import_snapshot(db, snapshot, EXTRACT)
        before = {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')]
                  for t in ['source', 'school', 'economic_observation', 'assessment_observation']}
        for snapshot in self.payload['states']:
            import_snapshot(db, snapshot, EXTRACT)
        self.assertEqual(before, {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')]
                  for t in before})
        self.assertFalse(db.execute('SELECT * FROM assessment_observation WHERE tested IS NOT NULL').fetchall())
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0], 'Unrelated')
        db.close()


if __name__ == '__main__':
    unittest.main()
