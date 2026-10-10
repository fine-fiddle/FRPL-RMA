import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_fairfax as audit


class FairfaxSourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.payload = audit.load_virginia()
        cls.links = {r['school_id']: r for r in cls.document['roster_links']}
        cls.native = {e['school_id']: e['raw'] for e in cls.document['raw_inputs']['native_profiles']['records']}
        cls.directory = {audit.ccd_identity(r['raw']): r['raw'] for r in cls.document['raw_inputs']['directory']['records']}

    def test_complete_original_roster_and_native_inventory(self):
        c = audit.validate(self.document, self.payload)
        self.assertEqual((c['directory_records'], c['operational_schools'], c['nonoperational_schools']), (223, 223, 0))
        self.assertEqual((c['native_profiles'], c['missing_native_profiles']), (195, 28))
        self.assertEqual(c['native_grade_bands'], dict(grade=162, high=25, mixed=4, unclassified=4))
        self.assertEqual(c['operational_statuses'], {'Open': 223})
        self.assertEqual(c['operational_ccd_charter'], {'No': 223})
        self.assertEqual(c['operational_ccd_school_types'], {'Alternative School': 11, 'Career and Technical School': 11, 'Regular School': 194, 'Special Education School': 7})
        self.assertEqual(len(self.document['sources']), 200)
        self.assertEqual(self.document['raw_inputs']['native_profiles']['source_inventory']['total_schools'], 1812)
        self.assertEqual(len(self.document['raw_inputs']['native_profiles']['source_inventory']['urls']), 182)

    def test_native_grade_high_mixed_membership_and_floor_holds(self):
        for band, profiles, eligible in [('grade', 162, 152), ('high', 25, 23), ('mixed', 4, 1), ('unclassified', 4, 0)]:
            cohort = self.document['cohorts'][band]
            self.assertEqual(cohort['profiles'], profiles)
            for subject in ['math', 'reading', 'combined']:
                result = cohort['subjects'][subject]
                self.assertEqual(result['usable'], eligible)
                self.assertEqual(result['applicable'], 0 if band == 'unclassified' else profiles)
                self.assertEqual(result['prospective_30_school_floor_met'], eligible >= 30)
                self.assertEqual(len(result['eligible_school_ids']), eligible)
                self.assertEqual(len(result['eligible_ncessch']), eligible)
        self.assertEqual(self.document['prospective_population'], 'grade')
        self.assertEqual(self.document['hard_holds'], [])
        self.assertEqual(self.document['release_holds']['grade'], [])
        self.assertTrue(self.document['release_holds']['high'])
        self.assertTrue(self.document['release_holds']['mixed'])
        self.assertFalse(self.document['approved_for_source'])
        self.assertFalse(self.document['approved_for_modeling'])
        self.assertEqual((self.document['status'], self.document['scope']), ('audit_pending', 'audit_pending'))

    def test_missing_ccd_membership_is_not_zero_or_ungraded(self):
        missing = [r for r in self.links.values() if not r['ccd_membership']['present']]
        self.assertEqual(len(missing), 24)
        for r in missing:
            self.assertFalse(r['native_profile_present'])
            self.assertIsNone(r['ccd_membership']['total'])
            self.assertIsNone(r['ccd_membership']['raw_total'])
            self.assertIsNone(r['ccd_membership']['total_source_row'])
            self.assertIsNone(r['ccd_membership']['reported_grade_sum'])
            self.assertEqual(r['ccd_membership']['grade_values'], [])
            self.assertTrue(r['offered']['no_reported_grades'])
            self.assertEqual(r['offered']['flags']['UG'], 'No')
            self.assertTrue(all(v == 'No' for v in r['offered']['flags'].values()))
            self.assertTrue(all(not v['usable'] for v in r['subjects'].values()))

    def test_four_native_missing_preschools_have_original_ccd_counts_only(self):
        centers = [r for r in self.links.values() if not r['native_profile_present'] and r['ccd_membership']['present']]
        self.assertEqual(len(centers), 4)
        self.assertEqual(sum(r['ccd_membership']['total'] for r in centers), 784)
        self.assertTrue(all(r['offered']['offered'] == ['PK'] for r in centers))
        self.assertTrue(all(r['income'] is None and not r['subjects']['combined']['usable'] for r in centers))
        self.assertEqual(len(self.document['missing_native_profiles']), 28)

    def test_exact_composite_native_codes_never_name_join(self):
        raw = self.directory['0290131']
        self.assertEqual(raw['ST_SCHID'], 'VA-029-0290131')
        self.assertEqual(audit.ccd_identity(dict(raw, SCH_NAME='Renamed display label')), '0290131')
        for field, value in [('ST_SCHID', 'VA-029-0131'), ('ST_SCHID', 'VA-029-029131'), ('ST_SCHID', 'VA-030-0290131'),
                             ('LEAID', '5101261'), ('ST_LEAID', 'VA-030'), ('SCHOOL_YEAR', '2023-2024'), ('ST', 'WV')]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                audit.ccd_identity(dict(raw, **{field: value}))
        for r in self.links.values():
            if r['native_profile_present']:
                self.assertEqual(audit.virginia.school_id(self.native[r['school_id']]), r['school_id'])

    def test_post_graduate_positive_count_keeps_lake_braddock_unclassified(self):
        r = self.links['0290090']
        self.assertIsNone(r['native_grade']['native_band'])
        self.assertEqual(r['native_grade']['positive_unrecognized_grades'], ['Post Graduate'])
        pg = next(v for v in r['native_grade']['native_grade_values'] if v['label'] == 'Post Graduate')
        self.assertEqual((pg['raw_count'], pg['reported_count']), ('1', 1))
        self.assertEqual(r['offered']['strict_offered_band'], 'mixed')
        self.assertEqual((r['subjects']['math']['native_rate'], r['subjects']['reading']['native_rate']), (87, 90))
        self.assertFalse(r['subjects']['combined']['usable'])
        changed = copy.deepcopy(self.native['0290090'])
        row = next(v for v in changed['grade_table']['rows'] if v['label'] == 'Post Graduate')
        row['values'][changed['grade_table']['years'].index('2024-2025')] = '0'
        self.assertEqual(audit.virginia.band_for(changed), 'mixed')

    def test_primary_only_profiles_have_no_applicable_native_rates(self):
        for key in ['0290550', '0292224', '0292231']:
            r = self.links[key]
            self.assertIsNone(r['native_grade']['native_band'])
            self.assertEqual(r['native_grade']['positive_unrecognized_grades'], [])
            self.assertEqual(r['offered']['strict_offered_band'], 'primary')
            self.assertIsNotNone(r['income']['percentage'])
            for subject in ['math', 'reading', 'combined']:
                self.assertFalse(r['subjects'][subject]['applicable'])
                self.assertFalse(r['subjects'][subject]['usable'])
                self.assertIsNone(r['subjects'][subject]['native_rate'])

    def test_native_income_reconciliation_stale_display_and_comma_raw_values(self):
        self.assertEqual(self.document['coverage']['income_unavailable'], 15)
        self.assertEqual(self.document['coverage']['stale_native_income_display_percentages'], 128)
        raw = self.native['0290550']; result = audit.income_evidence(raw)
        self.assertEqual(result['percentage'], 100 * 675 / 820)
        self.assertEqual(result['published_ed_percentage'], 82.924)
        self.assertTrue(result['stale_display_percentage'])
        lake = self.native['0290090']
        total = next(r for r in lake['grade_table']['rows'] if r['label'] == 'Total Enrollment')
        self.assertEqual(total['values'][1], '4,430')
        self.assertEqual(audit.income_evidence(lake)['reported_all_students'], 4430)
        self.assertEqual(audit.income_evidence(lake)['percentage'], 100 * 1064 / 4430)

    def test_masked_zero_grade_counts_and_complement_are_not_inferred(self):
        archer = self.native['0290110']
        result = audit.income_evidence(archer)
        self.assertIsNone(result['percentage'])
        self.assertEqual(result['exclusion'], 'At least one native same-year grade count is missing or suppressed')
        row = next(r for r in archer['grade_table']['rows'] if r['label'] == 'Pre-kindergarten')
        self.assertEqual(row['values'][1], '-')
        base = copy.deepcopy(self.native['0290550'])
        base['enrollment_subgroups']['3']['cnt'] = '*'
        self.assertIsNone(audit.income_evidence(base)['percentage'])
        self.assertEqual(audit.income_evidence(base)['exclusion'], 'Native individual ED count missing or suppressed')
        base = copy.deepcopy(self.native['0290550']); base['enrollment_subgroups']['18']['cnt'] = '*'
        self.assertIsNone(audit.income_evidence(base)['percentage'])
        base = copy.deepcopy(self.native['0290550']); base['enrollment_subgroups']['3']['pct'] = '*'
        self.assertIsNone(audit.income_evidence(base)['percentage'])

    def test_reported_income_zero_is_distinct_from_missing(self):
        raw = copy.deepcopy(self.native['0290550'])
        raw['enrollment_subgroups']['3'].update(cnt='0', pct='0')
        raw['enrollment_subgroups']['18']['cnt'] = raw['enrollment_subgroups']['5']['cnt']
        self.assertEqual(audit.income_evidence(raw)['percentage'], 0)
        raw['enrollment_subgroups']['3']['cnt'] = '*'
        self.assertIsNone(audit.income_evidence(raw)['percentage'])

    def test_same_year_and_all_students_assessment_guards(self):
        base = self.native['0290131']
        for field, value in [('population', 'Economically Disadvantaged'), ('test', 'Algebra I')]:
            raw = copy.deepcopy(base); raw['assessments']['math'][field] = value
            with self.assertRaises(ValueError): audit.virginia.assessment_value(raw, 'math')
        raw = copy.deepcopy(base); raw['assessments']['math']['years'][1] = '2023-2024'
        with self.assertRaises(ValueError): audit.virginia.assessment_value(raw, 'math')
        raw = copy.deepcopy(base); raw['enrollment_subgroups']['3']['sch_yr'] = '2023'
        with self.assertRaises(ValueError): audit.income_evidence(raw)

    def test_combined_and_all_model_uncertainty_remain_unavailable(self):
        for r in self.links.values():
            for s in r['subjects'].values():
                self.assertIsNone(s['valid_scores']); self.assertIsNone(s['sampling_variance'])
                self.assertFalse(s['sampling_interval_available'])
            if r['subjects']['combined']['usable']:
                self.assertEqual(r['subjects']['combined']['native_rate'], (r['subjects']['math']['native_rate'] + r['subjects']['reading']['native_rate']) / 2)
        self.assertIn('SOL plus VAAP', self.document['policy']['assessment'])
        self.assertIn('2023 mathematics', self.document['policy']['assessment'])
        self.assertIn('2024 English', self.document['policy']['assessment'])
        self.assertTrue(all(r['ccd_flags']['virtual_status'] is None for r in self.links.values()))

    def test_offered_grade_diagnostics_do_not_reclassify_native_band(self):
        raw = self.directory['0290131']
        changed = dict(raw, G_3_OFFERED='Yes')
        self.assertEqual(audit.offered_evidence(changed)['strict_offered_band'], 'mixed')
        self.assertEqual(audit.virginia.band_for(self.native['0290131']), 'high')
        self.assertEqual(len(self.document['cohorts']['grade']['strict_offered_intersection']), 162)
        self.assertEqual(self.document['cohorts']['grade']['offered_band_differences'], [])

    def test_original_ccd_member_sums_are_diagnostics_not_native_income(self):
        c = self.document['coverage']; planning = self.document['planning_identity_reconciliation']
        self.assertEqual((c['ccd_membership_schools'], c['ccd_membership_absent_schools']), (199, 24))
        self.assertEqual((c['raw_membership_rows'], c['raw_lunch_rows']), (1689, 965))
        self.assertEqual(planning['school_total_sum'], 179323)
        self.assertEqual((c['native_membership_sum'], c['ccd_membership_sum_for_native_profiles']), (179770, 178539))
        self.assertEqual(c['native_ccd_membership_differences'], 163)
        self.assertEqual(planning['native_grade_not_planning_ES'], [])
        self.assertEqual(planning['planning_ES_not_native_grade'], [])
        self.assertEqual([len(planning['potential_school_ids'][s]) for s in ['ES', 'HS']], [162, 25])

    def test_complete_native_definition_fragments_and_state_notes(self):
        d = self.document['state_definition_evidence']
        self.assertEqual(len(d['original_native_profile_definitions']), 195)
        for profile in d['original_native_profile_definitions']:
            self.assertEqual(len(profile['fragments']), 5)
            self.assertTrue(all(type(r['source_line']) is int and r['source_line'] > 0 for r in profile['fragments']))
            fragments = {r['label']: r['raw_markup'] for r in profile['fragments']}
            self.assertIn('Virginia Alternate Assessment Program', fragments['assessment_scope'])
            self.assertIn('Medicaid', fragments['individual_economic_status'])
            self.assertIn('September 30', fragments['fall_membership'])
            self.assertIn('end of secondary courses', fragments['math_population'])
        sheets = {s['worksheet']: s for s in d['complete_workbook_worksheets']}
        self.assertEqual(len(sheets['Data Notes']['rows']), 561)
        self.assertEqual(len(sheets), 8)

    def test_offline_validation_has_no_raw_archive_import_or_fit_dependency(self):
        with mock.patch.object(audit, 'extract_raw_inputs', side_effect=AssertionError('no raw reads')), \
             mock.patch.object(audit.virginia, 'import_data', side_effect=AssertionError('no import')), \
             mock.patch.object(audit.virginia, 'prepare', side_effect=AssertionError('no canonical prepare')), \
             mock.patch.object(audit.virginia, 'build_history', side_effect=AssertionError('no fit')):
            self.assertEqual(audit.validate(self.document, self.payload)['native_profiles'], 195)

    def test_adverse_provenance_raw_row_identity_and_definition_mutations_rejected(self):
        cases = [('source_sha',), ('source_url',), ('year',), ('approval',), ('raw_count',), ('raw_grade',), ('row_reference',),
                 ('native_rate',), ('native_year',), ('native_definition',), ('ccd_identity',), ('ccd_header',), ('source_inventory',), ('planning_ids',)]
        for (kind,) in cases:
            changed = copy.deepcopy(self.document)
            if kind == 'source_sha': changed['sources']['ccd_directory_2025']['sha256'] = '0' * 64
            elif kind == 'source_url': changed['sources']['va-profile-0290131']['url'] = 'https://example.com/'
            elif kind == 'year': changed['year'] = 2024
            elif kind == 'approval': changed['approved_for_source'] = True
            elif kind == 'raw_count': changed['raw_inputs']['membership']['records'][0]['raw']['STUDENT_COUNT'] = '0'
            elif kind == 'raw_grade': changed['raw_inputs']['membership']['records'][1]['raw']['GRADE'] = 'Ungraded'
            elif kind == 'row_reference': changed['raw_inputs']['directory']['records'][0]['source_row'] += 1
            elif kind == 'native_rate': changed['raw_inputs']['native_profiles']['records'][0]['raw']['assessments']['math']['school_values'][1] = '99'
            elif kind == 'native_year': changed['raw_inputs']['native_profiles']['records'][0]['raw']['grade_table']['years'][1] = '2023-2024'
            elif kind == 'native_definition': changed['raw_inputs']['definitions']['original_native_profile_definitions'][0]['fragments'][0]['raw_markup'] = 'SOL only'
            elif kind == 'ccd_identity': changed['raw_inputs']['directory']['records'][0]['raw']['ST_SCHID'] = 'VA-029-0131'
            elif kind == 'ccd_header': changed['raw_inputs']['lunch']['header'][0] = 'Renamed source column'
            elif kind == 'source_inventory': changed['raw_inputs']['native_profiles']['source_inventory']['total_schools'] = 1811
            else: changed['raw_inputs']['planning']['record']['potential_school_ids']['ES'].pop()
            with self.subTest(kind=kind), self.assertRaises(ValueError): audit.validate(changed, self.payload)

    def test_adverse_derived_results_hold_flags_and_ghosts_rejected(self):
        for kind in ['member', 'denominator', 'combined', 'floor', 'hold', 'coverage', 'ghost', 'model']:
            changed = copy.deepcopy(self.document)
            if kind == 'member': changed['cohorts']['grade']['subjects']['combined']['eligible_school_ids'].pop()
            elif kind == 'denominator': changed['roster_links'][0]['subjects']['math']['valid_scores'] = 100
            elif kind == 'combined': changed['roster_links'][0]['subjects']['combined']['native_rate'] = 0
            elif kind == 'floor': changed['cohorts']['high']['subjects']['math']['prospective_30_school_floor_met'] = True
            elif kind == 'hold': changed['release_holds']['mixed'] = []
            elif kind == 'coverage': changed['coverage']['missing_native_profiles'] = 0
            elif kind == 'ghost': changed['roster_links'].append(copy.deepcopy(changed['roster_links'][0]))
            else: changed['models'] = []
            with self.subTest(kind=kind), self.assertRaises(ValueError): audit.validate(changed, self.payload)

    def test_changed_in_memory_complete_state_source_rejected(self):
        changed = copy.deepcopy(self.payload); changed['profiles'].pop()
        with self.assertRaises(ValueError): audit.validate(self.document, changed)


if __name__ == '__main__':
    unittest.main()
