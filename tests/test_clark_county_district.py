import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_clark_county as audit


class ClarkCountyDistrictAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.snapshot = audit.load_nevada()
        cls.links = {r['school_id']: r for r in cls.document['roster_links']}
        cls.directory = {r['raw']['NCESSCH']: r['raw'] for r in cls.document['raw_inputs']['directory']['records']}

    def test_exact_operational_roster_and_separate_source_populations(self):
        c = audit.validate(self.document, self.snapshot)
        self.assertEqual((c['directory_records'], c['operational_schools'], c['nonoperational_schools']), (380, 379, 1))
        self.assertEqual(c['operational_statuses'], {'New': 1, 'Open': 378})
        self.assertEqual(c['nonoperational_statuses'], {'Future': 1})
        self.assertEqual(c['operational_graded_offered_scope'], {'high': 55, 'lower': 302, 'mixed': 22})
        self.assertEqual(c['operational_ungraded_offered'], 379)
        for key, count, applicable, usable in [
            ('native_grade_school_configurations', 299, 298, 286),
            ('native_offered_tested_grade', 298, 298, 286),
            ('native_positive_membership_tested_candidates', 296, 296, 286),
            ('native_configurations_with_usable_income', 291, 290, 286),
            ('historical_native_source_profiles', 289, 289, 286),
            ('native_primary_only', 1, 0, 0),
            ('mixed_offers_with_native_g38', 15, 0, 0),
        ]:
            cohort = self.document['cohorts'][key]
            self.assertEqual(cohort['profiles'], count)
            for subject in ['math', 'reading', 'combined']:
                self.assertEqual((cohort['subjects'][subject]['applicable'], cohort['subjects'][subject]['usable']), (applicable, usable))
        cohort = self.document['cohorts']['historical_native_source_profiles']
        self.assertEqual(cohort['combined_ccd_charter'], {'No': 283, 'Yes': 3})
        self.assertEqual(cohort['combined_ccd_school_type'], {'Regular School': 286})
        self.assertFalse(self.document['approved_for_source'])
        self.assertFalse(self.document['approved_for_modeling'])
        self.assertNotIn('models', self.document)

    def test_ungraded_exception_requires_reported_zero_and_reconciled_membership(self):
        key = '320006000008'
        link = self.links[key]; raw = self.directory[key]
        rows = [r for r in self.document['raw_inputs']['membership']['records'] if r['raw']['NCESSCH'] == key]
        total = next(r['raw'] for r in rows if r['raw']['TOTAL_INDICATOR'] == 'Education Unit Total')
        grades = {r['raw']['GRADE']: r['raw'] for r in rows if r['raw']['TOTAL_INDICATOR'] == 'Subtotal 4 - By Grade'}
        self.assertTrue(audit.nevada.grade_school(raw, grades, total))
        self.assertFalse(link['offered']['strict_pure_offered_lower'])
        for count, flag in [('1', 'Reported'), ('0', 'Suppressed'), ('', 'Missing')]:
            changed = copy.deepcopy(grades)
            changed['Ungraded'].update(STUDENT_COUNT=count, DMS_FLAG=flag)
            self.assertFalse(audit.nevada.grade_school(raw, changed, total))
        changed = copy.deepcopy(grades); changed['Grade 3']['STUDENT_COUNT'] = '117'
        self.assertFalse(audit.nevada.grade_school(raw, changed, total))
        changed = copy.deepcopy(grades); changed['Grade 3']['DMS_FLAG'] = 'Suppressed'
        self.assertFalse(audit.nevada.grade_school(raw, changed, total))
        changed = copy.deepcopy(grades); changed['Grade 9'] = dict(changed['Grade 3'], STUDENT_COUNT='1')
        self.assertFalse(audit.nevada.grade_school(raw, changed, total))
        for key in ['320006000740', '320006000797', '320006000814']:
            self.assertEqual(self.links[key]['offered']['high'], 'KG')
            self.assertFalse(self.links[key]['enrolled']['native_grade_school_contract'])
            self.assertFalse(self.links[key]['offered']['offered_tested_grades'])

    def test_primary_zero_income_suppression_and_type_missingness_remain_distinct(self):
        primary = self.links['320006000012']
        self.assertEqual((primary['income']['reported_membership'], primary['income']['reported_direct_certification']), (356, 125))
        self.assertFalse(primary['subjects']['math']['applicable'])
        self.assertFalse(primary['native_g38_pair'])
        for key in ['320006000080', '320006000807']:
            self.assertEqual(self.links[key]['income']['reported_membership'], 0)
            self.assertIsNone(self.links[key]['income']['percentage'])
            self.assertTrue(self.links[key]['enrolled']['native_grade_school_contract'])
            self.assertTrue(self.links[key]['subjects']['math']['applicable'])
        suppressed = self.links['320006000037']['income']
        self.assertEqual(suppressed['direct_status'], 'Suppressed')
        self.assertIsNone(suppressed['reported_direct_certification'])
        self.assertIsNone(suppressed['percentage'])
        self.assertEqual(self.links['320006000488']['income']['direct_status'], 'absent')
        variety = self.links['320006000619']
        self.assertEqual(variety['income']['percentage'], 100 * 22 / 28)
        self.assertFalse(variety['native_g38_pair'])
        self.assertFalse(variety['subjects']['combined']['usable'])
        for key in ['320006000010', '320006000099', '320006000607']:
            link = self.links[key]
            self.assertTrue(link['historical_state_source_profile'])
            for subject in ['math', 'reading']:
                self.assertEqual(link['subjects'][subject]['raw_rate'], '*')
                self.assertIsNone(link['subjects'][subject]['native_rate'])
            self.assertFalse(link['subjects']['combined']['usable'])

    def test_native_identity_renamed_charters_virtual_metadata_and_grade_totals(self):
        c = self.document['coverage']
        self.assertEqual((c['assessment_rows'], c['native_g38_pairs']), (2468, 310))
        self.assertEqual(c['g38_edc_virtual_rows'], {'No': 614, 'Supplemental virtual': 2, 'Yes': 4})
        self.assertTrue(all(not r for r in self.document['outside_operational_roster_records'].values()))
        self.assertTrue(all(r['ccd_flags']['virtual_status'] is None for r in self.links.values()))
        self.assertEqual(self.links['320006000488']['edc_metadata']['math']['SchVirtual'], 'Supplemental virtual')
        self.assertEqual(self.links['320006000949']['edc_metadata']['math']['SchVirtual'], 'Yes')
        self.assertFalse(self.links['320006000949']['subjects']['math']['usable'])
        directory = {k: {'raw': v} for k, v in self.directory.items()}
        e = next(r for r in self.document['raw_inputs']['assessment']['records'] if r['raw']['NCESSchoolID'] == '320006000670')
        renamed = dict(e['raw'], SchName='Any renamed school')
        self.assertEqual(audit.edc_identity(renamed, directory), '320006000670')
        with self.assertRaises(ValueError):
            audit.edc_identity(dict(renamed, StateAssignedSchID='2201'), directory)
        for subject in ['math', 'reading', 'combined']:
            for link in self.links.values():
                v = link['subjects'][subject]
                self.assertIsNone(v['valid_scores']); self.assertIsNone(v['sampling_variance'])
                self.assertFalse(v['sampling_interval_available'])
        for native in ['*', '<0.1', '0.1-0.2', '']:
            self.assertIsNone(audit.nevada.exact_rate(native))

    def test_offline_validation_requires_no_archives_csvs_or_ignored_cache(self):
        with mock.patch.object(audit.zipfile, 'ZipFile', side_effect=AssertionError('Raw archive unavailable')), \
                mock.patch.object(audit.subprocess, 'Popen', side_effect=AssertionError('Raw stream unavailable')), \
                mock.patch.object(audit.nevada, 'membership_cache', side_effect=AssertionError('Ignored cache unavailable')):
            self.assertEqual(audit.validate(self.document)['historical_native_source_profiles'], 289)
        inputs = self.document['raw_inputs']
        self.assertEqual((len(inputs['membership']['records']), inputs['membership']['all_district_csv_rows']), (3371, 49009))
        for source in inputs.values():
            self.assertEqual(source['header_source_row'], 1)
            self.assertTrue(all(r['source_row'] >= 2 for r in source['records']))
        self.assertIn('SchVirtual', inputs['assessment']['header'])
        self.assertIn('DMS_FLAG', inputs['membership']['header'])

    def test_source_year_identity_headers_counts_and_membership_drift_fail(self):
        mutations = [
            lambda d: d.update(approved_for_modeling=True),
            lambda d: d.update(approved_for_source=True),
            lambda d: d.update(year=2024),
            lambda d: d['sources']['edc_2025'].update(sha256='0' * 64),
            lambda d: d['raw_inputs']['directory']['records'][0]['raw'].update(ST_LEAID='NV-01'),
            lambda d: d['raw_inputs']['directory']['records'][0]['raw'].update(ST_SCHID='NV-02-99999'),
            lambda d: d['raw_inputs']['directory']['records'][0]['raw'].update(SCHOOL_YEAR='2023-2024'),
            lambda d: d['raw_inputs']['directory']['records'].pop(),
            lambda d: d['raw_inputs']['membership']['records'][0]['raw'].update(STUDENT_COUNT='99999'),
            lambda d: d['raw_inputs']['membership']['records'][0].update(source_row=2),
            lambda d: d['raw_inputs']['lunch']['records'][0]['raw'].update(DMS_FLAG='Suppressed'),
            lambda d: d['raw_inputs']['assessment']['records'][0]['raw'].update(ProficientOrAbove_percent='changed-suppression-marker'),
            lambda d: d['raw_inputs']['assessment']['records'][0]['raw'].update(GradeLevel='GHS'),
            lambda d: d['raw_inputs']['assessment']['header'].remove('SchVirtual'),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.validate(changed, self.snapshot)

    def test_derived_cohorts_missingness_denominators_and_historical_evidence_fail(self):
        mutations = [
            lambda d: d['cohorts']['historical_native_source_profiles']['subjects']['math']['eligible_school_ids'].append('320006000740'),
            lambda d: d['cohorts']['native_grade_school_configurations'].update(profiles=296),
            lambda d: d['roster_links'][0]['subjects']['math'].update(valid_scores=200),
            lambda d: d['roster_links'][0]['subjects']['math'].update(sampling_variance=0),
            lambda d: d['roster_links'][0]['subjects']['combined'].update(sampling_interval_available=True),
            lambda d: d['roster_links'][0]['enrolled'].update(ungraded_reported_count=0),
            lambda d: d['coverage'].update(direct_certification_rows=379),
            lambda d: d['nonoperational_directory'].clear(),
            lambda d: d['historical_state_lunch_notes'].clear(),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.document); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.validate(changed, self.snapshot)
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['schools'][0]['outcomes']['math']['tested'] = 100
        with self.assertRaises(ValueError): audit.validate(self.document, snapshot)


if __name__ == '__main__':
    unittest.main()
