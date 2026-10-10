"""Original Montgomery district source/cohort contracts; no model or DB writes."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_montgomery as audit


class MontgomerySourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document=json.loads(audit.OUTPUT.read_text())
        cls.snapshot=audit.load_maryland()
        cls.links={r['school_id']:r for r in cls.document['roster_links']}
        cls.inputs=cls.document['raw_inputs']
        cls.directory={audit.native_identity(e['raw']):e for e in cls.inputs['native_directory']['records']}
        cls.ccd={e['raw']['NCESSCH']:e for e in cls.inputs['directory']['records']}

    def native(self,key,subject='math'):
        label='Mathematics All Grades'if subject=='math'else'English Language Arts All Grades'
        return next(e for e in self.inputs['native_assessment']['records']if e['worksheet']=='School_Level'and audit.native_identity(e['raw'],aggregate=True)==key and e['raw']['Assessment'].strip()==label)

    def income(self,key):
        return [e for e in self.inputs['native_income']['records']if audit.native_identity(e['raw'],income=True,aggregate=True)==key]

    def enrollment(self,key):
        return [e['raw']for e in self.inputs['native_enrollment']['records']if audit.native_identity(e['raw'],aggregate=True)==key]

    def test_saved_original_replay_and_exact_population(self):
        coverage=audit.validate(self.document,self.snapshot)
        self.assertEqual((coverage['native_directory'],coverage['ccd_directory'],coverage['operational_roster']),(211,211,211))
        self.assertEqual(coverage['prospective_source_profiles'],172)
        self.assertEqual(coverage['prospective_usable_income'],168)
        self.assertEqual(coverage['prospective_usable'],{'math':166,'reading':167,'combined':166})
        self.assertEqual(coverage['planning_reconstructed_potential_cohorts'],{'ES':172,'HS':25})
        self.assertEqual(coverage['offered_bands'],{'grade':172,'high':27,'mixed':5,'primary':7})
        self.assertEqual(coverage['native_grade_spans'],{'E':138,'EMH':2,'H':25,'M':40,'MH':2,'None':4})

    def test_original_complete_record_headers_rows_and_typed_cells(self):
        expected={'directory':211,'lea_directory':1,'membership':1589,'lea_membership':16,
                  'native_directory':211,'native_assessment':1625,'native_enrollment':1376,'native_income':224}
        self.assertEqual(self.document['coverage']['source_rows'],expected)
        self.assertEqual(sum(expected.values()),5253)
        for section in [self.inputs[k]for k in expected]:
            self.assertEqual(section['header_source_row'],1)
            self.assertEqual(len(section['header']),len(set(section['header'])))
            for entry in section['records']:
                self.assertEqual(set(entry['raw']),set(section['header']))
                self.assertGreaterEqual(entry['source_row'],2)
        self.assertEqual(sum(len(e['raw'])for k in expected for e in self.inputs[k]['records']),87672)
        self.assertEqual(audit.fingerprint(self.inputs),audit.RAW_INPUT_SHA)

    def test_exact_original_native_nces_crosswalk_not_names_or_code_inference(self):
        for key,link in self.links.items():
            row=self.directory[key]['raw'];ccd=self.ccd[str(row['NCES Number'])]['raw']
            self.assertEqual(str(row['NCES Number']),link['ncessch'])
            self.assertEqual(audit.ccd_identity(ccd,directory=True),link['ncessch'])
            self.assertEqual(audit.native_identity(dict(row,**{'School Name':'Renamed label'})),key)
            self.assertEqual(audit.ccd_identity(dict(ccd,SCH_NAME='Renamed label')),link['ncessch'])
            self.assertEqual(link['native_school_id'],ccd['ST_SCHID'])
        self.assertEqual(len({r['ncessch']for r in self.links.values()}),211)
        self.assertEqual(self.document['unmatched_ccd_directory'],[])

    def test_foreign_wrong_year_malformed_and_aggregate_id_rejected(self):
        raw=self.directory['15-0051']['raw'];ccd=self.ccd['240048000864']['raw']
        for field,value in [('LEA','14'),('School','51'),('School','A'),('Year',2024),('Year',2025.0)]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                audit.native_identity(dict(raw,**{field:value}))
        for field,value in [('LEAID','2400481'),('ST_LEAID','MD-14'),('SCHOOL_YEAR','2023-2024'),('ST','VA'),('NCESSCH','240048100864'),('ST_SCHID','MD-14-150051'),('UPDATED_STATUS','9')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                audit.ccd_identity(dict(ccd,**{field:value}),directory=True)
        income=self.income('15-0051')[0]['raw']
        for field,value in [('LEA Number','14'),('School Number','51'),('Academic Year','2024')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                audit.native_identity(dict(income,**{field:value}),income=True)

    def test_grade_scope_separates_native_primary_unknown_high_and_mixed(self):
        profiles=[r for r in self.links.values()if r['source_profile_eligible']]
        self.assertEqual(len(profiles),172)
        primary={'15-0307','15-0754','15-0776','15-0780','15-0791','15-0794'}
        self.assertEqual(set(self.document['cohorts']['native_primary_configurations']['school_ids']),primary)
        unknown={'15-0239','15-0525','15-0587','15-0748'}
        self.assertEqual(set(self.document['cohorts']['native_unknown_configurations']['school_ids']),unknown)
        self.assertEqual(self.links['15-0239']['offered']['band'],'mixed')
        self.assertEqual(self.links['15-0239']['enrolled']['reported_total'],0)
        self.assertEqual(self.links['15-0587']['enrolled']['reported_total'],90)
        self.assertIsNone(self.links['15-0587']['income']['early_attendance_enrollment'])
        self.assertEqual(self.document['nonoperational_directory'],[])
        self.assertTrue(all(r['operational']for r in self.links.values()))
        self.assertTrue(all(not self.links[key]['source_profile_eligible']for key in primary|unknown))
        self.assertEqual(self.document['coverage']['school_type_prospective'],{'Regular School':171,'Special Education School':1})
        self.assertTrue(self.links['15-0215']['source_profile_eligible'])

    def test_grade_gate_rejects_adjusted_incomplete_high_adult_and_suppressed_high_rows(self):
        profile=self.directory['15-0051']['raw'];ccd=self.ccd['240048000864']['raw'];grades=self.enrollment('15-0051')
        self.assertTrue(audit.grade_school_contract(profile,ccd,grades))
        for field,value in [('IGOFFERED','Imputed'),('G_3_OFFERED','Unknown'),('G_9_OFFERED','Yes'),('G_13_OFFERED','Yes'),('G_UG_OFFERED','Yes'),('G_AE_OFFERED','Yes'),('UPDATED_STATUS','2'),('GSHI','12')]:
            with self.subTest(field=field):
                self.assertFalse(audit.grade_school_contract(profile,dict(ccd,**{field:value}),grades))
        self.assertFalse(audit.grade_school_contract(dict(profile,**{'Grade Span':'EMH'}),ccd,grades))
        self.assertFalse(audit.grade_school_contract(profile,ccd,grades+[dict(grades[0],Grade='Grade 9',**{'Enrolled Count':'*'})]))
        self.assertFalse(audit.grade_school_contract(profile,ccd,[]))

    def test_original_ccd_and_september_totals_reconcile_without_income_substitution(self):
        c=self.document['coverage']
        self.assertEqual((c['district_fall_membership'],c['operational_school_fall_sum'],c['native_september_school_total_sum'],c['district_september_enrollment']),(159181,159181,159181,159181))
        self.assertEqual(c['lea_minus_operational_school_fall_enrollment'],0)
        self.assertEqual(c['district_membership_grade_evidence']['full_grade_sum'],159181)
        self.assertEqual(c['district_early_attendance_income']['early_attendance_enrollment'],159872)
        self.assertEqual(c['known_school_early_attendance_enrollment_sum'],159747)
        self.assertEqual(c['district_minus_known_school_early_attendance_enrollment'],125)
        self.assertEqual(c['missing_school_early_attendance_denominator_ids'],['15-0239','15-0525','15-0587','15-0748'])
        self.assertEqual(c['missing_native_september_school_total_ids'],['15-0239','15-0525','15-0748'])
        self.assertEqual(c['schools_with_early_attendance_ccd_difference'],197)
        self.assertEqual(c['suppressed_native_enrollment_cells'],51)
        link=self.links['15-0051']
        self.assertEqual(link['income']['early_attendance_enrollment'],349)
        self.assertAlmostEqual(link['income']['percentage'],100*105/349)
        self.assertNotEqual(link['income']['early_attendance_enrollment'],link['enrolled']['reported_total'])

    def test_individual_income_uses_own_counts_and_published_rounding(self):
        income=audit.income_evidence(self.income('15-0051'))
        self.assertEqual((income['individual_low_income_count'],income['early_attendance_enrollment']),(105,349))
        self.assertAlmostEqual(income['percentage'],100*105/349)
        self.assertLessEqual(abs(income['published_rounding_error']),.0500001)
        changed=copy.deepcopy(self.income('15-0051'));changed[0]['raw']['Total Student Cnt']='1000'
        with self.assertRaises(ValueError):audit.income_evidence(changed)
        changed=copy.deepcopy(self.income('15-0051'));changed[0]['raw']['Economically Disadvantaged Pct']='80.0'
        with self.assertRaises(ValueError):audit.income_evidence(changed)
        changed=copy.deepcopy(self.income('15-0051'));changed[0]['raw']['Economically Disadvantaged Cnt']='350'
        with self.assertRaises(ValueError):audit.income_evidence(changed)

    def test_multiband_income_selects_native_all_without_averaging(self):
        for key,den,low in [('15-0799',53,18),('15-0916',77,35),('15-0951',59,20),('15-0965',83,44)]:
            entries=self.income(key);income=audit.income_evidence(entries)
            self.assertGreater(len(entries),1)
            self.assertEqual(income['selected_school_type'],'All')
            self.assertEqual((income['early_attendance_enrollment'],income['individual_low_income_count']),(den,low))
            self.assertAlmostEqual(income['percentage'],100*low/den)
            self.assertFalse(self.links[key]['source_profile_eligible'])
            changed=[e for e in entries if e['raw']['School Type']!='All']
            self.assertIsNone(audit.income_evidence(changed)['percentage'])
        duplicated=copy.deepcopy(self.income('15-0051'))*2
        with self.assertRaises(ValueError):audit.income_evidence(duplicated)

    def test_zero_missing_range_and_proxies_never_reconstruct_income(self):
        for value in ['<= 5.0','>= 95.0','*','',None,'5-10']:
            self.assertIsNone(audit.maryland.percentage(value))
        for value,expected in [('0',0),('5',5),('95',95),('100',100),('30.1',30.1)]:
            self.assertEqual(audit.maryland.percentage(value),expected)
        for key in ['15-0410','15-0420','15-0422','15-0604']:
            income=self.links[key]['income']
            self.assertEqual(income['raw_percentage'],'<= 5.0')
            self.assertIsNone(income['percentage']);self.assertIsNone(income['individual_low_income_count'])
            changed=copy.deepcopy(self.income(key));changed[0]['raw']['FARMS Pct']='80.0';changed[0]['raw']['FARMS Cnt']='200'
            self.assertIsNone(audit.income_evidence(changed)['percentage'])
        zero=copy.deepcopy(self.income('15-0051'));zero[0]['raw'].update({'Economically Disadvantaged Pct':'0','Economically Disadvantaged Cnt':'0'})
        self.assertEqual(audit.income_evidence(zero)['percentage'],0)
        self.assertIsNone(audit.income_evidence([])['percentage'])

    def test_outcome_is_exact_native_school_regular_all_grades(self):
        entry=self.native('15-0051');link=self.links['15-0051']
        outcome=audit.outcome_evidence(entry,'math',scope=True,income=link['income'])
        self.assertEqual(outcome['native_rate'],float(entry['raw']['Proficient Pct']))
        self.assertEqual(entry['raw']['Assessment'],' Mathematics All Grades')
        for field,value in [('Assessment','Mathematics 03'),('Student Group','Economically Disadvantaged'),('Year',2024),('LEA','14'),('School','A'),('Proficient Pct','99.9')]:
            changed=copy.deepcopy(entry);changed['raw'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                audit.outcome_evidence(changed,'math',scope=True,income=link['income'])
        for field,value in [('worksheet','LEA_Level'),('member','2025 MCAP ELA Administrative Data Report Card.xlsx')]:
            changed=copy.deepcopy(entry);changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                audit.outcome_evidence(changed,'math',scope=True,income=link['income'])

    def test_native_total_masks_are_not_reconstructed(self):
        self.assertEqual(self.links['15-0215']['subjects']['math']['raw_rate'],'<= 5.0')
        self.assertEqual(self.links['15-0215']['subjects']['reading']['raw_rate'],'<= 5.0')
        self.assertEqual(self.links['15-0557']['subjects']['math']['raw_rate'],'<= 5.0')
        self.assertEqual(self.links['15-0557']['subjects']['math']['raw_tested'],'738')
        self.assertIsNone(self.links['15-0557']['subjects']['math']['native_rate'])
        self.assertTrue(self.links['15-0557']['subjects']['reading']['usable'])
        self.assertFalse(self.links['15-0557']['subjects']['combined']['usable'])
        self.assertTrue(all(not s['usable']for s in self.links['15-0215']['subjects'].values()))
        self.assertTrue(all(not s['usable']for key in ['15-0410','15-0420','15-0422','15-0604']for s in self.links[key]['subjects'].values()))

    def test_native_grade_course_and_aggregate_inventory_preserved(self):
        c=self.document['coverage'];outside=self.document['outside_directory_records']
        self.assertEqual(c['native_assessment_worksheets'],{'LEA_Level':24,'School_Level':1601})
        self.assertEqual(c['outside_native_records'],{'native_enrollment':18,'native_income':4,'native_assessment':24})
        for name,entries in outside.items():
            self.assertEqual({audit.native_identity(e['raw'],income=name=='native_income',aggregate=True)for e in entries},{'15-A'})
        self.assertNotIn('15-A',self.links)
        self.assertEqual(c['eligible_course_row_presence'],{'Algebra 1':43,'Algebra 2':23,'Geometry':40})
        self.assertEqual(c['eligible_course_rows_numeric_administrative_count'],{'Algebra 1':40,'Algebra 2':3,'Geometry':40})
        self.assertEqual(c['eligible_administrative_math_component_counts_reconciled'],148)
        for key in ['15-0227','15-0238','15-0607']:
            rows=[r for r in self.links[key]['accelerated_course_rows']if r['assessment'].strip()=='Algebra 1']
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['raw_tested'],'*')
            self.assertFalse(self.links[key]['administrative_math_component_counts']['valid_score_certified'])

    def test_sampling_count_floor_and_approvals_remain_unavailable(self):
        for link in self.links.values():
            for s in link['subjects'].values():
                self.assertIsNone(s['tested']);self.assertIsNone(s['valid_scores']);self.assertIsNone(s['sampling_variance'])
                self.assertFalse(s['sampling_interval_available']);self.assertFalse(s['ten_valid_scored_floor_certified'])
            if link['subjects']['combined']['usable']:
                self.assertEqual(link['subjects']['combined']['native_rate'],(link['subjects']['math']['native_rate']+link['subjects']['reading']['native_rate'])/2)
        self.assertFalse(self.document['approved_for_source']);self.assertFalse(self.document['approved_for_modeling'])
        self.assertEqual((self.document['scope'],self.document['status']),('source_cohort_audit_only','audit_pending'))
        self.assertNotIn('models',self.document)

    def test_original_definition_evidence_preserves_individual_collection_and_course_waiver(self):
        defs=self.document['source_definition_evidence'];markup=defs['msde_definitions']['raw_markup']
        for term in ['Economically Disadvantaged','Early Attendance','Medicaid','SNAP','TANF','Foster Child','Head Start','2022–2023']:
            self.assertIn(term,markup)
        self.assertIn('2026',markup)
        self.assertIn('not applied retroactively',defs['msde_definitions']['limitations'])
        overview=defs['msde_mcap_overview']
        self.assertIn('grade6–7',overview['paraphrase']);self.assertEqual(overview['source_pages'],[1,2])
        self.assertLessEqual(len(overview['excerpt'].split()),25)
        self.assertEqual(overview['excerpt_word_count'],3)
        self.assertEqual(overview['excerpt'],'MCAP Participation Requirements')
        self.assertNotIn('pages',overview)
        threshold=defs['msde_reportcard']
        self.assertEqual(threshold['section_references'],['2022ELASpecAssessFootnote','2022MathSpecAssessFootnote'])
        self.assertIn('Levels3 or4',threshold['paraphrase'])
        self.assertNotIn('raw_markup',threshold)
        self.assertEqual(self.document['sources']['msde_reportcard']['sha256'],'9857e65d009ccc6614beeaa12e289cbb93c37c8c67f809d394226dc19b5f8125')
        self.assertEqual(self.document['sources']['msde_mcap_overview']['sha256'],'594f383d7917939572b99d293e89582decfc7819f5a888de21e2b9b6cbcb4680')

    def test_offline_replay_never_opens_original_archives_workbooks_or_database(self):
        with mock.patch.object(audit.zipfile,'ZipFile',side_effect=AssertionError('ZIP unavailable')),mock.patch.object(audit.subprocess,'Popen',side_effect=AssertionError('Original stream unavailable')),mock.patch.object(audit.openpyxl,'load_workbook',side_effect=AssertionError('Workbook unavailable')):
            self.assertEqual(audit.validate(self.document)['prospective_source_profiles'],172)

    def test_original_hashes_headers_derived_values_and_approval_drift_rejected(self):
        changes=[lambda d:d.update(approved_for_source=0),lambda d:d.update(approved_for_modeling=True),
            lambda d:d.update(schema_version=1.0),lambda d:d.update(year=2025.0),lambda d:d.update(scope='ready'),lambda d:d.update(models=[]),
            lambda d:d['sources']['msde_income'].update(sha256='0'*64),lambda d:d['raw_inputs']['native_directory']['records'].pop(),
            lambda d:d['raw_inputs']['native_income']['records'][0]['raw'].update({'Economically Disadvantaged Pct':'0'}),
            lambda d:d['raw_inputs']['native_assessment']['records'][0]['raw'].update({'Proficient Pct':'0'}),
            lambda d:d['raw_inputs']['directory']['header'].pop(),lambda d:d['raw_inputs']['lea_membership']['records'].pop(),
            lambda d:d['raw_inputs']['native_assessment']['records'][0].update(source_row=1),
            lambda d:d['raw_inputs']['definitions']['msde_mcap_overview'].update(paraphrase='Changed'),
            lambda d:d['raw_inputs']['planning']['record']['potential_school_ids']['ES'].pop(),
            lambda d:d['roster_links'][0]['subjects']['math'].update(valid_scores=100),
            lambda d:d['roster_links'][0]['subjects']['math'].update(ten_valid_scored_floor_certified=True),
            lambda d:d['cohorts']['native_grade_school_source_profiles']['subjects']['combined'].update(usable=172),
            lambda d:d['coverage'].update(district_minus_known_school_early_attendance_enrollment=0)]
        for i,change in enumerate(changes):
            altered=copy.deepcopy(self.document);change(altered)
            with self.subTest(change=i),self.assertRaises(ValueError):audit.validate(altered,self.snapshot)

    def test_semantic_original_identity_population_and_counts_rejected_after_hash_repin(self):
        changes=[lambda d:d['raw_inputs']['directory']['records'][0]['raw'].update(LEAID='2400481'),
            lambda d:d['raw_inputs']['membership']['records'][0]['raw'].update(ST_SCHID='MD-14-150051'),
            lambda d:d['raw_inputs']['native_income']['records'][0]['raw'].update({'Academic Year':'2024'}),
            lambda d:d['raw_inputs']['native_assessment']['records'][0]['raw'].update({'Student Group':'Economically Disadvantaged'}),
            lambda d:d['raw_inputs']['native_assessment']['records'][0].update(worksheet='LEA_Level'),
            lambda d:d['raw_inputs']['native_assessment']['records'].append(copy.deepcopy(d['raw_inputs']['native_assessment']['records'][0])),
            lambda d:d['raw_inputs']['planning']['record'].update(enrollment=159872),
            lambda d:d['raw_inputs']['native_directory']['records'][0].update(source_row=1)]
        for i,change in enumerate(changes):
            altered=copy.deepcopy(self.document);change(altered)
            with self.subTest(change=i),mock.patch.object(audit,'RAW_INPUT_SHA',audit.fingerprint(altered['raw_inputs'])),self.assertRaises(ValueError):
                audit.validate(altered,self.snapshot)

    def test_complete_historical_comparison_change_requires_fresh_audit(self):
        altered=copy.deepcopy(self.snapshot);altered['schools'][0]['name']='Changed unrelated source'
        with self.assertRaises(ValueError):audit.validate(self.document,altered)


if __name__=='__main__':
    unittest.main()
