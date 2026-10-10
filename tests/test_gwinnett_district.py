import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from database import connect
from state_snapshot import import_snapshot
import prepare_gwinnett as gwinnett

TABLES = ['dataset', 'source', 'school', 'economic_observation', 'assessment_definition',
          'economic_definition', 'assessment_observation', 'model_run', 'model_result']


def seed_other(db):
    """Same-state release with the same NCES school identity in all nine tables."""
    db.execute("INSERT INTO dataset VALUES ('other-ga','GA','Keep release','Keep population','ready')")
    db.execute("INSERT INTO source VALUES ('other-source','other-ga','other.json','https://example.test/source',?,'2025-01-01')", ('1' * 64,))
    db.execute("INSERT INTO assessment_definition VALUES ('other-assessment','GA','Other test',2025,'ES','3','Keep standard','https://example.test/assessment')")
    db.execute("INSERT INTO economic_definition VALUES ('other-income','Keep income','Keep definition','https://example.test/income')")
    db.execute("INSERT INTO school VALUES ('other-ga','130255003991','Keep school','other-district','Keep district',NULL,NULL,'{}','other-source',1)")
    db.execute("INSERT INTO economic_observation VALUES ('other-ga','130255003991',2025,'other-income','Keep school',100,30,30,'Keep income','{}','other-source',1)")
    db.execute("INSERT INTO assessment_observation VALUES ('other-ga','130255003991','other-assessment','math',40,100,'reported','{}','100','other-source',1)")
    db.execute("INSERT INTO model_run VALUES ('other-model','other-ga','other-assessment','math','keep-method',?,'{}')", ('2' * 64,))
    db.execute("INSERT INTO model_result VALUES ('other-model','other-ga','130255003991',40,45,-1,-2,0)")


def rows(db):
    return {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in TABLES}


def prior_rows(db):
    return {table: [r for r in records if not any(isinstance(v, str) and
            (v == gwinnett.DATASET or v.startswith(gwinnett.DATASET + ':')) for v in r)]
            for table, records in rows(db).items()}


class GwinnettIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.numerical = gwinnett.load_inputs()
        cls.payload = json.loads(gwinnett.EXTRACT.read_text())
        cls.expected = gwinnett.build_snapshot(cls.roster, cls.numerical)
        cls.native = {r['school_id']: r for r in cls.roster['roster_links']}
        cls.sandbox = tempfile.TemporaryDirectory(prefix='gwinnett-test-', dir=ROOT / 'data/build')
        cls.output = Path(cls.sandbox.name) / 'output'
        cls.database = Path(cls.sandbox.name) / 'schools.sqlite'
        with closing(connect(cls.database)) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text()); db.commit()
        gwinnett.prepare(cls.database, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    def test_exact_selection_namespace_and_scope_only_standard_wording(self):
        gwinnett.validate(self.payload, self.expected)
        self.assertEqual(self.payload['dataset'], 'ga-gwinnett-2025')
        self.assertEqual(self.payload['state'], {'id': 'GA', 'name': 'Georgia'})
        self.assertEqual((self.payload['region'], self.payload['region_name'], self.payload['release_status']), ('gwinnett', 'Gwinnett County', 'ready'))
        self.assertIs(self.payload['statewide'], False)
        self.assertEqual(len(self.payload['schools']), 111)
        native = gwinnett.roster_audit.load_georgia()['cohorts']
        self.assertEqual(self.payload['source_audit']['native_assessment_cohorts'], native)
        adjusted = copy.deepcopy(native); adjusted[0]['standard'] = gwinnett.model_audit.STANDARD
        self.assertEqual(self.payload['cohorts'], adjusted)
        self.assertTrue(self.payload['cohorts'][0]['allow_point_only'])
        self.assertEqual(native[0]['standard'].replace('separate state model', 'separate district model'), adjusted[0]['standard'])
        self.assertEqual(self.payload['income_definition'], gwinnett.roster_audit.load_georgia()['income_definition'])
        selected = {s['id'] for s in self.payload['schools']}
        self.assertEqual(selected, set(self.numerical['frozen_population']['native_source_profile_ids']))
        self.assertIn('130255003991', selected)
        self.assertFalse(selected.intersection(self.numerical['frozen_population']['mixed_offers_with_native_g38_ids']))
        selection = dict(self.payload['selection']); digest = selection.pop('sha256')
        self.assertEqual(digest, gwinnett.roster_audit.fingerprint(selection))
        self.assertEqual(selection['policy'], gwinnett.model_audit.POLICY)
        self.assertTrue(all(s['cohort'] == 'grade' and s['district_id'] == '1302550' for s in self.payload['schools']))
        for audit in [self.roster, self.numerical]:
            self.assertIs(audit['approved_for_source'], False); self.assertIs(audit['approved_for_modeling'], False)

    def test_every_original_source_row_and_income_outcome_metadata_retained(self):
        raw = self.roster['raw_inputs']; evidence = self.payload['source_audit']
        self.assertEqual(gwinnett.roster_audit.fingerprint(evidence['retained_raw_inputs']), gwinnett.roster_audit.RAW_INPUT_SHA)
        self.assertEqual([len(evidence['retained_raw_inputs'][s]['records']) for s in ['directory','membership','lunch','assessment']], [141,1099,705,942])
        self.assertEqual(evidence['state_definition_evidence'], self.roster['state_definition_evidence'])
        self.assertEqual(evidence['later_release_note_roster_gaps'], ['130255002906'])
        self.assertEqual(evidence['planning_identity_reconciliation'], self.roster['planning_identity_reconciliation'])
        excluded = {s['school_id']: s for s in evidence['excluded_operational_roster_records']}
        self.assertEqual(len(excluded), 30)
        self.assertEqual(excluded['130255004683']['subjects']['math']['native_rate'], 0.)
        self.assertEqual(excluded['130255004683']['subjects']['math']['raw_tested'], '*')
        self.assertEqual(evidence['excluded_native_configuration_records'], [])
        lunch = {r['source_row']: r['raw'] for r in raw['lunch']['records']}
        assessment = {r['source_row']: r['raw'] for r in raw['assessment']['records']}
        for school in self.payload['schools']:
            source = self.native[school['id']]
            self.assertEqual(school['income_raw']['direct_certification'], lunch[school['income_row']])
            self.assertEqual(school['income'], 100 * source['income']['reported_direct_certification'] / source['income']['reported_membership'])
            self.assertEqual(school['identity_raw']['edc_metadata'], source['edc_metadata'])
            self.assertEqual(school['identity_raw']['offered_evidence'], source['offered'])
            self.assertEqual(source['offered']['ungraded_offered'], 'No')
            self.assertTrue(source['offered']['strict_pure_offered_lower'])
            for subject in ['math','reading']:
                value, original = school['outcomes'][subject], source['subjects'][subject]
                self.assertEqual(value['raw']['assessment_raw'], assessment[value['source_row']])
                self.assertEqual(value['proficiency'], original['native_rate'])
                self.assertEqual(value['raw']['raw_tested_unverified'], original['raw_tested'])
                self.assertIsNone(value['exclusion'])
                self.assertTrue(all(value[k] is None for k in ['tested','valid_score_evidence','raw_tested']))
                self.assertIsNone(value['raw']['valid_score_count']); self.assertIsNone(value['raw']['sampling_variance'])
        self.assertEqual(hashlib.sha256(gwinnett.model_audit.ROSTER.read_bytes()).hexdigest(), gwinnett.model_audit.ROSTER_SHA)
        self.assertEqual(hashlib.sha256(gwinnett.model_audit.OUTPUT.read_bytes()).hexdigest(), gwinnett.NUMERICAL_SHA)

    def test_import_twice_preserves_other_same_state_native_id_and_definitions(self):
        with closing(connect(':memory:')) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text()); seed_other(db)
            before = prior_rows(db)
            import_snapshot(db, self.payload, gwinnett.EXTRACT); first = rows(db)
            import_snapshot(db, self.payload, gwinnett.EXTRACT)
            self.assertEqual(first, rows(db)); self.assertEqual(before, prior_rows(db))
            self.assertEqual(db.execute('SELECT count(*) FROM school WHERE dataset_id=?',(gwinnett.DATASET,)).fetchone()[0],111)
            self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=?',(gwinnett.DATASET,)).fetchone()[0],222)
            self.assertTrue(all(r['tested'] is None for r in db.execute('SELECT tested FROM assessment_observation WHERE dataset_id=?',(gwinnett.DATASET,))))
            source_ids = [r['id'] for r in db.execute('SELECT id FROM source WHERE dataset_id=?',(gwinnett.DATASET,))]
            self.assertEqual(len(source_ids),12); self.assertTrue(all(k.startswith(gwinnett.DATASET+':') for k in source_ids))
            definition = dict(db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (gwinnett.DATASET+':%',)).fetchone())
            cohort = self.payload['cohorts'][0]
            self.assertEqual([definition[k] for k in ['state','name','year','level','grades','standard','source_url']],
                             ['GA',cohort['assessment'],2025,'ES',cohort['grades'],cohort['standard'],cohort['source_url']])
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_prepare_twice_preserves_actual_georgia_and_validation_precedes_mutation(self):
        with tempfile.TemporaryDirectory(prefix='gwinnett-repeat-',dir=ROOT/'data/build') as folder:
            folder=Path(folder); database=folder/'schools.sqlite'; output=folder/'output'
            with closing(connect(database)) as db:
                db.executescript((ROOT/'scripts/schema.sql').read_text()); seed_other(db)
                import_snapshot(db,gwinnett.roster_audit.load_georgia(),gwinnett.roster_audit.georgia.EXTRACT)
                db.commit(); preserved=prior_rows(db)
            gwinnett.prepare(database,output)
            first={p.name:p.read_bytes() for p in output.glob('*.json')}
            with closing(connect(database)) as db: first_rows=rows(db)
            gwinnett.prepare(database,output)
            self.assertEqual(first,{p.name:p.read_bytes() for p in output.glob('*.json')})
            with closing(connect(database)) as db:
                self.assertEqual(first_rows,rows(db)); self.assertEqual(preserved,prior_rows(db))
                self.assertEqual(db.execute('SELECT count(*) FROM model_result WHERE dataset_id=?',(gwinnett.DATASET,)).fetchone()[0],333)
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            changed=copy.deepcopy(self.payload); changed['schools'][0]['outcomes']['math']['tested']=100
            wrong=folder/'wrong.json'; wrong.write_text(json.dumps(changed))
            with self.assertRaises(ValueError): gwinnett.prepare(database,output,wrong)
            with closing(connect(database)) as db: self.assertEqual(first_rows,rows(db))

    def test_all_canonical_and_current_history_points_match_frozen_numerical_audit(self):
        self.assertEqual(gwinnett.validate_canonical(self.payload,self.database,self.numerical), {'schools':111,'observations':222,'models':3,'results':333})
        self.assertEqual(gwinnett.validate_exports(self.payload,self.output,self.numerical),{f'gwinnett-2025-ES-{s}':111 for s in gwinnett.model_audit.SUBJECTS})
        schools=json.loads((self.output/'schools.json').read_text())
        self.assertEqual(len(schools['schools']),111)
        self.assertTrue(all(set(s['metrics'])=={'math','reading','combined'} and s['exclusions']=={} for s in schools['schools']))
        self.assertTrue(all(v['tested'] is None and v['low'] is None and v['high'] is None and 'variance' not in v
                            for s in schools['schools'] for v in s['metrics'].values()))
        region=json.loads((self.output/'catalog.json').read_text())['regions'][0]
        self.assertEqual((region['id'],region['name'],region['dataset']),('gwinnett','Gwinnett County',gwinnett.DATASET))
        self.assertIs(region['statewide'],False); self.assertEqual(region['levels'],['ES']); self.assertIsNone(region['boundaries'])
        with tempfile.TemporaryDirectory(prefix='gwinnett-canonical-corruption-',dir=ROOT/'data/build') as folder:
            wrong=Path(folder)/'wrong.sqlite'
            for sql in [
                "UPDATE model_result SET studentized=99 WHERE dataset_id='ga-gwinnett-2025' AND school_id='130255003991'",
                "UPDATE assessment_observation SET tested=100 WHERE dataset_id='ga-gwinnett-2025' AND school_id='130255003991'",
                "UPDATE economic_observation SET percentage=percentage+1e-12 WHERE dataset_id='ga-gwinnett-2025' AND school_id='130255003991'",
                "UPDATE school SET name='Wrong school' WHERE dataset_id='ga-gwinnett-2025' AND school_id='130255003991'",
                "INSERT INTO economic_observation SELECT dataset_id,school_id,2024,definition_id,name,enrollment,low_income,percentage,source_label,raw_json,source_id,source_order FROM economic_observation WHERE dataset_id='ga-gwinnett-2025' AND school_id='130255003991'",
                "INSERT INTO model_run SELECT id||':ghost',dataset_id,definition_id,subject,method_version,input_sha256,summary_json FROM model_run WHERE dataset_id='ga-gwinnett-2025' AND subject='math'",
            ]:
                with closing(connect(self.database)) as source, closing(connect(wrong)) as db:
                    source.backup(db); db.execute(sql); db.commit()
                with self.subTest(sql=sql),self.assertRaises(ValueError): gwinnett.validate_canonical(self.payload,wrong,self.numerical)

    def test_strict_normalized_source_population_count_note_and_type_drift_fails(self):
        mutations=[
            lambda d:d['schools'].pop(), lambda d:d['schools'][0].update(id='130255004683'),
            lambda d:d['schools'][0]['identity_raw']['enrolled_evidence'].update(native_grade_school_contract=1),
            lambda d:d['schools'][0]['income_raw']['direct_certification'].update(STUDENT_COUNT=False),
            lambda d:d['schools'][0]['outcomes']['math'].update(tested=10,valid_score_evidence='Invented'),
            lambda d:d['schools'][0]['outcomes']['math']['raw'].update(sampling_variance=0.),
            lambda d:d['cohorts'][0].update(allow_point_only=False),
            lambda d:d['cohorts'][0].update(standard='High-school standard'),
            lambda d:d['sources']['numerical_audit'].update(sha256='0'*64),
            lambda d:d['selection']['directory_school_ids'].pop(), lambda d:d.update(statewide=0),
            lambda d:d['source_audit']['release_basis'].update(exact_source_roster_replayed=1),
            lambda d:d['source_audit']['later_release_note_roster_gaps'].clear(),
            lambda d:d['source_audit']['retained_raw_inputs']['membership']['records'][0]['raw'].update(STUDENT_COUNT='0'),
            lambda d:d['source_audit']['state_definition_evidence']['georgia_rows_and_headers'][0]['rows'].pop(),
            lambda d:next(s for s in d['schools'] if s['id']=='130255003991')['identity_raw']['ccd_flags'].update(charter='No'),
        ]
        for mutate in mutations:
            changed=copy.deepcopy(self.payload); mutate(changed)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError): gwinnett.validate(changed,self.expected)
        with tempfile.TemporaryDirectory() as folder:
            wrong=Path(folder)/'wrong-audit.json'; wrong.write_text('{}')
            with mock.patch.object(gwinnett.model_audit,'OUTPUT',wrong),self.assertRaisesRegex(ValueError,'fingerprint'): gwinnett.load_inputs()

    def test_static_population_model_metric_history_coverage_and_type_corruptions_fail(self):
        originals={p.name:p.read_bytes() for p in self.output.glob('*.json')}
        with tempfile.TemporaryDirectory(prefix='gwinnett-export-corruption-',dir=ROOT/'data/build') as folder:
            folder=Path(folder); descriptor=json.loads(originals['catalog.json'])
            descriptor['regions'][0].update(schools=str((folder/'schools.json').relative_to(ROOT)),audit=str((folder/'coverage.json').relative_to(ROOT)))
            originals['catalog.json']=json.dumps(descriptor).encode()
            for filename,mutate in [
                ('history.json',lambda d:d['models'][0].update(slope=-99.)),
                ('schools.json',lambda d:d['history_models'].pop()),
                ('schools.json',lambda d:d['models'].update(HS=d['models']['ES'])),
                ('schools.json',lambda d:d['models']['ES']['math'].update(n=111.)),
                ('schools.json',lambda d:d['models']['ES']['math'].update(intercept=float('nan'))),
                ('schools.json',lambda d:d['schools'][0]['metrics'].update(HS={})),
                ('history.json',lambda d:d['records'][0]['subjects'].update(extra={})),
                ('schools.json',lambda d:d['schools'].append(copy.deepcopy(d['schools'][0]))),
                ('schools.json',lambda d:d['schools'][0]['metrics']['math'].update(studentized=99.)),
                ('schools.json',lambda d:d['schools'][0]['metrics']['math'].update(tested=False)),
                ('schools.json',lambda d:d['schools'][0]['metrics']['math'].update(low=0.)),
                ('schools.json',lambda d:d['schools'][0]['metrics']['math'].update(cohort_n=111.)),
                ('schools.json',lambda d:d['schools'][0]['metrics']['math'].update(predicted=float('inf'))),
                ('schools.json',lambda d:d['schools'][0].update(latitude=0.)),
                ('schools.json',lambda d:d['schools'][0].update(name='Different school')),
                ('history.json',lambda d:d['records'][0].update(income_year=2024)),
                ('catalog.json',lambda d:d['regions'][0].update(name='Statewide',statewide=True)),
                ('coverage.json',lambda d:d['cohorts']['grade']['eligible'].update(combined=112)),
                ('coverage.json',lambda d:d['source_audit']['release_basis'].update(historical_audits_approved_for_modeling=0)),
            ]:
                for name,content in originals.items(): (folder/name).write_bytes(content)
                changed=json.loads((folder/filename).read_text()); mutate(changed); (folder/filename).write_text(json.dumps(changed))
                with self.subTest(filename=filename,mutate=mutate),self.assertRaises(ValueError): gwinnett.validate_exports(self.payload,folder,self.numerical)

    def test_offline_extract_repeatability_and_native_source_pins_unchanged(self):
        with tempfile.TemporaryDirectory(prefix='gwinnett-extract-repeat-',dir=ROOT/'data/build') as folder:
            first,second=Path(folder)/'one.json',Path(folder)/'two.json'
            with mock.patch.object(gwinnett.roster_audit.zipfile,'ZipFile',side_effect=AssertionError('No raw ZIP')), \
                    mock.patch.object(gwinnett.roster_audit.subprocess,'Popen',side_effect=AssertionError('No raw stream')):
                gwinnett.extract(first); gwinnett.extract(second)
            self.assertEqual(first.read_bytes(),second.read_bytes()); self.assertEqual(first.read_bytes(),gwinnett.EXTRACT.read_bytes())
        self.assertEqual(hashlib.sha256(gwinnett.model_audit.ROSTER.read_bytes()).hexdigest(),gwinnett.model_audit.ROSTER_SHA)
        self.assertEqual(hashlib.sha256(gwinnett.model_audit.OUTPUT.read_bytes()).hexdigest(),gwinnett.NUMERICAL_SHA)


if __name__ == '__main__':
    unittest.main()
