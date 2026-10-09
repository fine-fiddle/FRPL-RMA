import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_new_york import EXTRACT, GRADE_FIELDS, cohort, count, identity, income, outcome
from database import connect
from state_snapshot import import_snapshot


class NewYorkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.outputs = {band: json.loads((ROOT / 'data' / path / 'schools.json').read_text())
            for band, path in [('grade', 'new-york'), ('mixed', 'new-york-mixed')]}

    def test_native_valid_scores_are_distinct_from_participation(self):
        row = {'NUM_TESTED': '80', 'NUM_PROF': '40', 'PER_PROF': '50', 'TOTAL_COUNT': '100'}
        self.assertEqual(outcome(row, 'math')['proficiency'], 50)
        self.assertEqual(outcome(row, 'math')['tested'], 80)
        row['NUM_PROF'] = 's'
        self.assertIsNone(outcome(row, 'math')['proficiency'])
        for token in ['s', '', '<5', '-9']:
            self.assertIsNone(count(token))
        row.update(NUM_PROF='40', PER_PROF='40')
        with self.assertRaises(ValueError):
            outcome(row, 'math')

    def test_individual_income_and_explicit_grade_scope(self):
        self.assertEqual(income({'NUM_ECDIS': '30', 'PER_ECDIS': '33'}, 90), (100/3, 30))
        self.assertEqual(income({'NUM_ECDIS': '', 'PER_ECDIS': '0'}, 90), (None, None))
        row = {g: '0' for g in GRADE_FIELDS}
        row.update({'3': '90', 'K12': '90'})
        self.assertEqual(cohort(row), 'grade')
        row.update({'UGS': '10', 'K12': '100'})
        self.assertEqual(cohort(row), 'mixed')
        row['UGS'] = 's'
        self.assertIsNone(cohort(row))
        with self.assertRaises(ValueError):
            identity({'ENTITY_CD': '10100010014'})

    def test_exports_use_exact_native_totals_and_same_year_identity(self):
        profiles = {s['id']: s for s in self.payload['schools']}
        with_regents = 0
        with_nonparticipants = 0
        for band, output in self.outputs.items():
            for school in output['schools']:
                p = profiles[school['id']]
                self.assertEqual(p['cohort'], band)
                self.assertEqual(school['id'], identity(p['directory_raw']))
                for row in [p['directory_raw'], p['grades_raw'], p['income_raw']]:
                    self.assertEqual(row['YEAR'], '2025')
                    self.assertEqual(identity(row), school['id'])
                self.assertEqual(school['income'], income(p['income_raw'], school['enrollment'])[0])
                for subject in ['math', 'reading']:
                    metric = school['metrics'].get(subject)
                    if not metric:
                        continue
                    raw = p['outcomes'][subject]['raw']
                    self.assertEqual(raw['ASSESSMENT_NAME'], 'MATH3_8' if subject == 'math' else 'ELA3_8')
                    self.assertEqual(raw['SUBGROUP_NAME'], 'All Students')
                    self.assertEqual(metric['actual'], 100 * int(raw['NUM_PROF']) / int(raw['NUM_TESTED']))
                    self.assertEqual(metric['tested'], int(raw['NUM_TESTED']))
                    self.assertIsNotNone(metric['low'])
                    with_nonparticipants += int(raw['TOTAL_COUNT']) > metric['tested']
                    with_regents += subject == 'math' and (count(raw['LEVEL5_COUNT']) or 0) > 0
                if school['metrics'].get('combined'):
                    self.assertEqual(school['metrics']['combined']['actual'],
                        (school['metrics']['math']['actual'] + school['metrics']['reading']['actual']) / 2)
        self.assertGreater(with_nonparticipants, 500)
        self.assertGreater(with_regents, 100)

    def test_separate_models_match_independent_deleted_school_fits(self):
        expected = {'grade': {'math': 2506, 'reading': 2573, 'combined': 2505},
                    'mixed': {'math': 797, 'reading': 940, 'combined': 797}}
        for band, output in self.outputs.items():
            models = output['models']['ES' if band == 'grade' else 'HS']
            for subject, model in models.items():
                self.assertEqual(model['n'], expected[band][subject])
                schools = [s for s in output['schools'] if subject in s['metrics']]
                X = np.column_stack([np.ones(len(schools)), [s['income'] for s in schools]])
                y = np.array([s['metrics'][subject]['actual'] for s in schools])
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                np.testing.assert_allclose([model['intercept'], model['slope']], beta, atol=1e-10)
                for i in [0, len(schools)//2, len(schools)-1]:
                    keep = np.arange(len(schools)) != i
                    deleted_beta = np.linalg.lstsq(X[keep], y[keep], rcond=None)[0]
                    errors = y[keep] - X[keep] @ deleted_beta
                    h = X[i] @ np.linalg.inv(X.T @ X) @ X[i]
                    t = (y[i] - X[i] @ beta) / np.sqrt((errors @ errors / (len(schools)-3)) * (1-h))
                    self.assertAlmostEqual(schools[i]['metrics'][subject]['studentized'], t, places=8)

    def test_repeat_import_and_dataset_identity_guard(self):
        db = connect(':memory:')
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        payload = dict(self.payload, dataset='ny-test', name='NY test', model_scope='Separate grade schools',
            cohorts=[dict(id='grade', level='ES', assessment='NY native', grades='3–8',
                standard='Native totals', source_url='https://data.nysed.gov/', source='assessment')],
            schools=[s for s in self.payload['schools'] if s['cohort'] == 'grade'])
        db.execute("INSERT INTO dataset VALUES ('keep', 'IL', 'Keep', 'Keep', 'ready')")
        import_snapshot(db, payload, EXTRACT)
        before = {t: db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in
            ['school', 'economic_observation', 'assessment_observation', 'source']}
        import_snapshot(db, payload, EXTRACT)
        self.assertEqual(before, {t: db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in before})
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        invalid = copy.deepcopy(payload)
        invalid['state']['id'] = 'NJ'
        with self.assertRaises(ValueError):
            import_snapshot(db, invalid, EXTRACT)
        self.assertEqual(db.execute("SELECT count(*) FROM dataset WHERE id='keep'").fetchone()[0], 1)
        db.close()


if __name__ == '__main__':
    unittest.main()
