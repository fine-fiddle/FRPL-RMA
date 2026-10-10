import copy
from collections import defaultdict
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_charlotte as audit


class CharlotteSourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.snapshot = audit.load_north_carolina()
        cls.links = {r['school_id']: r for r in cls.document['roster_links']}
        cls.directory = {audit.ccd_identity(e['raw']): e for e in cls.document['raw_inputs']['directory']['records']}
        cls.income = {e['raw']['school_code']: e for e in cls.document['raw_inputs']['income']['records']}

    def membership(self, key):
        rows = [e for e in self.document['raw_inputs']['membership']['records'] if audit.ccd_identity(e['raw']) == key]
        total = next(e for e in rows if e['raw']['TOTAL_INDICATOR'] == 'Education Unit Total')
        grades = {e['raw']['GRADE']: e for e in rows if e['raw']['TOTAL_INDICATOR'] == 'Subtotal 4 - By Grade'}
        return total, grades

    def native(self, key):
        return {('math' if e['raw']['subject'] == 'MA' else 'reading'): e
                for e in self.document['raw_inputs']['assessment']['records']
                if e['raw']['school_code'] == key and e['raw']['type'] == 'RG'
                and e['raw']['grade'] == 'GS' and e['raw']['subject'] in {'MA', 'RD'}}

    def test_complete_original_roster_headers_rows_and_population_inventory(self):
        c = audit.validate(self.document, self.snapshot)
        self.assertEqual((c['directory_records'], c['operational_schools'], c['nonoperational_schools']), (186, 186, 0))
        self.assertEqual(c['operational_statuses'], {'New': 2, 'Open': 184})
        self.assertEqual(c['operational_offered_bands'], {'grade': 146, 'high': 32, 'mixed': 6, 'primary': 2})
        self.assertEqual(c['operational_school_types'], {'Alternative School': 2, 'Career and Technical School': 1,
                                                       'Regular School': 181, 'Special Education School': 2})
        self.assertEqual(c['operational_charter'], {'No': 186})
        self.assertEqual(self.document['nonoperational_directory'], [])
        sections = ['directory', 'membership', 'lea_directory', 'lea_membership', 'assessment', 'income', 'native_location']
        inputs = self.document['raw_inputs']
        self.assertEqual([len(inputs[k]['records']) for k in sections], [186, 1457, 1, 17, 5667, 187, 187])
        self.assertEqual(sum(len(inputs[k]['records']) for k in sections), 7702)
        self.assertEqual(sum(len(e['raw']) for k in sections for e in inputs[k]['records']), 129992)
        for k in sections:
            self.assertEqual(inputs[k]['header_source_row'], 1)
            self.assertEqual(len(inputs[k]['header']), len(set(inputs[k]['header'])))
            self.assertEqual(len(inputs[k]['records']), len({e['source_row'] for e in inputs[k]['records']}))
            for e in inputs[k]['records']:
                self.assertIs(type(e['source_row']), int)
                self.assertGreater(e['source_row'], 1)
                self.assertEqual(set(e['raw']), set(inputs[k]['header']))
        self.assertEqual(c['native_assessment_types'], {'ALL': 2658, 'RG': 2640, 'X1': 369})

    def test_lower_primary_subject_masks_and_alternative_scope_are_separate(self):
        cohorts = self.document['cohorts']
        self.assertEqual(cohorts['ccd_lower_membership_contracts']['profiles'], 148)
        self.assertEqual(cohorts['ccd_grade_school_configurations']['profiles'], 146)
        source = cohorts['native_grade_school_source_profiles']
        self.assertEqual(source['profiles'], 146)
        for subject, n in [('math', 145), ('reading', 146), ('combined', 145)]:
            s = source['subjects'][subject]
            self.assertEqual((s['applicable'], s['usable']), (146, n))
            self.assertTrue(s['prospective_30_school_floor_met'])
        knights = self.links['600387']
        self.assertTrue(knights['source_profile_eligible'])
        self.assertEqual(knights['subjects']['math']['raw_rate'], '>95')
        self.assertIsNone(knights['subjects']['math']['native_rate'])
        self.assertFalse(knights['subjects']['combined']['usable'])
        self.assertEqual(knights['subjects']['reading']['native_rate'], 90.7)
        for key in ['600335', '600519']:
            r = self.links[key]
            self.assertEqual(r['offered']['band'], 'primary')
            self.assertTrue(r['enrolled']['native_grade_school_contract'])
            self.assertFalse(r['source_profile_eligible'])
            self.assertEqual(r['offered']['offered_tested_grades'], [])
            self.assertTrue(all(not s['applicable'] and not s['usable'] for s in r['subjects'].values()))
        alternative = self.links['600598']
        self.assertEqual(alternative['ccd_flags']['school_type'], 'Alternative School')
        self.assertTrue(alternative['source_profile_eligible'])
        self.assertTrue(all(s['usable'] for s in alternative['subjects'].values()))
        self.assertEqual((alternative['subjects']['math']['native_rate'], alternative['subjects']['reading']['native_rate']), (9.4, 14.6))

    def test_income_april_populations_do_not_backfill_fall_or_tested_counts(self):
        c = self.document['coverage']
        self.assertEqual((c['lea_fall_enrollment'], c['operational_school_fall_enrollment'], c['lea_minus_operational_school_fall_enrollment']), (147299, 145014, 2285))
        self.assertEqual((c['april_district_aggregate_enrollment'], c['operational_school_april_enrollment']), (145900, 145900))
        self.assertEqual(c['operational_usable_april_income'], 186)
        self.assertEqual(c['april_enrollment_different_from_fall'], 183)
        self.assertEqual(c['lea_grade_membership_evidence']['full_grade_sum'], 147299)
        self.assertEqual(c['lea_grade_membership_evidence']['total_source_row'], 2530267)
        self.assertEqual(self.document['raw_inputs']['lea_directory']['records'][0]['source_row'], 13259)
        school_grades = defaultdict(int)
        for e in self.document['raw_inputs']['membership']['records']:
            if e['raw']['TOTAL_INDICATOR'] == 'Subtotal 4 - By Grade':
                school_grades[e['raw']['GRADE']] += audit.grade_count(e['raw'])
        lea_grades = {e['raw']['GRADE']: audit.grade_count(e['raw'])
                      for e in self.document['raw_inputs']['lea_membership']['records']
                      if e['raw']['TOTAL_INDICATOR'] == 'Subtotal 4 - By Grade'}
        self.assertEqual((lea_grades['Pre-Kindergarten'], school_grades['Pre-Kindergarten']), (5600, 3315))
        self.assertEqual({g: lea_grades.get(g, 0) - school_grades.get(g, 0)
                          for g in set(lea_grades) | set(school_grades)
                          if lea_grades.get(g, 0) != school_grades.get(g, 0)}, {'Pre-Kindergarten': 2285})
        for r in self.links.values():
            self.assertEqual(r['enrolled']['full_grade_sum'], r['enrolled']['reported_total'])
            self.assertIsNone(r['income']['verified_low_income_count'])
            raw = self.income[r['school_id']]['raw']
            self.assertEqual(r['income']['percentage'], audit.north_carolina.exact_percent(raw['pct_eds']))
            self.assertEqual(r['income']['april_enrollment'], audit.north_carolina.exact_enrollment(raw['den']))
        self.assertEqual((self.links['600335']['income']['april_enrollment'], self.links['600335']['income']['percentage']), (356, 43.3))
        self.assertEqual((self.links['600519']['income']['april_enrollment'], self.links['600519']['income']['percentage']), (407, 15.2))

    def test_discovery_high_mixed_and_district_aggregates_never_select_members(self):
        p = self.document['planning_identity_reconciliation']
        self.assertEqual([len(p['potential_school_ids'][s]) for s in ['ES', 'HS']], [146, 25])
        self.assertEqual(len(p['source_eligible_ncessch']), 146)
        self.assertEqual(len(p['combined_eligible_ncessch']), 145)
        self.assertEqual(p['planning_ES_not_source_eligible'], [])
        self.assertEqual(p['source_not_planning_ES'], [])
        self.assertEqual(p['planning_ES_not_combined_eligible'], ['370297003648'])
        self.assertEqual(len(p['high_grade13_not_planning_HS']), 7)
        self.assertEqual(self.document['coverage']['operational_grade13_high_schools'], ['600334', '600404', '600443', '600498', '600567', '600569', '600594'])
        for name in ['high_school_configurations', 'mixed_configurations', 'primary_configurations', 'unknown_or_other_configurations']:
            self.assertTrue(all(s['usable'] == 0 for s in self.document['cohorts'][name]['subjects'].values()))
        self.assertEqual(self.document['coverage']['native_assessment_absent_school_ids'], ['600335', '600404', '600519'])
        for section in ['assessment', 'income']:
            self.assertEqual({e['raw']['school_code'] for e in self.document['outside_directory_records'][section]}, {'600LEA'})
        self.assertEqual({e['raw']['agency_code'] for e in self.document['outside_directory_records']['native_location']}, {'600LEA'})
        self.assertNotIn('600LEA', self.links)

    def test_authoritative_native_ccd_and_location_ids_not_names_or_prefixes(self):
        raw = self.directory['600300']['raw']
        self.assertEqual(audit.ccd_identity(dict(raw, SCH_NAME='Different display label')), '600300')
        for field, value in [('ST_SCHID', 'NC-601-300'), ('LEAID', '3702971'), ('ST_LEAID', 'NC-601'), ('SCHOOL_YEAR', '2023-2024'), ('NCESSCH', '370297199999'), ('ST', 'SC')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.ccd_identity(dict(raw, **{field: value}))
        eds = self.income['600300']['raw']
        for field, value in [('school_code', '601300'), ('psu_code', '601'), ('reporting_year', '2024'), ('collection_code', 'DEC')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.native_identity(dict(eds, **{field: value}), income=True)
        location = self.links['600300']['native_location']['raw']
        for field, value in [('agency_code', '601300'), ('agency_level', 'LEA'), ('lea_code', '601LEA'), ('year', '2025'), ('year', 2024), ('state', 'SC')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.location_identity(dict(location, **{field: value}))
        self.assertEqual(len(self.document['raw_inputs']['native_location']['header']), 24)
        self.assertEqual(self.document['coverage']['native_location_school_types'], {'Alternative Educat': 2, 'Exceptional Childr': 2, 'Regular School': 181, 'Vocational Educati': 1})

    def test_grade_contract_literal_zero_and_reported_counts_preserve_missingness(self):
        total, entries = self.membership('600300')
        grades = {g: e['raw'] for g, e in entries.items()}; raw = self.directory['600300']['raw']
        self.assertTrue(audit.grade_school_contract(raw, total['raw'], grades))
        unspecified = grades['Not Specified']
        self.assertEqual([unspecified[k] for k in ['STUDENT_COUNT', 'DMS_FLAG', 'RACE_ETHNICITY', 'SEX']], ['0', 'Derived', 'Not Specified', 'Not Specified'])
        self.assertEqual(audit.grade_count(unspecified), 0)
        for field, value in [('STUDENT_COUNT', '1'), ('DMS_FLAG', 'Suppressed'), ('RACE_ETHNICITY', 'No Category Codes')]:
            self.assertIsNone(audit.grade_count(dict(unspecified, **{field: value})))
        for change in ['outside', 'suppressed', 'drift', 'ungraded']:
            altered = copy.deepcopy(grades); offered = dict(raw)
            if change == 'outside': altered['Grade 9'] = dict(grades['Grade 3'], STUDENT_COUNT='1')
            elif change == 'suppressed': altered['Grade 3']['DMS_FLAG'] = 'Suppressed'
            elif change == 'drift': altered['Grade 3']['STUDENT_COUNT'] = '99999'
            else: offered['G_UG_OFFERED'] = 'Yes'
            self.assertFalse(audit.grade_school_contract(offered, total['raw'], altered))
        for value in ['Yes', 'Unknown', None]:
            self.assertFalse(audit.grade_school_contract(dict(raw, NOGRADES=value), total['raw'], grades))

    def test_native_scope_suppression_real_zero_and_income_proxies(self):
        native = self.native('600300')
        for field, value in [('type', 'ALL'), ('type', 'X1'), ('grade', '03'), ('subgroup', 'EDS'), ('subject', 'EOG')]:
            changed = copy.deepcopy(native); changed['math']['raw'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.subject_evidence(changed, operational=True, configuration=True, offered=self.links['600300']['offered'], income=self.links['600300']['income'])
        for value in ['<5', '>95', '-', '*', '', '5-10', None]:
            self.assertIsNone(audit.north_carolina.exact_percent(value))
        for value, expected in [('0', 0), ('5', 5), ('95', 95), ('100', 100)]:
            self.assertEqual(audit.north_carolina.exact_percent(value), expected)
        zero = copy.deepcopy(self.income['600300']); zero['raw']['pct_eds'] = '0'
        self.assertEqual(audit.income_evidence(zero)['percentage'], 0)
        self.assertIsNone(audit.income_evidence(zero)['exclusion'])
        missing = copy.deepcopy(zero); missing['raw'].update(pct_eds='<5', pct_nslp='80', pct_nslp_adj='100')
        self.assertIsNone(audit.income_evidence(missing)['percentage'])
        self.assertIsNotNone(audit.income_evidence(missing)['exclusion'])
        self.assertIsNone(audit.income_evidence(None)['percentage'])
        for value in ['<10', '', '0']:
            changed = copy.deepcopy(zero); changed['raw']['den'] = value
            self.assertIsNotNone(audit.income_evidence(changed)['exclusion'])

    def test_original_definitions_summer_grade8_math1_and_rcd_discrepancies(self):
        defs = self.document['source_definition_evidence']
        text = '\n'.join(p['text'] for p in defs['dpi_description']['pages'])
        for phrase in ['including 2024 summer school', 'includes NC Math 1 at grade 8', 'EXT1', 'Regular (Multiple Choice)', 'Achievement Level 3 and above', '9–12', '9–13']:
            self.assertIn(phrase, text)
        self.assertEqual(defs['embedded_description']['sha256'], audit.SOURCES['dpi_description']['sha256'])
        eds = '\n'.join(p['text'] for p in defs['dpi_income_definition']['pages'])
        for phrase in ['currently enrolled', 'pre-kindergarten through', 'charter schools must not submit', 'April data', 'a local process may be developed']:
            self.assertIn(phrase, eds)
        for phrase in ['Medicaid', 'TANF', 'FDPIR', 'Head Start']:
            self.assertIn(phrase.lower(), defs['dpi_eds_web_definition']['raw_markup'].lower())
        technical = '\n'.join(p['text'] for p in defs['dpi_technical']['pages'])
        self.assertIn('95%', technical)
        self.assertIn('3.1.1', technical)
        self.assertEqual([w['worksheet'] for w in defs['dpi_src_dictionary']['worksheets']], ['GENERAL RULES', 'TABLE INDEX', 'SY2425 COLUMNS', 'CODE DEFINITIONS'])
        self.assertEqual(len(self.document['sources']), 12)

    def test_counts_sampling_floor_approvals_and_combined_only_mean(self):
        for r in self.links.values():
            self.assertIsNone(r['income']['verified_low_income_count'])
            self.assertIsNone(r['ccd_flags']['virtual_status'])
            for s in r['subjects'].values():
                self.assertIsNone(s['valid_scores']); self.assertIsNone(s['sampling_variance'])
                self.assertFalse(s['sampling_interval_available']); self.assertFalse(s['ten_valid_scored_floor_certified'])
            if r['subjects']['combined']['usable']:
                self.assertEqual(r['subjects']['combined']['native_rate'], (r['subjects']['math']['native_rate'] + r['subjects']['reading']['native_rate']) / 2)
        self.assertIs(self.document['approved_for_source'], False)
        self.assertIs(self.document['approved_for_modeling'], False)
        self.assertEqual((self.document['scope'], self.document['status']), ('source_cohort_audit_only', 'audit_pending'))
        self.assertNotIn('models', self.document)

    def test_offline_replay_uses_pinned_records_without_any_original_reads(self):
        with mock.patch.object(audit.zipfile, 'ZipFile', side_effect=AssertionError('Raw ZIP unavailable')), \
                mock.patch.object(audit.subprocess, 'Popen', side_effect=AssertionError('Raw stream unavailable')), \
                mock.patch.object(audit.openpyxl, 'load_workbook', side_effect=AssertionError('Raw workbook unavailable')):
            self.assertEqual(audit.validate(self.document)['prospective_source_profiles'], 146)
        self.assertRegex(audit.RAW_INPUT_SHA, r'^[a-f0-9]{64}$')
        self.assertEqual(audit.fingerprint(self.document['raw_inputs']), audit.RAW_INPUT_SHA)

    def test_missing_extra_type_provenance_count_and_population_drift_rejected(self):
        mutations = [
            lambda d: d.update(approved_for_source=0), lambda d: d.update(approved_for_modeling=True),
            lambda d: d.update(schema_version=1.0), lambda d: d.update(year=2025.0), lambda d: d.update(scope='ready'),
            lambda d: d.update(models=[]), lambda d: d.pop('planning'),
            lambda d: d['sources']['dpi_income'].update(sha256='0' * 64),
            lambda d: d['raw_inputs']['directory']['records'].pop(),
            lambda d: d['raw_inputs']['directory']['records'].append(copy.deepcopy(d['raw_inputs']['directory']['records'][0])),
            lambda d: d['raw_inputs']['income']['records'][0]['raw'].update(pct_eds=False),
            lambda d: d['raw_inputs']['income'].update(worksheet='DEC 2025'),
            lambda d: d['raw_inputs']['assessment']['records'][0]['raw'].update(pct_glp='unexpected'),
            lambda d: d['raw_inputs']['assessment']['records'][0].update(source_row=True),
            lambda d: d['raw_inputs']['assessment']['header'].pop(),
            lambda d: d['raw_inputs']['definitions']['dpi_description']['pages'].pop(),
            lambda d: d['raw_inputs']['native_location']['records'][0]['raw'].update(year='2025'),
            lambda d: d['raw_inputs']['native_location'].update(member_sha256='0' * 64),
            lambda d: d['raw_inputs']['planning']['record']['potential_school_ids']['ES'].pop(),
            lambda d: d['raw_inputs']['lea_membership']['records'][0]['raw'].update(STUDENT_COUNT='145014'),
            lambda d: d['roster_links'][0]['subjects']['math'].update(valid_scores=100),
            lambda d: d['roster_links'][0]['subjects']['math'].update(ten_valid_scored_floor_certified=True),
            lambda d: d['cohorts']['native_grade_school_source_profiles']['subjects']['combined'].update(usable=145.0),
            lambda d: d['coverage'].update(lea_minus_operational_school_fall_enrollment=0),
            lambda d: d['coverage'].update(verified_valid_score_counts=False),
        ]
        for i, mutation in enumerate(mutations):
            changed = copy.deepcopy(self.document); mutation(changed)
            with self.subTest(mutation=i), self.assertRaises(ValueError):
                audit.validate(changed, self.snapshot)

    def test_semantic_identity_and_year_gates_even_with_repinned_test_fixture(self):
        changes = [
            lambda d: d['raw_inputs']['directory']['records'][0]['raw'].update(LEAID='3702971'),
            lambda d: d['raw_inputs']['membership']['records'][0]['raw'].update(ST_SCHID='NC-601-300'),
            lambda d: d['raw_inputs']['income']['records'][1]['raw'].update(reporting_year='2024'),
            lambda d: d['raw_inputs']['assessment']['records'][0]['raw'].update(subgroup='EDS'),
            lambda d: d['raw_inputs']['planning']['record'].update(enrollment=145014),
            lambda d: d['raw_inputs']['directory']['records'][0].update(source_row=1),
            lambda d: d['raw_inputs']['assessment'].update(header_source_row=True),
            lambda d: d['raw_inputs']['income'].update(header_source_row=1.0),
            lambda d: d['raw_inputs']['native_location']['records'][0]['raw'].update(agency_code='601300'),
        ]
        for i, change in enumerate(changes):
            changed = copy.deepcopy(self.document); change(changed)
            with self.subTest(mutation=i), mock.patch.object(audit, 'RAW_INPUT_SHA', audit.fingerprint(changed['raw_inputs'])), self.assertRaises(ValueError):
                audit.derive(changed, self.snapshot)


if __name__ == '__main__':
    unittest.main()
