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
import audit_wake_models as audit


class WakeNumericalAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = audit.load_roster()
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.expected = audit.build(cls.roster)
        cls.models = {m['subject']: m for m in cls.document['models']}

    def test_frozen_full_source_and_subject_specific_population_are_preserved(self):
        self.assertEqual(audit.validate(self.document, self.expected), {'wake-2025-ES-math': 159, 'wake-2025-ES-reading': 160, 'wake-2025-ES-combined': 159})
        self.assertEqual(self.document['hard_holds'], [])
        self.assertEqual((self.document['scope'], self.document['status']), ('numerical_audit_only', 'numerically_verified_pending_integration'))
        self.assertIs(self.document['approved_for_source'], False); self.assertIs(self.document['approved_for_modeling'], False)
        p = self.document['frozen_population']
        for field, size in [('complete_directory_ncessch', 202), ('operational_roster_school_ids', 198),
                            ('grade_school_configuration_ids', 162), ('native_source_profile_ids', 160),
                            ('high_school_configuration_ids', 33), ('mixed_configuration_ids', 3), ('nonoperational_school_ids', 4)]:
            self.assertEqual(len(p[field]), size)
        self.assertEqual(p['native_aggregate_codes'], ['920LEA'])
        raw = self.document['retained_source_evidence']['raw_inputs']
        self.assertEqual(audit.roster_audit.fingerprint(raw), audit.roster_audit.RAW_INPUT_SHA)
        self.assertEqual([len(raw[k]['records']) for k in ['directory', 'membership', 'assessment', 'income']], [202, 1520, 5792, 199])
        self.assertEqual(len(self.document['retained_scope_exclusions']['outside_grade_school_configuration_records']), 36)
        self.assertEqual(len(self.document['retained_scope_exclusions']['nonoperational_directory']), 4)
        self.assertEqual(self.document['retained_source_evidence']['source_approval'], {'approved_for_source': False, 'approved_for_modeling': False})
        for subject, n in [('math', 159), ('reading', 160), ('combined', 159)]:
            m = self.models[subject]
            self.assertEqual(m['coefficients']['n'], n)
            self.assertEqual(m['coverage']['grade_school_configuration_profiles'], 162)
            self.assertEqual(m['coverage']['native_source_profiles'], 160)
            self.assertEqual(m['coverage']['excluded_configuration_profiles'], 162 - n)
            self.assertEqual(m['diagnostics']['income_design_rank'], 2)
            self.assertEqual(m['diagnostics']['full_residual_degrees_of_freedom'], n - 2)
            self.assertEqual(m['diagnostics']['deleted_residual_degrees_of_freedom'], n - 3)
            self.assertEqual(m['independent_verification']['explicit_deleted_fits'], n)
            self.assertEqual(m['independent_verification']['deleted_training_members'], n - 1)
            self.assertEqual(m['independent_verification']['deleted_residual_degrees_of_freedom'], n - 3)
            self.assertTrue(all(v is None or v < audit.VERIFY_TOLERANCE for v in m['independent_verification']['maximum_absolute_errors'].values()))
            self.assertEqual(m['coverage']['charter'], {'No': n})
            self.assertEqual(m['coverage']['school_types'], {'Alternative School': 3, 'Regular School': n - 3})
            self.assertGreater(m['diagnostics']['minimum_deleted_sse'], 0)
            self.assertGreater(m['diagnostics']['minimum_deleted_residual_scale'], 0)
        self.assertNotIn('snapshots', self.document)

    def test_unweighted_raw_design_full_and_every_deleted_fit_reproduce_all_results(self):
        for m in self.document['models']:
            x = np.array([r['income_pct'] for r in m['inputs']]); y = np.array([r['outcome_pct'] for r in m['inputs']]); n = len(x)
            X = np.column_stack([np.ones(n), x]); beta = np.linalg.lstsq(X, y, rcond=None)[0]
            pred = X @ beta; residual = y - pred; sse = float(residual @ residual); scale2 = sse / (n - 2)
            H = X @ np.linalg.inv(X.T @ X) @ X.T
            self.assertAlmostEqual(float(beta[0]), m['coefficients']['intercept'], delta=2e-10)
            self.assertAlmostEqual(float(beta[1]), m['coefficients']['slope'], delta=2e-10)
            self.assertAlmostEqual(1 - sse / float((y - y.mean()) @ (y - y.mean())), m['coefficients']['r2'], delta=2e-10)
            for i, row in enumerate(m['results']):
                keep = np.arange(n) != i; D = X[keep]; b = np.linalg.lstsq(D, y[keep], rcond=None)[0]
                deleted_residual = y[keep] - D @ b; deleted_sse = float(deleted_residual @ deleted_residual)
                deleted_scale = math.sqrt(deleted_sse / (n - 3)); held = float(X[i] @ b)
                h_deleted = float(X[i] @ np.linalg.inv(D.T @ D) @ X[i])
                external_t = (y[i] - held) / (deleted_scale * math.sqrt(1 + h_deleted))
                cook = residual[i] ** 2 * H[i, i] / (2 * scale2 * (1 - H[i, i]) ** 2)
                endpoints = np.column_stack([np.ones(2), [x.min(), x.max()]])
                shift = float(np.max(np.abs(endpoints @ beta - endpoints @ b)))
                with self.subTest(subject=m['subject'], school=row['school_id']):
                    for actual, expected in [(row['predicted'], pred[i]), (row['residual'], residual[i]), (row['leverage'], H[i, i]),
                                             (row['studentized'], external_t), (row['cooks_distance'], cook),
                                             (row['deleted_intercept'], b[0]), (row['deleted_slope'], b[1]),
                                             (row['deleted_residual_scale'], deleted_scale), (row['deleted_held_out_prediction'], held),
                                             (row['deleted_held_out_prediction_leverage'], h_deleted),
                                             (row['maximum_prediction_change_on_observed_income_range'], shift)]:
                        self.assertAlmostEqual(actual, float(expected), delta=2e-9)
                    self.assertAlmostEqual(row['deleted_sse'], deleted_sse, delta=2e-9)

    def test_exact_native_rates_april_income_masks_and_outsiders_never_get_substitutes(self):
        for m in self.document['models']:
            for r in m['inputs']:
                eds = r['sources']['april_income']['raw']
                self.assertEqual((eds['reporting_year'], eds['collection_code'], eds['psu_code'], eds['school_code']), ('2025', 'APR', '920', r['school_id']))
                self.assertEqual(r['income_pct'], float(eds['pct_eds']))
                self.assertEqual(r['april_enrollment'], int(eds['den']))
                self.assertEqual(audit.roster_audit.ccd_identity(r['sources']['directory_raw']), r['school_id'])
                for subject, entry in r['sources']['native_assessments'].items():
                    native = entry['raw']
                    self.assertEqual((native['type'], native['grade'], native['subgroup'], native['subject']), ('RG', 'GS', 'ALL', 'MA' if subject == 'math' else 'RD'))
                    self.assertEqual(native['school_code'], r['school_id'])
                    self.assertEqual(r['outcome_by_subject'][subject], audit.roster_audit.north_carolina.exact_percent(native['pct_glp']))
            exclusions = {r['school_id']: r for r in m['coverage']['excluded_configuration_records']}
            self.assertIn('920314', exclusions); self.assertIn('920614', exclusions)
            self.assertEqual(exclusions['920314']['income']['raw_percentage'], '<5')
            self.assertEqual(exclusions['920614']['income']['raw_percentage'], '<5')
            if m['subject'] != 'reading':
                self.assertIn('920502', exclusions)
                self.assertEqual(exclusions['920502']['subjects']['math']['raw_rate'], '>95')
            else:
                self.assertIn('920502', [r['school_id'] for r in m['inputs']])
        outside = self.document['retained_scope_exclusions']['outside_grade_school_configuration_records']
        mixed = next(r for r in outside if r['school_id'] == '920585')
        self.assertTrue(mixed['native_regular_gs_pair']); self.assertEqual(mixed['native_grade_spans'], ['06-13'])
        self.assertTrue(all(r['school_id'] not in self.document['frozen_population']['eligible_school_ids_by_subject']['math'] for r in outside))
        self.assertEqual(self.document['source_coverage']['lea_minus_operational_school_fall_enrollment'], 149)
        self.assertEqual(self.document['source_coverage']['april_enrollment_different_from_fall'], 192)

    def test_combined_uses_its_own_population_fit_and_studentization(self):
        math_model, ela, combined = [self.models[s] for s in ['math', 'reading', 'combined']]
        by_ela = {r['school_id']: r for r in ela['inputs']}; by_ela_result = {r['school_id']: r for r in ela['results']}
        x = np.array([r['income_pct'] for r in combined['inputs']]); X = np.column_stack([np.ones(len(x)), x])
        y_ela_matching = np.array([by_ela[r['school_id']]['outcome_pct'] for r in combined['inputs']])
        restricted_ela = np.linalg.lstsq(X, y_ela_matching, rcond=None)[0]
        for r in combined['inputs']:
            self.assertEqual(r['outcome_pct'], (r['outcome_by_subject']['math'] + r['outcome_by_subject']['reading']) / 2)
        for i, field in enumerate(['intercept', 'slope']):
            self.assertAlmostEqual(combined['coefficients'][field], (math_model['coefficients'][field] + float(restricted_ela[i])) / 2, delta=2e-10)
        self.assertGreater(abs(combined['coefficients']['intercept'] - (math_model['coefficients']['intercept'] + ela['coefficients']['intercept']) / 2), .05)
        self.assertTrue(any(abs(c['studentized'] - (m['studentized'] + by_ela_result[c['school_id']]['studentized']) / 2) > .01
                            for c, m in zip(combined['results'], math_model['results'])))

    def test_every_count_variance_endpoint_and_scored_floor_remains_unavailable(self):
        self.assertFalse(self.document['count_definition_status']['ten_valid_scored_floor_certified'])
        for m in self.document['models']:
            self.assertFalse(m['approved_for_source']); self.assertFalse(m['approved_for_modeling']); self.assertFalse(m['valid_score_floor_certified'])
            self.assertFalse(m['intervals']['available_for_entire_model']); self.assertFalse(m['intervals']['ten_valid_scored_floor_certified'])
            self.assertIsNone(m['intervals']['valid_score_counts']); self.assertIsNone(m['intervals']['sampling_variances'])
            for r in m['inputs']:
                self.assertEqual(r['valid_scores_by_subject'], {'math': None, 'reading': None})
                self.assertIsNone(r['display_valid_scores']); self.assertIsNone(r['sampling_variance'])
                self.assertFalse(r['ten_valid_scored_floor_certified'])
            for r in m['results']:
                self.assertTrue(all(r[k] is None for k in ['valid_scores', 'sampling_variance', 'low', 'high']))
        m = self.models['math']; passed = []; real_fit = audit.fit_model
        def capture(x, y, variance):
            passed.append(variance.copy()); return real_fit(x, y, variance)
        with mock.patch.object(audit, 'fit_model', side_effect=capture):
            result = audit.fit_audited_model(m['inputs'], m['coverage'], 'math')
        self.assertTrue(np.array_equal(passed[0], np.zeros(159)))
        self.assertTrue(all(r['low'] is None and r['high'] is None for r in result['results']))

    def test_direct_calls_reject_incomplete_or_changed_native_inputs_before_fit(self):
        m = self.models['math']
        mutations = [lambda x: x.pop(), lambda x: x.reverse(), lambda x: x.append(copy.deepcopy(x[0])),
            lambda x: x[0].update(level='HS'), lambda x: x[0].update(income_year=2024), lambda x: x[0].update(income_year=2025.),
            lambda x: x[0].update(school_id='920585'), lambda x: x[0].update(ncessch='370472099999'),
            lambda x: x[0].update(income_pct=False), lambda x: x[0].update(outcome_pct=float('nan')),
            lambda x: x[0].update(sampling_variance=0.), lambda x: x[0].update(display_valid_scores=10),
            lambda x: x[0]['valid_scores_by_subject'].update(math=10), lambda x: x[0].update(ten_valid_scored_floor_certified=True),
            lambda x: x[0]['sources']['april_income']['raw'].update(pct_eds='0'),
            lambda x: x[0]['sources']['native_assessments']['math']['raw'].update(type='ALL'),
            lambda x: x[0]['sources']['native_assessments']['math']['raw'].update(num_tested='1'),
            lambda x: x[0]['sources']['directory_raw'].update(UPDATED_STATUS='7'),
            lambda x: x[0]['sources']['enrolled_evidence'].update(native_grade_school_contract=False)]
        for i, mutation in enumerate(mutations):
            inputs = copy.deepcopy(m['inputs']); mutation(inputs)
            with self.subTest(mutation=i), mock.patch.object(audit, 'fit_model', side_effect=AssertionError('No fit before source validation')), self.assertRaises(ValueError):
                audit.fit_audited_model(inputs, m['coverage'], 'math')
        with mock.patch.object(audit, 'fit_model', side_effect=AssertionError('No fit below floor')), self.assertRaisesRegex(ValueError, 'at least 30'):
            audit.fit_audited_model(m['inputs'][:29], m['coverage'], 'math')
        for subject in ['high', 'mixed', 'science']:
            with self.assertRaises(ValueError): audit.fit_audited_model(m['inputs'], m['coverage'], subject)
        coverage = copy.deepcopy(m['coverage']); coverage['usable_schools'] = 160
        with self.assertRaises(ValueError): audit.fit_audited_model(m['inputs'], coverage, 'math')

    def test_rank_positive_full_and_deleted_scales_are_hard_gates(self):
        m = self.models['math']; x = np.array([r['income_pct'] for r in m['inputs']]); y = np.array([r['outcome_pct'] for r in m['inputs']]); zero = np.zeros(len(x))
        for bad_x, bad_y in [(np.full(len(x), 20.), y), (x, 10. + .5 * x), (np.r_[30., np.full(len(x) - 1, 20.)], y)]:
            with self.assertRaises(ValueError): audit.fit_model(bad_x, bad_y, zero)
        one_outlier = 10. + .5 * x; one_outlier[0] += 1.
        coefficients, rows = audit.fit_model(x, one_outlier, zero)
        for row in rows:
            row.update(low=None, high=None)
        with self.assertRaisesRegex(ValueError, 'deleted-school residual scale'):
            audit.verify_independently(x, one_outlier, coefficients, rows)
        for bad in [np.full(len(x), np.nan), np.full(len(x), np.inf)]:
            with self.assertRaises(ValueError): audit.verify_independently(bad, y, m['coefficients'], m['results'])

    def test_corrupt_fitter_coefficients_results_and_boolean_numbers_fail_independent_verification(self):
        m = self.models['math']; real_fit = audit.fit_model
        for location, key, bad in [('coefficients', 'intercept', 0.), ('coefficients', 'n', False),
                                  ('coefficients', 'r2', float('nan')), ('results', 'actual', 0.),
                                  ('results', 'predicted', float('inf')), ('results', 'residual', False),
                                  ('results', 'studentized', 0.), ('results', 'leverage', False)]:
            def corrupt(x, y, variance):
                coefficients, rows = real_fit(x, y, variance)
                (coefficients if location == 'coefficients' else rows[0])[key] = bad
                return coefficients, rows
            with self.subTest(location=location, key=key), mock.patch.object(audit, 'fit_model', side_effect=corrupt), self.assertRaisesRegex(ValueError, 'Independent'):
                audit.fit_audited_model(m['inputs'], m['coverage'], 'math')

    def test_saved_source_policy_approval_population_and_count_mutations_fail_exact_replay(self):
        mutations = [lambda d: d.update(approved_for_source=0), lambda d: d.update(approved_for_modeling=True),
            lambda d: d.update(scope='ready'), lambda d: d['count_definition_status'].update(ten_valid_scored_floor_certified=True),
            lambda d: d['sources']['roster_audit'].update(sha256='0' * 64),
            lambda d: d['source_coverage'].update(verified_valid_score_counts=False),
            lambda d: d['retained_source_evidence']['raw_inputs']['assessment']['records'].pop(),
            lambda d: d['frozen_population']['eligible_school_ids_by_subject']['math'].append('920502'),
            lambda d: d['models'][0]['inputs'][0].update(income_pct=25.),
            lambda d: d['models'][0]['coverage']['excluded_configuration_records'].pop(),
            lambda d: d['models'][0]['intervals'].update(valid_score_counts=100),
            lambda d: d['models'][0]['results'][0].update(actual=d['models'][0]['results'][0]['actual'] + 1e-12),
            lambda d: d['models'][0]['results'][0].update(low=0.),
            lambda d: d['models'][0]['results'][0].update(sampling_variance=0.),
            lambda d: d['models'][0]['independent_verification'].update(tolerance_absolute=1.),
            lambda d: d['retained_scope_exclusions']['nonoperational_directory'].pop()]
        for i, mutation in enumerate(mutations):
            d = copy.deepcopy(self.document); mutation(d)
            with self.subTest(mutation=i), self.assertRaises(ValueError): audit.validate(d, self.expected)

    def test_saved_numerical_fields_require_finite_correct_types_and_tolerance(self):
        for key in ['predicted', 'residual', 'studentized', 'leverage', 'cooks_distance', 'deleted_sse', 'deleted_residual_scale', 'maximum_prediction_change_on_observed_income_range']:
            for bad in [False, float('nan'), float('inf')]:
                d = copy.deepcopy(self.document); d['models'][0]['results'][0][key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError): audit.validate(d, self.expected)
        d = copy.deepcopy(self.document); d['models'][0]['coefficients']['slope'] += .01
        with self.assertRaises(ValueError): audit.validate(d, self.expected)
        self.assertFalse(audit.numeric_equal(True, 1.)); self.assertFalse(audit.numeric_equal(1, 1.))
        self.assertFalse(audit.numeric_equal(2025., 2025))
        self.assertTrue(audit.numeric_equal(1. + 1e-12, 1.))

    def test_pinned_historical_source_and_in_memory_source_drift_cannot_be_fit(self):
        for path, sha in [(audit.ROSTER, audit.ROSTER_SHA), (audit.SOURCE_CODE, audit.SOURCE_CODE_SHA)]:
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sha)
        changed = copy.deepcopy(self.roster); changed['roster_links'][0]['income']['percentage'] += 1.
        with self.assertRaises(ValueError): audit.build(changed)
        with self.assertRaises(ValueError): audit.selected_inputs(changed, 'math')
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'changed.json'; p.write_text(json.dumps(changed))
            with self.assertRaises(ValueError): audit.load_roster(p)

    def test_two_numerical_builds_and_read_only_offline_replay_are_identical(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t) / 'a.json', Path(t) / 'b.json'
            first = audit.prepare(a); second = audit.prepare(b)
            self.assertEqual(first, second); self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(a.read_bytes(), audit.OUTPUT.read_bytes())
            before = a.read_bytes()
            with mock.patch.object(audit.roster_audit.zipfile, 'ZipFile', side_effect=AssertionError('No original archive')), \
                    mock.patch.object(audit.roster_audit.subprocess, 'Popen', side_effect=AssertionError('No original stream')), \
                    mock.patch.object(audit.roster_audit.openpyxl, 'load_workbook', side_effect=AssertionError('No original workbook')):
                self.assertEqual(audit.prepare(a, check=True), first)
            self.assertEqual(before, a.read_bytes())


if __name__ == '__main__':
    unittest.main()
