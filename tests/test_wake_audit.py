import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_wake as audit


class WakeSourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.snapshot = audit.load_north_carolina()
        cls.links = {r['school_id']: r for r in cls.document['roster_links']}
        cls.directory = {audit.ccd_identity(r['raw']): r for r in cls.document['raw_inputs']['directory']['records']}
        cls.income = {r['raw']['school_code']: r for r in cls.document['raw_inputs']['income']['records']}

    def membership(self, key):
        rows = [e for e in self.document['raw_inputs']['membership']['records'] if audit.ccd_identity(e['raw']) == key]
        total = next(e for e in rows if e['raw']['TOTAL_INDICATOR'] == 'Education Unit Total')
        grades = {e['raw']['GRADE']: e for e in rows if e['raw']['TOTAL_INDICATOR'] == 'Subtotal 4 - By Grade'}
        return total, grades

    def native(self, key):
        return {('math' if e['raw']['subject'] == 'MA' else 'reading'): e
                for e in self.document['raw_inputs']['assessment']['records']
                if e['raw']['school_code'] == key and e['raw']['type'] == 'RG' and e['raw']['grade'] == 'GS' and e['raw']['subject'] in {'MA', 'RD'}}

    def test_complete_original_roster_and_separate_population_screens(self):
        c = audit.validate(self.document, self.snapshot)
        self.assertEqual((c['directory_records'], c['operational_schools'], c['nonoperational_schools']), (202, 198, 4))
        self.assertEqual(c['operational_statuses'], {'New': 1, 'Open': 197})
        self.assertEqual(c['nonoperational_statuses'], {'Future': 4})
        self.assertEqual(c['operational_offered_bands'], {'grade': 162, 'high': 33, 'mixed': 3})
        self.assertEqual(c['operational_school_types'], {'Alternative School': 5, 'Regular School': 192, 'Special Education School': 1})
        self.assertEqual(c['operational_charter'], {'No': 198})
        self.assertEqual(c['original_native_units'], 198)
        self.assertEqual(c['original_native_all_students_rows'], 5792)
        self.assertEqual(c['original_april_eds_rows'], 199)
        self.assertEqual([len(self.document['raw_inputs'][k]['records']) for k in ['directory', 'membership', 'lea_directory', 'lea_membership', 'assessment', 'income']], [202, 1520, 1, 1, 5792, 199])
        self.assertEqual(len(self.document['roster_links']), 198)
        self.assertEqual(len(self.document['nonoperational_directory']), 4)

    def test_prospective_profiles_and_subject_missingness_remain_separate(self):
        cohorts = self.document['cohorts']
        self.assertEqual(cohorts['ccd_grade_school_configurations']['profiles'], 162)
        source = cohorts['native_grade_school_source_profiles']
        self.assertEqual(source['profiles'], 160)
        for subject, size in [('math', 159), ('reading', 160), ('combined', 159)]:
            s = source['subjects'][subject]
            self.assertEqual((s['applicable'], s['usable']), (160, size))
            self.assertTrue(s['prospective_30_school_floor_met'])
            self.assertEqual(s['verified_valid_score_counts'], 0)
            self.assertFalse(s['ten_valid_scored_floor_certified'])
        for key in ['920314', '920614']:
            self.assertEqual(self.links[key]['income']['raw_percentage'], '<5')
            self.assertIsNone(self.links[key]['income']['percentage'])
            self.assertFalse(self.links[key]['source_profile_eligible'])
            for subject in ['math', 'reading', 'combined']:
                self.assertFalse(self.links[key]['subjects'][subject]['usable'])
        mills = self.links['920502']
        self.assertTrue(mills['source_profile_eligible'])
        self.assertEqual(mills['subjects']['math']['raw_rate'], '>95')
        self.assertIsNone(mills['subjects']['math']['native_rate'])
        self.assertFalse(mills['subjects']['combined']['usable'])
        self.assertTrue(mills['subjects']['reading']['usable'])
        self.assertEqual(self.links['920614']['subjects']['math']['raw_rate'], '>95')

    def test_april_and_fall_populations_reconcile_without_substituting_denominators(self):
        c = self.document['coverage']
        self.assertEqual((c['lea_fall_enrollment'], c['operational_school_fall_enrollment'], c['lea_minus_operational_school_fall_enrollment']), (163325, 163176, 149))
        self.assertEqual((c['april_district_aggregate_enrollment'], c['operational_school_april_enrollment']), (164495, 164495))
        self.assertEqual(c['april_enrollment_different_from_fall'], 192)
        river = self.links['920302']
        self.assertEqual((river['income']['april_enrollment'], river['enrolled']['reported_total'], river['april_minus_fall_enrollment']), (732, 709, 23))
        self.assertEqual(river['income']['percentage'], 59.8)
        self.assertIsNone(river['income']['verified_low_income_count'])
        self.assertEqual(self.document['raw_inputs']['lea_directory']['records'][0]['source_row'], 13296)
        self.assertEqual(self.document['raw_inputs']['lea_membership']['records'][0]['source_row'], 2539658)
        self.assertTrue(all(r['enrolled']['full_grade_sum'] == r['enrolled']['reported_total'] for r in self.links.values()))

    def test_planning_reconstructed_with_income_and_outcome_exclusions(self):
        p = self.document['planning_identity_reconciliation']
        self.assertEqual([len(p['potential_school_ids'][s]) for s in ['ES', 'HS']], [162, 29])
        self.assertEqual(len(p['source_eligible_ncessch']), 160)
        self.assertEqual(len(p['combined_eligible_ncessch']), 159)
        self.assertEqual(p['planning_ES_not_source_eligible'], ['370472003377', '370472003624'])
        self.assertEqual(p['planning_ES_not_combined_eligible'], ['370472003205', '370472003377', '370472003624'])
        self.assertEqual(p['source_not_planning_ES'], [])
        self.assertEqual(len(p['high_grade13_not_planning_HS']), 4)
        self.assertEqual(self.document['coverage']['operational_grade13_high_schools'], ['920518', '920581', '920582', '920583'])
        self.assertEqual(self.document['coverage']['operational_grade13_mixed_schools'], ['920585', '920586'])

    def test_high_mixed_future_and_aggregate_rates_do_not_enter_grade_cohorts(self):
        self.assertEqual(self.document['cohorts']['high_school_configurations']['profiles'], 33)
        self.assertEqual(self.document['cohorts']['mixed_configurations']['profiles'], 3)
        for label in ['high_school_configurations', 'mixed_configurations', 'primary_configurations', 'unknown_or_other_configurations']:
            for subject in ['math', 'reading', 'combined']:
                self.assertEqual(self.document['cohorts'][label]['subjects'][subject]['usable'], 0)
        for key in ['920585', '920586']:
            r = self.links[key]
            self.assertTrue(r['native_regular_gs_pair'])
            self.assertEqual(r['offered']['band'], 'mixed')
            self.assertEqual(r['native_grade_spans'], ['06-13'])
            self.assertFalse(r['subjects']['combined']['usable'])
        self.assertEqual(self.links['920324']['native_all_students_rows'], [])
        for r in self.document['nonoperational_directory']:
            self.assertFalse(r['operational']); self.assertFalse(r['source_profile_eligible'])
            self.assertTrue(all(not s['usable'] for s in r['subjects'].values()))
        outside = self.document['outside_directory_records']
        self.assertTrue(outside['assessment'])
        self.assertEqual({e['raw']['school_code'] for e in outside['assessment']}, {'920LEA'})
        self.assertEqual([e['raw']['school_code'] for e in outside['income']], ['920LEA'])
        self.assertNotIn('920LEA', self.links)

    def test_exact_native_identity_year_and_population_do_not_join_by_name(self):
        raw = self.directory['920302']['raw']
        self.assertEqual(audit.ccd_identity(dict(raw, SCH_NAME='Renamed display label')), '920302')
        for field, value in [('ST_SCHID', 'NC-919-302'), ('LEAID', '3704721'), ('ST_LEAID', 'NC-919'), ('SCHOOL_YEAR', '2023-2024'), ('NCESSCH', '370472199999'), ('ST', 'SC')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.ccd_identity(dict(raw, **{field: value}))
        eds = self.income['920302']['raw']
        for field, value in [('school_code', '919302'), ('psu_code', '919'), ('reporting_year', '2024'), ('collection_code', 'DEC')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.native_identity(dict(eds, **{field: value}), income=True)
        native = self.native('920302')
        for field, value in [('type', 'ALL'), ('type', 'X1'), ('grade', '03'), ('subgroup', 'EDS'), ('subject', 'EOG')]:
            changed = copy.deepcopy(native); changed['math']['raw'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.subject_evidence(changed, operational=True, configuration=True, offered=self.links['920302']['offered'], income=self.links['920302']['income'])

    def test_complete_grade_counts_and_zero_unspecified_are_preserved(self):
        total, entries = self.membership('920302')
        grades = {g: e['raw'] for g, e in entries.items()}; raw = self.directory['920302']['raw']
        self.assertTrue(audit.grade_school_contract(raw, total['raw'], grades))
        unspecified = grades['Not Specified']
        self.assertEqual([unspecified[k] for k in ['STUDENT_COUNT', 'DMS_FLAG', 'RACE_ETHNICITY', 'SEX']], ['0', 'Derived', 'Not Specified', 'Not Specified'])
        self.assertEqual(audit.grade_count(unspecified), 0)
        for field, value in [('GRADE', 'Grade 3'), ('STUDENT_COUNT', '1'), ('DMS_FLAG', 'Suppressed'), ('RACE_ETHNICITY', 'No Category Codes')]:
            self.assertIsNone(audit.grade_count(dict(unspecified, **{field: value})))
        for change in ['outside', 'suppressed', 'drift', 'ungraded']:
            altered = copy.deepcopy(grades); offered = dict(raw)
            if change == 'outside': altered['Grade 9'] = dict(grades['Grade 3'], STUDENT_COUNT='1')
            elif change == 'suppressed': altered['Grade 3']['DMS_FLAG'] = 'Suppressed'
            elif change == 'drift': altered['Grade 3']['STUDENT_COUNT'] = '99999'
            else: offered['G_UG_OFFERED'] = 'Yes'
            self.assertFalse(audit.grade_school_contract(offered, total['raw'], altered))
        for field, value in [('G_9_OFFERED', 'Yes'), ('G_3_OFFERED', 'Unknown'), ('IGOFFERED', 'Imputed')]:
            self.assertFalse(audit.grade_school_contract(dict(raw, **{field: value}), total['raw'], grades))

    def test_numeric_zero_missing_ranges_and_proxy_income_are_distinct(self):
        for value in ['<5', '>95', '-', '*', '', '5-10', None]:
            self.assertIsNone(audit.north_carolina.exact_percent(value))
        for value, expected in [('0', 0), ('5', 5), ('95', 95), ('100', 100), ('59.8', 59.8)]:
            self.assertEqual(audit.north_carolina.exact_percent(value), expected)
        zero = copy.deepcopy(self.income['920302']); zero['raw']['pct_eds'] = '0'
        self.assertEqual(audit.income_evidence(zero)['percentage'], 0)
        self.assertIsNone(audit.income_evidence(zero)['exclusion'])
        self.assertIsNone(audit.income_evidence(None)['percentage'])
        for field in ['pct_nslp', 'pct_nslp_adj']:
            proxy = copy.deepcopy(self.income['920314']); proxy['raw'][field] = '80'
            self.assertIsNone(audit.income_evidence(proxy)['percentage'])
        for value in ['<10', '', '0']:
            changed = copy.deepcopy(self.income['920302']); changed['raw']['den'] = value
            self.assertIsNotNone(audit.income_evidence(changed)['exclusion'])

    def test_every_sampling_field_count_floor_and_approval_remains_unavailable(self):
        for r in self.document['roster_links'] + self.document['nonoperational_directory']:
            self.assertIsNone(r['income']['verified_low_income_count'])
            for s in r['subjects'].values():
                self.assertIsNone(s['valid_scores']); self.assertIsNone(s['sampling_variance'])
                self.assertFalse(s['sampling_interval_available']); self.assertFalse(s['ten_valid_scored_floor_certified'])
            if r['subjects']['combined']['usable']:
                self.assertEqual(r['subjects']['combined']['native_rate'], (r['subjects']['math']['native_rate'] + r['subjects']['reading']['native_rate']) / 2)
        self.assertFalse(self.document['approved_for_source']); self.assertFalse(self.document['approved_for_modeling'])
        self.assertEqual((self.document['scope'], self.document['status']), ('source_cohort_audit_only', 'audit_pending'))
        self.assertNotIn('models', self.document)
        self.assertEqual(self.document['coverage']['native_assessment_types'], {'ALL': 2701, 'RG': 2701, 'X1': 390})

    def test_primary_definition_pages_and_original_eds_eligibility_evidence(self):
        defs = self.document['source_definition_evidence']
        text = '\n'.join(p['text'] for p in defs['dpi_description']['pages'])
        self.assertIn('including 2024 summer school', text)
        self.assertIn('includes NC Math 1 at grade 8', text)
        self.assertIn('EXT1', text)
        self.assertIn('Regular (Multiple Choice)', text)
        eds = '\n'.join(p['text'] for p in defs['dpi_income_definition']['pages'])
        self.assertIn('pre-kindergarten through', eds)
        self.assertIn('charter schools must not submit', eds)
        self.assertIn('April data', eds)
        markup = defs['dpi_eds_web_definition']['raw_markup']
        for term in ['Medicaid', 'TANF', 'FDPIR', 'Head Start']:
            self.assertTrue(term.lower() in markup.lower(), 'Missing original EDS eligibility term: ' + term)
        self.assertEqual(defs['embedded_description']['sha256'], audit.SOURCES['dpi_description']['sha256'])
        self.assertIn('stale CEP', self.document['policy']['eds_definition_limits'])
        self.assertEqual(self.document['sources']['dpi_eds_web_definition']['sha256'], '36e318a6f5927bd14f53e714ac3527b92eab17abe6d0e889dbec0f0768c42df8')

    def test_offline_replay_never_opens_raw_archives_workbooks_or_sampling_database(self):
        with mock.patch.object(audit.zipfile, 'ZipFile', side_effect=AssertionError('Raw ZIP unavailable')), \
                mock.patch.object(audit.subprocess, 'Popen', side_effect=AssertionError('Raw stream unavailable')), \
                mock.patch.object(audit.openpyxl, 'load_workbook', side_effect=AssertionError('Raw workbook unavailable')):
            self.assertEqual(audit.validate(self.document)['prospective_source_profiles'], 160)
        self.assertEqual(audit.fingerprint(self.document['raw_inputs']), audit.RAW_INPUT_SHA)

    def test_source_rows_definitions_identity_headers_and_discovery_drift_rejected(self):
        mutations = [
            lambda d: d.update(approved_for_source=0), lambda d: d.update(approved_for_modeling=True),
            lambda d: d.update(schema_version=1.0), lambda d: d.update(year=2025.0), lambda d: d.update(scope='ready'),
            lambda d: d.update(models=[]), lambda d: d['sources']['dpi_income'].update(sha256='0' * 64),
            lambda d: d['raw_inputs']['directory']['records'].pop(),
            lambda d: d['raw_inputs']['directory']['records'][0]['raw'].update(ST_SCHID='NC-920-999'),
            lambda d: d['raw_inputs']['membership']['records'][0]['raw'].update(STUDENT_COUNT='0'),
            lambda d: d['raw_inputs']['income']['records'][1]['raw'].update(pct_eds='0'),
            lambda d: d['raw_inputs']['income'].update(worksheet='DEC 2025'),
            lambda d: d['raw_inputs']['assessment']['records'][0]['raw'].update(pct_glp='0'),
            lambda d: d['raw_inputs']['assessment']['records'][0].update(source_row=2),
            lambda d: d['raw_inputs']['assessment']['header'].pop(),
            lambda d: d['raw_inputs']['definitions']['dpi_description']['pages'].pop(),
            lambda d: d['raw_inputs']['planning']['record']['potential_school_ids']['ES'].pop(),
            lambda d: d['raw_inputs']['lea_membership']['records'][0]['raw'].update(STUDENT_COUNT='163176'),
            lambda d: d['roster_links'][0]['subjects']['math'].update(valid_scores=100),
            lambda d: d['roster_links'][0]['subjects']['math'].update(ten_valid_scored_floor_certified=True),
            lambda d: d['cohorts']['native_grade_school_source_profiles']['subjects']['combined'].update(usable=160),
            lambda d: d['coverage'].update(lea_minus_operational_school_fall_enrollment=0),
        ]
        for i, mutation in enumerate(mutations):
            changed = copy.deepcopy(self.document); mutation(changed)
            with self.subTest(mutation=i), self.assertRaises(ValueError):
                audit.validate(changed, self.snapshot)

    def test_semantic_identity_and_population_rejection_without_raw_hash_guard(self):
        changes = [
            lambda d: d['raw_inputs']['directory']['records'][0]['raw'].update(LEAID='3704721'),
            lambda d: d['raw_inputs']['membership']['records'][0]['raw'].update(ST_SCHID='NC-919-302'),
            lambda d: d['raw_inputs']['income']['records'][1]['raw'].update(reporting_year='2024'),
            lambda d: d['raw_inputs']['assessment']['records'][0]['raw'].update(subgroup='EDS'),
            lambda d: d['raw_inputs']['planning']['record'].update(enrollment=163176),
            lambda d: d['raw_inputs']['directory']['records'][0].update(source_row=1),
            lambda d: d['raw_inputs']['assessment']['records'].append(copy.deepcopy(d['raw_inputs']['assessment']['records'][0])),
        ]
        for i, change in enumerate(changes):
            changed = copy.deepcopy(self.document); change(changed)
            with self.subTest(mutation=i), mock.patch.object(audit, 'RAW_INPUT_SHA', audit.fingerprint(changed['raw_inputs'])), self.assertRaises(ValueError):
                audit.validate(changed, self.snapshot)

    def test_complete_historical_snapshot_changes_require_a_fresh_audit(self):
        changed = copy.deepcopy(self.snapshot)
        changed['schools'][0]['name'] = 'Changed unrelated historical source'
        with self.assertRaises(ValueError):
            audit.validate(self.document, changed)


if __name__ == '__main__':
    unittest.main()
