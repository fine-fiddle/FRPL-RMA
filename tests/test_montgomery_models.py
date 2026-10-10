"""Montgomery fixed source populations and independent deleted-school OLS replay."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_montgomery_models as audit


class MontgomeryNumericalAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster=audit.load_roster()
        cls.document=json.loads(audit.OUTPUT.read_text())
        cls.expected=audit.build(cls.roster)
        cls.models={m['subject']:m for m in cls.document['models']}

    def test_fixed_complete_source_subject_populations_and_false_release_flags(self):
        expected={'montgomery-2025-ES-math':166,'montgomery-2025-ES-reading':167,'montgomery-2025-ES-combined':166}
        self.assertEqual(audit.validate(self.document,self.expected),expected)
        self.assertEqual(self.document['hard_holds'],[])
        self.assertEqual((self.document['state'],self.document['nces_lea_id'],self.document['native_lea_id'],self.document['msde_lea_id']),('MD','2400480','MD-15','15'))
        self.assertEqual((self.document['scope'],self.document['status']),('numerical_audit_only','numerically_verified_pending_integration'))
        self.assertIs(self.document['approved_for_source'],False);self.assertIs(self.document['approved_for_modeling'],False)
        pop=self.document['frozen_population']
        counts={'complete_directory_ncessch':211,'operational_roster_school_ids':211,'grade_school_configuration_ids':172,
                'native_source_profile_ids':172,'usable_income_school_ids':168,'ccd_high_school_configuration_ids':27,
                'ccd_mixed_configuration_ids':5,'ccd_primary_configuration_ids':7,'native_high_configuration_ids':25,
                'native_mixed_configuration_ids':4,'native_primary_configuration_ids':6,'native_unknown_configuration_ids':4,
                'nonoperational_school_ids':0,'unmatched_ccd_ncessch':0}
        for field,n in counts.items():self.assertEqual(len(pop[field]),n,field)
        self.assertEqual(pop['native_aggregate_codes'],['15-A'])
        self.assertEqual(len(self.document['retained_scope_exclusions']['outside_grade_school_configuration_records']),39)
        self.assertNotIn('snapshots',self.document)
        for subject,n in [('math',166),('reading',167),('combined',166)]:
            m=self.models[subject]
            self.assertEqual(m['coverage']['grade_school_configuration_profiles'],172)
            self.assertEqual(m['coverage']['native_source_profiles'],172)
            self.assertEqual(m['coverage']['usable_income_profiles'],168)
            self.assertEqual(m['coverage']['excluded_configuration_profiles'],172-n)
            self.assertEqual(m['coefficients']['n'],n)
            self.assertEqual(m['coverage']['charter'],{'No':n})
            self.assertEqual(m['coverage']['school_types'],{'Regular School':n})
            self.assertEqual(m['diagnostics']['income_design_rank'],2)
            self.assertEqual(m['diagnostics']['full_residual_degrees_of_freedom'],n-2)
            self.assertEqual(m['diagnostics']['deleted_residual_degrees_of_freedom'],n-3)
            self.assertEqual(m['independent_verification']['explicit_deleted_fits'],n)
            self.assertEqual(m['independent_verification']['deleted_training_members'],n-1)
            self.assertEqual(m['independent_verification']['deleted_residual_degrees_of_freedom'],n-3)
            self.assertGreater(m['diagnostics']['minimum_deleted_sse'],0)
            self.assertGreater(m['diagnostics']['minimum_deleted_residual_scale'],0)
        self.assertEqual(sum(m['independent_verification']['explicit_deleted_fits']for m in self.models.values()),499)

    def test_original_raw_complete_evidence_and_historical_flags_are_immutable(self):
        retained=self.document['retained_source_evidence'];raw=retained['raw_inputs']
        self.assertEqual(audit.roster_audit.fingerprint(raw),audit.roster_audit.RAW_INPUT_SHA)
        self.assertEqual(sum(len(v['records'])for v in raw.values()if isinstance(v,dict)and'records'in v),5253)
        self.assertEqual(sum(len(e['raw'])for v in raw.values()if isinstance(v,dict)and'records'in v for e in v['records']),87672)
        self.assertEqual(retained['source_scope'],'source_cohort_audit_only')
        self.assertEqual(retained['source_status'],'audit_pending')
        self.assertEqual(retained['source_approval'],{'approved_for_source':False,'approved_for_modeling':False})
        self.assertEqual(self.document['sources']['source_audit_tests']['sha256'],audit.SOURCE_TEST_SHA)
        self.assertEqual(len(self.document['sources']['native_sources']),11)
        self.assertEqual(retained['source_definition_evidence']['msde_mcap_overview']['excerpt_word_count'],3)
        self.assertIn('Levels3 or4',retained['source_definition_evidence']['msde_reportcard']['paraphrase'])

    def test_raw_unweighted_full_and_every_explicit_deleted_fit_reproduce_metrics(self):
        for m in self.document['models']:
            x=np.array([r['income_pct']for r in m['inputs']]);y=np.array([r['outcome_pct']for r in m['inputs']]);n=len(x)
            X=np.column_stack([np.ones(n),x]);beta=np.linalg.lstsq(X,y,rcond=None)[0]
            pred=X@beta;residual=y-pred;sse=float(residual@residual);scale2=sse/(n-2)
            H=X@np.linalg.inv(X.T@X)@X.T
            self.assertAlmostEqual(float(beta[0]),m['coefficients']['intercept'],delta=2e-10)
            self.assertAlmostEqual(float(beta[1]),m['coefficients']['slope'],delta=2e-10)
            self.assertAlmostEqual(1-sse/float((y-y.mean())@(y-y.mean())),m['coefficients']['r2'],delta=2e-10)
            for i,row in enumerate(m['results']):
                keep=np.arange(n)!=i;D=X[keep];b=np.linalg.lstsq(D,y[keep],rcond=None)[0]
                e=y[keep]-D@b;deleted_sse=float(e@e);deleted_scale=math.sqrt(deleted_sse/(n-3));held=float(X[i]@b)
                predictive_h=float(X[i]@np.linalg.inv(D.T@D)@X[i]);external_t=(y[i]-held)/(deleted_scale*math.sqrt(1+predictive_h))
                cook=residual[i]**2*H[i,i]/(2*scale2*(1-H[i,i])**2)
                endpoints=np.column_stack([np.ones(2),[x.min(),x.max()]]);shift=float(np.max(np.abs(endpoints@beta-endpoints@b)))
                with self.subTest(subject=m['subject'],school=row['school_id']):
                    for field,value in [('predicted',pred[i]),('residual',residual[i]),('leverage',H[i,i]),('studentized',external_t),
                            ('cooks_distance',cook),('deleted_intercept',b[0]),('deleted_slope',b[1]),('deleted_sse',deleted_sse),
                            ('deleted_residual_scale',deleted_scale),('deleted_held_out_prediction',held),
                            ('deleted_held_out_prediction_leverage',predictive_h),('maximum_prediction_change_on_observed_income_range',shift)]:
                        self.assertAlmostEqual(row[field],float(value),delta=2e-9)
                    analytic_scale=math.sqrt((sse-residual[i]**2/(1-H[i,i]))/(n-3))
                    self.assertAlmostEqual(row['studentized'],residual[i]/(analytic_scale*math.sqrt(1-H[i,i])),delta=2e-9)

    def test_income_is_its_own_individual_early_attendance_ratio_and_outcome_is_published(self):
        for m in self.document['models']:
            for r in m['inputs']:
                native=r['sources']['native_directory']['raw'];ccd=r['sources']['directory_raw'];income=r['sources']['early_attendance_income']['raw']
                self.assertEqual(audit.roster_audit.native_identity(native),r['school_id'])
                self.assertEqual(str(native['NCES Number']),r['ncessch'])
                self.assertEqual(audit.roster_audit.ccd_identity(ccd),r['ncessch'])
                self.assertEqual((income['Academic Year'],income['LEA Number'],income['School Number']),('2025','15',r['school_id'][-4:]))
                self.assertEqual(r['income_pct'],100*int(income['Economically Disadvantaged Cnt'])/int(income['Total Student Cnt']))
                self.assertEqual(r['early_attendance_enrollment'],int(income['Total Student Cnt']))
                self.assertEqual(r['individual_low_income_count'],int(income['Economically Disadvantaged Cnt']))
                self.assertLessEqual(abs(r['income_pct']-float(income['Economically Disadvantaged Pct'])),.0500001)
                self.assertTrue(audit.native_grade_scope(native,ccd,r['sources']['native_enrollment']))
                for subject,entry in r['sources']['native_assessments'].items():
                    raw=entry['raw']
                    self.assertEqual(entry['worksheet'],'School_Level')
                    self.assertEqual(audit.roster_audit.native_identity(raw),r['school_id'])
                    self.assertEqual(raw['Student Group'],'All Students')
                    self.assertEqual(raw['Assessment'].strip(),'Mathematics All Grades'if subject=='math'else'English Language Arts All Grades')
                    self.assertEqual(r['outcome_by_subject'][subject],audit.exact_percent(raw['Proficient Pct']))
        c=self.document['source_coverage']
        self.assertEqual(c['district_fall_membership'],159181);self.assertEqual(c['district_early_attendance_income']['early_attendance_enrollment'],159872)
        self.assertEqual(c['district_minus_known_school_early_attendance_enrollment'],125)
        self.assertEqual(c['schools_with_early_attendance_ccd_difference'],197)

    def test_all_masks_primary_unknown_mixed_and_aggregate_records_remain_evidence(self):
        income_masks={'15-0410','15-0420','15-0422','15-0604'}
        for subject,m in self.models.items():
            exclusions={r['school_id']:r for r in m['coverage']['excluded_configuration_records']}
            self.assertTrue(income_masks.issubset(exclusions))
            self.assertIn('15-0215',exclusions)
            self.assertEqual(exclusions['15-0215']['subjects']['math']['raw_rate'],'<= 5.0')
            self.assertEqual(exclusions['15-0215']['subjects']['reading']['raw_rate'],'<= 5.0')
            self.assertEqual(exclusions['15-0215']['ccd_flags']['school_type'],'Special Education School')
            for key in income_masks:self.assertEqual(exclusions[key]['income']['raw_percentage'],'<= 5.0')
            if subject!='reading':
                self.assertIn('15-0557',exclusions);self.assertEqual(exclusions['15-0557']['subjects']['math']['raw_tested'],'738')
            else:self.assertIn('15-0557',[r['school_id']for r in m['inputs']])
        outside={r['school_id']:r for r in self.document['retained_scope_exclusions']['outside_grade_school_configuration_records']}
        for key in ['15-0307','15-0754','15-0776','15-0780','15-0791','15-0794','15-0239','15-0525','15-0587','15-0748','15-0799','15-0916','15-0951','15-0965']:
            self.assertIn(key,outside)
            self.assertTrue(all(key not in [r['school_id']for r in m['inputs']]for m in self.models.values()))
        self.assertEqual(outside['15-0239']['offered']['band'],'mixed')
        self.assertEqual(outside['15-0239']['enrolled']['reported_total'],0)
        self.assertEqual(self.document['source_coverage']['outside_native_records'],{'native_enrollment':18,'native_income':4,'native_assessment':24})

    def test_accelerated_course_scope_keeps_starred_presence_separate_from_counts(self):
        c=self.document['source_coverage']
        self.assertEqual(c['eligible_course_row_presence'],{'Algebra 1':43,'Geometry':40,'Algebra 2':23})
        self.assertEqual(c['eligible_course_rows_numeric_administrative_count'],{'Algebra 1':40,'Geometry':40,'Algebra 2':3})
        self.assertEqual(c['eligible_administrative_math_component_counts_reconciled'],148)
        self.assertIn('Algebra1/Geometry/Algebra2',self.models['math']['assessment_standard'])
        for key in ['15-0227','15-0238','15-0607']:
            r=next(r for r in self.models['math']['inputs']if r['school_id']==key)
            course=[e for e in r['sources']['accelerated_course_rows']if e['assessment'].strip()=='Algebra 1']
            self.assertEqual(course[0]['raw_tested'],'*')

    def test_combined_has_its_own_equal_mean_population_and_external_studentization(self):
        math_model,ela,combined=[self.models[s]for s in ['math','reading','combined']]
        by_ela={r['school_id']:r for r in ela['inputs']};ela_result={r['school_id']:r for r in ela['results']}
        x=np.array([r['income_pct']for r in combined['inputs']]);X=np.column_stack([np.ones(len(x)),x]);matching_ela=np.array([by_ela[r['school_id']]['outcome_pct']for r in combined['inputs']])
        restricted_ela=np.linalg.lstsq(X,matching_ela,rcond=None)[0]
        for r in combined['inputs']:self.assertEqual(r['outcome_pct'],(r['outcome_by_subject']['math']+r['outcome_by_subject']['reading'])/2)
        for i,field in enumerate(['intercept','slope']):
            self.assertAlmostEqual(combined['coefficients'][field],(math_model['coefficients'][field]+float(restricted_ela[i]))/2,delta=2e-10)
        self.assertGreater(abs(combined['coefficients']['intercept']-(math_model['coefficients']['intercept']+ela['coefficients']['intercept'])/2),.001)
        self.assertTrue(any(abs(c['studentized']-(m['studentized']+ela_result[c['school_id']]['studentized'])/2)>.01 for c,m in zip(combined['results'],math_model['results'])))

    def test_external_studentization_is_not_one_common_residual_standard_deviation(self):
        for m in self.models.values():
            raw=np.array([r['residual']for r in m['results']]);common=raw/raw.std(ddof=1)
            self.assertTrue(any(abs(r['studentized']-value)>.01 for r,value in zip(m['results'],common)))

    def test_influence_flags_are_descriptive_and_preserve_every_eligible_member(self):
        for m in self.models.values():
            self.assertEqual([r['school_id']for r in m['results']],self.document['frozen_population']['eligible_school_ids_by_subject'][m['subject']])
            self.assertGreater(m['diagnostics']['income']['standard_deviation_population'],17)
            self.assertGreaterEqual(m['diagnostics']['income']['distinct'],165)
            self.assertLess(m['diagnostics']['maximum_leverage'],1)
            self.assertGreater(m['diagnostics']['maximum_cooks_distance'],4/m['coefficients']['n'])
            for row in m['results']:
                self.assertEqual(row['review_flags']['absolute_external_t_above_2'],abs(row['studentized'])>2)
                self.assertEqual(row['review_flags']['leverage_above_2p_over_n'],row['leverage']>4/m['coefficients']['n'])
                self.assertEqual(row['review_flags']['cooks_above_4_over_n'],row['cooks_distance']>4/m['coefficients']['n'])

    def test_all_valid_counts_variances_endpoints_and_scored_floor_stay_unavailable(self):
        self.assertEqual(self.document['count_definition_status']['raw_field'],'Tested Count')
        self.assertIs(self.document['count_definition_status']['ten_valid_scored_floor_certified'],False)
        for m in self.models.values():
            self.assertFalse(m['approved_for_source']);self.assertFalse(m['approved_for_modeling']);self.assertFalse(m['valid_score_floor_certified'])
            self.assertFalse(m['intervals']['available_for_entire_model']);self.assertIsNone(m['intervals']['valid_score_counts']);self.assertIsNone(m['intervals']['sampling_variances'])
            for r in m['inputs']:
                self.assertEqual(r['valid_scores_by_subject'],{'math':None,'reading':None});self.assertIsNone(r['display_valid_scores']);self.assertIsNone(r['sampling_variance']);self.assertFalse(r['ten_valid_scored_floor_certified'])
            for r in m['results']:self.assertTrue(all(r[k]is None for k in ['valid_scores','sampling_variance','low','high']))
        passed=[];real=audit.fit_model
        def capture(x,y,variance):passed.append(variance.copy());return real(x,y,variance)
        m=self.models['math']
        with mock.patch.object(audit,'fit_model',side_effect=capture):result=audit.fit_audited_model(m['inputs'],m['coverage'],'math')
        self.assertTrue(np.array_equal(passed[0],np.zeros(166)));self.assertTrue(all(r['low']is None and r['high']is None for r in result['results']))

    def test_direct_fit_rejects_changed_members_values_proxies_counts_and_source_records(self):
        m=self.models['math']
        mutations=[lambda x:x.pop(),lambda x:x.reverse(),lambda x:x.append(copy.deepcopy(x[0])),lambda x:x[0].update(level='HS'),
            lambda x:x[0].update(income_year=2024),lambda x:x[0].update(income_year=2025.),lambda x:x[0].update(school_id='15-A'),
            lambda x:x[0].update(ncessch='240048199999'),lambda x:x[0].update(income_pct=False),lambda x:x[0].update(outcome_pct=float('nan')),
            lambda x:x[0].update(sampling_variance=0.),lambda x:x[0].update(display_valid_scores=10),lambda x:x[0]['valid_scores_by_subject'].update(math=10),
            lambda x:x[0].update(ten_valid_scored_floor_certified=True),lambda x:x[0].update(early_attendance_enrollment=159181),
            lambda x:x[0]['sources']['early_attendance_income']['raw'].update({'Economically Disadvantaged Pct':'0'}),
            lambda x:x[0]['sources']['early_attendance_income']['raw'].update({'Total Student Cnt':'159181'}),
            lambda x:x[0]['sources']['native_assessments']['math']['raw'].update({'Assessment':'Mathematics 03'}),
            lambda x:x[0]['sources']['native_assessments']['math']['raw'].update({'Tested Count':'10'}),
            lambda x:x[0]['sources']['native_assessments']['math'].update(worksheet='LEA_Level'),
            lambda x:x[0]['sources']['directory_raw'].update(UPDATED_STATUS='2'),
            lambda x:x[0]['sources']['native_directory']['raw'].update({'Grade Span':'H'})]
        for i,mutation in enumerate(mutations):
            changed=copy.deepcopy(m['inputs']);mutation(changed)
            with self.subTest(change=i),mock.patch.object(audit,'fit_model',side_effect=AssertionError('No fit before source guards')),self.assertRaises(ValueError):audit.fit_audited_model(changed,m['coverage'],'math')
        with mock.patch.object(audit,'fit_model',side_effect=AssertionError('No fit below floor')),self.assertRaisesRegex(ValueError,'at least 30'):audit.fit_audited_model(m['inputs'][:29],m['coverage'],'math')
        for subject in ['high','mixed','science']:
            with self.assertRaises(ValueError):audit.fit_audited_model(m['inputs'],m['coverage'],subject)
        coverage=copy.deepcopy(m['coverage']);coverage['usable_schools']=172
        with self.assertRaises(ValueError):audit.fit_audited_model(m['inputs'],coverage,'math')

    def test_independent_scope_guard_rejects_high_ungraded_incomplete_and_suppressed_high_rows(self):
        r=self.models['math']['inputs'][0];profile=r['sources']['native_directory']['raw'];ccd=r['sources']['directory_raw'];grades=r['sources']['native_enrollment']
        self.assertTrue(audit.native_grade_scope(profile,ccd,grades))
        for key,value in [('G_9_OFFERED','Yes'),('G_UG_OFFERED','Yes'),('G_AE_OFFERED','Yes'),('IGOFFERED','Imputed'),('G_3_OFFERED','Unknown'),('UPDATED_STATUS','2')]:
            self.assertFalse(audit.native_grade_scope(profile,dict(ccd,**{key:value}),grades))
        self.assertFalse(audit.native_grade_scope(dict(profile,**{'Grade Span':'EMH'}),ccd,grades))
        self.assertFalse(audit.native_grade_scope(profile,ccd,grades+[dict(grades[0],raw=dict(grades[0]['raw'],Grade='Grade 9',**{'Enrolled Count':'*'}))]))

    def test_numeric_zero_masks_ranges_and_nonstring_original_values_are_distinct(self):
        for value in ['<= 5.0','>= 95.0','*','',None,'5-10',True,0]:self.assertIsNone(audit.exact_percent(value))
        for value,expected in [('0',0.),('5',5.),('100',100.),('30.1',30.1)]:self.assertEqual(audit.exact_percent(value),expected)
        self.assertEqual(audit.exact_count('0'),0)
        for value in ['*','<= 5','',None,True,1,1.0]:self.assertIsNone(audit.exact_count(value))
        for value in ['101','100.1']:
            with self.assertRaises(ValueError):audit.exact_percent(value)

    def test_rank_positive_full_and_each_deleted_scale_are_hard_gates(self):
        m=self.models['math'];x=np.array([r['income_pct']for r in m['inputs']]);y=np.array([r['outcome_pct']for r in m['inputs']]);zero=np.zeros(len(x))
        for bad_x,bad_y in [(np.full(len(x),20.),y),(x,10.+.5*x),(np.r_[30.,np.full(len(x)-1,20.)],y)]:
            with self.assertRaises(ValueError):audit.fit_model(bad_x,bad_y,zero)
        one_outlier=10.+.5*x;one_outlier[0]+=1.
        with self.assertRaisesRegex(ValueError,'Deleted-school residual variance'):audit.fit_model(x,one_outlier,zero)
        # Supply a full-fit scaffold directly: neither implementation may accept
        # the perfect deleted fit merely because the complete fit has variance.
        centered=x-x.mean();design=np.column_stack([np.ones(len(x)),centered]);beta=np.linalg.lstsq(design,one_outlier,rcond=None)[0]
        predicted=design@beta;residual=one_outlier-predicted;leverage=1/len(x)+centered**2/(centered@centered)
        coefficients={'n':len(x),'intercept':float(beta[0]-beta[1]*x.mean()),'slope':float(beta[1]),'r2':float(1-(residual@residual)/((one_outlier-one_outlier.mean())@(one_outlier-one_outlier.mean())))}
        rows=[{'actual':float(one_outlier[i]),'predicted':float(predicted[i]),'residual':float(residual[i]),'leverage':float(leverage[i]),'studentized':0.,'low':None,'high':None}for i in range(len(x))]
        with self.assertRaisesRegex(ValueError,'deleted-school residual scale'):audit.verify_independently(x,one_outlier,coefficients,rows)
        for bad in [np.full(len(x),np.nan),np.full(len(x),np.inf),np.full(len(x),20.)]:
            with self.assertRaises(ValueError):audit.verify_independently(bad,y,m['coefficients'],m['results'])

    def test_corrupt_shared_fitter_coefficients_outputs_and_boolean_numbers_are_rejected(self):
        m=self.models['math'];real=audit.fit_model
        changes=[('coefficients','intercept',0.),('coefficients','n',False),('coefficients','r2',float('nan')),
            ('results','actual',0.),('results','predicted',float('inf')),('results','residual',False),('results','studentized',0.),('results','leverage',False)]
        for location,key,bad in changes:
            def corrupt(x,y,variance):
                coefficients,rows=real(x,y,variance);(coefficients if location=='coefficients'else rows[0])[key]=bad;return coefficients,rows
            with self.subTest(location=location,key=key),mock.patch.object(audit,'fit_model',side_effect=corrupt),self.assertRaisesRegex(ValueError,'Independent'):audit.fit_audited_model(m['inputs'],m['coverage'],'math')

    def test_saved_source_policy_membership_count_and_approval_mutations_fail_exact_replay(self):
        changes=[lambda d:d.update(approved_for_source=0),lambda d:d.update(approved_for_modeling=True),lambda d:d.update(scope='ready'),
            lambda d:d['count_definition_status'].update(ten_valid_scored_floor_certified=True),lambda d:d['sources']['roster_audit'].update(sha256='0'*64),
            lambda d:d['sources']['source_audit_tests'].update(sha256='0'*64),lambda d:d['source_coverage'].update(verified_valid_score_counts=False),
            lambda d:d['retained_source_evidence']['raw_inputs']['native_assessment']['records'].pop(),
            lambda d:d['frozen_population']['eligible_school_ids_by_subject']['math'].append('15-0557'),lambda d:d['models'][0]['inputs'][0].update(income_pct=25.),
            lambda d:d['models'][0]['coverage']['excluded_configuration_records'].pop(),lambda d:d['models'][0]['intervals'].update(valid_score_counts=100),
            lambda d:d['models'][0]['results'][0].update(actual=d['models'][0]['results'][0]['actual']+1e-12),lambda d:d['models'][0]['results'][0].update(low=0.),
            lambda d:d['models'][0]['results'][0].update(sampling_variance=0.),lambda d:d['models'][0]['independent_verification'].update(tolerance_absolute=1.),
            lambda d:d['retained_scope_exclusions']['outside_directory_records']['native_assessment'].pop()]
        for i,change in enumerate(changes):
            changed=copy.deepcopy(self.document);change(changed)
            with self.subTest(change=i),self.assertRaises(ValueError):audit.validate(changed,self.expected)

    def test_saved_deleted_and_other_numerical_fields_require_finite_correct_types_and_tolerance(self):
        fields=['predicted','residual','studentized','leverage','cooks_distance','deleted_intercept','deleted_slope','deleted_sse','deleted_residual_scale',
            'deleted_held_out_prediction','deleted_held_out_prediction_leverage','maximum_prediction_change_on_observed_income_range']
        for field in fields:
            for bad in [False,float('nan'),float('inf')]:
                changed=copy.deepcopy(self.document);changed['models'][0]['results'][0][field]=bad
                with self.subTest(field=field,bad=bad),self.assertRaises(ValueError):audit.validate(changed,self.expected)
            changed=copy.deepcopy(self.document);changed['models'][0]['results'][0][field]+=1.
            with self.subTest(field=field),self.assertRaises(ValueError):audit.validate(changed,self.expected)
        changed=copy.deepcopy(self.document);changed['models'][0]['coefficients']['slope']+=.01
        with self.assertRaises(ValueError):audit.validate(changed,self.expected)
        self.assertFalse(audit.numeric_equal(True,1.));self.assertFalse(audit.numeric_equal(1,1.));self.assertFalse(audit.numeric_equal(2025.,2025));self.assertTrue(audit.numeric_equal(1.+1e-12,1.))

    def test_source_artifact_code_test_and_in_memory_original_drift_fail_before_fit(self):
        for path,sha in [(audit.ROSTER,audit.ROSTER_SHA),(audit.SOURCE_CODE,audit.SOURCE_CODE_SHA),(audit.SOURCE_TEST,audit.SOURCE_TEST_SHA)]:
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),sha)
        changed=copy.deepcopy(self.roster);changed['roster_links'][0]['income']['percentage']+=1.
        with self.assertRaises(ValueError):audit.build(changed)
        with self.assertRaises(ValueError):audit.selected_inputs(changed,'math')
        with tempfile.TemporaryDirectory()as t:
            p=Path(t)/'changed.json';p.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):audit.load_roster(p)
            for field in ['SOURCE_CODE','SOURCE_TEST']:
                with mock.patch.object(audit,field,p),self.assertRaises(ValueError):audit.load_roster()

    def test_two_numerical_builds_and_offline_replay_never_access_raw_sources_or_canonical_database(self):
        with tempfile.TemporaryDirectory()as t:
            first,second=Path(t)/'first.json',Path(t)/'second.json'
            a=audit.prepare(first);b=audit.prepare(second)
            self.assertEqual(a,b);self.assertEqual(first.read_bytes(),second.read_bytes());self.assertEqual(first.read_bytes(),audit.OUTPUT.read_bytes())
            before=first.read_bytes()
            with mock.patch.object(audit.roster_audit.zipfile,'ZipFile',side_effect=AssertionError('No raw ZIP')),mock.patch.object(audit.roster_audit.subprocess,'Popen',side_effect=AssertionError('No raw stream')),mock.patch.object(audit.roster_audit.openpyxl,'load_workbook',side_effect=AssertionError('No workbook')),mock.patch.object(sqlite3,'connect',side_effect=AssertionError('No canonical access')):
                self.assertEqual(audit.prepare(first,check=True),a)
            self.assertEqual(first.read_bytes(),before)


if __name__=='__main__':
    unittest.main()
