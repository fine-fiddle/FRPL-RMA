import copy
import hashlib
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
import audit_miami_dade_models as audit


class MiamiDadeModelAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = audit.load_roster()
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.expected = audit.build(cls.roster)

    def test_three_independent_exact_pure_point_only_models_replay(self):
        counts = audit.validate(self.document, self.expected)
        self.assertEqual(counts, {f'miami-dade-2025-ES-{s}': 357 for s in audit.SUBJECTS})
        self.assertFalse(self.document['hard_holds'])
        self.assertFalse(self.document['approved_for_modeling'])
        self.assertEqual(self.document['status'], 'numerically_verified_pending_integration')
        self.assertNotIn('snapshots', self.document)
        population = self.document['frozen_population']
        self.assertEqual(len(population['operational_roster_school_ids']), 530)
        self.assertEqual(len(population['pure_lower_directory_school_ids']), 370)
        self.assertEqual(len(population['offered_applicable_school_ids']), 365)
        self.assertEqual(len(population['primary_only_school_ids']), 5)
        self.assertEqual(len(population['native_grade_schools_with_mixed_offers']), 10)
        expected_ids = population['eligible_school_ids_by_subject']['combined']
        for model in self.document['models']:
            self.assertEqual([r['school_id'] for r in model['inputs']], expected_ids)
            self.assertEqual(model['coefficients']['n'], 357)
            self.assertEqual(model['diagnostics']['income_design_rank'], 2)
            self.assertEqual(model['coverage']['charter'], {'No': 261, 'Yes': 96})
            self.assertEqual(model['coverage']['school_types'], {'Regular School': 357})
            self.assertEqual(len(model['coverage']['excluded_directory_records']), 13)
            self.assertFalse(set(expected_ids).intersection(population['native_grade_schools_with_mixed_offers']))
            self.assertEqual(model['independent_verification']['explicit_deleted_fits'], 357)
            self.assertTrue(all(v is None or v < audit.VERIFY_TOLERANCE
                                for v in model['independent_verification']['maximum_absolute_errors'].values()))
            self.assertTrue(all(r['sources']['offered_evidence']['scope'] == 'ES'
                                and r['sources']['enrolled_evidence']['native_grade_school_contract']
                                and r['income_year'] == 2025 for r in model['inputs']))
        self.assertEqual(hashlib.sha256(audit.ROSTER.read_bytes()).hexdigest(), audit.ROSTER_SHA)

    def test_external_studentization_and_cook_match_manual_deleted_fits(self):
        for model in self.document['models']:
            x = np.array([r['income_pct'] for r in model['inputs']])
            y = np.array([r['outcome_pct'] for r in model['inputs']])
            n = len(x)
            results = model['results']
            indices = {0, n - 1, max(range(n), key=lambda i: results[i]['leverage']),
                       max(range(n), key=lambda i: abs(results[i]['studentized']))}
            X = np.column_stack([np.ones(n), x - x.mean()])
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            full_residual = y - X @ beta
            full_scale2 = float(full_residual @ full_residual) / (n - 2)
            for i in indices:
                keep = np.arange(n) != i
                mean_x = x[keep].mean()
                D = np.column_stack([np.ones(n - 1), x[keep] - mean_x])
                b = np.linalg.lstsq(D, y[keep], rcond=None)[0]
                deleted_residual = y[keep] - D @ b
                deleted_sse = float(deleted_residual @ deleted_residual)
                scale = math.sqrt(deleted_sse / (n - 3))
                held_out = np.array([1., x[i] - mean_x])
                deleted_h = float(held_out @ np.linalg.inv(D.T @ D) @ held_out)
                external_t = (y[i] - held_out @ b) / (scale * math.sqrt(1 + deleted_h))
                full_h = float(X[i] @ np.linalg.inv(X.T @ X) @ X[i])
                cook = full_residual[i] ** 2 * full_h / (2 * full_scale2 * (1 - full_h) ** 2)
                with self.subTest(subject=model['subject'], school=results[i]['school_id']):
                    self.assertAlmostEqual(external_t, results[i]['studentized'], delta=2e-10)
                    self.assertAlmostEqual(deleted_sse, results[i]['deleted_sse'], delta=2e-9)
                    self.assertAlmostEqual(cook, results[i]['cooks_distance'], delta=2e-10)

    def test_combined_uses_equal_native_mean_and_separate_district_fit(self):
        models = {m['subject']: m for m in self.document['models']}
        for school in models['combined']['inputs']:
            values = school['outcome_by_subject']
            self.assertEqual(school['outcome_pct'], (values['math'] + values['reading']) / 2)
            self.assertEqual(values['math'], school['sources']['assessment_raw'][9])
            self.assertEqual(values['reading'], school['sources']['assessment_raw'][6])
        for field in ['intercept', 'slope']:
            self.assertAlmostEqual(models['combined']['coefficients'][field],
                                   (models['math']['coefficients'][field] + models['reading']['coefficients'][field]) / 2,
                                   delta=2e-10)
        # Equal rates and shared memberships imply linear coefficients, but the
        # Combined residual scale is independently fitted, not averaged subject t.
        self.assertTrue(any(abs(c['studentized'] - (m['studentized'] + e['studentized']) / 2) > .01
                            for c, m, e in zip(models['combined']['results'], models['math']['results'], models['reading']['results'])))

    def test_internal_point_estimate_sentinel_never_becomes_sampling_uncertainty(self):
        for model in self.document['models']:
            self.assertFalse(model['intervals']['available_for_entire_model'])
            self.assertIsNone(model['intervals']['valid_score_counts'])
            self.assertIsNone(model['intervals']['sampling_variances'])
            for school in model['inputs']:
                self.assertEqual(school['valid_scores_by_subject'], {'math': None, 'reading': None})
                self.assertIsNone(school['display_valid_scores'])
                self.assertIsNone(school['sampling_variance'])
            for row in model['results']:
                self.assertTrue(all(row[k] is None for k in ['valid_scores', 'sampling_variance', 'low', 'high']))
        model = self.document['models'][0]
        real_fit = audit.fit_model
        passed = []

        def capture(x, y, variance):
            passed.append(variance.copy())
            return real_fit(x, y, variance)

        with mock.patch.object(audit, 'fit_model', side_effect=capture):
            result = audit.fit_audited_model(model['inputs'], model['coverage'], model['subject'])
        self.assertTrue(np.array_equal(passed[0], np.zeros(357)))
        self.assertTrue(all(r['low'] is None and r['high'] is None and r['sampling_variance'] is None for r in result['results']))
        for mutate in [lambda r: r.update(sampling_variance=0.), lambda r: r.update(display_valid_scores=10),
                       lambda r: r['valid_scores_by_subject'].update(math=10)]:
            inputs = copy.deepcopy(model['inputs'])
            mutate(inputs[0])
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, 'fabricated'):
                audit.fit_audited_model(inputs, model['coverage'], model['subject'])

    def test_floor_rank_full_scale_deleted_scale_and_finite_values_are_hard_gates(self):
        model = self.document['models'][0]
        inputs = model['inputs']
        with self.assertRaisesRegex(ValueError, 'at least 30'):
            audit.fit_audited_model(inputs[:29], model['coverage'], 'math')
        with self.assertRaisesRegex(ValueError, 'rank two'):
            audit.fit_audited_model([dict(r, income_pct=70.) for r in inputs], model['coverage'], 'math')
        exact_line = [dict(r, outcome_pct=10. + .5 * r['income_pct']) for r in inputs]
        with self.assertRaisesRegex(ValueError, 'no studentization scale'):
            audit.fit_audited_model(exact_line, model['coverage'], 'math')
        exact_line[0]['outcome_pct'] += 1.
        with self.assertRaisesRegex(ValueError, 'Deleted-school residual variance'):
            audit.fit_audited_model(exact_line, model['coverage'], 'math')
        singular_deletion = [dict(r, income_pct=70.) for r in inputs]
        singular_deletion[0]['income_pct'] = 50.
        with self.assertRaisesRegex(ValueError, 'singular or numerically unstable'):
            audit.fit_audited_model(singular_deletion, model['coverage'], 'math')
        for field, value in [('level', 'HS'), ('income_year', 2024), ('school_id', '12-0041'),
                             ('ncessch', '120000000001'), ('income_pct', float('nan')), ('outcome_pct', 101.)]:
            changed = copy.deepcopy(inputs)
            changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.fit_audited_model(changed, model['coverage'], 'math')
        with self.assertRaises(ValueError):
            audit.fit_audited_model(inputs[:-1] + [inputs[0]], model['coverage'], 'math')

    def test_independent_verification_rejects_wrong_full_fit_or_native_actual(self):
        model = self.document['models'][0]
        real_fit = audit.fit_model
        for key in ['intercept', 'predicted', 'actual', 'studentized']:
            def wrong(x, y, variance):
                coefficients, results = real_fit(x, y, variance)
                if key == 'intercept':
                    coefficients[key] += 1.
                else:
                    results[0][key] += 1.
                return coefficients, results

            with self.subTest(key=key), mock.patch.object(audit, 'fit_model', side_effect=wrong):
                with self.assertRaisesRegex(ValueError, 'Independent'):
                    audit.fit_audited_model(model['inputs'], model['coverage'], 'math')

    def test_source_population_interval_and_material_metric_drift_fail_replay(self):
        mutations = [
            lambda d: d.update(approved_for_modeling=True),
            lambda d: d['sources']['roster_audit'].update(sha256='0' * 64),
            lambda d: d['frozen_population']['offered_applicable_school_ids'].append('13-0441'),
            lambda d: d['models'][0]['inputs'][0].update(income_pct=d['models'][0]['inputs'][0]['income_pct'] + 1e-12),
            lambda d: d['models'][0]['inputs'][0].update(income_year=2024),
            lambda d: d['models'][0]['inputs'][0]['sources'].update(assessment_source_row=99999),
            lambda d: d['models'][0]['inputs'][0]['sources']['income_raw'].__setitem__(7, '*'),
            lambda d: d['models'][0]['inputs'][0]['valid_scores_by_subject'].update(math=10),
            lambda d: d['models'][0]['inputs'][0].update(sampling_variance=0.),
            lambda d: d['models'][0]['coverage'].update(usable_schools=361),
            lambda d: d['models'][0]['coefficients'].update(n=357.),
            lambda d: d['models'][0]['coefficients'].update(slope=-.1),
            lambda d: d['models'][0]['results'][0].update(actual=0.),
            lambda d: d['models'][0]['results'][0].update(studentized=99.),
            lambda d: d['models'][0]['results'][0].update(low=0.),
            lambda d: d['models'][0]['results'][0].update(valid_scores=10),
            lambda d: d['models'][0]['results'][0].update(sampling_variance=0.),
            lambda d: d['models'][0]['intervals'].update(available_for_entire_model=True),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.validate(changed, self.expected)
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / 'source.json'
            wrong.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                audit.load_roster(wrong)

    def test_tiny_computed_float_variation_does_not_relax_source_integrity(self):
        changed = copy.deepcopy(self.document)
        changed['models'][0]['coefficients']['intercept'] += 1e-11
        changed['models'][0]['results'][0]['studentized'] += 1e-11
        self.assertEqual(audit.validate(changed, self.expected), audit.validate(self.document, self.expected))


if __name__ == '__main__':
    unittest.main()
