import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_los_angeles_models as audit


class LosAngelesModelAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = audit.load_roster()
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.expected = audit.build(cls.roster)

    def test_six_independent_pure_district_cohorts_replay(self):
        counts = audit.validate(self.document, self.expected)
        self.assertFalse(self.document['hard_holds'])
        self.assertEqual(sorted(counts.values()), [136, 137, 137, 561, 561, 561])
        self.assertFalse(self.document['approved_for_modeling'])
        self.assertNotIn('snapshots', self.document)
        pure = {r['school_id']: r for r in self.roster['roster_links'] if r.get('scope') in ['ES', 'HS']}
        mixed = {r['school_id'] for r in self.roster['roster_links'] if r.get('scope') == 'mixed'}
        for model in self.document['models']:
            inputs = model['inputs']
            self.assertEqual(len(inputs), model['coefficients']['n'])
            self.assertEqual(model['diagnostics']['income_design_rank'], 2)
            self.assertTrue(model['intervals']['available_for_entire_model'])
            self.assertEqual(model['independent_verification']['explicit_deleted_fits'], len(inputs))
            self.assertFalse({r['school_id'] for r in inputs}.intersection(mixed))
            self.assertTrue(all(pure[r['school_id']]['scope'] == model['level'] for r in inputs))
            self.assertTrue(all(r['income_year'] == 2025 for r in inputs))
            self.assertEqual(model['coverage']['charter']['Yes'], 45 if model['level'] == 'ES' else 5)
            self.assertIn('Alternative School', model['coverage']['school_types'])
            self.assertTrue(all(v < audit.VERIFY_TOLERANCE for v in model['independent_verification']['maximum_absolute_errors'].values()))

    def test_external_studentization_matches_explicit_held_out_prediction(self):
        for model in self.document['models']:
            x = np.array([r['income_pct'] for r in model['inputs']])
            y = np.array([r['outcome_pct'] for r in model['inputs']])
            n = len(x)
            results = model['results']
            indices = {0, n - 1, max(range(n), key=lambda i: results[i]['leverage']),
                       max(range(n), key=lambda i: abs(results[i]['studentized']))}
            for i in indices:
                keep = np.arange(n) != i
                center = x[keep].mean()
                X = np.column_stack([np.ones(n - 1), x[keep] - center])
                b = np.linalg.lstsq(X, y[keep], rcond=None)[0]
                residual = y[keep] - X @ b
                scale = math.sqrt(float(residual @ residual) / (n - 3))
                held_out = np.array([1., x[i] - center])
                prediction_variance_factor = float(held_out @ np.linalg.inv(X.T @ X) @ held_out)
                independent = (y[i] - held_out @ b) / (scale * math.sqrt(1 + prediction_variance_factor))
                with self.subTest(model=model['model_id'], school=results[i]['school_id']):
                    self.assertAlmostEqual(independent, results[i]['studentized'], delta=2e-10)

    def test_intervals_propagate_every_member_and_combined_subject_variances(self):
        for model in self.document['models']:
            inputs, results = model['inputs'], model['results']
            x = np.array([r['income_pct'] for r in inputs])
            v = np.array([r['sampling_variance'] for r in inputs])
            X = np.column_stack([np.ones(len(x)), x - x.mean()])
            H = X @ np.linalg.pinv(X)
            A = np.eye(len(x)) - H
            propagated = np.einsum('ij,j,ij->i', A, v, A)
            denom = np.sqrt(np.array([r['deleted_sse'] for r in results]) / (len(x) - 3) * (1 - np.diag(H)))
            se = np.sqrt(propagated) / denom
            np.testing.assert_allclose([r['low'] for r in results],
                                       [r['studentized'] for r in results] - 1.96 * se, rtol=2e-10, atol=2e-10)
            np.testing.assert_allclose([r['high'] for r in results],
                                       [r['studentized'] for r in results] + 1.96 * se, rtol=2e-10, atol=2e-10)
        model = next(m for m in self.document['models'] if m['subject'] == 'combined' and m['level'] == 'ES')
        school = model['inputs'][0]
        native = next(r for r in self.roster['roster_links'] if r['school_id'] == school['school_id'])
        variances = []
        for subject in ['math', 'reading']:
            value = native['assessments']['ES'][subject]
            n = value['valid_scores']
            smoothed = (value['proficiency'] / 100 * n + .5) / (n + 1)
            variances.append(10000 * smoothed * (1 - smoothed) / n)
        expected = (math.sqrt(variances[0]) + math.sqrt(variances[1])) ** 2 / 4
        self.assertAlmostEqual(school['sampling_variance'], expected, places=12)
        n = school['display_valid_scores']
        smoothed = (school['outcome_pct'] / 100 * n + .5) / (n + 1)
        self.assertGreater(abs(expected - 10000 * smoothed * (1 - smoothed) / n), 1e-6)

    def test_one_missing_member_count_omits_all_model_intervals(self):
        model = self.document['models'][0]
        inputs = copy.deepcopy(model['inputs'])
        inputs[0]['valid_scores_by_subject']['math'] = None
        result = audit.fit_audited_model(inputs, model['coverage'], model['level'], model['subject'])
        self.assertFalse(result['intervals']['available_for_entire_model'])
        self.assertEqual(result['intervals']['eligible_members_with_verified_subject_counts'], len(inputs) - 1)
        self.assertTrue(all(r['low'] is None and r['high'] is None for r in result['results']))
        self.assertEqual(result['coefficients'], model['coefficients'])

    def test_independent_full_fit_rejects_incorrect_returned_coefficients(self):
        model = self.document['models'][0]
        real_fit = audit.fit_model

        def wrong_coefficient(x, y, variance):
            coefficients, results = real_fit(x, y, variance)
            coefficients['intercept'] += 1.
            return coefficients, results

        with mock.patch.object(audit, 'fit_model', side_effect=wrong_coefficient):
            with self.assertRaisesRegex(ValueError, 'Independent'):
                audit.fit_audited_model(model['inputs'], model['coverage'], model['level'], model['subject'])

    def test_floor_rank_and_population_identity_are_hard_gates(self):
        model = self.document['models'][0]
        inputs = model['inputs']
        with self.assertRaisesRegex(ValueError, 'at least 30'):
            audit.fit_audited_model(inputs[:29], model['coverage'], 'ES', 'math')
        fixed_income = [dict(r, income_pct=90.) for r in inputs]
        with self.assertRaisesRegex(ValueError, 'rank two'):
            audit.fit_audited_model(fixed_income, model['coverage'], 'ES', 'math')
        for field, value in [('level', 'mixed'), ('income_year', 2024)]:
            changed = copy.deepcopy(inputs)
            changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.fit_audited_model(changed, model['coverage'], 'ES', 'math')
        with self.assertRaises(ValueError):
            audit.fit_audited_model(inputs[:-1] + [inputs[0]], model['coverage'], 'ES', 'math')

    def test_material_result_and_any_source_identity_or_count_drift_fail(self):
        mutations = [
            lambda d: d['sources']['roster_audit'].update(sha256='0' * 64),
            lambda d: d['models'][0]['inputs'][0].update(income_pct=d['models'][0]['inputs'][0]['income_pct'] + 1e-12),
            lambda d: d['models'][0]['inputs'][0].update(school_id='19647330000000'),
            lambda d: d['models'][0]['inputs'][0]['valid_scores_by_subject'].update(math=999999),
            lambda d: d['models'][0]['coverage'].update(usable_schools=591),
            lambda d: d['models'][0]['coefficients'].update(n=561.),
            lambda d: d['models'][0]['coefficients'].update(slope=-.1),
            lambda d: d['models'][0]['results'][0].update(studentized=99.),
            lambda d: d['models'][0]['results'][0].update(low=-999.),
        ]
        for mutation in mutations:
            changed = copy.deepcopy(self.document)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.validate(changed, self.expected)
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / 'wrong-roster.json'
            wrong.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                audit.load_roster(wrong)

    def test_tiny_computed_float_variation_is_portable_without_loosening_evidence(self):
        changed = copy.deepcopy(self.document)
        changed['models'][0]['coefficients']['intercept'] += 1e-11
        changed['models'][0]['results'][0]['studentized'] += 1e-11
        self.assertEqual(audit.validate(changed, self.expected), audit.validate(self.document, self.expected))


if __name__ == '__main__':
    unittest.main()
