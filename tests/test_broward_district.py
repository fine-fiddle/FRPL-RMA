import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_broward as audit


class BrowardDistrictAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.payload = audit.load_florida()
        cls.links = {r['school_id']: r for r in cls.document['roster_links']}

    def test_exact_roster_and_distinct_source_proposed_populations(self):
        c = audit.validate(self.document, self.payload)
        self.assertEqual((c['directory_records'], c['operational_schools'], c['exact_fall_profile_matches']),
                         (327, 325, 324))
        self.assertEqual(c['operational_statuses'], {'Added': 2, 'Open': 323})
        self.assertEqual(c['nonoperational_statuses'], {'Closed': 2})
        self.assertEqual(c['operational_offered_scope'], {'ES': 249, 'HS': 45, 'mixed': 31})
        for name, profiles, applicable, usable, income in [
            ('native_enrolled_grade_school_contract', 252, 252, 244, 251),
            ('proposed_pure_lower_directory', 249, 243, 241, 248),
            ('proposed_pure_offered_tested_grade', 243, 243, 241, 243),
            ('pure_lower_enrolled_tested_evidence', 242, 242, 241, 242),
            ('pure_lower_primary_offers_only', 6, 0, 0, 5),
            ('native_grade_schools_with_mixed_offers', 3, 3, 3, 3),
        ]:
            group = self.document['cohorts'][name]
            self.assertEqual((group['profiles'], group['income_available_profiles']), (profiles, income))
            for subject in ['math', 'reading', 'combined']:
                self.assertEqual((group['subjects'][subject]['applicable'], group['subjects'][subject]['usable']),
                                 (applicable, usable))
        group = self.document['cohorts']['proposed_pure_offered_tested_grade']
        self.assertEqual(group['combined_ccd_charter'], {'No': 176, 'Yes': 65})
        self.assertEqual(group['combined_ccd_school_type'], {'Regular School': 241})
        self.assertFalse(self.document['approved_for_source'])
        self.assertFalse(self.document['approved_for_modeling'])
        self.assertEqual(self.document['scope'], 'audit_pending')
        self.assertNotIn('models', self.document)
        self.assertNotIn('snapshots', self.document)

    def test_offered_enrolled_primary_and_mixed_memberships_remain_distinct(self):
        c = self.document['coverage']
        self.assertEqual((c['profiles_with_offered_enrolled_differences'],
                          c['offered_with_explicit_zero_enrolled_grade_cells']), (44, 136))
        self.assertEqual((c['profiles_with_protected_enrolled_grades'], c['protected_enrolled_grade_cells']), (47, 96))
        self.assertEqual(c['profiles_with_positive_or_protected_enrolled_grade_without_offer'], 0)
        self.assertEqual(set(self.document['cohorts']['pure_lower_primary_offers_only']['school_ids']),
                         {'06-5511', '06-5521', '06-5541', '06-5561', '06-5581', '06-5641'})
        zero_tested = {r['school_id'] for r in self.links.values() if r['matched'] and
                       r['offered']['scope'] == 'ES' and r['offered']['offered_tested_grades'] and
                       r['enrolled']['explicit_zero_tested_grades']}
        self.assertEqual(zero_tested, {'06-5017'})
        self.assertTrue(self.links['06-5017']['subjects']['math']['district_applicable'])
        self.assertFalse(self.links['06-5017']['subjects']['math']['district_usable'])
        mixed = set(self.document['cohorts']['native_grade_schools_with_mixed_offers']['subjects']['combined']['eligible_school_ids'])
        self.assertEqual(mixed, {'06-5038', '06-5355', '06-5381'})
        for key in mixed:
            self.assertTrue(self.links[key]['subjects']['combined']['native_grade_school_usable'])
            self.assertFalse(self.links[key]['subjects']['combined']['district_usable'])
            self.assertEqual(self.links[key]['ccd_flags']['charter'], 'Yes')

    def test_income_only_provider_and_nonoperational_records_cannot_expand_scope(self):
        self.assertEqual({k for k, r in self.links.items() if not r['matched']}, {'06-0007'})
        self.assertNotIn('subjects', self.links['06-0007'])
        income = self.document['income_without_fall_registry_links']
        self.assertEqual(len(income), 1)
        row = income[0]
        self.assertEqual((row['school_id'], row['source_row'], row['survey_enrollment'], row['individual_eligible']),
                         ('06-0007', 235, 31, 10))
        self.assertAlmostEqual(row['percentage'], 100 * 10 / 31)
        self.assertTrue(row['exact_operational_roster_match'])
        self.assertFalse(row['grade_scope_available'])
        self.assertFalse(row['district_usable'])
        self.assertEqual(self.document['outside_roster_profiles'], [])
        self.assertEqual(self.document['native_assessments_without_operational_roster'], [])
        self.assertEqual({r['school_id'] for r in self.document['nonoperational_directory']}, {'06-6051', '06-6017'})
        provider = [a for a in self.document['native_records']['assessments'] if a['raw'][3] not in ('', None)]
        self.assertEqual([(a['id'], a['row'], a['raw'][3]) for a in provider], [('06-7001', 492, '302')])
        self.assertIn('Provider-specific virtual', audit.florida.outcome(provider[0]['raw'], 'math')[1])
        self.assertEqual(self.links['06-7001']['income']['individual_eligible'], 2)
        self.assertAlmostEqual(self.links['06-7001']['income']['percentage'], 100 * 2 / 86)
        self.assertFalse(self.links['06-7001']['subjects']['math']['district_usable'])
        self.assertEqual(self.document['coverage']['collocated_assessment_rows'], 0)
        self.assertEqual(self.document['coverage']['campus_charter_disagreements'], 0)
        self.assertTrue(all(r['ccd_flags']['virtual_status'] is None for r in self.links.values()))

    def test_individual_income_true_zero_masking_and_native_rates(self):
        for key in ['06-5541', '06-5581']:
            self.assertEqual(self.links[key]['income']['percentage'], 0)
            self.assertIsNone(self.links[key]['income']['exclusion'])
        masked = self.links['06-5561']['income']
        self.assertEqual(masked['native_fields']['provision2_4'], '*')
        self.assertIsNone(masked['individual_eligible'])
        self.assertIsNone(masked['percentage'])
        eligible = [r for r in self.links.values() if r['matched'] and r['subjects']['combined']['district_usable']]
        self.assertEqual(len(eligible), 241)
        for r in eligible:
            raw = r['income']['raw']
            self.assertAlmostEqual(r['income']['percentage'], 100 * (raw[5] + raw[6] + raw[8]) / raw[4])
            math, ela, combined = (r['subjects'][s] for s in ['math', 'reading', 'combined'])
            self.assertEqual(math['native_rate'], math['native_achievement_raw'])
            self.assertEqual(ela['native_rate'], ela['native_achievement_raw'])
            self.assertEqual(combined['native_rate'], (math['native_rate'] + ela['native_rate']) / 2)
        for r in self.links.values():
            for value in r.get('subjects', {}).values():
                self.assertIsNone(value['valid_scores'])
                self.assertIsNone(value['sampling_variance'])
                self.assertFalse(value['sampling_interval_available'])

    def test_native_protected_counts_and_program_exclusions_are_not_zero(self):
        source = self.links['06-0011']
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
        campus = next(a for a in self.document['native_records']['assessments'] if a['id'] == '06-0011')
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
            self.assertEqual(audit.validate(self.document)['operational_schools'], 325)
        self.assertEqual(audit.fingerprint(self.document['directory_header']), audit.DIRECTORY_HEADER_SHA)
        header = self.document['income_worksheet_headers']
        self.assertEqual(header['worksheet'], '2425 FS3_Schl')
        self.assertEqual([r['source_row'] for r in header['rows']], [1, 2, 3])
        self.assertIn('2024-25, Final Survey 3', header['rows'][0]['raw'][0])
        self.assertEqual(set(self.document['native_records']['source_notes']), {'lunch', 'assessment', 'grade'})

    def test_planning_reconciliation_rejects_foreign_missing_duplicate_and_changed_metadata(self):
        agency = next(a for a in json.loads(audit.PLANNING.read_text())['agencies'] if a['nces_lea_id'] == audit.LEA)
        profiles = {p['id']: p for p in self.payload['profiles'] if p['id'].startswith('06-')}
        actual = audit.planning_reconciliation(agency, self.document['directory_records'], profiles)
        self.assertEqual(actual, self.document['planning_identity_reconciliation'])
        self.assertEqual(actual['source_proposed_not_in_planning_ES'], [])
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
        profiles.pop('06-0011')
        self.assertEqual(audit.planning_reconciliation(agency, self.document['directory_records'], profiles)
                         ['planning_ES_not_in_source_proposed'], ['06-0011'])

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
            lambda d: d['cohorts']['proposed_pure_offered_tested_grade']['subjects']['math'].update(usable=244),
            lambda d: d['cohorts']['proposed_pure_offered_tested_grade']['subjects']['math']['eligible_school_ids'].append('06-5355'),
            lambda d: d['roster_links'][0]['subjects']['math'].update(valid_scores=100),
            lambda d: d['roster_links'][0]['subjects']['math'].update(sampling_variance=0),
            lambda d: d['roster_links'][0]['subjects']['combined'].update(sampling_interval_available=0),
            lambda d: d['roster_links'][0]['profile']['grades'].__setitem__(14, '*'),
            lambda d: d['native_records']['assessments'][0]['raw'].__setitem__(9, '*'),
            lambda d: d['income_without_fall_registry_links'][0].update(district_usable=True),
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
        self.assertEqual(audit.directory_identity(dict(raw, SCH_NAME='Renamed', LEA_NAME='Renamed')), '06-0011')
        self.assertEqual(audit.offered_evidence(dict(raw, G_8_OFFERED=''))['scope'], 'uncertain')
        payload = copy.deepcopy(self.payload)
        next(p for p in payload['profiles'] if p['id'] == '06-0011')['grades'][14] = '*'
        with self.assertRaises(ValueError):
            audit.validate(self.document, payload)


if __name__ == '__main__':
    unittest.main()
