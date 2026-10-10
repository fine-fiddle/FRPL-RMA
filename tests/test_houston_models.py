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
import audit_houston_models as audit


class HoustonPublishedModelAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = audit.load_roster()
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.expected = audit.build(cls.roster)

    def test_distinct_point_only_policy_preserves_source_and_open_count_hold(self):
        self.assertEqual(audit.validate(self.document, self.expected), {f'houston-published-2025-ES-{s}': 210 for s in audit.SUBJECTS})
        self.assertEqual(self.document['hard_holds'], [])
        self.assertIs(self.document['approved_for_source'], False)
        self.assertIs(self.document['approved_for_modeling'], False)
        self.assertEqual(self.document['status'], 'numerically_verified_pending_integration')
        self.assertEqual(self.document['scope'], 'published_rate_only_numerical_audit')
        self.assertNotIn('snapshots', self.document)
        self.assertEqual(self.document['count_definition_hold']['issue_number'], 16)
        self.assertIs(self.document['count_definition_hold']['ten_valid_scored_floor_certified'], False)
        self.assertIs(self.document['count_definition_hold']['numerical_success_resolves_hold'], False)
        self.assertEqual(self.document['retained_source_evidence']['source_approval'], {'approved_for_source': False, 'approved_for_modeling': False})
        self.assertEqual(self.document['retained_source_evidence']['source_policy'], self.roster['policy'])
        self.assertEqual(self.document['source_coverage'], self.roster['coverage'])
        self.assertEqual(self.document['source_coverage']['model_results'], 0)
        self.assertIs(self.document['source_coverage']['canonical_import_performed'], False)
        self.assertIs(self.document['source_coverage']['served_comparison_created'], False)
        self.assertEqual(hashlib.sha256(audit.ROSTER.read_bytes()).hexdigest(), audit.ROSTER_SHA)
        self.assertEqual(audit.roster_audit.fingerprint(self.document['retained_source_evidence']['raw_inputs']), audit.roster_audit.RAW_INPUT_SHA)
        with mock.patch.object(audit.roster_audit.zipfile, 'ZipFile', side_effect=AssertionError('No original archive')), \
                mock.patch.object(audit.roster_audit.subprocess, 'Popen', side_effect=AssertionError('No original stream')):
            self.assertEqual(audit.validate(self.document), audit.validate(self.document, self.expected))

    def test_exact_population_and_explicit_suppressed_outside_records(self):
        population = self.document['frozen_population']
        for field, count in [('complete_directory_ncessch', 274), ('operational_roster_school_ids', 274),
                             ('native_source_profile_ids', 273), ('native_grade_school_configuration_ids', 212),
                             ('native_primary_only_ids', 10), ('native_high_school_ids', 42),
                             ('native_mixed_school_ids', 9), ('missing_native_school_ids', 1)]:
            self.assertEqual(len(population[field]), count)
        self.assertEqual(len(self.document['retained_scope_exclusions']['outside_native_configuration_records']), 62)
        outsiders = {r['native_school_id']: r for r in self.document['retained_scope_exclusions']['outside_native_configuration_records']}
        rogers = outsiders['101912039']
        self.assertEqual(rogers['native_reference']['GRDTYPE'], 'E')
        self.assertEqual(rogers['native_enrolled']['scope'], 'mixed')
        self.assertEqual(rogers['native_enrolled']['high_enrollment'], 31)
        self.assertIn('101912466', outsiders)
        self.assertFalse(outsiders['101912466']['native_present'])
        for model in self.document['models']:
            self.assertEqual([r['school_id'] for r in model['inputs']], population['eligible_school_ids_by_subject'][model['subject']])
            self.assertEqual(model['coefficients']['n'], 210)
            self.assertEqual(model['coverage']['charter'], {'No': 207, 'Yes': 3})
            self.assertEqual(model['coverage']['native_grade_school_configuration_profiles'], 212)
            self.assertIs(model['coverage']['ten_valid_scored_floor_certified'], False)
            exclusions = {r['native_school_id']: r for r in model['coverage']['excluded_configuration_records']}
            self.assertEqual(set(exclusions), {'101912340', '101912402'})
            for subject in ['math', 'reading']:
                self.assertEqual(exclusions['101912340']['published_subjects'][subject]['raw_published_rate'], '')
                self.assertEqual(exclusions['101912402']['published_subjects'][subject]['raw_published_rate'], '-1')
                self.assertIsNone(exclusions['101912340']['published_subjects'][subject]['published_rate'])
                self.assertIsNone(exclusions['101912402']['published_subjects'][subject]['published_rate'])
            self.assertTrue(all(r['native_school_id'] not in outsiders for r in model['inputs']))
            self.assertEqual(model['independent_verification']['explicit_deleted_fits'], 210)
            self.assertEqual(model['independent_verification']['deleted_training_members'], 209)
            self.assertEqual(model['independent_verification']['deleted_residual_degrees_of_freedom'], 207)
            self.assertTrue(all(v is None or v < audit.VERIFY_TOLERANCE for v in model['independent_verification']['maximum_absolute_errors'].values()))

    def test_native_display_outcomes_and_same_year_income_are_exact(self):
        counts_different = {'math': 0, 'reading': 0}
        income_rounding, income_membership = 0, 0
        for school in self.document['models'][0]['inputs']:
            native = school['sources']['native_student']['raw']
            total, ed, other = [int(native[k]) for k in ['CPNTALLC', 'CPNTECOC', 'CPNTNEDC']]
            self.assertEqual(ed + other, total)
            self.assertEqual(school['income_pct'], 100 * ed / total)
            self.assertEqual(school['income_year'], 2025)
            self.assertEqual(school['sources']['native_income_evidence']['snapshot_date'], '2024-10-25')
            income_rounding += school['income_pct'] != float(native['CPNTECOP'])
            income_membership += total != int(native['CPETALLC'])
            self.assertEqual(school['school_id'], school['ncessch'])
            self.assertEqual(school['sources']['directory_raw']['ST_SCHID'], 'TX-101912-' + school['native_school_id'])
            self.assertEqual(school['sources']['directory_raw']['NCESSCH'], school['school_id'])
            self.assertEqual(school['sources']['native_grade_evidence']['scope'], 'grade-school')
            assessment = school['sources']['native_assessment']['raw']
            for subject in ['math', 'reading']:
                rate = school['outcome_by_subject'][subject]
                self.assertEqual(rate, int(assessment[audit.roster_audit.FIELDS[subject][2]]))
                counts_different[subject] += rate != school['sources']['unverified_reported_subject_evidence'][subject]['proficiency']
        self.assertEqual(counts_different, {'math': 202, 'reading': 203})
        self.assertGreater(income_rounding, 0)
        self.assertGreater(income_membership, 0)
        for model in self.document['models']:
            for school in model['inputs']:
                expected = ((school['outcome_by_subject']['math'] + school['outcome_by_subject']['reading']) / 2
                            if model['subject'] == 'combined' else school['outcome_by_subject'][model['subject']])
                self.assertEqual(school['outcome_pct'], expected)
            self.assertEqual(sum(r['outcome_pct'] for r in model['inputs']), {'math': 9832., 'reading': 10724., 'combined': 10278.}[model['subject']])

    def test_published_rate_availability_never_uses_reported_count_or_source_screen(self):
        row = copy.deepcopy(self.roster['raw_inputs']['assessment']['records'][0]['raw'])
        for subject in ['math', 'reading']:
            field = audit.roster_audit.FIELDS[subject][2]
            for raw, expected in [('0', 0.), ('100', 100.), ('', None), ('-1', None), ('-2', None), ('-3', None), ('*', None), ('**', None), ('•', None)]:
                row[field] = raw
                for count_value in ['0', '1', '9', '10', '', '-1', 'not-a-count']:
                    row[audit.roster_audit.FIELDS[subject][0]] = count_value
                    row[audit.roster_audit.FIELDS[subject][1]] = count_value
                    evidence = audit.published_rate_evidence(row, subject)
                    self.assertEqual(evidence['published_rate'], expected)
                    self.assertEqual(evidence['available'], expected is not None)
                    self.assertIsNone(evidence['valid_scores'])
                    self.assertIsNone(evidence['sampling_variance'])
            for bad in ['101', '1.5', '-4', 'NaN', 'Infinity', 'x', False, 12]:
                row[field] = bad
                with self.subTest(subject=subject, bad=bad), self.assertRaises(ValueError):
                    audit.published_rate_evidence(row, subject)
        changed = copy.deepcopy(self.roster)
        for row in changed['raw_inputs']['assessment']['records']:
            for subject in ['math', 'reading']:
                for field in audit.roster_audit.FIELDS[subject][:2]: row['raw'][field] = '0'
        for school in changed['roster_links']:
            for value in school['subjects'].values():
                value.update(source_usable=False, native_fields_usable=False, proficiency=None)
        for subject in audit.SUBJECTS:
            before, _ = audit.selected_inputs(self.roster, subject)
            after, _ = audit.selected_inputs(changed, subject)
            self.assertEqual([(r['school_id'], r['income_pct'], r['outcome_pct']) for r in before],
                             [(r['school_id'], r['income_pct'], r['outcome_pct']) for r in after])
        with self.assertRaises(ValueError): audit.build(changed)

    def test_external_studentization_influence_and_line_shift_match_every_manual_deletion(self):
        for model in self.document['models']:
            x = np.array([r['income_pct'] for r in model['inputs']]); y = np.array([r['outcome_pct'] for r in model['inputs']])
            n = len(x); X = np.column_stack([np.ones(n), x - x.mean()])
            beta = np.linalg.lstsq(X, y, rcond=None)[0]; full_residual = y - X @ beta
            full_scale2 = float(full_residual @ full_residual) / (n - 2)
            for i, row in enumerate(model['results']):
                keep = np.arange(n) != i; mean_x = x[keep].mean()
                D = np.column_stack([np.ones(n - 1), x[keep] - mean_x]); b = np.linalg.lstsq(D, y[keep], rcond=None)[0]
                residual = y[keep] - D @ b; deleted_sse = float(residual @ residual)
                scale = math.sqrt(deleted_sse / (n - 3)); held_out = np.array([1., x[i] - mean_x])
                deleted_h = float(held_out @ np.linalg.inv(D.T @ D) @ held_out)
                t = (y[i] - held_out @ b) / (scale * math.sqrt(1 + deleted_h))
                h = float(X[i] @ np.linalg.inv(X.T @ X) @ X[i])
                cook = full_residual[i] ** 2 * h / (2 * full_scale2 * (1 - h) ** 2)
                endpoints = np.array([x.min(), x.max()])
                full_line = beta[0] + beta[1] * (endpoints - x.mean()); deleted_line = b[0] + b[1] * (endpoints - mean_x)
                with self.subTest(subject=model['subject'], school=row['school_id']):
                    self.assertAlmostEqual(t, row['studentized'], delta=2e-10)
                    self.assertAlmostEqual(deleted_sse, row['deleted_sse'], delta=2e-9)
                    self.assertAlmostEqual(cook, row['cooks_distance'], delta=2e-10)
                    self.assertAlmostEqual(float(np.max(np.abs(full_line - deleted_line))), row['maximum_prediction_change_on_observed_income_range'], delta=2e-10)

    def test_combined_has_separate_residual_scale_not_averaged_studentization(self):
        models = {m['subject']: m for m in self.document['models']}
        for field in ['intercept', 'slope']:
            self.assertAlmostEqual(models['combined']['coefficients'][field], (models['math']['coefficients'][field] + models['reading']['coefficients'][field]) / 2, delta=2e-10)
        self.assertTrue(any(abs(c['studentized'] - (m['studentized'] + e['studentized']) / 2) > .01
                            for c, m, e in zip(models['combined']['results'], models['math']['results'], models['reading']['results'])))

    def test_point_only_sentinel_never_becomes_a_verified_count_variance_or_interval(self):
        for model in self.document['models']:
            self.assertIs(model['intervals']['available_for_entire_model'], False)
            self.assertIsNone(model['intervals']['valid_score_counts']); self.assertIsNone(model['intervals']['sampling_variances'])
            self.assertIs(model['valid_score_floor_certified'], False)
            for school in model['inputs']:
                self.assertEqual(school['valid_scores_by_subject'], {'math': None, 'reading': None})
                self.assertIsNone(school['display_valid_scores']); self.assertIsNone(school['sampling_variance'])
            for row in model['results']:
                self.assertTrue(all(row[k] is None for k in ['valid_scores', 'sampling_variance', 'low', 'high']))
        model = self.document['models'][0]; real_fit = audit.fit_model; passed = []
        def capture(x, y, variance):
            passed.append(variance.copy()); return real_fit(x, y, variance)
        with mock.patch.object(audit, 'fit_model', side_effect=capture):
            result = audit.fit_audited_model(model['inputs'], model['coverage'], model['subject'])
        self.assertTrue(np.array_equal(passed[0], np.zeros(210)))
        self.assertTrue(all(r['low'] is None and r['high'] is None and r['sampling_variance'] is None for r in result['results']))
        for mutate in [lambda r: r.update(sampling_variance=0.), lambda r: r.update(display_valid_scores=10),
                       lambda r: r['valid_scores_by_subject'].update(math=10)]:
            changed = copy.deepcopy(model['inputs']); mutate(changed[0])
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, 'exact frozen native'):
                audit.fit_audited_model(changed, model['coverage'], model['subject'])

    def test_floor_rank_deleted_scale_and_complete_native_membership_are_hard_gates(self):
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
        with self.assertRaisesRegex(ValueError, 'complete eligible membership'):
            audit.fit_audited_model(inputs[:-1], model['coverage'], 'math')
        for field, value in [('level', 'HS'), ('income_year', 2024), ('income_year', 2025.), ('income_pct', False),
                             ('school_id', '482364001272'), ('native_school_id', '101912999'), ('income_pct', float('nan')),
                             ('outcome_pct', 101.), ('outcome_basis', 'count_ratio')]:
            changed = copy.deepcopy(inputs); changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): audit.fit_audited_model(changed, model['coverage'], 'math')
        changed = copy.deepcopy(inputs); changed[0]['outcome_pct'] = changed[0]['sources']['unverified_reported_subject_evidence']['math']['proficiency']
        with self.assertRaisesRegex(ValueError, 'exact frozen native'): audit.fit_audited_model(changed, model['coverage'], 'math')
        with self.assertRaises(ValueError): audit.fit_audited_model(inputs[:-1] + [inputs[0]], model['coverage'], 'math')
        for mutate in [lambda r: r['sources']['native_grade_evidence'].update(scope='mixed'),
                       lambda r: r['sources']['native_grade_evidence'].update(high_enrollment=1),
                       lambda r: r['sources']['native_student']['raw'].update(CPNTG09C='1'),
                       lambda r: r['sources']['directory_raw'].update(UPDATED_STATUS='2'),
                       lambda r: r['sources']['native_assessment']['raw'].update(DISTRICT='101999')]:
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

    def test_source_policy_count_hold_frozen_membership_and_diagnostics_reject_corruption(self):
        mutations = [
            lambda d: d.update(approved_for_modeling=True), lambda d: d.update(approved_for_source=0),
            lambda d: d['count_definition_hold'].update(ten_valid_scored_floor_certified=True),
            lambda d: d['count_definition_hold'].update(numerical_success_resolves_hold=True),
            lambda d: d['policy'].update(outcome='count ratios'),
            lambda d: d['sources']['roster_audit'].update(sha256='0' * 64),
            lambda d: d['retained_source_evidence']['source_approval'].update(approved_for_source=True),
            lambda d: d['retained_source_evidence']['raw_inputs']['stud']['records'][0]['raw'].update(CPNTECOC='0'),
            lambda d: d['retained_source_evidence']['raw_inputs']['assessment']['records'][0]['raw'].update(CDA38AM0E225R='0'),
            lambda d: d['retained_scope_exclusions']['outside_native_configuration_records'].clear(),
            lambda d: d['frozen_population']['eligible_school_ids_by_subject']['math'].pop(),
            lambda d: d['models'][0].update(approved_for_modeling=0),
            lambda d: d['models'][0].update(outcome_basis='count_ratio'),
            lambda d: d['models'][0].update(valid_score_floor_certified=True),
            lambda d: d['models'][0]['independent_verification'].update(tolerance_absolute=2e-9 + 1e-12),
            lambda d: d['models'][0]['independent_verification'].update(deleted_residual_degrees_of_freedom=208),
            lambda d: d['models'][0]['inputs'][0].update(income_pct=d['models'][0]['inputs'][0]['income_pct'] + 1e-12),
            lambda d: d['models'][0]['inputs'][0].update(income_year=2024),
            lambda d: d['models'][0]['inputs'][0]['sources']['native_source_rows'].update(assessment=99999),
            lambda d: d['models'][0]['inputs'][0]['sources']['native_student']['raw'].update(CPNTALLC='1'),
            lambda d: d['models'][0]['inputs'][0]['valid_scores_by_subject'].update(math=10),
            lambda d: d['models'][0]['inputs'][0].update(sampling_variance=0.),
            lambda d: d['models'][0]['coverage'].update(usable_schools=211),
            lambda d: d['models'][0]['coefficients'].update(n=210.),
            lambda d: d['models'][0]['coefficients'].update(slope=-.1),
            lambda d: d['models'][0]['results'][0].update(actual=0.),
            lambda d: d['models'][0]['results'][0].update(studentized=99.),
            lambda d: d['models'][0]['results'][0].update(deleted_slope=0.),
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

    def test_computed_float_tolerance_does_not_relax_source_or_hold_metadata(self):
        changed = copy.deepcopy(self.document)
        changed['models'][0]['coefficients']['intercept'] += 1e-11
        changed['models'][0]['results'][0]['studentized'] += 1e-11
        self.assertEqual(audit.validate(changed, self.expected), audit.validate(self.document, self.expected))
        changed['models'][0]['results'][0]['studentized'] = float('nan')
        with self.assertRaises(ValueError): audit.validate(changed, self.expected)

    def test_numerical_failure_is_retained_as_hold_and_rebuilds_are_identical(self):
        with mock.patch.object(audit, 'fit_model', side_effect=ValueError('Unresolved deleted scale')):
            held = audit.build(self.roster)
        self.assertEqual(held['status'], 'numerical_hold')
        self.assertEqual(len(held['hard_holds']), 3)
        self.assertTrue(all(m['status'] == 'numerical_hold' and 'results' not in m for m in held['models']))
        self.assertEqual(audit.validate(held, held), {f'houston-published-2025-ES-{s}': 210 for s in audit.SUBJECTS})
        self.assertEqual(held['count_definition_hold'], audit.COUNT_HOLD)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'models.json'
            audit.prepare(path); first = path.read_bytes()
            audit.prepare(path)
            self.assertEqual(path.read_bytes(), first)
            self.assertEqual(first, audit.OUTPUT.read_bytes())
            audit.prepare(path, check=True)


if __name__ == '__main__':
    unittest.main()
