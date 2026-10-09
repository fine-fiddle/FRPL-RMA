import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from database import connect
from prepare_michigan import EXTRACT, OUTPUT, count, expected_grades, grade_school, native_income, native_outcome, validate
from state_snapshot import import_snapshot


class MichiganTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.snapshots = cls.payload['snapshots']
        cls.outputs = [json.loads((OUTPUT / slug / 'schools.json').read_text())
                       for slug in ['mstep', 'psat8']]

    def test_same_year_individual_income_and_separate_assessment_populations(self):
        self.assertEqual(self.payload['school_year'], '24 - 25 School Year')
        self.assertEqual({s['dataset'] for s in self.snapshots}, {'mi-mstep-2025', 'mi-psat8-2025'})
        for snapshot in self.snapshots:
            validate(snapshot)
            self.assertEqual(snapshot['year'], 2025)
            self.assertEqual(snapshot['state']['id'], 'MI')
            self.assertEqual(len(snapshot['cohorts']), 1)
            self.assertEqual(snapshot['cohorts'][0]['level'], 'ES')
            for school in snapshot['schools']:
                row = school['income_raw']
                self.assertEqual(row['SchoolYear'], '24 - 25 School Year')
                self.assertEqual(row['BuildingCode'], school['id'])
                self.assertEqual(school['enrollment'], int(row['TOTAL_ENROLLMENT']))
                self.assertEqual(school['low_income'], int(row['ECONOMIC_DISADVANTAGED_ENROLLMENT']))
                self.assertEqual(school['income'], 100 * school['low_income'] / school['enrollment'])
                self.assertTrue(grade_school(row))
                self.assertTrue(all(row[f'GRADE_{g}_ENROLLMENT'] == '0' for g in range(9, 13)))
                self.assertEqual(row['UNGRADED_ENROLLMENT'], '0')

    def test_protected_income_never_uses_universal_meals_or_test_subgroups(self):
        row = copy.deepcopy(self.snapshots[0]['schools'][0]['income_raw'])
        for field in ['TOTAL_ENROLLMENT', 'ECONOMIC_DISADVANTAGED_ENROLLMENT']:
            for token in ['<10', '*', '', '10-20', 'nan', True]:
                changed = dict(row, **{field: token})
                self.assertEqual(native_income(changed), (None, None))
        for token in ['<10', '*', '', '-1', '1.0', True, False, None]:
            self.assertIsNone(count(token))
        self.assertEqual(count('0'), 0)
        self.assertEqual(count('10'), 10)

    def test_high_mixed_and_unknown_grade_configuration_is_not_grade_scope(self):
        row = copy.deepcopy(self.snapshots[0]['schools'][0]['income_raw'])
        for field, token in [('GRADE_9_ENROLLMENT', '1'), ('GRADE_12_ENROLLMENT', '<10'),
                             ('UNGRADED_ENROLLMENT', '1'), ('UNGRADED_ENROLLMENT', '<10'),
                             ('SchoolLevel', 'Elem thru High School')]:
            self.assertFalse(grade_school(dict(row, **{field: token})))
        for g in range(1, 9):
            row[f'GRADE_{g}_ENROLLMENT'] = '0'
        for g in [3, 6, 7]:
            row[f'GRADE_{g}_ENROLLMENT'] = '20'
        self.assertEqual(expected_grades(row, 'M-STEP'), ['03', '06', '07'])
        row['GRADE_4_ENROLLMENT'] = '<10'
        self.assertEqual(expected_grades(row, 'M-STEP'), ['03', '04', '06', '07'])
        self.assertEqual(expected_grades(row, 'PSAT'), [])

    def test_exact_income_year_identity_and_normalized_values_are_bound(self):
        for field, value in [('SchoolYear', '23 - 24 School Year'), ('BuildingCode', '99999'),
                             ('DistrictCode', '99999'), ('ECONOMIC_DISADVANTAGED_ENROLLMENT', '<10'),
                             ('GRADE_9_ENROLLMENT', '1')]:
            snapshot = copy.deepcopy(self.snapshots[0])
            snapshot['schools'][0]['income_raw'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(snapshot)
        for field in ['income', 'low_income', 'enrollment']:
            snapshot = copy.deepcopy(self.snapshots[0])
            snapshot['schools'][0][field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(snapshot)
        snapshot = copy.deepcopy(self.snapshots[0])
        snapshot['cohorts'][0]['assessment'] = self.snapshots[1]['cohorts'][0]['assessment']
        with self.assertRaises(ValueError):
            validate(snapshot)
        for mutation in ['eligible', 'methodology', 'coverage']:
            snapshot = copy.deepcopy(self.snapshots[0])
            if mutation == 'eligible':
                snapshot['source_audit']['eligible']['math'] += 1
            elif mutation == 'methodology':
                snapshot['methodology']['summary'] = 'National pooled school ranking'
            else:
                snapshot['coverage_note'] = 'All Michigan schools and assessments are covered.'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(snapshot)

    def test_count_weighted_complete_grades_and_protected_response_guard(self):
        for snapshot, testtype in zip(self.snapshots, ['M-STEP', 'PSAT']):
            for school in snapshot['schools']:
                grades = expected_grades(school['income_raw'], testtype)
                for subject, outcome in school['outcomes'].items():
                    if outcome['proficiency'] is None:
                        continue
                    rows = [item['raw'] for item in outcome['raw']]
                    self.assertEqual(sorted(row['GradeContentTested'] for row in rows), grades)
                    total = sum(int(row['NumberAssessed']) for row in rows)
                    met = sum(int(row['TotalMet']) for row in rows)
                    self.assertEqual(outcome['tested'], total)
                    self.assertEqual(outcome['proficiency'], 100 * met / total)
                    self.assertTrue(outcome['valid_score_evidence'])
            school = next(s for s in snapshot['schools'] if s['outcomes']['math']['proficiency'] is not None)
            grades = expected_grades(school['income_raw'], testtype)
            for token in ['*', '<=5%', '>=95%', '10-20', '']:
                rows = copy.deepcopy(school['outcomes']['math']['raw'])
                rows[0]['raw']['PercentMet'] = token
                # Exact counts do not override the response percentage's mask.
                self.assertIsNone(native_outcome(rows, grades, 'math', testtype)['proficiency'])
            for field in ['TotalMet', 'NumberAssessed']:
                rows = copy.deepcopy(school['outcomes']['math']['raw'])
                rows[0]['raw'][field] = '*'
                self.assertIsNone(native_outcome(rows, grades, 'math', testtype)['proficiency'])
            for mutation in ['missing_grade', 'duplicate_grade', 'subgroup', 'other_assessment', 'wrong_year']:
                changed = copy.deepcopy(snapshot)
                changed_school = next(s for s in changed['schools'] if s['id'] == school['id'])
                rows = changed_school['outcomes']['math']['raw']
                if mutation == 'missing_grade':
                    rows.pop()
                elif mutation == 'duplicate_grade':
                    rows.append(copy.deepcopy(rows[0]))
                elif mutation == 'subgroup':
                    rows[0]['raw']['ReportCategory'] = 'Economically Disadvantaged'
                elif mutation == 'other_assessment':
                    rows[0]['raw']['TestType'] = 'MI-Access'
                else:
                    rows[0]['raw']['SchoolYear'] = '23 - 24 School Year'
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    validate(changed)

    def test_independent_deleted_school_models_and_every_member_intervals(self):
        expected = [dict(math=1532, reading=1662, combined=1520),
                    dict(math=492, reading=593, combined=476)]
        for output, sizes in zip(self.outputs, expected):
            self.assertEqual(set(output['levels']), {'ES'})
            for subject, model in output['models']['ES'].items():
                schools = [s for s in output['schools'] if subject in s['metrics']]
                self.assertEqual(model['n'], sizes[subject])
                self.assertEqual(model['n'], len(schools))
                x = np.array([s['income'] for s in schools])
                y = np.array([s['metrics'][subject]['actual'] for s in schools])
                X = np.column_stack([np.ones(len(x)), x])
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                self.assertAlmostEqual(model['slope'], beta[1], places=9)
                for i in [0, len(x) // 2, len(x) - 1]:
                    keep = np.arange(len(x)) != i
                    deleted = np.linalg.lstsq(X[keep], y[keep], rcond=None)[0]
                    errors = y[keep] - X[keep] @ deleted
                    variance = errors @ errors / (len(x) - 3)
                    leverage = X[i] @ np.linalg.inv(X.T @ X) @ X[i]
                    expected_residual = (y[i] - X[i] @ beta) / np.sqrt(variance * (1 - leverage))
                    self.assertAlmostEqual(schools[i]['metrics'][subject]['studentized'], expected_residual, places=8)
                for school in schools:
                    metric = school['metrics'][subject]
                    self.assertGreaterEqual(metric['tested'], 10)
                    self.assertIsNotNone(metric['low'])
                    self.assertIsNotNone(metric['high'])
            for school in output['schools']:
                if 'combined' in school['metrics']:
                    m = school['metrics']
                    self.assertEqual(m['combined']['actual'], (m['math']['actual'] + m['reading']['actual']) / 2)

    def test_repeat_import_preserves_other_datasets_and_two_model_namespaces(self):
        db = connect(':memory:')
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Keep','Keep','ready')")
        for snapshot in self.snapshots:
            import_snapshot(db, snapshot, EXTRACT)
        tables = ['source', 'school', 'economic_observation', 'assessment_observation']
        before = {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        for snapshot in self.snapshots:
            import_snapshot(db, snapshot, EXTRACT)
        self.assertEqual(before, {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertIsNotNone(db.execute("SELECT * FROM dataset WHERE id='keep'").fetchone())
        overlaps = db.execute('''SELECT COUNT(*) FROM school a JOIN school b USING(school_id)
            WHERE a.dataset_id='mi-mstep-2025' AND b.dataset_id='mi-psat8-2025' ''').fetchone()[0]
        self.assertGreater(overlaps, 0)
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        db.close()


if __name__ == '__main__':
    unittest.main()
