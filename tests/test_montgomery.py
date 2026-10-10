"""Montgomery native published-rate normalization, canonical ownership and exports."""
import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from database import connect
from state_snapshot import import_snapshot,prepare_snapshot
import state_snapshot
import prepare_montgomery as district

TABLES=['dataset','source','assessment_definition','economic_definition','school','economic_observation','assessment_observation','model_run','model_result']
WORK=ROOT/'data/build/montgomery-integration-implementation'
MISSING_INCOME={'15-0410','15-0420','15-0422','15-0604'}


def rows(db):
    return {t:[tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in TABLES}


def prior_rows(db):
    return {t:[r for r in records if not any(isinstance(v,str) and(v==district.DATASET or v.startswith(district.DATASET+':')) for v in r)] for t,records in rows(db).items()}


def seed_other(db):
    """Same native identity in an independently owned statewide population."""
    db.execute("INSERT INTO dataset VALUES ('other-md','MD','Keep release','Keep population','ready')")
    db.execute("INSERT INTO source VALUES ('other-source','other-md','other.json','https://example.test/source',?,'2025-01-01')",('1'*64,))
    db.execute("INSERT INTO assessment_definition VALUES ('other-assessment','MD','Other test',2025,'ES','3','Keep standard','https://example.test/assessment')")
    db.execute("INSERT INTO economic_definition VALUES ('other-income','Keep income','Keep definition','https://example.test/income')")
    db.execute("INSERT INTO school VALUES ('other-md','15-0051','Keep school','other-district','Keep district',NULL,NULL,'{}','other-source',1)")
    db.execute("INSERT INTO economic_observation VALUES ('other-md','15-0051',2025,'other-income','Keep school',100,30,30,'Keep income','{}','other-source',1)")
    db.execute("INSERT INTO assessment_observation VALUES ('other-md','15-0051','other-assessment','math',40,100,'reported','{}','100','other-source',1)")
    db.execute("INSERT INTO model_run VALUES ('other-model','other-md','other-assessment','math','keep-method',?,'{}')",('2'*64,))
    db.execute("INSERT INTO model_result VALUES ('other-model','other-md','15-0051',40,45,-1,-2,0)")


def run_prepared(operation,*args):
    handles=[];original=state_snapshot.connect
    def tracked(path):
        handle=original(path);handles.append(handle);return handle
    try:
        with mock.patch.object(state_snapshot,'connect',side_effect=tracked):return operation(*args)
    finally:
        for handle in handles:handle.close()


class MontgomeryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True,exist_ok=True)
        cls.roster,cls.numerical=district.load_inputs()
        cls.payload=json.loads(district.EXTRACT.read_text());cls.expected=district.build_snapshot(cls.roster,cls.numerical)
        cls.links={r['school_id']:r for r in cls.roster['roster_links']};cls.profiles={s['id']:s for s in cls.payload['schools']}
        cls.sandbox=tempfile.TemporaryDirectory(prefix='test-',dir=WORK);cls.output=Path(cls.sandbox.name)/'output';cls.database=Path(cls.sandbox.name)/'schools.sqlite'
        with closing(connect(cls.database)) as db:db.executescript((ROOT/'scripts/schema.sql').read_text());seed_other(db);db.commit()
        run_prepared(district.prepare,cls.database,cls.output)

    @classmethod
    def tearDownClass(cls):cls.sandbox.cleanup()

    def test_complete_nullable_profiles_and_separate_normalized_approval(self):
        district.validate(self.payload,self.expected)
        self.assertEqual((self.payload['dataset'],self.payload['region'],self.payload['region_name'],self.payload['release_status']),('md-montgomery-2025','montgomery','Montgomery County','ready'))
        self.assertEqual(self.payload['state'],{'id':'MD','name':'Maryland'});self.assertIs(self.payload['statewide'],False)
        self.assertIs(self.payload['approved_for_source'],True);self.assertIs(self.payload['approved_for_modeling'],True)
        self.assertEqual(len(self.profiles),172);self.assertEqual(set(self.profiles),set(self.numerical['frozen_population']['grade_school_configuration_ids']))
        self.assertEqual({s['id'] for s in self.payload['schools'] if s['income'] is None},MISSING_INCOME)
        self.assertEqual(sum(s['income'] is not None for s in self.payload['schools']),168)
        for scope in ['ccd_high_school_configuration_ids','ccd_mixed_configuration_ids','ccd_primary_configuration_ids','native_unknown_configuration_ids']:
            self.assertFalse(set(self.profiles).intersection(self.numerical['frozen_population'][scope]))
        for historical in [self.roster,self.numerical]:
            self.assertIs(historical['approved_for_source'],False);self.assertIs(historical['approved_for_modeling'],False)
        self.assertEqual(len(self.payload['sources']),17)
        selection=dict(self.payload['selection']);digest=selection.pop('sha256');self.assertEqual(digest,district.roster_audit.fingerprint(selection))
        c=self.payload['cohorts'][0]
        self.assertEqual((c['assessment'],c['standard']),(district.model_audit.ASSESSMENT,district.model_audit.STANDARD))
        self.assertEqual(c['grades'],'3–8 plus accelerated math courses');self.assertIs(c['allow_point_only'],True)
        for text in [c['note'],self.payload['coverage_note'],self.payload['methodology']['summary']]:
            for term in ['valid-score count scope','ten-valid-scored floor','uncertified','sampling intervals','unavailable']:self.assertIn(term,text.casefold())

    def test_all_original_identity_grade_income_course_and_definition_evidence_retained(self):
        evidence=self.payload['source_audit'];raw=evidence['retained_raw_inputs']
        self.assertEqual(district.roster_audit.fingerprint(raw),district.roster_audit.RAW_INPUT_SHA)
        self.assertEqual(sum(len(v['records']) for v in raw.values() if isinstance(v,dict)and'records'in v),5253)
        self.assertEqual(sum(len(e['raw']) for v in raw.values() if isinstance(v,dict)and'records'in v for e in v['records']),87672)
        self.assertEqual(evidence['source_definition_evidence'],self.roster['source_definition_evidence'])
        self.assertEqual(evidence['planning_identity_reconciliation'],self.roster['planning'])
        self.assertEqual(len(evidence['excluded_operational_roster_records']),39)
        self.assertEqual(evidence['nonoperational_directory'],[]);self.assertEqual(evidence['unmatched_ccd_directory'],[])
        self.assertEqual([evidence['subject_coverage'][s]['excluded_configuration_profiles'] for s in district.model_audit.SUBJECTS],[6,5,6])
        self.assertEqual([len(evidence['outside_directory_records'][k]) for k in ['native_enrollment','native_income','native_assessment']],[18,4,24])
        for key,s in self.profiles.items():
            link=self.links[key];identity=s['identity_raw'];native=identity['native_directory']['raw'];ccd=identity['ccd']['raw']
            self.assertEqual(district.roster_audit.native_identity(native),key)
            self.assertEqual(str(native['NCES Number']),s['ncessch']);self.assertEqual(district.roster_audit.ccd_identity(ccd),s['ncessch'])
            self.assertEqual(identity['native_school_id'],ccd['ST_SCHID']);self.assertEqual(s['district_id'],'2400480')
            self.assertEqual(s['name'],native['School Name']);self.assertEqual(s['city'],ccd['LCITY'] or None)
            self.assertEqual(identity['enrolled_evidence'],link['enrolled']);self.assertEqual(s['income_raw']['individual_income_evidence'],link['income'])
            self.assertTrue(district.model_audit.native_grade_scope(native,ccd,identity['native_september_enrollment']))
            for subject in ['math','reading']:
                value=s['outcomes'][subject];entry=value['raw']['assessment_record'];r=entry['raw']
                self.assertEqual((entry['worksheet'],r['Year'],r['Student Group']),('School_Level',2025,'All Students'))
                self.assertEqual(r['Assessment'].strip(),'Mathematics All Grades'if subject=='math'else'English Language Arts All Grades')
                self.assertEqual(value['proficiency'],district.model_audit.exact_percent(r['Proficient Pct']))
                self.assertEqual(value['raw']['assessment_raw'],r);self.assertTrue(all(value[k]is None for k in ['tested','raw_tested','valid_score_evidence']))
                self.assertIsNone(value['raw']['sampling_variance']);self.assertIsNone(value['raw']['valid_score_count']);self.assertIs(value['raw']['ten_valid_scored_floor_certified'],False)
        self.assertEqual(self.profiles['15-0215']['identity_raw']['ccd_flags']['school_type'],'Special Education School')
        self.assertEqual(self.profiles['15-0215']['outcomes']['math']['raw']['native_rate'],'<= 5.0')
        self.assertEqual(self.profiles['15-0557']['outcomes']['math']['raw']['assessment_raw']['Tested Count'],'738')
        self.assertEqual(self.profiles['15-0557']['outcomes']['reading']['proficiency'],23.3)
        c=evidence['operational_roster'];self.assertEqual(c['eligible_course_row_presence'],{'Algebra 1':43,'Geometry':40,'Algebra 2':23})
        self.assertEqual(c['eligible_course_rows_numeric_administrative_count'],{'Algebra 1':40,'Geometry':40,'Algebra 2':3})
        self.assertEqual(c['eligible_administrative_math_component_counts_reconciled'],148)

    def test_income_uses_own_same_year_denominator_and_keeps_masked_published_outcomes(self):
        for key,s in self.profiles.items():
            raw=s['income_raw']['early_attendance_income']['raw'];den=int(raw['Total Student Cnt'])
            self.assertEqual((raw['Academic Year'],raw['LEA Number'],raw['School Number']),('2025','15',key[-4:]))
            self.assertEqual(s['enrollment'],den)
            if key in MISSING_INCOME:
                self.assertEqual(raw['Economically Disadvantaged Pct'],'<= 5.0');self.assertEqual(raw['Economically Disadvantaged Cnt'],'*')
                self.assertIsNone(s['income']);self.assertIsNone(s['low_income'])
                self.assertTrue(all(s['outcomes'][subject]['proficiency'] is not None for subject in ['math','reading']))
            else:
                self.assertEqual(s['low_income'],int(raw['Economically Disadvantaged Cnt']))
                self.assertEqual(s['income'],100*int(raw['Economically Disadvantaged Cnt'])/den)
                self.assertLessEqual(abs(s['income']-float(raw['Economically Disadvantaged Pct'])),.0500001)
        c=self.payload['source_audit']['operational_roster']
        self.assertEqual((c['district_fall_membership'],c['district_september_enrollment'],c['native_september_school_total_sum']),(159181,159181,159181))
        self.assertEqual(c['district_early_attendance_income']['early_attendance_enrollment'],159872)
        self.assertEqual((c['known_school_early_attendance_enrollment_sum'],c['district_minus_known_school_early_attendance_enrollment']),(159747,125))
        self.assertEqual(c['schools_with_early_attendance_ccd_difference'],197)
        self.assertTrue(any(s['enrollment']!=s['identity_raw']['enrolled_evidence']['reported_total'] for s in self.profiles.values()))

    def test_repeat_import_preserves_shared_native_identity_all_nine_tables(self):
        with closing(connect(':memory:')) as db:
            db.executescript((ROOT/'scripts/schema.sql').read_text());seed_other(db);before=prior_rows(db)
            import_snapshot(db,self.payload,district.EXTRACT);first=rows(db);import_snapshot(db,self.payload,district.EXTRACT)
            self.assertEqual(first,rows(db));self.assertEqual(before,prior_rows(db))
            self.assertEqual({t:len(rows(db)[t])-len(before[t]) for t in TABLES},dict(dataset=1,source=18,assessment_definition=1,economic_definition=1,school=172,economic_observation=172,assessment_observation=344,model_run=0,model_result=0))
            self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=? AND status="reported"',(district.DATASET,)).fetchone()[0],341)
            self.assertEqual(db.execute('SELECT count(*) FROM economic_observation WHERE dataset_id=? AND percentage IS NULL',(district.DATASET,)).fetchone()[0],4)
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall());self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_prepare_twice_preserves_complete_maryland_state_results_and_rejects_before_mutation(self):
        with tempfile.TemporaryDirectory(prefix='repeat-',dir=WORK) as t:
            folder=Path(t);database=folder/'schools.sqlite';output=folder/'output';state=district.roster_audit.load_maryland()
            with closing(connect(database)) as db:db.executescript((ROOT/'scripts/schema.sql').read_text());seed_other(db);db.commit()
            run_prepared(prepare_snapshot,state,district.roster_audit.maryland.EXTRACT,folder/'state-output',database)
            with closing(connect(database)) as db:before=prior_rows(db)
            run_prepared(district.prepare,database,output);first_files={p.name:p.read_bytes() for p in output.glob('*.json')}
            with closing(connect(database)) as db:first=rows(db)
            run_prepared(district.prepare,database,output)
            self.assertEqual(first_files,{p.name:p.read_bytes() for p in output.glob('*.json')})
            with closing(connect(database)) as db:self.assertEqual(first,rows(db));self.assertEqual(before,prior_rows(db))
            wrong=folder/'wrong.json';bad=copy.deepcopy(self.payload);bad['schools'][0]['outcomes']['math'].update(tested=100,valid_score_evidence='Enrollment');wrong.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):run_prepared(district.prepare,database,output,wrong)
            with closing(connect(database)) as db:self.assertEqual(first,rows(db))
            self.assertEqual(first_files,{p.name:p.read_bytes() for p in output.glob('*.json')})
            with mock.patch.object(district,'prepare_snapshot',side_effect=AssertionError('No mutation')),self.assertRaises(ValueError):district.prepare(database,Path('/tmp/montgomery-output'),district.EXTRACT)

    def test_all_499_canonical_current_history_results_and_missing_profiles_match_numerical_audit(self):
        self.assertEqual(district.validate_canonical(self.payload,self.database,self.numerical),{'schools':172,'observations':344,'models':3,'results':499})
        self.assertEqual(district.validate_exports(self.payload,self.output,self.numerical),{f'montgomery-2025-ES-{s}':district.EXPECTED_N[s] for s in district.model_audit.SUBJECTS})
        selected={s['id']:s for s in json.loads((self.output/'schools.json').read_text())['schools']}
        for key,s in selected.items():
            if key in MISSING_INCOME or key=='15-0215':
                self.assertEqual(s['metrics'],{});self.assertEqual(set(s['exclusions']),{'math','reading','combined'})
                self.assertEqual(s['history'][0]['subjects'],{})
            elif key=='15-0557':
                self.assertEqual(set(s['metrics']),{'reading'});self.assertEqual(set(s['exclusions']),{'math','combined'})
            else:self.assertEqual(set(s['metrics']),{'math','reading','combined'});self.assertEqual(s['exclusions'],{})
            self.assertTrue(all(v['tested']is None and v['low']is None and v['high']is None and'variance'not in v for v in s['metrics'].values()))
            self.assertEqual((s['program'],s['latitude'],s['longitude']),('Unclassified',None,None))
        with closing(connect(self.database)) as db:
            self.assertEqual({t:len(rows(db)[t])-1 for t in TABLES},dict(dataset=1,source=18,assessment_definition=1,economic_definition=1,school=172,economic_observation=172,assessment_observation=344,model_run=3,model_result=499))

    def test_combined_has_own_equal_mean_population_fit_and_studentization(self):
        models={m['subject']:m for m in self.numerical['models']};combined=models['combined']
        self.assertGreater(abs(combined['coefficients']['intercept']-(models['math']['coefficients']['intercept']+models['reading']['coefficients']['intercept'])/2),.01)
        for r in combined['inputs']:self.assertEqual(r['outcome_pct'],(r['outcome_by_subject']['math']+r['outcome_by_subject']['reading'])/2)
        export=json.loads((self.output/'schools.json').read_text())['models']['ES']['combined']
        self.assertAlmostEqual(export['intercept'],82.92382709332801,places=10);self.assertAlmostEqual(export['slope'],-.9505661637503635,places=10);self.assertAlmostEqual(export['r2'],.8306995759472636,places=10)

    def test_normalized_source_masks_ownership_counts_policy_and_frozen_input_corruptions_rejected(self):
        mutations=[lambda d:d['schools'].pop(),lambda d:d['schools'][0].update(id='15-A'),lambda d:d['schools'][0]['identity_raw']['ccd']['raw'].update(LEAID='2400490'),
            lambda d:d['schools'][0]['identity_raw']['native_directory']['raw'].update(Year=2024),lambda d:d['schools'][0]['income_raw']['early_attendance_income']['raw'].update(**{'Total Student Cnt':'355'}),
            lambda d:d['schools'][0]['outcomes']['math']['raw']['assessment_raw'].update(**{'Student Group':'All economically disadvantaged'}),
            lambda d:d['schools'][0]['outcomes']['math'].update(tested=100,valid_score_evidence='CCD'),lambda d:d['schools'][0]['outcomes']['reading'].update(proficiency=99.),
            lambda d:next(s for s in d['schools']if s['id']=='15-0410').update(income=0.,low_income=0),lambda d:d['cohorts'][0].update(allow_point_only=False),
            lambda d:d['cohorts'][0].update(assessment='DLM'),lambda d:d['source_audit']['excluded_operational_roster_records'].clear(),
            lambda d:d['source_audit']['outside_directory_records']['native_assessment'].clear(),lambda d:d['source_audit']['retained_raw_inputs']['membership']['records'][0]['raw'].update(STUDENT_COUNT='0'),
            lambda d:d['source_audit']['release_basis'].update(historical_audits_approved_for_modeling=0),lambda d:d['source_audit']['count_definition_status'].update(ten_valid_scored_floor_certified=True),
            lambda d:d['sources']['numerical_audit_tests'].update(sha256='0'*64),lambda d:d['selection']['directory_school_ids'].pop(),lambda d:d.update(statewide=0),lambda d:d.update(approved_for_modeling=1),lambda d:d['schools'][0].update(income=True)]
        for i,mutate in enumerate(mutations):
            changed=copy.deepcopy(self.payload);mutate(changed)
            with self.subTest(i=i),self.assertRaises(ValueError):district.validate(changed,self.expected)
        for kind in ['source','numeric','boolean']:
            source,numeric=copy.deepcopy(self.roster),copy.deepcopy(self.numerical)
            if kind=='source':source['roster_links'].pop()
            elif kind=='numeric':numeric['models'][0]['results'][0]['studentized']+=1.
            else:numeric['approved_for_source']=0
            with self.subTest(kind=kind),self.assertRaises(ValueError):district.build_snapshot(source,numeric)
        with tempfile.TemporaryDirectory(dir=WORK) as t:
            wrong=Path(t)/'wrong';wrong.write_text('{}')
            for attribute,owner in [('NUMERICAL_CODE',district),('NUMERICAL_TEST',district),('OUTPUT',district.model_audit)]:
                with mock.patch.object(owner,attribute,wrong),self.assertRaisesRegex(ValueError,'fingerprint'):district.load_inputs()

    def test_canonical_proxies_orphans_raw_drift_and_foreign_namespace_rejected(self):
        corruptions = [
            "UPDATE model_result SET studentized=99 WHERE dataset_id='md-montgomery-2025' AND school_id='15-0051'",
            "UPDATE assessment_observation SET tested=893 WHERE dataset_id='md-montgomery-2025' AND school_id='15-0410'",
            "UPDATE assessment_observation SET proficiency=95,status='reported' WHERE dataset_id='md-montgomery-2025' AND school_id='15-0557' AND subject='math'",
            "UPDATE assessment_observation SET proficiency=NULL,status='suppressed_or_not_reported' WHERE dataset_id='md-montgomery-2025' AND school_id='15-0410'",
            "UPDATE economic_observation SET percentage=0,low_income=0 WHERE dataset_id='md-montgomery-2025' AND school_id='15-0410'",
            "UPDATE economic_observation SET percentage=percentage+1e-12 WHERE dataset_id='md-montgomery-2025' AND school_id='15-0051'",
            "UPDATE school SET name='Wrong school' WHERE dataset_id='md-montgomery-2025' AND school_id='15-0051'",
            "UPDATE assessment_observation SET raw_value='{}' WHERE dataset_id='md-montgomery-2025' AND school_id='15-0410'",
            "INSERT INTO economic_observation SELECT dataset_id,school_id,2024,definition_id,name,enrollment,low_income,percentage,source_label,raw_json,source_id,source_order FROM economic_observation WHERE dataset_id='md-montgomery-2025' AND school_id='15-0051'",
            "INSERT INTO model_run SELECT id||':ghost',dataset_id,definition_id,subject,method_version,input_sha256,summary_json FROM model_run WHERE dataset_id='md-montgomery-2025' AND subject='math'",
            "INSERT INTO economic_definition SELECT id||':ghost',name,definition,source_url FROM economic_definition WHERE id='md-montgomery-2025:income'",
            "INSERT INTO assessment_definition SELECT id||':ghost',state,name,year,level,grades,standard,source_url FROM assessment_definition WHERE id LIKE 'md-montgomery-2025:%'",
            "INSERT INTO model_result VALUES ('other-model','md-montgomery-2025','15-0410',91,90,1,NULL,NULL)",
            "INSERT INTO source SELECT id||':ghost','other-md',path,url,sha256,imported_at FROM source WHERE id='md-montgomery-2025:extract'",
            "INSERT INTO model_run SELECT id||':ghost','other-md',definition_id,subject,method_version,input_sha256,summary_json FROM model_run WHERE dataset_id='md-montgomery-2025' AND subject='math'",
            "UPDATE school SET source_id='md-montgomery-2025:extract' WHERE dataset_id='other-md'",
            "UPDATE economic_observation SET definition_id='md-montgomery-2025:income' WHERE dataset_id='other-md'",
            "UPDATE economic_observation SET source_id='md-montgomery-2025:extract' WHERE dataset_id='other-md'",
            "UPDATE assessment_observation SET definition_id=(SELECT id FROM assessment_definition WHERE id LIKE 'md-montgomery-2025:%') WHERE dataset_id='other-md'",
            "UPDATE assessment_observation SET source_id='md-montgomery-2025:extract' WHERE dataset_id='other-md'",
        ]
        with tempfile.TemporaryDirectory(prefix='corrupt-db-', dir=WORK) as folder:
            wrong = Path(folder) / 'wrong.sqlite'
            for sql in corruptions:
                with closing(connect(self.database)) as source, closing(connect(wrong)) as db:
                    source.backup(db); db.execute(sql); db.commit()
                with self.subTest(sql=sql), self.assertRaises(ValueError):
                    district.validate_canonical(self.payload, wrong, self.numerical)

    def test_static_ghosts_counts_income_promotion_and_nonfinite_metrics_rejected(self):
        originals = {p.name: p.read_bytes() for p in self.output.glob('*.json')}
        with tempfile.TemporaryDirectory(prefix='corrupt-export-', dir=WORK) as folder:
            folder = Path(folder); descriptor = json.loads(originals['catalog.json'])
            descriptor['regions'][0].update(schools=str((folder / 'schools.json').relative_to(ROOT)),
                audit=str((folder / 'coverage.json').relative_to(ROOT)))
            originals['catalog.json'] = json.dumps(descriptor).encode()
            for filename, mutate in [
                ('schools.json', lambda d: d['models'].update(HS=d['models']['ES'])),
                ('schools.json', lambda d: d['models']['ES']['math'].update(n=166.)),
                ('schools.json', lambda d: d['models']['ES']['math'].update(slope=float('nan'))),
                ('schools.json', lambda d: d['schools'].append(copy.deepcopy(d['schools'][0]))),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(studentized=99.)),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(tested=False)),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(low=0.)),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(cohort_n=166.)),
                ('schools.json', lambda d: d['schools'][0].update(latitude=0.)),
                ('schools.json', lambda d: d['schools'][0].update(hidden_model={})),
                ('schools.json', lambda d: d.update(hidden_history=[])),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id'] == '15-0410')['metrics'].update(math=d['schools'][0]['metrics']['math'])),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id'] == '15-0410')['exclusions'].clear()),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id'] == '15-0557')['metrics'].update(math=d['schools'][0]['metrics']['math'])),
                ('history.json', lambda d: d['models'][0].update(intercept=-99.)),
                ('history.json', lambda d: d['records'][0].update(income_year=2024)),
                ('history.json', lambda d: d['records'][0]['subjects'].update(extra={})),
                ('history.json', lambda d: d['records'][0].update(raw_count_proxy=100)),
                ('history.json', lambda d: d.update(ghost_records=[])),
                ('coverage.json', lambda d: d['cohorts']['grade']['eligible'].update(combined=172)),
                ('coverage.json', lambda d: d['source_audit']['subject_coverage']['math']['excluded_configuration_records'].clear()),
                ('catalog.json', lambda d: d['regions'][0].update(name='Statewide', statewide=True)),
            ]:
                for name, content in originals.items(): (folder / name).write_bytes(content)
                changed = json.loads((folder / filename).read_text()); mutate(changed)
                (folder / filename).write_text(json.dumps(changed))
                with self.subTest(filename=filename, mutate=mutate), self.assertRaises(ValueError):
                    district.validate_exports(self.payload, folder, self.numerical)

    def test_offline_extract_repeatability_keeps_historical_pins_immutable(self):
        paths = [district.model_audit.ROSTER, district.model_audit.OUTPUT,
                 ROOT / 'scripts/audit_montgomery.py', ROOT / 'scripts/audit_montgomery_models.py',
                 ROOT / 'tests/test_montgomery_audit.py', ROOT / 'tests/test_montgomery_models.py']
        before = {p: p.read_bytes() for p in paths}
        with tempfile.TemporaryDirectory(prefix='extract-repeat-', dir=WORK) as folder:
            first, second = Path(folder) / 'one.json', Path(folder) / 'two.json'
            with mock.patch.object(district.roster_audit, 'extract_raw_inputs', side_effect=AssertionError('No original archive access')):
                district.extract(first); district.extract(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first.read_bytes(), district.EXTRACT.read_bytes())
        self.assertEqual(before, {p: p.read_bytes() for p in paths})
        self.assertEqual(hashlib.sha256(district.model_audit.ROSTER.read_bytes()).hexdigest(), district.model_audit.ROSTER_SHA)
        self.assertEqual(hashlib.sha256(district.model_audit.OUTPUT.read_bytes()).hexdigest(), district.NUMERICAL_SHA)


if __name__ == '__main__':
    unittest.main()
