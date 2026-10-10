import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_houston as audit


class HoustonSourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.inputs = cls.document['raw_inputs']
        cls.links = {r['native_school_id']: r for r in cls.document['roster_links']}
        cls.native = {r['raw']['CAMPUS']: r['raw'] for r in cls.inputs['stud']['records']}
        cls.outcomes = {r['raw']['CAMPUS']: r['raw'] for r in cls.inputs['assessment']['records']}

    def test_exact_source_only_counts_and_no_approval(self):
        c = audit.validate(self.document)
        self.assertEqual((c['directory_records'], c['operational_schools'], c['native_campuses']), (274, 274, 273))
        self.assertEqual(c['native_scope_counts'], {'grade-school': 212, 'high': 42, 'mixed': 9, 'primary-only': 10})
        self.assertEqual(c['prospective_subject_members'], {'math': 210, 'reading': 210, 'combined': 210})
        self.assertEqual(c['ccd_school_types'], {'Alternative School': 10, 'Regular School': 261, 'Special Education School': 3})
        self.assertEqual(c['ccd_charter'], {'No': 267, 'Yes': 7})
        self.assertEqual(self.document['scope'], 'source_cohort_audit_only')
        self.assertEqual(self.document['status'], 'audit_pending')
        self.assertIs(self.document['approved_for_source'], False)
        self.assertIs(self.document['approved_for_modeling'], False)
        for field in ['models', 'model_runs', 'model_results', 'residuals']:
            self.assertNotIn(field, self.document)
        self.assertEqual(c['verified_valid_score_counts'], 0)
        self.assertFalse(c['sampling_intervals_available'])
        self.assertEqual(c['reported_reconciled_performance_denominators'], {'math': 217, 'reading': 217})
        self.assertIn('N/NAAR', c['valid_score_verification_hold'])

    def test_exact_native_and_full_ccd_ids(self):
        native = self.native['101912068']
        self.assertEqual(audit.native_identity(dict(native, CAMPNAME='Renamed school')), '101912068')
        directory = self.inputs['directory']['records'][0]['raw']
        self.assertEqual(audit.ccd_identity(directory), ('482364001271', '101912068'))
        self.assertEqual(directory['ST_SCHID'], 'TX-101912-101912068')
        for field, value in [('CAMPUS', 101912068), ('CAMPUS', '10191268'), ('CAMPUS', '101913068'), ('DISTRICT', '101913')]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                audit.native_identity(dict(native, **{field: value}))
        for field, value in [('ST_SCHID', 'TX-101912068'), ('ST_SCHID', 'TX-101912-101913068'), ('ST_LEAID', 'TX-101913'), ('LEAID', '4823641'), ('SCHOOL_YEAR', '2023-2024')]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                audit.ccd_identity(dict(directory, **{field: value}))

    def test_complete_native_enrollment_never_reference_type_selects(self):
        r = self.links['101912039']
        self.assertEqual(r['native_reference']['GRDTYPE'], 'E')
        self.assertEqual(r['native_reference']['GRDSPAN'], 'EE - 08')
        self.assertEqual(r['native_enrolled']['high_enrollment'], 31)
        self.assertEqual([r['native_enrolled']['counts']['CPNTG%02dC' % g] for g in range(9, 13)], [4, 7, 7, 13])
        self.assertEqual(r['native_enrolled']['scope'], 'mixed')
        self.assertFalse(r['subjects']['combined']['source_usable'])
        self.assertTrue(r['native_reference_conflicts_with_positive_high_enrollment'])
        self.assertEqual(self.document['coverage']['native_reference_high_grade_contradictions'], ['101912039'])
        altered = dict(self.native['101912068'], CPNTG09C='1')
        with self.assertRaises(ValueError): audit.grade_evidence(altered)
        altered['CPNTALLC'] = str(int(altered['CPNTALLC']) + 1)
        self.assertEqual(audit.grade_evidence(altered)['scope'], 'mixed')
        missing = dict(self.native['101912068'], CPNTG09C='-1')
        self.assertEqual(audit.grade_evidence(missing)['scope'], 'unknown')
        self.assertFalse(audit.grade_evidence(missing)['prospective_grade_school'])

    def test_primary_and_absent_reported_zero_are_retained(self):
        primary = self.document['cohorts']['primary_only']
        self.assertEqual(primary['profiles'], 10)
        self.assertTrue(all(primary['subjects'][s]['usable'] == 0 for s in ['math', 'reading', 'combined']))
        self.assertTrue(all(self.links[k]['native_enrolled']['tested_grades_enrollment'] == 0 for k in primary['native_school_ids']))
        missing = self.links['101912466']
        self.assertEqual(missing['school_id'], '482364012656')
        self.assertEqual(missing['name'], 'EL DAEP')
        self.assertEqual(missing['ccd_membership']['reported_total'], 0)
        self.assertFalse(missing['native_present'])
        self.assertIsNone(missing['native_enrolled'])
        self.assertIsNone(missing['income']['percentage'])
        self.assertIsNone(missing['subjects']['math']['proficiency'])
        self.assertEqual(len(self.document['outside_grade_school_population']), 62)
        self.assertEqual(self.document['cohorts']['native_no_high_grade_profiles']['profiles'], 222)

    def test_exact_individual_income_and_distinct_membership(self):
        e = self.document['enrollment_reconciliation']
        self.assertEqual([e[k] for k in ['ccd_lea_reported', 'ccd_operational_school_sum', 'native_campus_sum']], [176727] * 3)
        self.assertEqual(e['native_economic_disadvantage_sum'], 137435)
        self.assertEqual(e['native_peims_membership_sum'], 176039)
        self.assertEqual(len(e['native_enrollment_membership_differences']), 150)
        self.assertEqual(e['matched_school_enrollment_differences'], [])
        for k, raw in self.native.items():
            income = audit.income_evidence(raw)
            self.assertEqual(income['economic_disadvantage'] + income['not_economic_disadvantage'], income['enrollment'])
            self.assertEqual(income['percentage'], 100 * int(raw['CPNTECOC']) / int(raw['CPNTALLC']))
            self.assertEqual(income['snapshot_date'], '2024-10-25')
        raw = dict(self.native['101912275'])
        self.assertNotEqual(raw['CPNTALLC'], raw['CPETALLC'])
        with self.assertRaises(ValueError): audit.income_evidence(dict(raw, CPNTALLC=raw['CPETALLC']))
        total = raw['CPNTALLC']
        zero = audit.income_evidence(dict(raw, CPNTECOC='0', CPNTNEDC=total, CPNTECOP='0'))
        self.assertEqual(zero['percentage'], 0)
        self.assertIsNone(zero['exclusion'])
        self.assertIsNone(audit.income_evidence(dict(raw, CPNTECOC='-1'))['percentage'])

    def test_source_ratios_reconcile_without_valid_score_promotion(self):
        cohort = self.document['cohorts']['prospective_grade_school']
        for subject, expected in [('math', (62468, 30826, 72)), ('reading', (62519, 33808, 72))]:
            members = [self.links[k]['subjects'][subject] for k in cohort['subjects'][subject]['prospective_native_school_ids']]
            self.assertEqual((sum(r['reported_tested'] for r in members), sum(r['reported_meets_or_above'] for r in members), min(r['reported_tested'] for r in members)), expected)
            for row in members:
                self.assertEqual(row['proficiency'], 100 * row['reported_meets_or_above'] / row['reported_tested'])
                self.assertLessEqual(abs(row['proficiency'] - row['published_rate']), .500001)
                self.assertIsNone(row['valid_scores'])
                self.assertIsNone(row['sampling_variance'])
                self.assertFalse(row['sampling_interval_available'])
                self.assertIn('held', row['valid_score_verification_status'])
            self.assertTrue(cohort['subjects'][subject]['prospective_30_school_floor_met'])
            self.assertFalse(cohort['subjects'][subject]['approved_for_modeling'])
            self.assertIn('does not certify', cohort['subjects'][subject]['availability_note'])

    def test_missing_masked_and_true_zero_outcomes_are_distinct(self):
        for k, expected in [('101912340', ['', '', '']), ('101912402', ['-1', '-1', '-1'])]:
            row = self.links[k]['subjects']['math']
            self.assertEqual(row['raw'], expected)
            self.assertIsNone(row['proficiency'])
            self.assertFalse(row['source_usable'])
            self.assertIn('missing or masked', row['exclusion'])
        income = audit.income_evidence(self.native['101912068'])
        raw = dict(self.outcomes['101912068'])
        fields = audit.FIELDS['math']
        for field, value in zip(fields, ['10', '0', '0']): raw[field] = value
        row = audit.subject_evidence(raw, 'math', True, income)
        self.assertEqual(row['proficiency'], 0)
        self.assertTrue(row['source_usable'])
        for mask in ['', '-1', '-2', '-3', '*', '•']:
            row = audit.subject_evidence(dict(raw, **{fields[2]: mask}), 'math', True, income)
            self.assertIsNone(row['proficiency'])
            self.assertEqual(row['reported_tested'], 10)
            self.assertIsNone(row['reported_performance_denominator'])
            self.assertFalse(row['source_usable'])
        for vals in [('4', '1', '25'), ('10', '11', '100'), ('10', '1', '80')]:
            bad = dict(raw, **dict(zip(fields, vals)))
            with self.subTest(vals=vals), self.assertRaises(ValueError): audit.subject_evidence(bad, 'math', True, income)

    def test_prospective_reported_ten_screen_does_not_certify_scored_floor(self):
        raw = dict(self.outcomes['101912068'], **dict(zip(audit.FIELDS['math'], ['5', '1', '20'])))
        income = audit.income_evidence(self.native['101912068'])
        row = audit.subject_evidence(raw, 'math', True, income)
        self.assertEqual(row['reported_performance_denominator'], 5)
        self.assertFalse(row['source_usable'])
        self.assertIn('reported performance tests', row['exclusion'])
        self.assertIn('verification held', row['exclusion'])
        self.assertIsNone(row['valid_scores'])
        self.assertIsNone(row['sampling_variance'])

    def test_combined_mean_and_outside_observations_never_pooled(self):
        for r in self.document['roster_links']:
            m, e, c = [r['subjects'][s] for s in ['math', 'reading', 'combined']]
            if m['proficiency'] is not None and e['proficiency'] is not None:
                self.assertEqual(c['proficiency'], (m['proficiency'] + e['proficiency']) / 2)
            else: self.assertIsNone(c['proficiency'])
            self.assertIsNone(c['valid_scores'])
        mixed = self.document['cohorts']['mixed_grade']
        self.assertEqual(mixed['profiles'], 9)
        for s in ['math', 'reading', 'combined']:
            self.assertEqual(mixed['subjects'][s]['native_fields_usable'], 7)
            self.assertEqual(mixed['subjects'][s]['usable'], 0)
            self.assertFalse(mixed['subjects'][s]['prospective_30_school_floor_met'])

    def test_complete_raw_headers_rows_and_primary_definition_proof(self):
        for source, expected in [('directory', 274), ('membership', 2157), ('lea_directory', 1), ('lea_membership', 16), ('ref', 273), ('stud', 273), ('assessment', 273)]:
            raw = self.inputs[source]
            self.assertEqual(len(raw['records']), expected)
            self.assertTrue(all(type(e['source_row']) is int and e['source_row'] >= 2 for e in raw['records']))
            self.assertTrue(all(set(e['raw']) == set(raw['header']) for e in raw['records']))
        definitions = self.inputs['definitions']
        glossary = '\n'.join(p['text'] for p in definitions['glossary']['pages'])
        for text in ['accountability subset', 'Spanish STAAR', 'STAAR Alternate 2', 'English I or II EOC', 'Algebra I EOC', 'Enrollment:', 'Membership:']:
            self.assertIn(text, glossary)
        teds = '\n'.join(p['text'] for p in definitions['income-guide']['pages'])
        for text in ['Community Eligibility Provision', 'Provision 2', 'locally developed income survey', 'not returned', 'continuously enrolled']:
            self.assertIn(text, teds)
        self.assertEqual([p['pdf_page'] for p in definitions['accountability-manual']['pages']], [173, 177, 204])
        self.assertEqual([p['pdf_page'] for p in definitions['performance-listing']['pages']], [4, 6, 8])
        self.assertEqual(len(definitions['dictionary']['lines']), 12)
        extension = '\n'.join(e['html'] for e in definitions['income-extension']['lines'])
        self.assertIn('January 16, 2025', extension)
        self.assertIn('October 25, 2024', extension)
        self.assertEqual(audit.fingerprint(self.inputs), audit.RAW_INPUT_SHA)

    def test_planning_identity_reconstruction_is_separate(self):
        p = self.document['planning_identity_reconciliation']
        self.assertEqual([len(p['potential_school_ids'][s]) for s in ['ES', 'HS']], [212, 42])
        self.assertEqual(p['source_not_planning_ES'], [])
        self.assertEqual(p['planning_ES_not_source_usable'], ['482364008608', '482364012655'])
        self.assertEqual(self.inputs['planning']['record']['directory_source_row'], 17354)
        self.assertEqual(self.inputs['planning']['record']['membership_source_row'], 3355775)
        charter = [r for r in self.document['roster_links'] if r['ccd_flags']['charter'] == 'Yes']
        self.assertEqual(len(charter), 7)
        self.assertEqual(sum(r['subjects']['combined']['source_usable'] for r in charter), 3)

    def test_missing_and_nonintegral_cells_never_zero(self):
        for raw in ['', '-1', '-2', '-3', '*', '**', '•']:
            self.assertIsNone(audit.count(raw)); self.assertIsNone(audit.number(raw))
        self.assertEqual(audit.count('0'), 0)
        self.assertEqual(audit.count('100000000000000000001'), 100000000000000000001)
        for raw in ['-4', 'nan', 'inf', 'abc', True, 1, None]:
            with self.subTest(raw=raw), self.assertRaises(ValueError): audit.count(raw)
        with self.assertRaises(ValueError): audit.count('1.5')

    def test_offline_replay_requires_no_original_download_or_fit(self):
        with mock.patch.object(audit.zipfile, 'ZipFile', side_effect=AssertionError('Original ZIP unavailable')), \
                mock.patch.object(audit.subprocess, 'Popen', side_effect=AssertionError('Original stream unavailable')):
            self.assertEqual(audit.validate(self.document)['native_campuses'], 273)

    def test_rebuild_normalizes_bootstrap_dictionary_position_for_identical_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'audit.json'
            inputs = dict(self.inputs)
            # The original-file parser emits definitions before planning, while
            # a separately extracted bootstrap can put them after planning.
            definitions = inputs.pop('definitions')
            planning = inputs.pop('planning')
            inputs['definitions'] = definitions
            inputs['planning'] = planning
            audit.build(inputs, output)
            self.assertEqual(output.read_bytes(), audit.OUTPUT.read_bytes())
            audit.build(self.inputs, output)
            self.assertEqual(output.read_bytes(), audit.OUTPUT.read_bytes())

    def test_source_and_typed_evidence_corruptions_rejected(self):
        mutations = [
            lambda d: d.update(schema_version=1.0), lambda d: d.update(year=2025.0),
            lambda d: d.update(approved_for_source=0), lambda d: d.update(approved_for_modeling=True),
            lambda d: d.update(models=[]), lambda d: d.update(status='ready'),
            lambda d: d['sources']['assessment'].update(sha256='0' * 64),
            lambda d: d['raw_inputs']['stud']['records'][0]['raw'].update(CPNTALLC='0'),
            lambda d: d['raw_inputs']['stud']['records'][0]['raw'].update(CAMPUS=101912001),
            lambda d: d['raw_inputs']['assessment']['records'][0]['raw'].update(CDA38AM0E225R='0'),
            lambda d: d['raw_inputs']['assessment']['records'][0].update(source_row=3),
            lambda d: d['raw_inputs']['directory']['records'].pop(),
            lambda d: d['raw_inputs']['membership']['records'][0]['raw'].update(DMS_FLAG='Suppressed'),
            lambda d: d['raw_inputs']['stud']['labels'].__setitem__(10, '2024'),
            lambda d: d['raw_inputs']['definitions']['performance-listing']['pages'].pop(),
            lambda d: d['raw_inputs']['planning']['record'].update(enrollment=176727.0),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): audit.validate(changed)

    def test_derived_approval_denominator_population_and_income_corruptions_rejected(self):
        mutations = [
            lambda d: d['coverage'].update(verified_valid_score_counts=420),
            lambda d: d['coverage'].update(sampling_intervals_available=True),
            lambda d: d['coverage']['prospective_subject_members'].update(math=210.0),
            lambda d: d['roster_links'][0]['subjects']['math'].update(valid_scores=100),
            lambda d: d['roster_links'][0]['subjects']['math'].update(sampling_variance=0),
            lambda d: d['roster_links'][0]['subjects']['combined'].update(sampling_interval_available=True),
            lambda d: d['roster_links'][0]['income'].update(snapshot_date='2023-10-27'),
            lambda d: d['cohorts']['prospective_grade_school']['subjects']['math'].update(approved_for_modeling=True),
            lambda d: d['cohorts']['prospective_grade_school']['subjects']['combined']['prospective_native_school_ids'].append('101912039'),
            lambda d: d['enrollment_reconciliation'].update(native_campus_sum=176039),
            lambda d: d['outside_grade_school_population'].pop(),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): audit.validate(changed)
        snapshot = audit.load_texas(); snapshot['profiles'][0]['profile_row'] = 0
        with self.assertRaises(ValueError): audit.validate(self.document, snapshot)


if __name__ == '__main__':
    unittest.main()
