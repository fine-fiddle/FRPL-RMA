import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_gwinnett as audit


class GwinnettSourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.snapshot = audit.load_georgia()
        cls.links = {r['school_id']: r for r in cls.document['roster_links']}
        cls.directory = {r['raw']['NCESSCH']: r for r in cls.document['raw_inputs']['directory']['records']}

    def membership(self, key):
        rows = [r for r in self.document['raw_inputs']['membership']['records'] if r['raw']['NCESSCH'] == key]
        total = next(r for r in rows if r['raw']['TOTAL_INDICATOR'] == 'Education Unit Total')
        grades = {r['raw']['GRADE']: r for r in rows if r['raw']['TOTAL_INDICATOR'] == 'Subtotal 4 - By Grade'}
        direct = next(r for r in self.document['raw_inputs']['lunch']['records'] if r['raw']['NCESSCH'] == key and r['raw']['DATA_GROUP'] == 'Direct Certification')
        return total, grades, direct

    def test_complete_roster_populations_and_discovery_reconciliation(self):
        c = audit.validate(self.document, self.snapshot)
        self.assertEqual((c['directory_records'], c['operational_schools'], c['nonoperational_schools']), (141, 141, 0))
        self.assertEqual(c['operational_statuses'], {'New': 1, 'Open': 140})
        self.assertEqual(c['operational_graded_offered_scope'], {'high': 24, 'lower': 111, 'mixed': 6})
        self.assertEqual(c['operational_ccd_school_types'], {'Alternative School': 2, 'Regular School': 139})
        self.assertEqual(c['operational_ccd_charter'], {'No': 140, 'Yes': 1})
        for name, count in [('native_grade_school_configurations', 111), ('native_offered_tested_grade', 111),
                            ('native_positive_membership_tested_candidates', 111), ('native_configurations_with_usable_income', 111),
                            ('historical_native_source_profiles', 111), ('native_primary_only', 0), ('mixed_offers_with_native_g38', 6)]:
            cohort = self.document['cohorts'][name]
            self.assertEqual(cohort['profiles'], count)
            for subject in ['math', 'reading', 'combined']:
                expected = 111 if count == 111 else 0
                self.assertEqual((cohort['subjects'][subject]['applicable'], cohort['subjects'][subject]['usable']), (expected, expected))
                self.assertEqual(cohort['subjects'][subject]['prospective_30_school_floor_met'], expected >= 30)
        eligible = self.document['cohorts']['historical_native_source_profiles']
        self.assertEqual(eligible['combined_ccd_charter'], {'No': 110, 'Yes': 1})
        self.assertEqual(eligible['combined_ccd_school_type'], {'Regular School': 111})
        planning = self.document['planning_identity_reconciliation']
        self.assertEqual([len(planning['potential_school_ids'][s]) for s in ['ES', 'HS']], [111, 24])
        self.assertEqual(planning['source_not_in_planning_ES'], [])
        self.assertEqual(planning['planning_ES_not_source_eligible'], [])
        self.assertFalse(self.document['approved_for_source'])
        self.assertFalse(self.document['approved_for_modeling'])
        self.assertEqual((self.document['status'], self.document['scope']), ('audit_pending', 'audit_pending'))
        self.assertNotIn('models', self.document)

    def test_offered_and_enrolled_contract_requires_complete_reconciled_native_counts(self):
        key = '130255000046'; raw = self.directory[key]['raw']
        total, grade_entries, _ = self.membership(key)
        grades = {g: r['raw'] for g, r in grade_entries.items()}
        self.assertTrue(audit.georgia.grade_school(raw, grades, total['raw']))
        self.assertTrue(self.links[key]['offered']['strict_pure_offered_lower'])
        self.assertTrue(all(r['offered']['ungraded_offered'] == 'No' for r in self.links.values()))
        for field, value in [('G_9_OFFERED', 'Yes'), ('G_3_OFFERED', 'Unknown'), ('IGOFFERED', 'Imputed'), ('GSHI', 'KG')]:
            changed = dict(raw); changed[field] = value
            self.assertFalse(audit.georgia.grade_school(changed, grades, total['raw']))
        for change in ['count', 'suppressed', 'outside', 'ungraded']:
            changed = copy.deepcopy(grades)
            if change == 'count': changed['Grade 3']['STUDENT_COUNT'] = '99999'
            elif change == 'suppressed': changed['Grade 3']['DMS_FLAG'] = 'Suppressed'
            elif change == 'outside': changed['Grade 9'] = dict(changed['Grade 3'], STUDENT_COUNT='1')
            else:
                offered = dict(raw, G_UG_OFFERED='Yes')
                self.assertFalse(audit.georgia.grade_school(offered, changed, total['raw']))
                continue
            self.assertFalse(audit.georgia.grade_school(raw, changed, total['raw']))
        unspecified = grade_entries['Not Specified']['raw']
        self.assertEqual((unspecified['STUDENT_COUNT'], unspecified['DMS_FLAG'], unspecified['SEX']), ('0', 'Derived', 'Not Specified'))
        self.assertTrue(all(not r['enrolled']['positive_enrolled_without_offer'] for r in self.links.values()))

    def test_individual_direct_certification_zero_missing_and_suppression_are_distinct(self):
        key = '130255000046'; raw = self.directory[key]['raw']
        total, grades, direct = self.membership(key)
        actual = audit.income_evidence(raw, total, direct, grades)
        self.assertEqual(actual['percentage'], 100 * 137 / 819)
        self.assertEqual(actual['membership_source_row'], 2910686)
        self.assertEqual(actual['direct_source_row'], 115753)
        self.assertIsNone(actual['income_exclusion'])
        zero = copy.deepcopy(direct); zero['raw']['STUDENT_COUNT'] = '0'
        result = audit.income_evidence(raw, total, zero, grades)
        self.assertEqual(result['percentage'], 0)
        self.assertIsNone(result['income_exclusion'])
        absent = audit.income_evidence(raw, total, None, grades)
        self.assertIsNone(absent['percentage']); self.assertEqual(absent['direct_status'], 'absent')
        suppressed = copy.deepcopy(direct); suppressed['raw'].update(STUDENT_COUNT='', DMS_FLAG='Suppressed')
        result = audit.income_evidence(raw, total, suppressed, grades)
        self.assertIsNone(result['percentage']); self.assertEqual(result['direct_status'], 'Suppressed')
        excess = copy.deepcopy(direct); excess['raw']['STUDENT_COUNT'] = '820'
        self.assertIsNone(audit.income_evidence(raw, total, excess, grades)['percentage'])
        self.assertEqual(self.document['coverage']['direct_certification_flags'], {'Reported': 141})
        self.assertTrue(all(r['income']['percentage'] > 0 for r in self.links.values()))

    def test_georgia_native_prefixed_ids_year_and_assessment_population(self):
        entry = next(r for r in self.document['raw_inputs']['assessment']['records'] if r['raw']['NCESSchoolID'] == '130255003395')
        raw = entry['raw']
        self.assertEqual(audit.edc_identity(dict(raw, SchName='Renamed display label'), self.directory), '130255003395')
        self.assertEqual(raw['StateAssignedSchID'], '667-1005')
        for field, value in [('StateAssignedSchID', '1005'), ('StateAssignedDistID', '666'), ('NCESSchoolID', '130255003991'),
                             ('NCESDistrictID', '1302551'), ('SchYear', '2023-24'), ('GradeLevel', 'GHS'),
                             ('AssmtName', 'Georgia Milestones EOC'), ('AssmtType', 'Alternate'),
                             ('ProficiencyCriteria', 'Levels 2-4'), ('StudentSubGroup', 'Economically Disadvantaged')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.edc_identity(dict(raw, **{field: value}), self.directory)
        for field, value in [('SCHOOL_YEAR', '2023-2024'), ('ST_LEAID', 'GA-666'), ('ST_SCHID', 'GA-667-99999')]:
            with self.assertRaises(ValueError): audit.ccd_identity(dict(self.directory['130255003395']['raw'], **{field: value}))
        self.assertEqual(self.document['coverage']['assessment_grade_rows']['G38'], 234)
        self.assertEqual(self.document['coverage']['native_g38_pairs'], 117)

    def test_mixed_true_zero_raw_unverified_counts_and_charter_inclusion(self):
        charter = self.links['130255003991']
        self.assertEqual(charter['native_school_id'], 'GA-667-1020')
        self.assertEqual(charter['ccd_flags']['charter'], 'Yes')
        self.assertTrue(charter['subjects']['combined']['usable'])
        for key in ['130255004683', '130255004257']:
            mixed = self.links[key]
            self.assertEqual(mixed['subjects']['math']['native_rate'], 0)
            self.assertEqual(mixed['subjects']['math']['raw_rate'], '0')
            self.assertIsNone(mixed['subjects']['math']['outcome_exclusion'])
            self.assertFalse(mixed['subjects']['combined']['usable'])
            self.assertEqual(mixed['offered']['graded_scope'], 'mixed')
        self.assertEqual(self.links['130255004683']['subjects']['math']['raw_tested'], '*')
        for link in self.links.values():
            for subject, outcome in link['subjects'].items():
                self.assertIsNone(outcome['valid_scores']); self.assertIsNone(outcome['sampling_variance'])
                self.assertFalse(outcome['sampling_interval_available'])
            if link['subjects']['combined']['usable']:
                self.assertEqual(link['subjects']['combined']['native_rate'], (link['subjects']['math']['native_rate'] + link['subjects']['reading']['native_rate']) / 2)
        for raw in ['*', '', '<0.1', '0.1-0.2']:
            self.assertIsNone(audit.georgia.exact_rate(raw))
        self.assertTrue(all(r['ccd_flags']['virtual_status'] is None for r in self.links.values()))
        self.assertEqual(self.document['coverage']['g38_edc_virtual_rows'], {'No': 234})

    def test_original_definition_rows_preserve_eligibility_era_and_roster_mismatch(self):
        definitions = self.document['state_definition_evidence']
        sheets = {s['worksheet']: {r['source_row']: r['raw'] for r in s['rows']} for s in definitions['georgia_rows_and_headers']}
        eligibility = sheets['Data Notes'][129]
        self.assertEqual(eligibility[5], 'CCD-0060')
        self.assertIn('Medicaid income', eligibility[9]); self.assertIn('2024', eligibility[9])
        self.assertIn('foster', eligibility[9])
        program = sheets['Data Notes'][133]
        self.assertEqual(program[5], 'DGO-0033'); self.assertIn('130255002906', program[11])
        self.assertEqual(self.document['later_release_note_roster_gaps'], ['130255002906'])
        self.assertNotIn('130255002906', self.directory)
        self.assertIn('outside programs', sheets['CCD Membership Metadata'][14][6])
        self.assertEqual(sheets['CCD Grades Offered Metadata'][14][3], 'Does not offer ungraded instruction')
        codebook = definitions['complete_codebook_worksheets'][0]
        g38 = next(r['raw'] for r in codebook['rows'] if r['source_row'] == 44)
        self.assertIn('G38', g38)
        self.assertIn('SEA', ' '.join(str(v) for v in g38))
        self.assertEqual(self.document['historical_state_lunch_notes'], [])

    def test_offline_replay_without_raw_archives_or_ignored_membership_cache(self):
        with mock.patch.object(audit.zipfile, 'ZipFile', side_effect=AssertionError('Raw ZIP unavailable')), \
                mock.patch.object(audit.subprocess, 'Popen', side_effect=AssertionError('Raw stream unavailable')), \
                mock.patch.object(audit.georgia, 'membership_cache', side_effect=AssertionError('Ignored cache unavailable')):
            self.assertEqual(audit.validate(self.document)['historical_native_source_profiles'], 111)
        inputs = self.document['raw_inputs']
        self.assertEqual([len(inputs[s]['records']) for s in ['directory', 'membership', 'lunch', 'assessment']], [141, 1099, 705, 942])
        self.assertNotIn('all_district_csv_rows', inputs['membership'])
        self.assertEqual(sum(r['raw']['TOTAL_INDICATOR'] == 'Education Unit Total' for r in inputs['membership']['records']), 141)
        for source in ['directory', 'membership', 'lunch', 'assessment']:
            self.assertEqual(inputs[source]['header_source_row'], 1)
            self.assertTrue(all(type(r['source_row']) is int and r['source_row'] >= 2 for r in inputs[source]['records']))
        self.assertEqual(audit.fingerprint(inputs), audit.RAW_INPUT_SHA)

    def test_exact_source_types_headers_rows_and_discovery_corruption_rejected(self):
        mutations = [
            lambda d: d.update(approved_for_source=0), lambda d: d.update(approved_for_modeling=True),
            lambda d: d.update(schema_version=1.0), lambda d: d.update(year=2025.0),
            lambda d: d.update(status='ready'), lambda d: d.update(models=[]),
            lambda d: d['sources']['edc_2025'].update(sha256='0' * 64),
            lambda d: d['raw_inputs']['directory']['records'].pop(),
            lambda d: d['raw_inputs']['directory']['records'][0]['raw'].update(ST_SCHID='GA-667-9999'),
            lambda d: d['raw_inputs']['membership']['records'][0]['raw'].update(STUDENT_COUNT='0'),
            lambda d: d['raw_inputs']['membership']['records'][0].update(source_row=2),
            lambda d: d['raw_inputs']['lunch']['records'][0]['raw'].update(DMS_FLAG='Suppressed'),
            lambda d: d['raw_inputs']['assessment']['records'][0]['raw'].update(ProficientOrAbove_percent='changed'),
            lambda d: d['raw_inputs']['assessment']['header'].remove('SchVirtual'),
            lambda d: d['raw_inputs']['definitions']['georgia_rows_and_headers'][0]['rows'].pop(),
            lambda d: d['raw_inputs']['planning']['record']['potential_school_ids']['ES'].append('130255099999'),
            lambda d: d['raw_inputs']['planning']['record'].update(enrollment=182518.0),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): audit.validate(changed, self.snapshot)

    def test_derived_selection_uncertainty_and_historical_snapshot_drift_rejected(self):
        mutations = [
            lambda d: d['cohorts']['historical_native_source_profiles'].update(profiles=111.0),
            lambda d: d['coverage'].update(sampling_intervals_available=0),
            lambda d: d['coverage'].update(verified_valid_score_counts=False),
            lambda d: d['roster_links'][0]['subjects']['math'].update(valid_scores=819),
            lambda d: d['roster_links'][0]['subjects']['math'].update(sampling_variance=0),
            lambda d: d['roster_links'][0]['subjects']['combined'].update(sampling_interval_available=True),
            lambda d: d['roster_links'][0]['enrolled'].update(native_grade_school_contract=1),
            lambda d: d['later_release_note_roster_gaps'].clear(),
            lambda d: d['cohorts']['historical_native_source_profiles']['subjects']['math']['eligible_school_ids'].append('130255004683'),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): audit.validate(changed, self.snapshot)
        snapshot = copy.deepcopy(self.snapshot); snapshot['schools'][0]['outcomes']['math']['tested'] = 100
        with self.assertRaises(ValueError): audit.validate(self.document, snapshot)
        snapshot = copy.deepcopy(self.snapshot); snapshot['schools'][0]['enrollment'] = False
        with self.assertRaises(ValueError): audit.validate(self.document, snapshot)


if __name__ == '__main__':
    unittest.main()
