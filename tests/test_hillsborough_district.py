import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_hillsborough as audit


class HillsboroughDistrictAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.payload = audit.load_florida()
        cls.links = {r['school_id']: r for r in cls.document['roster_links']}

    def test_exact_roster_and_distinct_source_proposed_populations(self):
        c = audit.validate(self.document, self.payload)
        self.assertEqual((c['directory_records'], c['operational_schools'], c['exact_fall_profile_matches']),
                         (309, 293, 289))
        self.assertEqual(c['operational_statuses'], {'Added': 1, 'Open': 292})
        self.assertEqual(c['nonoperational_statuses'], {'Closed': 13, 'Future': 3})
        self.assertEqual(c['operational_offered_scope'], {'ES': 224, 'HS': 34, 'mixed': 35})
        for name, profiles, applicable, usable, income in [
            ('native_enrolled_grade_school_contract', 223, 223, 219, 223),
            ('proposed_pure_lower_directory', 222, 220, 219, 222),
            ('proposed_pure_offered_tested_grade', 220, 220, 219, 220),
            ('pure_lower_enrolled_tested_evidence', 219, 219, 219, 219),
            ('pure_lower_primary_offers_only', 2, 0, 0, 2),
            ('native_grade_schools_with_mixed_offers', 1, 1, 0, 1),
        ]:
            group = self.document['cohorts'][name]
            self.assertEqual((group['profiles'], group['income_available_profiles']), (profiles, income))
            for subject in ['math', 'reading', 'combined']:
                self.assertEqual((group['subjects'][subject]['applicable'], group['subjects'][subject]['usable']),
                                 (applicable, usable))
        group = self.document['cohorts']['proposed_pure_offered_tested_grade']
        self.assertEqual(group['combined_ccd_charter'], {'No': 184, 'Yes': 35})
        self.assertEqual(group['combined_ccd_school_type'], {'Regular School': 219})
        self.assertFalse(self.document['approved_for_source'])
        self.assertFalse(self.document['approved_for_modeling'])
        self.assertEqual(self.document['scope'], 'audit_pending')
        self.assertNotIn('models', self.document)
        self.assertNotIn('snapshots', self.document)

    def test_offered_enrolled_primary_and_mixed_memberships_remain_distinct(self):
        c = self.document['coverage']
        self.assertEqual((c['profiles_with_offered_enrolled_differences'],
                          c['offered_with_explicit_zero_enrolled_grade_cells']), (29, 101))
        self.assertEqual((c['profiles_with_protected_enrolled_grades'], c['protected_enrolled_grade_cells']), (33, 142))
        self.assertEqual(c['profiles_with_positive_or_protected_enrolled_grade_without_offer'], 0)
        self.assertEqual(set(self.document['cohorts']['pure_lower_primary_offers_only']['school_ids']),
                         {'29-5372', '29-5375'})
        zero_tested = {r['school_id'] for r in self.links.values() if r['matched'] and
                       r['offered']['scope'] == 'ES' and r['offered']['offered_tested_grades'] and
                       r['enrolled']['explicit_zero_tested_grades']}
        self.assertEqual(zero_tested, {'29-7817'})
        self.assertTrue(self.links['29-7817']['subjects']['math']['district_applicable'])
        self.assertFalse(self.links['29-7817']['subjects']['math']['district_usable'])
        mixed = self.document['cohorts']['native_grade_schools_with_mixed_offers']
        self.assertEqual(mixed['school_ids'], ['29-4324'])
        self.assertEqual(mixed['subjects']['combined']['eligible_school_ids'], [])
        self.assertTrue(self.links['29-4324']['enrolled']['native_grade_school_contract'])
        self.assertFalse(self.links['29-4324']['subjects']['combined']['district_usable'])
        self.assertEqual(self.links['29-4324']['ccd_flags']['school_type'], 'Alternative School')
        inventory = self.document['cohorts']['exact_operational_pure_lower_directory']
        self.assertEqual(inventory['profiles'], 224)
        self.assertEqual(set(inventory['without_fall_profile_school_ids']), {'29-6529', '29-6531'})
        self.assertEqual(set(inventory['primary_only_school_ids']), {'29-5372', '29-5375', '29-6529', '29-6531'})

    def test_unmatched_outside_and_nonoperational_records_cannot_expand_scope(self):
        self.assertEqual({k for k, r in self.links.items() if not r['matched']},
                         {'29-6529', '29-6531', '29-3525', '29-7001'})
        for key in ['29-6529', '29-6531', '29-3525', '29-7001']:
            self.assertNotIn('subjects', self.links[key])
            self.assertNotIn('income', self.links[key])
        outside = {r['school_id']: r for r in self.document['outside_roster_profiles']}
        self.assertEqual(set(outside), {'29-6608', '29-7006'})
        self.assertTrue(outside['29-6608']['exact_directory_match'])
        self.assertEqual(outside['29-6608']['ccd_flags']['status_text'], 'Closed')
        self.assertFalse(outside['29-7006']['exact_directory_match'])
        for row in outside.values():
            self.assertIsNone(row['income']['raw'])
            self.assertIsNone(row['income']['percentage'])
        self.assertEqual(self.document['income_without_fall_registry_links'], [])
        self.assertEqual(self.document['native_assessments_without_operational_roster'], [])
        self.assertEqual(len(self.document['nonoperational_directory']), 16)
        self.assertEqual(len(self.document['native_records']['profiles']), 291)
        self.assertEqual(len(self.document['native_records']['assessments']), 260)
        self.assertTrue(all(a['raw'][3] in ('', None) for a in self.document['native_records']['assessments']))
        self.assertEqual(self.document['coverage']['collocated_assessment_rows'], 0)
        self.assertEqual(self.document['coverage']['campus_charter_disagreements'], 0)
        self.assertTrue(all(r['ccd_flags']['virtual_status'] is None for r in self.links.values()))

    def test_same_year_individual_income_native_rates_and_missingness(self):
        eligible = [r for r in self.links.values() if r['matched'] and r['subjects']['combined']['district_usable']]
        self.assertEqual(len(eligible), 219)
        for r in eligible:
            raw = r['income']['raw']
            self.assertAlmostEqual(r['income']['percentage'], 100 * (raw[5] + raw[6] + raw[8]) / raw[4])
            math, ela, combined = (r['subjects'][s] for s in ['math', 'reading', 'combined'])
            self.assertEqual(math['native_rate'], math['native_achievement_raw'])
            self.assertEqual(ela['native_rate'], ela['native_achievement_raw'])
            self.assertEqual(combined['native_rate'], (math['native_rate'] + ela['native_rate']) / 2)
        self.assertTrue(all(self.links[key]['income']['percentage'] is not None for key in
                            self.document['cohorts']['proposed_pure_lower_directory']['school_ids']))
        self.assertIsNone(self.links['29-7004']['income']['percentage'])
        self.assertEqual(self.links['29-7004']['income']['native_fields']['provision2_4'], '*')
        self.assertEqual(self.document['coverage']['native_profiles_with_masked_income_count_cells'], 1)
        self.assertEqual(self.document['coverage']['native_profiles_without_income_row'], 2)
        self.assertEqual(self.document['coverage']['native_profiles_with_verified_zero_individual_income'], 0)
        # A synthetic verified zero remains zero, while source absences stay unavailable.
        profile = copy.deepcopy(self.links['29-0311']['profile'])
        for field in [5, 6, 8]:
            profile['income_raw'][field] = 0
        self.assertEqual(audit.income_record(profile)['percentage'], 0.)
        profile['income_raw'] = None
        self.assertIsNone(audit.income_record(profile)['percentage'])
        for r in self.links.values():
            for value in r.get('subjects', {}).values():
                self.assertIsNone(value['valid_scores'])
                self.assertIsNone(value['sampling_variance'])
                self.assertFalse(value['sampling_interval_available'])

    def test_native_protected_counts_and_program_exclusions_are_not_zero(self):
        source = self.links['29-0311']
        profile = copy.deepcopy(source['profile'])
        profile['grades'][14] = '*'
        e = audit.enrolled_evidence(profile, source['offered'])
        self.assertFalse(e['native_grade_school_contract'])
        self.assertIsNone(e['grade_values']['9']['reported_count'])
        self.assertEqual(e['grade_values']['9']['status'], 'protected_positive')
        profile = copy.deepcopy(source['profile'])
        profile['grades'][8] = '*'
        e = audit.enrolled_evidence(profile, source['offered'])
        self.assertTrue(e['native_grade_school_contract'])
        self.assertIn('3', e['positive_or_protected_tested_grades'])
        campus = next(a for a in self.document['native_records']['assessments'] if a['id'] == '29-0311')
        for field, raw, reason in [(47, 'Y', 'collocated'), (3, '302', 'Provider-specific virtual'),
                                   (9, '*', 'unavailable')]:
            changed = copy.deepcopy(campus)
            changed['raw'][field] = raw
            value = audit.subjects(profile, changed, None)['math']
            self.assertFalse(value['district_usable'])
            self.assertIsNone(value['native_rate'])
            self.assertIn(reason, value['native_outcome_exclusion'])
        for code4 in ['*', 12]:
            changed = copy.deepcopy(profile)
            changed['income_raw'][7] = code4
            self.assertIsNone(audit.income_record(changed)['percentage'])

    def test_offline_replay_retains_headers_without_reopening_raw_sources(self):
        with mock.patch.object(audit.zipfile, 'ZipFile', side_effect=AssertionError('Raw ZIP unavailable')), \
                mock.patch.object(audit.florida.openpyxl, 'load_workbook', side_effect=AssertionError('Workbook unavailable')):
            self.assertEqual(audit.validate(self.document)['operational_schools'], 293)
        self.assertEqual(audit.fingerprint(self.document['directory_header']), audit.DIRECTORY_HEADER_SHA)
        header = self.document['income_worksheet_headers']
        self.assertEqual(header['worksheet'], '2425 FS3_Schl')
        self.assertEqual([r['source_row'] for r in header['rows']], [1, 2, 3])
        self.assertIn('2024-25, Final Survey 3', header['rows'][0]['raw'][0])
        self.assertEqual(set(self.document['native_records']['source_notes']), {'lunch', 'assessment', 'grade'})

    def test_planning_reconciliation_rejects_foreign_missing_duplicate_and_changed_metadata(self):
        agency = next(a for a in json.loads(audit.PLANNING.read_text())['agencies'] if a['nces_lea_id'] == audit.LEA)
        profiles = {p['id']: p for p in self.payload['profiles'] if p['id'].startswith('29-')}
        actual = audit.planning_reconciliation(agency, self.document['directory_records'], profiles)
        self.assertEqual(actual, self.document['planning_identity_reconciliation'])
        self.assertEqual(actual['source_proposed_not_in_planning_ES'], ['29-7791', '29-7805'])
        self.assertEqual(actual['planning_ES_not_in_source_proposed'], [])
        for mutate in [lambda a: a.update(state='GA'), lambda a: a.update(native_lea_id='FL-13'),
                       lambda a: a.update(enrollment=243554), lambda a: a.update(enrollment_flag='Suppressed'),
                       lambda a: a['potential_school_ids']['ES'].pop(),
                       lambda a: a['potential_school_ids']['ES'].__setitem__(0, '120039000001'),
                       lambda a: a['potential_school_ids']['HS'].__setitem__(0, a['potential_school_ids']['HS'][1]),
                       lambda a: a['potential_school_ids']['HS'].__setitem__(0, a['potential_school_ids']['ES'][0])]:
            changed = copy.deepcopy(agency)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.planning_reconciliation(changed, self.document['directory_records'], profiles)
        # Exact discovery membership is compared with independently selected source scope, not used to select it.
        profiles.pop('29-0311')
        self.assertEqual(audit.planning_reconciliation(agency, self.document['directory_records'], profiles)
                         ['planning_ES_not_in_source_proposed'], ['29-0311'])

    def test_original_suppressed_membership_explains_planning_only(self):
        evidence = self.document['planning_membership_evidence']
        self.assertEqual(audit.fingerprint(evidence), audit.PLANNING_MEMBERSHIP_SHA)
        self.assertEqual(len(evidence['records']), 19)
        result = self.document['planning_membership_exclusions']
        self.assertEqual([(r['school_id'], r['ncessch'], r['total_source_row']) for r in result],
                         [('29-7791', '120087008438', 2485085), ('29-7805', '120087008556', 2485702)])
        for row in result:
            self.assertIsNone(row['membership_count'])
            self.assertEqual(row['membership_flag'], 'Suppressed')
            self.assertIsNone(row['source_population_exclusion'])
            self.assertTrue(self.links[row['school_id']]['subjects']['combined']['district_usable'])
        for mutate in [lambda e: e['records'].pop(),
                       lambda e: e['records'][0]['raw'].update(DMS_FLAG='Reported', STUDENT_COUNT='0'),
                       lambda e: e['records'][0]['raw'].update(ST_SCHID='FL-29-0311'),
                       lambda e: e['records'][0].update(source_row=2485085.),
                       lambda e: e['header']['fields'].pop(),
                       lambda e: e['source'].update(sha256='0' * 64)]:
            changed = copy.deepcopy(self.document)
            mutate(changed['planning_membership_evidence'])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.validate(changed, self.payload)

    def test_year_identity_source_cells_typed_flags_and_derived_counts_cannot_drift(self):
        mutations = [
            lambda d: d.update(year=2024), lambda d: d.update(approved_for_source=0),
            lambda d: d.update(approved_for_modeling=True), lambda d: d.update(scope='ready'),
            lambda d: d['directory_records'][0]['raw'].update(SCHOOL_YEAR='2023-2024'),
            lambda d: d['directory_records'][0]['raw'].update(ST_LEAID='FL-13'),
            lambda d: d['directory_records'][0]['raw'].update(ST_SCHID='FL-13-0011'),
            lambda d: d['directory_records'][0]['raw'].update(NCESSCH='120039000001'),
            lambda d: d['directory_records'][0]['raw'].update(G_9_OFFERED='Yes'),
            lambda d: d['directory_records'][0].update(source_row=99999),
            lambda d: d['directory_records'].append(copy.deepcopy(d['directory_records'][0])),
            lambda d: d['directory_records'].pop(),
            lambda d: d['directory_header']['fields'].pop(),
            lambda d: d['sources']['income'].update(sha256='0' * 64),
            lambda d: d['income_worksheet_headers']['rows'][0]['raw'].__setitem__(0, '2023-24, Final Survey 3'),
            lambda d: d['cohorts']['proposed_pure_offered_tested_grade']['subjects']['math'].update(usable=220),
            lambda d: d['cohorts']['proposed_pure_offered_tested_grade']['subjects']['math']['eligible_school_ids'].append('29-4324'),
            lambda d: d['roster_links'][0]['subjects']['math'].update(valid_scores=100),
            lambda d: d['roster_links'][0]['subjects']['math'].update(sampling_variance=0),
            lambda d: d['roster_links'][0]['subjects']['combined'].update(sampling_interval_available=0),
            lambda d: d['roster_links'][0]['profile']['grades'].__setitem__(14, '*'),
            lambda d: d['native_records']['assessments'][0]['raw'].__setitem__(9, '*'),
            lambda d: d['outside_roster_profiles'][0].update(exact_directory_match=False),
            lambda d: d['nonoperational_directory'].pop(),
            lambda d: d['coverage'].update(verified_valid_score_counts=False),
            lambda d: d['planning_identity_reconciliation']['planning_ES_school_ids'].pop(),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.validate(changed, self.payload)
        raw = self.document['directory_records'][0]['raw']
        self.assertEqual(audit.directory_identity(dict(raw, SCH_NAME='Renamed', LEA_NAME='Renamed')), '29-0311')
        self.assertEqual(audit.offered_evidence(dict(raw, G_8_OFFERED=''))['scope'], 'uncertain')
        payload = copy.deepcopy(self.payload)
        next(p for p in payload['profiles'] if p['id'] == '29-0311')['grades'][14] = '*'
        with self.assertRaises(ValueError):
            audit.validate(self.document, payload)


if __name__ == '__main__':
    unittest.main()
