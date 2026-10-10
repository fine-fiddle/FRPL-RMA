import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_palm_beach as audit


class PalmBeachDistrictAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.payload = audit.load_florida()
        cls.links = {r['school_id']: r for r in cls.document['roster_links']}

    def test_exact_roster_distinct_population_and_source_only_approval(self):
        c = audit.validate(self.document, self.payload)
        self.assertEqual((c['directory_records'], c['operational_schools'], c['exact_fall_profile_matches']), (238, 234, 230))
        self.assertEqual(c['operational_statuses'], {'Added': 2, 'Open': 232})
        self.assertEqual(c['nonoperational_statuses'], {'Closed': 3, 'Future': 1})
        self.assertEqual(c['operational_offered_scope'], {'ES': 170, 'HS': 26, 'mixed': 38})
        for name, profiles, applicable, usable in [
            ('native_enrolled_grade_school_contract',170,170,165),
            ('proposed_pure_lower_directory',170,168,165),
            ('proposed_pure_offered_tested_grade',168,168,165),
            ('pure_lower_enrolled_tested_evidence',168,168,165),
            ('pure_lower_primary_offers_only',2,0,0),
            ('native_grade_schools_with_mixed_offers',0,0,0),
        ]:
            group=self.document['cohorts'][name]
            self.assertEqual((group['profiles'],group['income_available_profiles']),(profiles,profiles))
            for subject in ['math','reading','combined']:
                self.assertEqual((group['subjects'][subject]['applicable'],group['subjects'][subject]['usable']),(applicable,usable))
        group=self.document['cohorts']['proposed_pure_offered_tested_grade']
        self.assertEqual(group['combined_ccd_charter'],{'No':141,'Yes':24})
        self.assertEqual(group['combined_ccd_school_type'],{'Regular School':164,'Career and Technical School':1})
        career=self.links['50-3441']
        self.assertEqual(career['ccd_flags']['school_type'],'Career and Technical School')
        self.assertEqual(career['ccd_flags']['charter'],'Yes')
        self.assertEqual(career['offered']['offered_tested_grades'],['6','7','8'])
        self.assertTrue(career['subjects']['combined']['district_usable'])
        self.assertEqual((career['subjects']['math']['native_rate'],career['subjects']['reading']['native_rate'],career['subjects']['combined']['native_rate']),(67,70,68.5))
        self.assertAlmostEqual(career['income']['percentage'],100*350/528)
        self.assertIs(self.document['approved_for_source'],False)
        self.assertIs(self.document['approved_for_modeling'],False)
        self.assertEqual(self.document['scope'],'audit_pending')
        self.assertNotIn('models',self.document)
        self.assertNotIn('snapshots',self.document)

    def test_full_directory_primary_offers_and_native_memberships_remain_distinct(self):
        inventory=self.document['cohorts']['exact_operational_pure_lower_directory']
        self.assertEqual((inventory['profiles'],inventory['native_fall_profile_matches']),(170,170))
        self.assertEqual(len(inventory['offered_tested_school_ids']),168)
        self.assertEqual(inventory['without_fall_profile_school_ids'],[])
        self.assertEqual(set(inventory['primary_only_school_ids']),{'50-1931','50-3100'})
        self.assertEqual(self.links['50-1931']['offered']['offered'],['PK','KG','1','2'])
        self.assertEqual(self.links['50-3100']['offered']['offered'],['PK','KG'])
        self.assertEqual(self.links['50-3100']['enrolled']['grade_values']['KG']['status'],'explicit_zero')
        for key in ['50-1931','50-3100']:
            self.assertFalse(self.links[key]['subjects']['combined']['district_applicable'])
            self.assertIsNotNone(self.links[key]['income']['percentage'])
        self.assertEqual(self.document['cohorts']['native_grade_schools_with_mixed_offers']['school_ids'],[])
        c=self.document['coverage']
        self.assertEqual((c['profiles_with_offered_enrolled_differences'],c['offered_with_explicit_zero_enrolled_grade_cells']),(39,79))
        self.assertEqual((c['profiles_with_protected_enrolled_grades'],c['protected_enrolled_grade_cells']),(40,109))
        self.assertEqual(c['profiles_with_positive_or_protected_enrolled_grade_without_offer'],0)
        self.assertEqual(c['pure_offered_tested_with_explicit_zero_enrolled_tested'],0)

    def test_unmatched_provider_and_nonoperational_records_do_not_acquire_outcomes(self):
        missing={'50-3081','50-3931','50-7023','50-9063'}
        self.assertEqual({k for k,r in self.links.items() if not r['matched']},missing)
        for key in missing:
            self.assertEqual(self.links[key]['offered']['scope'],'mixed')
            self.assertNotIn('income',self.links[key]);self.assertNotIn('subjects',self.links[key])
        self.assertEqual(len(self.document['nonoperational_directory']),4)
        self.assertEqual(self.document['outside_roster_profiles'],[])
        self.assertEqual(self.document['income_without_fall_registry_links'],[])
        self.assertEqual(self.document['native_assessments_without_operational_roster'],[])
        self.assertEqual((len(self.document['native_records']['profiles']),len(self.document['native_records']['assessments'])),(230,201))
        self.assertEqual(self.document['coverage']['provider_specific_virtual_assessment_rows'],2)
        self.assertEqual(self.document['coverage']['campus_assessment_rows'],199)
        self.assertEqual(self.document['coverage']['campus_charter_disagreements'],0)
        self.assertTrue(all(r['ccd_flags']['virtual_status'] is None for r in self.links.values()))
        provider=[a for a in self.document['native_records']['assessments'] if a['raw'][3] not in ('',None)]
        self.assertEqual([(a['id'],a['row'],a['raw'][3],a['raw'][9],a['raw'][6]) for a in provider],
                         [('50-7001',2712,'302',67,81),('50-7001',2713,'309',38,56)])
        virtual=self.links['50-7001']
        self.assertEqual(virtual['income']['individual_eligible'],9)
        self.assertEqual(virtual['income']['survey_enrollment'],89)
        self.assertIsNone(virtual['subjects']['math']['native_rate'])
        self.assertEqual([r['role'] for r in virtual['native_assessment_flags']],['provider_specific_virtual']*2)
        self.assertTrue(all(not virtual['subjects'][s]['district_usable'] for s in ['math','reading','combined']))

    def test_individual_income_true_zero_masked_same_year_rates_and_null_intervals(self):
        eligible=[r for r in self.links.values() if r['matched'] and r['subjects']['combined']['district_usable']]
        self.assertEqual(len(eligible),165)
        for r in eligible:
            raw=r['income']['raw'];self.assertEqual(r['income']['year'],2025)
            self.assertAlmostEqual(r['income']['percentage'],100*(raw[5]+raw[6]+raw[8])/raw[4])
            math,ela,combined=(r['subjects'][s] for s in ['math','reading','combined'])
            self.assertEqual(math['native_rate'],math['native_achievement_raw'])
            self.assertEqual(ela['native_rate'],ela['native_achievement_raw'])
            self.assertEqual(combined['native_rate'],(math['native_rate']+ela['native_rate'])/2)
        self.assertTrue(all(r['income']['percentage']>0 for r in eligible))
        for key,total in [('50-2791',165),('50-3100',32)]:
            self.assertEqual(self.links[key]['income']['percentage'],0.)
            self.assertEqual(self.links[key]['income']['survey_enrollment'],total)
            self.assertEqual(self.links[key]['income']['native_fields']['provision2_4'],0)
            self.assertFalse(self.links[key]['subjects']['combined']['district_usable'])
        self.assertTrue(self.links['50-2791']['subjects']['combined']['district_applicable'])
        self.assertFalse(self.links['50-3100']['subjects']['combined']['district_applicable'])
        self.assertEqual(self.document['coverage']['native_profiles_with_verified_zero_individual_income'],7)
        self.assertEqual(self.document['coverage']['native_profiles_with_masked_income_count_cells'],2)
        self.assertEqual(self.document['coverage']['native_profiles_without_income_row'],0)
        for key in ['50-3039','50-3091']:
            self.assertEqual(self.links[key]['offered']['scope'],'mixed')
            self.assertEqual(self.links[key]['income']['raw'][4:9],['*']*5)
            self.assertIsNone(self.links[key]['income']['percentage'])
            self.assertIsNone(self.links[key]['income']['survey_enrollment'])
        for r in self.links.values():
            for value in r.get('subjects',{}).values():
                self.assertIsNone(value['valid_scores']);self.assertIsNone(value['sampling_variance'])
                self.assertIs(value['sampling_interval_available'],False)

    def test_protected_or_masked_counts_and_provider_exclusions_never_become_zero(self):
        source=self.links['50-3441'];profile=copy.deepcopy(source['profile'])
        profile['grades'][14]='*'
        evidence=audit.enrolled_evidence(profile,source['offered'])
        self.assertFalse(evidence['native_grade_school_contract'])
        self.assertIsNone(evidence['grade_values']['9']['reported_count'])
        self.assertEqual(evidence['grade_values']['9']['status'],'protected_positive')
        campus=next(a for a in self.document['native_records']['assessments'] if a['id']=='50-3441')
        for field,value,reason in [(47,'Y','collocated'),(3,'302','Provider-specific virtual'),(9,'*','unavailable')]:
            changed=copy.deepcopy(campus);changed['raw'][field]=value
            result=audit.subjects(source['profile'],changed,None)['math']
            self.assertIsNone(result['native_rate']);self.assertFalse(result['district_usable'])
            self.assertIn(reason,result['native_outcome_exclusion'])
        for code4 in ['*',12]:
            changed=copy.deepcopy(source['profile']);changed['income_raw'][7]=code4
            self.assertIsNone(audit.income_record(changed)['percentage'])
        changed['income_raw']=None
        self.assertIsNone(audit.income_record(changed)['percentage'])

    def test_offline_validation_replays_complete_pinned_evidence_without_downloads(self):
        with mock.patch.object(audit.zipfile, 'ZipFile', side_effect=AssertionError('No raw ZIP')), \
                mock.patch.object(audit.florida.openpyxl, 'load_workbook', side_effect=AssertionError('No workbook')):
            self.assertEqual(audit.validate(self.document)['operational_schools'], 234)
        self.assertEqual(audit.fingerprint(self.document['directory_header']), audit.DIRECTORY_HEADER_SHA)
        header = self.document['income_worksheet_headers']
        self.assertEqual(header['worksheet'], '2425 FS3_Schl')
        self.assertEqual([r['source_row'] for r in header['rows']], [1, 2, 3])
        self.assertIn('2024-25, Final Survey 3', header['rows'][0]['raw'][0])
        self.assertEqual(set(self.document['native_records']['source_notes']), {'lunch', 'assessment', 'grade'})

    def test_exact_planning_ids_metadata_and_scope_are_discovery_only(self):
        agency = next(a for a in json.loads(audit.PLANNING.read_text())['agencies'] if a['nces_lea_id'] == audit.LEA)
        profiles = {p['id']: p for p in self.payload['profiles'] if p['id'].startswith('50-')}
        actual = audit.planning_reconciliation(agency, self.document['directory_records'], profiles)
        self.assertEqual(actual, self.document['planning_identity_reconciliation'])
        self.assertEqual(actual['source_proposed_not_in_planning_ES'], [])
        self.assertEqual(actual['planning_ES_not_in_source_proposed'], [])
        for mutate in [lambda a: a.update(state='GA'), lambda a: a.update(native_lea_id='FL-48'),
                       lambda a: a.update(enrollment=189635), lambda a: a.update(enrollment_flag='Suppressed'),
                       lambda a: a['potential_cohorts'].update(ES=168.),
                       lambda a: a['potential_school_ids']['ES'].pop(),
                       lambda a: a['potential_school_ids']['ES'].__setitem__(0, '120087008438'),
                       lambda a: a['potential_school_ids']['HS'].__setitem__(0, a['potential_school_ids']['HS'][1]),
                       lambda a: a['potential_school_ids']['HS'].__setitem__(0, a['potential_school_ids']['ES'][0])]:
            changed = copy.deepcopy(agency); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.planning_reconciliation(changed, self.document['directory_records'], profiles)
        profiles.pop('50-3441')
        self.assertEqual(audit.planning_reconciliation(agency, self.document['directory_records'], profiles)['planning_ES_not_in_source_proposed'], ['50-3441'])

    def test_original_membership_proof_preserves_zero_mixed_and_positive_primary(self):
        evidence=self.document['planning_membership_evidence']
        self.assertEqual(audit.fingerprint(evidence),audit.PLANNING_MEMBERSHIP_SHA)
        self.assertEqual(len(evidence['records']),58)
        proof={r['school_id']:r for r in self.document['planning_membership_exclusions']}
        self.assertEqual(len(proof),6)
        self.assertEqual((proof['50-1931']['membership_count'],proof['50-1931']['total_source_row']),(569,2625085))
        self.assertEqual((proof['50-3100']['membership_count'],proof['50-3100']['total_source_row']),(25,2630569))
        for key,row in proof.items():
            self.assertEqual(row['membership_flag'],'Reported')
            if not self.links[key]['matched']:
                self.assertEqual(row['membership_count'],0)
                self.assertNotIn('income',self.links[key])
                self.assertEqual(self.links[key]['offered']['scope'],'mixed')
        # CCD569, Fall569 and February564 are different observations; don't substitute them.
        self.assertEqual(self.links['50-1931']['income']['survey_enrollment'],564)
        self.assertEqual(self.links['50-3100']['income']['survey_enrollment'],32)
        for mutate in [lambda e:e['records'].pop(),
                       lambda e:e['records'][0]['raw'].update(STUDENT_COUNT='1'),
                       lambda e:e['records'][0]['raw'].update(DMS_FLAG='Suppressed'),
                       lambda e:e['records'][0]['raw'].update(ST_SCHID='FL-50-3441'),
                       lambda e:e['records'][0].update(source_row=2625085.),
                       lambda e:e['header']['fields'].pop(),
                       lambda e:e['source'].update(sha256='0'*64)]:
            changed=copy.deepcopy(self.document);mutate(changed['planning_membership_evidence'])
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                audit.validate(changed,self.payload)

    def test_typed_source_scope_identity_suppression_and_derived_values_cannot_drift(self):
        mutations = [
            lambda d: d.update(year=2024), lambda d: d.update(approved_for_source=0),
            lambda d: d.update(approved_for_modeling=True), lambda d: d.update(scope='ready'),
            lambda d: d['directory_records'][0]['raw'].update(SCHOOL_YEAR='2023-2024'),
            lambda d: d['directory_records'][0]['raw'].update(ST_LEAID='FL-48'),
            lambda d: d['directory_records'][0]['raw'].update(NCESSCH='120087008438'),
            lambda d: d['directory_records'][0]['raw'].update(G_9_OFFERED='Yes'),
            lambda d: d['directory_records'][0].update(source_row=99999),
            lambda d: d['directory_records'].append(copy.deepcopy(d['directory_records'][0])),
            lambda d: d['directory_records'].pop(), lambda d: d['directory_header']['fields'].pop(),
            lambda d: d['sources']['income'].update(sha256='0' * 64),
            lambda d: d['income_worksheet_headers']['rows'][0]['raw'].__setitem__(0, '2023-24, Final Survey 3'),
            lambda d: d['cohorts']['proposed_pure_offered_tested_grade']['subjects']['math'].update(usable=166),
            lambda d: d['cohorts']['proposed_pure_offered_tested_grade']['subjects']['math']['eligible_school_ids'].append('50-7001'),
            lambda d: next(r for r in d['roster_links'] if r['school_id'] == '50-3441')['income']['raw'].__setitem__(5, False),
            lambda d: next(r for r in d['roster_links'] if r['school_id'] == '50-3441')['subjects']['math'].update(valid_scores=183),
            lambda d: next(r for r in d['roster_links'] if r['school_id'] == '50-3441')['subjects']['combined'].update(sampling_interval_available=0),
            lambda d: next(a for a in d['native_records']['assessments'] if a['id'] == '50-7001')['raw'].__setitem__(3, ''),
            lambda d: d['nonoperational_directory'].pop(),
            lambda d: d['coverage'].update(verified_valid_score_counts=False),
            lambda d: d['planning_identity_reconciliation']['planning_ES_school_ids'].pop(),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.validate(changed, self.payload)
        raw = self.document['directory_records'][0]['raw']
        self.assertEqual(audit.directory_identity(dict(raw, SCH_NAME='Renamed', LEA_NAME='Renamed')), audit.directory_identity(raw))
        self.assertEqual(audit.offered_evidence(dict(raw, G_8_OFFERED=''))['scope'], 'uncertain')
        payload = copy.deepcopy(self.payload)
        next(p for p in payload['profiles'] if p['id'] == '50-3441')['income_raw'][5] = False
        with self.assertRaises(ValueError):
            audit.validate(self.document, payload)


if __name__ == '__main__':
    unittest.main()
