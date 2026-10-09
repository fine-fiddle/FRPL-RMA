import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT, connect
from prepare_north_carolina import EXTRACT, OUTPUT, validate, exact_percent, agency_id
from state_snapshot import import_snapshot


class NorthCarolinaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((OUTPUT/'schools.json').read_text())

    def test_native_point_rates_and_april_individual_income(self):
        validate(self.payload)
        self.assertEqual(agency_id('NC-010-303'), '010303')
        self.assertEqual(agency_id('NC-13C-000'), '13C000')
        for value in ['*', '<5', '>95', '0*', '', '-', 'NaN', '20-30']:
            self.assertIsNone(exact_percent(value))
        self.assertEqual(exact_percent('5'), 5)
        for school in self.payload['schools']:
            self.assertEqual(school['income'], float(school['income_raw']['pct_eds']))
            self.assertEqual(school['enrollment'], int(school['income_raw']['den']))
            self.assertIsNone(school['low_income'])
            for outcome in school['outcomes'].values():
                self.assertIsNone(outcome['tested'])
                self.assertEqual(outcome['proficiency'], exact_percent(outcome['raw']['pct_glp']))

    def test_general_alt_and_accountability_population_cannot_be_substituted(self):
        for change in ['alt', 'all', 'grade', 'mixed', 'subject', 'income_year', 'income_collection', 'income_proxy', 'income_count', 'nces_id']:
            payload = copy.deepcopy(self.payload)
            school = payload['schools'][0]
            row = school['outcomes']['math']['raw']
            if change == 'alt': row['type'] = 'X1'
            elif change == 'all': row['type'] = 'ALL'
            elif change == 'grade': row['grade'] = '03'
            elif change == 'mixed': row['grade_span'] = '0K-12'
            elif change == 'subject': row['subject'] = 'EOG'
            elif change == 'income_year': school['income_raw']['reporting_year'] = '2024'
            elif change == 'income_collection': school['income_raw']['collection_code'] = 'DEC'
            elif change == 'income_proxy': school['income'] = float(school['income_raw']['pct_nslp_adj'])
            elif change == 'income_count': school['low_income'] = 100
            else: school['membership_raw']['NCESSCH'] = '999999999999'
            with self.subTest(change=change), self.assertRaises(ValueError): validate(payload)

    def test_no_reconstructed_suppression_or_unverified_counts(self):
        for change in ['rate', 'count']:
            payload = copy.deepcopy(self.payload)
            outcome = payload['schools'][0]['outcomes']['math']
            if change == 'rate': outcome['raw']['pct_glp'] = '<5'; outcome['proficiency'] = 5
            else: outcome['tested'] = int(outcome['raw_tested']); outcome['valid_score_evidence'] = 'Not audited'
            with self.subTest(change=change), self.assertRaises(ValueError): validate(payload)
        self.assertFalse(any(m['tested'] is not None or m['low'] is not None or m['high'] is not None
            for s in self.output['schools'] for m in s['metrics'].values()))

    def test_independent_deleted_school_models(self):
        self.assertEqual(set(self.output['levels']), {'ES'})
        for subject, model in self.output['models']['ES'].items():
            schools = [s for s in self.output['schools'] if subject in s['metrics']]
            x = np.array([s['income'] for s in schools]); y = np.array([s['metrics'][subject]['actual'] for s in schools])
            X = np.column_stack([np.ones(len(x)), x]); beta = np.linalg.lstsq(X, y, rcond=None)[0]
            self.assertEqual(model['n'], len(schools)); self.assertAlmostEqual(model['slope'], beta[1], places=9)
            for i in [0, len(x)//2, len(x)-1]:
                keep = np.arange(len(x)) != i; deleted = np.linalg.lstsq(X[keep], y[keep], rcond=None)[0]
                errors = y[keep] - X[keep]@deleted; variance = errors@errors/(len(x)-3)
                leverage = X[i]@np.linalg.inv(X.T@X)@X[i]
                t = (y[i] - X[i]@beta)/np.sqrt(variance*(1-leverage))
                self.assertAlmostEqual(schools[i]['metrics'][subject]['studentized'], t, places=8)
        for school in self.output['schools']:
            if 'combined' in school['metrics']:
                self.assertEqual(school['metrics']['combined']['actual'],
                    (school['metrics']['math']['actual']+school['metrics']['reading']['actual'])/2)

    def test_repeat_import_preserves_other_datasets(self):
        db = connect(':memory:'); db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_snapshot(db, self.payload, EXTRACT)
        before = {t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')]
                  for t in ['source', 'school', 'economic_observation', 'assessment_observation']}
        import_snapshot(db, self.payload, EXTRACT)
        self.assertEqual(before, {t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in before})
        self.assertIsNotNone(db.execute("SELECT * FROM dataset WHERE id='keep'").fetchone())
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        db.close()


if __name__ == '__main__': unittest.main()
