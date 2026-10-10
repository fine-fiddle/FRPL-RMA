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
import audit_gwinnett_models as audit


class GwinnettModelAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = audit.load_roster()
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.expected = audit.build(cls.roster)

    def test_three_separate_frozen_native_models_preserve_all_source_scope(self):
        self.assertEqual(audit.validate(self.document, self.expected), {f'gwinnett-2025-ES-{s}': 111 for s in audit.SUBJECTS})
        self.assertEqual(self.document['hard_holds'], [])
        self.assertIs(self.document['approved_for_source'], False)
        self.assertIs(self.document['approved_for_modeling'], False)
        self.assertEqual(self.document['status'], 'numerically_verified_pending_integration')
        self.assertNotIn('snapshots', self.document)
        population = self.document['frozen_population']
        for field, count in [('complete_directory_ncessch', 141), ('operational_roster_school_ids', 141),
                             ('native_grade_school_configuration_ids', 111), ('offered_applicable_school_ids', 111),
                             ('positive_membership_tested_candidate_ids', 111), ('native_source_profile_ids', 111),
                             ('mixed_offers_with_native_g38_ids', 6)]:
            self.assertEqual(len(population[field]), count)
        self.assertEqual(population['primary_only_school_ids'], [])
        self.assertEqual(population['later_release_note_roster_gaps'], ['130255002906'])
        self.assertNotIn('130255002906', population['complete_directory_ncessch'])
        self.assertEqual(audit.roster_audit.fingerprint(self.document['retained_source_evidence']['raw_inputs']), audit.roster_audit.RAW_INPUT_SHA)
        self.assertEqual([len(self.document['retained_source_evidence']['raw_inputs'][s]['records'])
                          for s in ['directory', 'membership', 'lunch', 'assessment']], [141, 1099, 705, 942])
        outsiders = {r['school_id']: r for r in self.document['retained_scope_exclusions']['outside_native_configuration_records']}
        self.assertEqual(len(outsiders), 30)
        self.assertEqual(outsiders['130255004683']['subjects']['math']['raw_rate'], '0')
        self.assertEqual(outsiders['130255004683']['subjects']['math']['raw_tested'], '*')
        self.assertEqual(outsiders['130255004683']['subjects']['math']['native_rate'], 0.)
        self.assertFalse(outsiders['130255004683']['subjects']['math']['usable'])
        expected_ids = population['eligible_school_ids_by_subject']['combined']
        self.assertIn('130255003991', expected_ids)
        for model in self.document['models']:
            self.assertEqual([r['school_id'] for r in model['inputs']], expected_ids)
            self.assertEqual(model['coefficients']['n'], 111)
            self.assertEqual(model['diagnostics']['income_design_rank'], 2)
            self.assertEqual(model['coverage']['charter'], {'No': 110, 'Yes': 1})
            self.assertEqual(model['coverage']['school_types'], {'Regular School': 111})
            self.assertEqual(model['coverage']['excluded_configuration_records'], [])
            self.assertEqual(model['coverage']['mixed_g38_pairs_outside_population'], 6)
            self.assertEqual(model['independent_verification']['explicit_deleted_fits'], 111)
            self.assertTrue(all(v is None or v < audit.VERIFY_TOLERANCE for v in model['independent_verification']['maximum_absolute_errors'].values()))
            charter = next(r for r in model['inputs'] if r['school_id'] == '130255003991')
            self.assertEqual(charter['sources']['native_school_id'], 'GA-667-1020')
            self.assertEqual(charter['charter'], 'Yes')
            self.assertTrue(all(r['sources']['offered_evidence']['strict_pure_offered_lower'] is True and r['income_year'] == 2025 for r in model['inputs']))
            self.assertTrue(all(r['income_pct'] > 0 for r in model['inputs']))
        self.assertEqual(hashlib.sha256(audit.ROSTER.read_bytes()).hexdigest(), audit.ROSTER_SHA)
        with mock.patch.object(audit.roster_audit.zipfile, 'ZipFile', side_effect=AssertionError('No originals')), \
                mock.patch.object(audit.roster_audit.subprocess, 'Popen', side_effect=AssertionError('No raw stream')), \
                mock.patch.object(audit.roster_audit.georgia, 'membership_cache', side_effect=AssertionError('No ignored cache')):
            self.assertEqual(audit.validate(self.document), audit.validate(self.document, self.expected))

    def test_external_studentization_cook_and_line_shift_match_manual_deletions(self):
        for model in self.document['models']:
            x = np.array([r['income_pct'] for r in model['inputs']])
            y = np.array([r['outcome_pct'] for r in model['inputs']])
            n = len(x); results = model['results']
            X = np.column_stack([np.ones(n), x - x.mean()])
            b = np.linalg.lstsq(X, y, rcond=None)[0]
            full_residual = y - X @ b
            full_scale2 = float(full_residual @ full_residual) / (n - 2)
            self.assertEqual(n - 3, 108)
            indices = {0, n - 1, max(range(n), key=lambda i: results[i]['leverage']),
                       max(range(n), key=lambda i: abs(results[i]['studentized'])),
                       next(i for i, r in enumerate(model['inputs']) if r['school_id'] == '130255003991')}
            for i in indices:
                keep = np.arange(n) != i
                mean_x = x[keep].mean()
                D = np.column_stack([np.ones(n - 1), x[keep] - mean_x])
                beta = np.linalg.lstsq(D, y[keep], rcond=None)[0]
                residual = y[keep] - D @ beta
                deleted_sse = float(residual @ residual)
                scale = math.sqrt(deleted_sse / (n - 3))
                held_out = np.array([1., x[i] - mean_x])
                deleted_h = float(held_out @ np.linalg.inv(D.T @ D) @ held_out)
                t = (y[i] - held_out @ beta) / (scale * math.sqrt(1 + deleted_h))
                h = float(X[i] @ np.linalg.inv(X.T @ X) @ X[i])
                cook = full_residual[i] ** 2 * h / (2 * full_scale2 * (1 - h) ** 2)
                endpoints = np.array([x.min(), x.max()])
                full_line = b[0] + b[1] * (endpoints - x.mean())
                deleted_line = beta[0] + beta[1] * (endpoints - mean_x)
                with self.subTest(subject=model['subject'], school=results[i]['school_id']):
                    self.assertAlmostEqual(t, results[i]['studentized'], delta=2e-10)
                    self.assertAlmostEqual(deleted_sse, results[i]['deleted_sse'], delta=2e-9)
                    self.assertAlmostEqual(cook, results[i]['cooks_distance'], delta=2e-10)
                    self.assertAlmostEqual(float(np.max(np.abs(full_line - deleted_line))), results[i]['maximum_prediction_change_on_observed_income_range'], delta=2e-10)

    def test_combined_equal_native_rates_have_their_own_residual_scale(self):
        models = {m['subject']: m for m in self.document['models']}
        for school in models['combined']['inputs']:
            values = school['outcome_by_subject']
            self.assertEqual(school['outcome_pct'], (values['math'] + values['reading']) / 2)
            for subject in ['math', 'reading']:
                row = school['sources']['assessment_rows_by_subject'][subject]['raw']
                self.assertEqual(values[subject], 100 * audit.roster_audit.georgia.exact_rate(row['ProficientOrAbove_percent']))
                self.assertEqual(row['GradeLevel'], 'G38')
                self.assertEqual(row['StateAssignedSchID'], school['sources']['native_school_id'][3:])
        for field in ['intercept', 'slope']:
            self.assertAlmostEqual(models['combined']['coefficients'][field], (models['math']['coefficients'][field] + models['reading']['coefficients'][field]) / 2, delta=2e-10)
        self.assertTrue(any(abs(c['studentized'] - (m['studentized'] + e['studentized']) / 2) > .01
                            for c, m, e in zip(models['combined']['results'], models['math']['results'], models['reading']['results'])))
        changed = copy.deepcopy(models['combined']['inputs']); changed[0]['outcome_pct'] += 1.
        with self.assertRaisesRegex(ValueError, 'exact equally weighted'):
            audit.fit_audited_model(changed, models['combined']['coverage'], 'combined')

    def test_point_only_internal_sentinel_never_becomes_public_uncertainty(self):
        for model in self.document['models']:
            self.assertFalse(model['intervals']['available_for_entire_model'])
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
        self.assertTrue(np.array_equal(passed[0], np.zeros(111)))
        self.assertTrue(all(r['low'] is None and r['high'] is None and r['sampling_variance'] is None for r in result['results']))
        for mutate in [lambda r: r.update(sampling_variance=0.), lambda r: r.update(display_valid_scores=10),
                       lambda r: r['valid_scores_by_subject'].update(math=10)]:
            changed = copy.deepcopy(model['inputs']); mutate(changed[0])
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, 'fabricated'):
                audit.fit_audited_model(changed, model['coverage'], model['subject'])

    def test_floor_rank_full_deleted_scales_and_native_scope_are_hard_gates(self):
        model = self.document['models'][0]; inputs = model['inputs']
        with self.assertRaisesRegex(ValueError, 'at least 30'): audit.fit_audited_model(inputs[:29], model['coverage'], 'math')
        with self.assertRaisesRegex(ValueError, 'rank two'): audit.fit_audited_model([dict(r, income_pct=20.) for r in inputs], model['coverage'], 'math')
        exact_line = [dict(r, outcome_pct=10. + .5 * r['income_pct']) for r in inputs]
        with self.assertRaisesRegex(ValueError, 'no studentization scale'): audit.fit_audited_model(exact_line, model['coverage'], 'math')
        exact_line[0]['outcome_pct'] += 1.
        with self.assertRaisesRegex(ValueError, '[Dd]eleted-school residual (variance|scale)'): audit.fit_audited_model(exact_line, model['coverage'], 'math')
        singular_deletion = [dict(r, income_pct=20.) for r in inputs]; singular_deletion[0]['income_pct'] = 30.
        with self.assertRaisesRegex(ValueError, 'singular or numerically unstable'): audit.fit_audited_model(singular_deletion, model['coverage'], 'math')
        for field, value in [('level', 'HS'), ('income_year', 2024), ('income_year', 2025.), ('income_pct', False),
                             ('school_id', '130255004683'), ('ncessch', '130000000001'), ('income_pct', float('nan')), ('outcome_pct', 101.)]:
            changed = copy.deepcopy(inputs); changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): audit.fit_audited_model(changed, model['coverage'], 'math')
        with self.assertRaises(ValueError): audit.fit_audited_model(inputs[:-1] + [inputs[0]], model['coverage'], 'math')
        for mutate in [lambda r: r['sources']['offered_evidence'].update(graded_scope='mixed'),
                       lambda r: r['sources']['offered_evidence'].update(offered_tested_grades=[]),
                       lambda r: r['sources']['offered_evidence'].update(strict_pure_offered_lower=1),
                       lambda r: r['sources']['enrolled_evidence'].update(native_grade_school_contract=False),
                       lambda r: r['sources']['directory_raw'].update(UPDATED_STATUS='2'),
                       lambda r: r['sources'].update(native_school_id='GA-667-9999')]:
            changed = copy.deepcopy(inputs); mutate(changed[0])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): audit.fit_audited_model(changed, model['coverage'], 'math')

    def test_independent_verification_rejects_wrong_or_nonfinite_fitter_results(self):
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

    def test_typed_source_population_uncertainty_and_material_metrics_fail_replay(self):
        mutations = [
            lambda d: d.update(approved_for_modeling=True), lambda d: d.update(approved_for_source=0),
            lambda d: d['source_coverage'].update(verified_valid_score_counts=False),
            lambda d: d['sources']['roster_audit'].update(sha256='0' * 64),
            lambda d: d['retained_source_evidence']['raw_inputs']['membership']['records'][0]['raw'].update(STUDENT_COUNT='0'),
            lambda d: d['retained_source_evidence']['raw_inputs']['assessment']['records'][0]['raw'].update(ProficientOrAbove_percent='*'),
            lambda d: d['retained_source_evidence']['raw_inputs']['definitions']['georgia_rows_and_headers'][0]['rows'].pop(),
            lambda d: d['frozen_population']['later_release_note_roster_gaps'].clear(),
            lambda d: d['frozen_population']['eligible_school_ids_by_subject']['math'].pop(),
            lambda d: d['models'][0].update(approved_for_modeling=0),
            lambda d: d['models'][0]['independent_verification'].update(tolerance_absolute=2e-9 + 1e-12),
            lambda d: d['models'][0]['inputs'][0].update(income_pct=d['models'][0]['inputs'][0]['income_pct'] + 1e-12),
            lambda d: d['models'][0]['inputs'][0].update(income_year=2024),
            lambda d: d['models'][0]['inputs'][0]['sources'].update(income_source_row=99999),
            lambda d: d['models'][0]['inputs'][0]['sources']['income_raw'].update(STUDENT_COUNT=False),
            lambda d: d['models'][0]['inputs'][0]['sources']['directory_raw'].update(ST_SCHID='GA-667-9999'),
            lambda d: d['models'][0]['inputs'][0]['valid_scores_by_subject'].update(math=10),
            lambda d: d['models'][0]['inputs'][0].update(sampling_variance=0.),
            lambda d: d['models'][0]['coverage'].update(usable_schools=112),
            lambda d: d['models'][0]['coefficients'].update(n=111.),
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

    def test_computed_float_tolerance_is_narrow_and_does_not_relax_exact_sources(self):
        changed = copy.deepcopy(self.document)
        changed['models'][0]['coefficients']['intercept'] += 1e-11
        changed['models'][0]['results'][0]['studentized'] += 1e-11
        self.assertEqual(audit.validate(changed, self.expected), audit.validate(self.document, self.expected))
        changed['models'][0]['results'][0]['studentized'] = float('nan')
        with self.assertRaises(ValueError): audit.validate(changed, self.expected)


if __name__ == '__main__':
    unittest.main()
