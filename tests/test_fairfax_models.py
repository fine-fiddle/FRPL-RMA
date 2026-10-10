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
import audit_fairfax_models as audit


class FairfaxModelAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = audit.load_roster()
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.expected = audit.build(cls.roster)

    def test_frozen_grade_population_retains_original_source_and_all_outsiders(self):
        self.assertEqual(audit.validate(self.document, self.expected), {f'fairfax-2025-ES-{s}': 152 for s in audit.SUBJECTS})
        self.assertEqual(self.document['hard_holds'], [])
        self.assertIs(self.document['approved_for_source'], False)
        self.assertIs(self.document['approved_for_modeling'], False)
        self.assertEqual(self.document['status'], 'numerically_verified_pending_integration')
        self.assertEqual(self.document['scope'], 'numerical_audit_only')
        self.assertNotIn('snapshots', self.document)
        population = self.document['frozen_population']
        for field, count in [('complete_directory_ncessch', 223), ('operational_roster_school_ids', 223),
                             ('native_source_profile_ids', 195), ('native_grade_school_configuration_ids', 162),
                             ('native_high_school_ids', 25), ('native_mixed_school_ids', 4),
                             ('native_unclassified_school_ids', 4), ('missing_native_school_ids', 28)]:
            self.assertEqual(len(population[field]), count)
        self.assertEqual(audit.roster_audit.fingerprint(self.document['retained_source_evidence']['raw_inputs']), audit.roster_audit.RAW_INPUT_SHA)
        self.assertEqual([len(self.document['retained_source_evidence']['raw_inputs'][s]['records'])
                          for s in ['directory', 'membership', 'lunch', 'native_profiles']], [223, 1689, 965, 195])
        self.assertEqual(self.document['retained_scope_exclusions']['release_holds'], self.roster['release_holds'])
        self.assertEqual(len(self.document['retained_scope_exclusions']['outside_native_configuration_records']), 61)
        outsiders = {r['school_id']: r for r in self.document['retained_scope_exclusions']['outside_native_configuration_records']}
        lake = outsiders['0290090']
        self.assertIsNone(lake['native_grade']['native_band'])
        self.assertEqual(lake['native_grade']['positive_unrecognized_grades'], ['Post Graduate'])
        self.assertEqual(next(r['raw_count'] for r in lake['native_grade']['native_grade_values'] if r['label'] == 'Post Graduate'), '1')
        self.assertEqual((lake['subjects']['math']['native_rate'], lake['subjects']['reading']['native_rate']), (87., 90.))
        self.assertTrue(all(r['school_id'] not in population['eligible_school_ids_by_subject']['math'] for r in outsiders.values()))
        expected_ids = population['eligible_school_ids_by_subject']['combined']
        for model in self.document['models']:
            self.assertEqual([r['school_id'] for r in model['inputs']], expected_ids)
            self.assertEqual(model['coefficients']['n'], 152)
            self.assertEqual(model['assessment'], audit.roster_audit.virginia.BANDS['grade'][1])
            self.assertEqual(model['coverage']['charter'], {'No': 152})
            self.assertEqual(model['coverage']['school_types'], {'Regular School': 152})
            self.assertEqual(len(model['coverage']['excluded_configuration_records']), 10)
            self.assertEqual(model['coverage']['native_grade_school_configuration_profiles'], 162)
            self.assertEqual(model['independent_verification']['explicit_deleted_fits'], 152)
            self.assertEqual(model['independent_verification']['deleted_training_members'], 151)
            self.assertEqual(model['independent_verification']['deleted_residual_degrees_of_freedom'], 149)
            self.assertTrue(all(v is None or v < audit.VERIFY_TOLERANCE for v in model['independent_verification']['maximum_absolute_errors'].values()))
        self.assertEqual(hashlib.sha256(audit.ROSTER.read_bytes()).hexdigest(), audit.ROSTER_SHA)
        with mock.patch.object(audit.roster_audit.zipfile, 'ZipFile', side_effect=AssertionError('No original archive')), \
                mock.patch.object(audit.roster_audit.subprocess, 'Popen', side_effect=AssertionError('No original stream')):
            self.assertEqual(audit.validate(self.document), audit.validate(self.document, self.expected))

    def test_external_studentization_influence_and_line_shift_match_every_manual_deletion(self):
        for model in self.document['models']:
            x = np.array([r['income_pct'] for r in model['inputs']])
            y = np.array([r['outcome_pct'] for r in model['inputs']])
            n = len(x)
            X = np.column_stack([np.ones(n), x - x.mean()])
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            full_residual = y - X @ beta
            full_scale2 = float(full_residual @ full_residual) / (n - 2)
            for i, row in enumerate(model['results']):
                keep = np.arange(n) != i
                mean_x = x[keep].mean()
                D = np.column_stack([np.ones(n - 1), x[keep] - mean_x])
                b = np.linalg.lstsq(D, y[keep], rcond=None)[0]
                residual = y[keep] - D @ b
                deleted_sse = float(residual @ residual)
                scale = math.sqrt(deleted_sse / (n - 3))
                held_out = np.array([1., x[i] - mean_x])
                deleted_h = float(held_out @ np.linalg.inv(D.T @ D) @ held_out)
                t = (y[i] - held_out @ b) / (scale * math.sqrt(1 + deleted_h))
                h = float(X[i] @ np.linalg.inv(X.T @ X) @ X[i])
                cook = full_residual[i] ** 2 * h / (2 * full_scale2 * (1 - h) ** 2)
                endpoints = np.array([x.min(), x.max()])
                full_line = beta[0] + beta[1] * (endpoints - x.mean())
                deleted_line = b[0] + b[1] * (endpoints - mean_x)
                with self.subTest(subject=model['subject'], school=row['school_id']):
                    self.assertAlmostEqual(t, row['studentized'], delta=2e-10)
                    self.assertAlmostEqual(deleted_sse, row['deleted_sse'], delta=2e-9)
                    self.assertAlmostEqual(cook, row['cooks_distance'], delta=2e-10)
                    self.assertAlmostEqual(float(np.max(np.abs(full_line - deleted_line))), row['maximum_prediction_change_on_observed_income_range'], delta=2e-10)

    def test_native_reconciled_income_and_direct_passed_are_exact_not_ccd_or_stale_display(self):
        model = self.document['models'][0]
        stale, different_membership = 0, 0
        for school in model['inputs']:
            native = school['sources']['native_profile']['raw']
            groups = native['enrollment_subgroups']
            total = int(groups['5']['cnt'].replace(',', ''))
            ed = int(groups['3']['cnt'].replace(',', ''))
            other = int(groups['18']['cnt'].replace(',', ''))
            self.assertEqual(ed + other, total)
            self.assertEqual(school['income_pct'], 100 * ed / total)
            self.assertEqual(school['sources']['native_school_id'], 'VA-029-' + school['school_id'])
            self.assertEqual(school['sources']['directory_raw']['NCESSCH'], school['ncessch'])
            self.assertEqual(school['sources']['native_grade_evidence']['native_band'], 'grade')
            self.assertEqual(school['sources']['native_grade_evidence']['missing_or_suppressed_grades'], [])
            stale += school['sources']['native_income_evidence']['stale_display_percentage']
            different_membership += school['sources']['membership_difference_native_minus_ccd'] != 0
            for subject in ['math', 'reading']:
                raw = native['assessments'][subject]; index = raw['years'].index('2024-2025')
                self.assertEqual(raw['population'], 'All Students')
                self.assertEqual(school['outcome_by_subject'][subject], float(raw['school_values'][index]))
                self.assertEqual(school['outcome_by_subject'][subject], float(raw['table_all_students'][4 * index + 2]))
        self.assertGreater(stale, 0)
        self.assertGreater(different_membership, 0)
        for excluded in model['coverage']['excluded_configuration_records']:
            self.assertIsNone(excluded['income']['percentage'])
            self.assertTrue(excluded['native_grade']['missing_or_suppressed_grades'])
            self.assertNotIn(excluded['school_id'], [r['school_id'] for r in model['inputs']])

    def test_combined_equal_native_rates_have_separate_studentization(self):
        models = {m['subject']: m for m in self.document['models']}
        for school in models['combined']['inputs']:
            values = school['outcome_by_subject']
            self.assertEqual(school['outcome_pct'], (values['math'] + values['reading']) / 2)
        for field in ['intercept', 'slope']:
            self.assertAlmostEqual(models['combined']['coefficients'][field], (models['math']['coefficients'][field] + models['reading']['coefficients'][field]) / 2, delta=2e-10)
        self.assertTrue(any(abs(c['studentized'] - (m['studentized'] + e['studentized']) / 2) > .01
                            for c, m, e in zip(models['combined']['results'], models['math']['results'], models['reading']['results'])))
        changed = copy.deepcopy(models['combined']['inputs']); changed[0]['outcome_pct'] += 1.
        with self.assertRaisesRegex(ValueError, 'exact frozen native'):
            audit.fit_audited_model(changed, models['combined']['coverage'], 'combined')

    def test_point_only_sentinel_does_not_become_a_verified_count_or_interval(self):
        for model in self.document['models']:
            self.assertIs(model['intervals']['available_for_entire_model'], False)
            self.assertIsNone(model['intervals']['valid_score_counts']); self.assertIsNone(model['intervals']['sampling_variances'])
            for school in model['inputs']:
                self.assertEqual(school['valid_scores_by_subject'], {'math': None, 'reading': None})
                self.assertIsNone(school['display_valid_scores']); self.assertIsNone(school['sampling_variance'])
            for row in model['results']:
                self.assertTrue(all(row[k] is None for k in ['valid_scores', 'sampling_variance', 'low', 'high']))
        model = self.document['models'][0]; real_fit = audit.fit_model; passed = []
        def capture(x, y, variance):
            passed.append(variance.copy())
            return real_fit(x, y, variance)
        with mock.patch.object(audit, 'fit_model', side_effect=capture):
            result = audit.fit_audited_model(model['inputs'], model['coverage'], model['subject'])
        self.assertTrue(np.array_equal(passed[0], np.zeros(152)))
        self.assertTrue(all(r['low'] is None and r['high'] is None and r['sampling_variance'] is None for r in result['results']))
        for mutate in [lambda r: r.update(sampling_variance=0.), lambda r: r.update(display_valid_scores=10),
                       lambda r: r['valid_scores_by_subject'].update(math=10)]:
            changed = copy.deepcopy(model['inputs']); mutate(changed[0])
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, 'exact frozen native'):
                audit.fit_audited_model(changed, model['coverage'], model['subject'])

    def test_floor_rank_full_deleted_scales_and_same_year_native_scope_are_hard_gates(self):
        model = self.document['models'][0]; inputs = model['inputs']
        with self.assertRaisesRegex(ValueError, 'at least 30'): audit.fit_audited_model(inputs[:29], model['coverage'], 'math')
        x = np.array([r['income_pct'] for r in inputs]); y = np.array([r['outcome_pct'] for r in inputs]); sentinel = np.zeros(len(x))
        with self.assertRaisesRegex(ValueError, 'varying income'): audit.fit_model(np.full(len(x), 20.), y, sentinel)
        exact_line = 10. + .5 * x
        with self.assertRaisesRegex(ValueError, 'no studentization scale'): audit.fit_model(x, exact_line, sentinel)
        exact_line[0] += 1.
        with self.assertRaisesRegex(ValueError, '[Dd]eleted-school residual (variance|scale)'): audit.fit_model(x, exact_line, sentinel)
        singular_deletion = np.full(len(x), 20.); singular_deletion[0] = 30.
        with self.assertRaisesRegex(ValueError, 'singular or numerically unstable'): audit.fit_model(singular_deletion, y, sentinel)
        for field in ['income_pct', 'outcome_pct']:
            changed = copy.deepcopy(inputs); changed[0][field] += .001
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'exact frozen native'):
                audit.fit_audited_model(changed, model['coverage'], 'math')
        with self.assertRaisesRegex(ValueError, 'complete eligible membership'):
            audit.fit_audited_model(inputs[:-1], model['coverage'], 'math')
        for field, value in [('level', 'HS'), ('income_year', 2024), ('income_year', 2025.), ('income_pct', False),
                             ('school_id', '0290090'), ('ncessch', '130000000001'), ('income_pct', float('nan')), ('outcome_pct', 101.)]:
            changed = copy.deepcopy(inputs); changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): audit.fit_audited_model(changed, model['coverage'], 'math')
        with self.assertRaises(ValueError): audit.fit_audited_model(inputs[:-1] + [inputs[0]], model['coverage'], 'math')
        for mutate in [lambda r: r['sources']['native_grade_evidence'].update(native_band='mixed'),
                       lambda r: r['sources']['native_grade_evidence'].update(positive_unrecognized_grades=['Post Graduate']),
                       lambda r: r['sources']['native_grade_evidence'].update(missing_or_suppressed_grades=['Pre-kindergarten']),
                       lambda r: r['sources']['native_grade_evidence'].update(academic_year='2023-2024'),
                       lambda r: r['sources']['directory_raw'].update(SY_STATUS='2'),
                       lambda r: r['sources'].update(native_school_id='VA-029-0299999')]:
            changed = copy.deepcopy(inputs); mutate(changed[0])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): audit.fit_audited_model(changed, model['coverage'], 'math')

    def test_independent_full_deleted_verification_rejects_corrupt_fitter_output(self):
        model = self.document['models'][0]; real_fit = audit.fit_model
        for key in ['intercept', 'predicted', 'actual', 'studentized']:
            def wrong(x, y, variance):
                coefficients, results = real_fit(x, y, variance)
                if key == 'intercept': coefficients[key] += 1.
                else: results[0][key] += 1.
                return coefficients, results
            with self.subTest(key=key), mock.patch.object(audit, 'fit_model', side_effect=wrong), self.assertRaisesRegex(ValueError, 'Independent'):
                audit.fit_audited_model(model['inputs'], model['coverage'], 'math')
        for location, key in [('coefficients', 'intercept'), ('coefficients', 'slope'), ('coefficients', 'r2'),
                              ('results', 'actual'), ('results', 'predicted'), ('results', 'residual'),
                              ('results', 'studentized'), ('results', 'leverage')]:
            for bad in [float('nan'), float('inf'), float('-inf'), False]:
                def wrong(x, y, variance):
                    coefficients, results = real_fit(x, y, variance)
                    (coefficients if location == 'coefficients' else results[0])[key] = bad
                    return coefficients, results
                with self.subTest(location=location, key=key, bad=bad), mock.patch.object(audit, 'fit_model', side_effect=wrong), self.assertRaisesRegex(ValueError, 'Independent'):
                    audit.fit_audited_model(model['inputs'], model['coverage'], 'math')

    def test_raw_provenance_exact_population_scope_and_material_metrics_fail_replay(self):
        mutations = [
            lambda d: d.update(approved_for_modeling=True), lambda d: d.update(approved_for_source=0),
            lambda d: d['source_coverage'].update(verified_valid_score_counts=False),
            lambda d: d['sources']['roster_audit'].update(sha256='0' * 64),
            lambda d: d['retained_source_evidence']['raw_inputs']['membership']['records'][0]['raw'].update(STUDENT_COUNT='0'),
            lambda d: d['retained_source_evidence']['raw_inputs']['native_profiles']['records'][0]['raw']['enrollment_subgroups']['3'].update(cnt='0'),
            lambda d: d['retained_source_evidence']['raw_inputs']['native_profiles']['records'][0]['raw']['assessments']['math']['years'].__setitem__(1, '2023-2024'),
            lambda d: d['retained_scope_exclusions']['release_holds']['high'].clear(),
            lambda d: d['frozen_population']['missing_native_school_ids'].pop(),
            lambda d: d['frozen_population']['eligible_school_ids_by_subject']['math'].pop(),
            lambda d: d['models'][0].update(approved_for_modeling=0),
            lambda d: d['models'][0]['independent_verification'].update(tolerance_absolute=2e-9 + 1e-12),
            lambda d: d['models'][0]['independent_verification'].update(deleted_residual_degrees_of_freedom=150),
            lambda d: d['models'][0]['inputs'][0].update(income_pct=d['models'][0]['inputs'][0]['income_pct'] + 1e-12),
            lambda d: d['models'][0]['inputs'][0].update(income_year=2024),
            lambda d: d['models'][0]['inputs'][0]['sources'].update(native_source_row=99999),
            lambda d: d['models'][0]['inputs'][0]['sources']['native_profile']['raw']['grade_table']['rows'][0]['values'].__setitem__(1, '-'),
            lambda d: d['models'][0]['inputs'][0]['sources']['directory_raw'].update(ST_SCHID='VA-029-0299999'),
            lambda d: d['models'][0]['inputs'][0]['valid_scores_by_subject'].update(math=10),
            lambda d: d['models'][0]['inputs'][0].update(sampling_variance=0.),
            lambda d: d['models'][0]['coverage'].update(usable_schools=153),
            lambda d: d['models'][0]['coefficients'].update(n=152.),
            lambda d: d['models'][0]['coefficients'].update(slope=-.1),
            lambda d: d['models'][0]['results'][0].update(actual=0.),
            lambda d: d['models'][0]['results'][0].update(studentized=99.),
            lambda d: d['models'][0]['results'][0].update(low=0.),
            lambda d: d['models'][0]['results'][0].update(valid_scores=10),
            lambda d: d['models'][0]['results'][0].update(sampling_variance=0.),
            lambda d: d['models'][0]['results'][0]['review_flags'].update(cooks_above_4_over_n=0),
            lambda d: d['models'][0]['intervals'].update(available_for_entire_model=True),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): audit.validate(changed, self.expected)
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / 'source.json'; wrong.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'fingerprint'): audit.load_roster(wrong)

    def test_computed_float_tolerance_is_narrow_and_exact_sources_remain_exact(self):
        changed = copy.deepcopy(self.document)
        changed['models'][0]['coefficients']['intercept'] += 1e-11
        changed['models'][0]['results'][0]['studentized'] += 1e-11
        self.assertEqual(audit.validate(changed, self.expected), audit.validate(self.document, self.expected))
        changed['models'][0]['results'][0]['studentized'] = float('nan')
        with self.assertRaises(ValueError): audit.validate(changed, self.expected)

    def test_numerical_failure_is_retained_as_hold_and_builds_are_identical(self):
        with mock.patch.object(audit, 'fit_model', side_effect=ValueError('Unresolved deleted scale')):
            held = audit.build(self.roster)
        self.assertEqual(held['status'], 'numerical_hold')
        self.assertEqual(len(held['hard_holds']), 3)
        self.assertTrue(all(m['status'] == 'numerical_hold' and 'results' not in m for m in held['models']))
        self.assertEqual(audit.validate(held, held), {f'fairfax-2025-ES-{s}': 152 for s in audit.SUBJECTS})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'models.json'
            audit.prepare(path)
            first = path.read_bytes()
            audit.prepare(path)
            self.assertEqual(path.read_bytes(), first)
            self.assertEqual(first, audit.OUTPUT.read_bytes())
            audit.prepare(path, check=True)


if __name__ == '__main__':
    unittest.main()
