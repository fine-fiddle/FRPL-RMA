import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_miami_dade as audit


class MiamiDadeDistrictAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.payload = audit.load_florida()
        cls.links = {r['school_id']: r for r in cls.document['roster_links']}

    def test_exact_roster_and_distinct_native_proposed_populations(self):
        coverage = audit.validate(self.document, self.payload)
        self.assertEqual((coverage['directory_records'], coverage['operational_schools'],
                          coverage['exact_fall_profile_matches']), (544, 530, 521))
        self.assertEqual(coverage['operational_offered_scope'], {'ES': 370, 'HS': 87, 'mixed': 73})
        self.assertEqual(coverage['nonoperational_statuses'], {'Closed': 11, 'Future': 3})
        for name, profiles, applicable, usable in [
            ('native_enrolled_grade_school_contract', 380, 380, 361),
            ('proposed_pure_lower_directory', 370, 365, 357),
            ('proposed_pure_offered_tested_grade', 365, 365, 357),
            ('pure_lower_enrolled_tested_evidence', 361, 361, 357),
            ('pure_lower_primary_offers_only', 5, 0, 0),
            ('native_grade_schools_with_mixed_offers', 10, 10, 4),
        ]:
            cohort = self.document['cohorts'][name]
            self.assertEqual(cohort['profiles'], profiles)
            for subject in ['math', 'reading', 'combined']:
                self.assertEqual((cohort['subjects'][subject]['applicable'], cohort['subjects'][subject]['usable']),
                                 (applicable, usable))
        proposed = self.document['cohorts']['proposed_pure_offered_tested_grade']
        self.assertIn('does not assert tested-grade applicability',
                      self.document['cohorts']['native_enrolled_grade_school_contract']['applicable_basis'])
        self.assertEqual(proposed['combined_ccd_charter'], {'No': 261, 'Yes': 96})
        self.assertEqual(proposed['combined_ccd_school_type'], {'Regular School': 357})
        missing = [r for r in self.links.values() if r['matched'] and
                   r['subjects']['combined']['district_applicable'] and not r['subjects']['combined']['district_usable']]
        self.assertEqual(len(missing), 8)
        self.assertTrue(all(r['ccd_flags']['charter'] == 'Yes' for r in missing))
        self.assertEqual(sorted(r['ccd_flags']['school_type'] for r in missing),
                         ['Alternative School'] * 2 + ['Regular School'] * 5 + ['Special Education School'])
        self.assertFalse(self.document['approved_for_modeling'])
        self.assertNotIn('models', self.document)
        self.assertNotIn('snapshots', self.document)

    def test_offered_enrolled_and_primary_only_differences_remain_explicit(self):
        coverage = self.document['coverage']
        self.assertEqual((coverage['profiles_with_offered_enrolled_differences'],
                          coverage['offered_with_explicit_zero_enrolled_grade_cells']), (72, 205))
        self.assertEqual((coverage['profiles_with_protected_enrolled_grades'],
                          coverage['protected_enrolled_grade_cells']), (46, 151))
        self.assertEqual(coverage['profiles_with_positive_or_protected_enrolled_grade_without_offer'], 0)
        self.assertEqual(set(self.document['cohorts']['pure_lower_primary_offers_only']['school_ids']),
                         {'13-2531', '13-8016', '13-9013', '13-0331', '13-0351'})
        zero_enrolled = {r['school_id'] for r in self.links.values() if r['matched'] and
                         r['offered']['scope'] == 'ES' and r['offered']['offered_tested_grades'] and
                         r['enrolled']['explicit_zero_tested_grades']}
        self.assertEqual(zero_enrolled, {'13-0402', '13-4328', '13-5119', '13-5219'})
        for key in zero_enrolled:
            self.assertTrue(self.links[key]['subjects']['math']['district_applicable'])
            self.assertFalse(self.links[key]['subjects']['math']['district_usable'])
        extra_usable = set(self.document['cohorts']['native_grade_schools_with_mixed_offers']['subjects']['combined']['eligible_school_ids'])
        self.assertEqual(extra_usable, {'13-0441', '13-2332', '13-3034', '13-6047'})
        for key in extra_usable:
            self.assertTrue(self.links[key]['subjects']['combined']['native_grade_school_usable'])
            self.assertFalse(self.links[key]['subjects']['combined']['district_usable'])

    def test_unmatched_outside_and_provider_identity_cannot_expand_population(self):
        unmatched = {key for key, r in self.links.items() if not r['matched']}
        self.assertEqual(unmatched, {'13-7013', '13-7023', '13-7834', '13-8005', '13-8017',
                                     '13-8139', '13-8901', '13-8911', '13-9733'})
        for key in unmatched:
            self.assertNotIn('income', self.links[key])
            self.assertNotIn('subjects', self.links[key])
        self.assertEqual([r['school_id'] for r in self.document['outside_roster_profiles']], ['13-7006'])
        self.assertNotIn('13-7006', {audit.directory_identity(r['raw']) for r in self.document['directory_records']})
        self.assertEqual(len(self.document['native_records']['profiles']), 522)
        self.assertEqual(len(self.document['native_records']['assessments']), 470)
        provider = [r for r in self.document['native_records']['assessments'] if r['raw'][3] not in ('', None)]
        self.assertEqual([(r['id'], r['row'], r['raw'][3]) for r in provider], [('13-7001', 1032, '302')])
        self.assertEqual(audit.florida.outcome(provider[0]['raw'], 'math')[1],
                         'Provider-specific virtual school achievement lacks matching provider income')
        self.assertEqual(self.document['coverage']['campus_charter_disagreements'], 0)
        self.assertEqual(self.document['coverage']['collocated_assessment_rows'], 0)
        self.assertTrue(all(r['ccd_flags']['virtual_status'] is None for r in self.links.values()))
        high = next(r for r in self.links.values() if r['matched'] and r['offered']['scope'] == 'HS')
        self.assertTrue(all(not v['native_grade_school_usable'] and not v['district_usable']
                            for v in high['subjects'].values()))

    def test_protected_membership_missing_income_and_native_exclusions_never_become_zero(self):
        source = next(r for r in self.links.values() if r['matched'] and r['subjects']['math']['district_usable'])
        profile = copy.deepcopy(source['profile'])
        profile['grades'][14] = '*'
        evidence = audit.enrolled_evidence(profile, source['offered'])
        self.assertFalse(evidence['native_grade_school_contract'])
        self.assertIsNone(evidence['grade_values']['9']['reported_count'])
        self.assertEqual(evidence['grade_values']['9']['status'], 'protected_positive')
        profile = copy.deepcopy(source['profile'])
        profile['grades'][8] = '*'
        evidence = audit.enrolled_evidence(profile, source['offered'])
        self.assertTrue(evidence['native_grade_school_contract'])
        self.assertIn('3', evidence['positive_or_protected_tested_grades'])
        self.assertIsNone(evidence['grade_values']['3']['reported_count'])
        campus = next(a for a in self.document['native_records']['assessments']
                      if a['id'] == profile['id'] and a['raw'][3] in ('', None))
        for provision2 in [12, '*']:
            changed = copy.deepcopy(profile)
            changed['income_raw'][7] = provision2
            result = audit.subjects(changed, campus, None)
            self.assertFalse(result['math']['district_usable'])
            self.assertIsNone(audit.income_record(changed)['percentage'])
            self.assertEqual(audit.income_record(changed)['raw'][7], provision2)
        collocated = copy.deepcopy(campus)
        collocated['raw'][47] = 'Y'
        result = audit.subjects(profile, collocated, None)
        self.assertFalse(result['math']['native_grade_school_usable'])
        self.assertIn('collocated', result['math']['native_outcome_exclusion'])
        suppressed = copy.deepcopy(campus)
        suppressed['raw'][9] = '*'
        result = audit.subjects(profile, suppressed, None)
        self.assertIsNone(result['math']['native_rate'])
        self.assertIsNone(result['combined']['native_rate'])
        self.assertEqual(result['math']['native_achievement_raw'], '*')
        for value in result.values():
            self.assertIsNone(value['valid_scores'])
            self.assertFalse(value['sampling_interval_available'])

    def test_offline_validation_needs_no_native_workbooks_or_raw_archive(self):
        with mock.patch.object(audit.zipfile, 'ZipFile', side_effect=AssertionError('Raw archive unavailable')), \
                mock.patch.object(audit.florida.openpyxl, 'load_workbook', side_effect=AssertionError('Native workbook unavailable')):
            self.assertEqual(audit.validate(self.document)['operational_schools'], 530)
        header = self.document['income_worksheet_headers']
        self.assertEqual(header['worksheet'], '2425 FS3_Schl')
        self.assertEqual([r['source_row'] for r in header['rows']], [1, 2, 3])
        self.assertIn('2024-25, Final Survey 3', header['rows'][0]['raw'][0])
        self.assertEqual(header['rows'][2]['raw'][5:9], [
            '# of Free Lunch Students (Codes D&F)', '# of Reduced-Price Lunch Students (Codes 3&E)',
            '# of Provision 2 Students (Code 4)', '# of Direct Certification CEP Students (Codes C&R)'])

    def test_wrong_year_identity_scope_headers_and_provenance_fail(self):
        mutations = [
            lambda d: d.update(approved_for_modeling=True),
            lambda d: d.update(year=2024),
            lambda d: d['directory_records'][0]['raw'].update(SCHOOL_YEAR='2023-2024'),
            lambda d: d['directory_records'][0]['raw'].update(ST_LEAID='FL-12'),
            lambda d: d['directory_records'][0]['raw'].update(ST_SCHID='FL-12-0041'),
            lambda d: d['directory_records'][0]['raw'].update(NCESSCH='120000000367'),
            lambda d: d['directory_records'][0]['raw'].update(G_9_OFFERED='Yes'),
            lambda d: d['directory_records'][0].update(source_row=99999),
            lambda d: d['directory_records'].append(copy.deepcopy(d['directory_records'][0])),
            lambda d: d['directory_records'].pop(),
            lambda d: d['sources']['income'].update(sha256='0' * 64),
            lambda d: d['income_worksheet_headers']['rows'][0]['raw'].__setitem__(0, '2023-24, Final Survey 3'),
            lambda d: d['income_worksheet_headers']['rows'][2]['raw'].__setitem__(5, 'USDA adjusted numerator'),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.validate(changed, self.payload)
        raw = self.document['directory_records'][0]['raw']
        self.assertEqual(audit.directory_identity(dict(raw, SCH_NAME='Any name', LEA_NAME='Any district')), '13-0041')
        self.assertEqual(audit.offered_evidence(dict(raw, G_8_OFFERED=''))['scope'], 'uncertain')

    def test_retained_source_cells_exclusions_memberships_and_denominators_cannot_drift(self):
        mutations = [
            lambda d: d['cohorts']['proposed_pure_offered_tested_grade']['subjects']['combined'].update(usable=361),
            lambda d: d['cohorts']['proposed_pure_offered_tested_grade']['subjects']['math']['eligible_school_ids'].append('13-0441'),
            lambda d: d['roster_links'][0]['subjects']['math'].update(valid_scores=100),
            lambda d: d['roster_links'][0]['subjects']['combined'].update(sampling_interval_available=True),
            lambda d: d['roster_links'][0]['profile']['grades'].__setitem__(14, '*'),
            lambda d: d['roster_links'][0]['income']['raw'].__setitem__(7, 50),
            lambda d: d['native_records']['assessments'][0]['raw'].__setitem__(9, '*'),
            lambda d: d['outside_roster_profiles'].clear(),
            lambda d: d['nonoperational_directory'].pop(),
            lambda d: d['coverage'].update(protected_enrolled_grade_cells=0),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.validate(changed, self.payload)
        payload = copy.deepcopy(self.payload)
        native = next(p for p in payload['profiles'] if p['id'] == '13-0041')
        native['grades'][14] = '*'
        with self.assertRaises(ValueError):
            audit.validate(self.document, payload)


if __name__ == '__main__':
    unittest.main()
