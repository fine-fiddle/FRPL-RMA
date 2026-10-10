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
import prepare_houston as houston
import prepare_texas as texas

TABLES = ['dataset', 'source', 'assessment_definition', 'economic_definition', 'school',
          'economic_observation', 'assessment_observation', 'model_run', 'model_result']
MISSING_OUTCOMES = {'482364008608', '482364012655'}


def rows(db):
    return {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')]
            for table in TABLES}


def prior_rows(db):
    return {table: [r for r in records if not any(isinstance(v, str) and
            (v == houston.DATASET or v.startswith(houston.DATASET + ':')) for v in r)]
            for table, records in rows(db).items()}


def seed_other(db):
    """Same state and NCES identity with independent data across every table."""
    db.execute("INSERT INTO dataset VALUES ('other-tx','TX','Keep release','Keep population','ready')")
    db.execute("INSERT INTO source VALUES ('other-source','other-tx','other.json','https://example.test/source',?,'2025-01-01')", ('1' * 64,))
    db.execute("INSERT INTO assessment_definition VALUES ('other-assessment','TX','Other test',2025,'ES','3','Keep standard','https://example.test/assessment')")
    db.execute("INSERT INTO economic_definition VALUES ('other-income','Keep income','Keep definition','https://example.test/income')")
    db.execute("INSERT INTO school VALUES ('other-tx','482364001271','Keep school','other-district','Keep district',NULL,NULL,'{}','other-source',1)")
    db.execute("INSERT INTO economic_observation VALUES ('other-tx','482364001271',2025,'other-income','Keep school',100,30,30,'Keep income','{}','other-source',1)")
    db.execute("INSERT INTO assessment_observation VALUES ('other-tx','482364001271','other-assessment','math',40,100,'reported','{}','100','other-source',1)")
    db.execute("INSERT INTO model_run VALUES ('other-model','other-tx','other-assessment','math','keep-method',?,'{}')", ('2' * 64,))
    db.execute("INSERT INTO model_result VALUES ('other-model','other-tx','482364001271',40,45,-1,-2,0)")


class HoustonIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.numerical = houston.load_inputs()
        cls.payload = json.loads(houston.EXTRACT.read_text())
        cls.expected = houston.build_snapshot(cls.roster, cls.numerical)
        cls.links = {r['school_id']: r for r in cls.roster['roster_links']}
        cls.students = {r['raw']['CAMPUS']: r for r in cls.roster['raw_inputs']['stud']['records']}
        cls.assessments = {r['raw']['CAMPUS']: r for r in cls.roster['raw_inputs']['assessment']['records']}
        cls.sandbox = tempfile.TemporaryDirectory(prefix='houston-test-', dir=ROOT / 'data/build')
        cls.output = Path(cls.sandbox.name) / 'output'
        cls.database = Path(cls.sandbox.name) / 'schools.sqlite'
        with closing(connect(cls.database)) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text()); seed_other(db); db.commit()
        houston.prepare(cls.database, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    def test_exact_separate_grade_school_population_and_historical_false_approvals(self):
        houston.validate(self.payload, self.expected)
        self.assertEqual(self.payload['dataset'], 'tx-houston-2025')
        self.assertEqual(self.payload['state'], {'id': 'TX', 'name': 'Texas'})
        self.assertEqual((self.payload['region'], self.payload['release_status'], self.payload['statewide']), ('houston', 'ready', False))
        selected = {r['id'] for r in self.payload['schools']}
        self.assertEqual(len(selected), 212)
        self.assertEqual({r['identity_raw']['native_school_id'] for r in self.payload['schools']},
                         set(self.numerical['frozen_population']['native_grade_school_configuration_ids']))
        excluded = self.payload['source_audit']['excluded_operational_roster_records']
        self.assertEqual(len(excluded), 62)
        self.assertFalse(selected.intersection(r['school_id'] for r in excluded))
        self.assertEqual(selected | {r['school_id'] for r in excluded}, set(self.links))
        rogers = next(r for r in excluded if r['native_school_id'] == '101912039')
        self.assertEqual(rogers['native_enrolled']['high_enrollment'], 31)
        self.assertEqual(rogers['native_enrolled']['scope'], 'mixed')
        for audit in [self.roster, self.numerical]:
            self.assertIs(audit['approved_for_source'], False)
            self.assertIs(audit['approved_for_modeling'], False)
        selection = dict(self.payload['selection']); digest = selection.pop('sha256')
        self.assertEqual(digest, houston.roster_audit.fingerprint(selection))
        self.assertEqual(self.payload['cohorts'][0]['assessment'], houston.model_audit.ASSESSMENT)
        self.assertEqual(self.payload['cohorts'][0]['standard'], houston.model_audit.STANDARD)
        self.assertIs(self.payload['cohorts'][0]['allow_point_only'], True)
        self.assertEqual(self.payload['source_audit']['count_definition_hold'], houston.model_audit.COUNT_HOLD)

    def test_every_raw_identity_income_native_rate_and_outside_record_retained(self):
        evidence = self.payload['source_audit']
        self.assertEqual(houston.roster_audit.fingerprint(evidence['retained_raw_inputs']), houston.roster_audit.RAW_INPUT_SHA)
        self.assertEqual(evidence['native_source_definition_evidence'], self.roster['raw_inputs']['definitions'])
        self.assertEqual(evidence['enrollment_reconciliation'], self.roster['enrollment_reconciliation'])
        self.assertEqual(evidence['planning_identity_reconciliation'], self.roster['planning_identity_reconciliation'])
        self.assertEqual(evidence['historical_state_consistency'], self.roster['historical_state_consistency'])
        self.assertEqual(len(evidence['excluded_native_configuration_records']), 2)
        self.assertEqual(len(evidence['outside_native_configuration_records']), 62)
        differences = dict(math=0, reading=0)
        for school in self.payload['schools']:
            link = self.links[school['id']]; native = school['identity_raw']['native_school_id']
            student, assessment = self.students[native], self.assessments[native]
            self.assertEqual(school['identity_raw']['native_student'], student)
            self.assertEqual(school['identity_raw']['native_assessment'], assessment)
            self.assertEqual(school['income_raw']['original_student_record'], student)
            self.assertEqual(school['income'], houston.roster_audit.income_evidence(student['raw'])['percentage'])
            self.assertEqual(school['enrollment'], link['income']['enrollment'])
            self.assertEqual(school['low_income'], link['income']['economic_disadvantage'])
            self.assertEqual(school['income_row'], student['source_row'])
            for subject in ['math', 'reading']:
                value = school['outcomes'][subject]
                expected = houston.model_audit.published_rate_evidence(assessment['raw'], subject)
                self.assertEqual(value['proficiency'], expected['published_rate'])
                self.assertEqual(value['raw']['published_rate_evidence'], expected)
                self.assertEqual(value['raw']['original_assessment_record'], assessment)
                self.assertEqual(value['raw']['unverified_reported_subject_evidence'], link['subjects'][subject])
                self.assertTrue(all(value[k] is None for k in ['tested', 'valid_score_evidence', 'raw_tested']))
                self.assertIsNone(value['raw']['sampling_variance'])
                self.assertIsNone(value['raw']['valid_score_count'])
                if school['id'] not in MISSING_OUTCOMES:
                    differences[subject] += value['proficiency'] != link['subjects'][subject]['proficiency']
        self.assertEqual(differences, dict(math=202, reading=203))

    def test_missing_masked_displays_preserved_and_not_reconstructed(self):
        masked = {s['id']: s for s in self.payload['schools'] if s['id'] in MISSING_OUTCOMES}
        self.assertEqual(set(masked), MISSING_OUTCOMES)
        for key, school in masked.items():
            self.assertIsNotNone(school['income'])
            for subject in ['math', 'reading']:
                value = school['outcomes'][subject]
                self.assertIsNone(value['proficiency'])
                self.assertEqual(value['raw']['published_rate_evidence']['raw_published_rate'],
                                 '' if key == '482364008608' else '-1')
                self.assertIn('missing or masked', value['exclusion'])
        raw = copy.deepcopy(self.assessments['101912068']['raw'])
        raw[houston.roster_audit.FIELDS['math'][2]] = '0'
        self.assertEqual(houston.model_audit.published_rate_evidence(raw, 'math')['published_rate'], 0)
        raw[houston.roster_audit.FIELDS['math'][2]] = '*'
        self.assertIsNone(houston.model_audit.published_rate_evidence(raw, 'math')['published_rate'])

    def test_repeat_import_preserves_same_state_same_identity_all_tables(self):
        with closing(connect(':memory:')) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text()); seed_other(db)
            before = prior_rows(db)
            import_snapshot(db, self.payload, houston.EXTRACT); first = rows(db)
            import_snapshot(db, self.payload, houston.EXTRACT)
            self.assertEqual(first, rows(db)); self.assertEqual(before, prior_rows(db))
            self.assertEqual({t: len(rows(db)[t]) - len(before[t]) for t in TABLES},
                dict(dataset=1, source=18, assessment_definition=1, economic_definition=1,
                     school=212, economic_observation=212, assessment_observation=424, model_run=0, model_result=0))
            self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=? AND status="reported"', (houston.DATASET,)).fetchone()[0], 420)
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_prepare_twice_preserves_native_texas_and_fails_before_bad_source_mutation(self):
        with tempfile.TemporaryDirectory(prefix='houston-repeat-', dir=ROOT / 'data/build') as folder:
            folder = Path(folder); database = folder / 'schools.sqlite'; output = folder / 'output'
            with closing(connect(database)) as db:
                db.executescript((ROOT / 'scripts/schema.sql').read_text()); seed_other(db)
                import_snapshot(db, texas.normalize(houston.roster_audit.load_texas()), ROOT / 'data/source/texas.json')
                db.commit(); before = prior_rows(db)
            houston.prepare(database, output)
            first_files = {p.name: p.read_bytes() for p in output.glob('*.json')}
            with closing(connect(database)) as db: first = rows(db)
            houston.prepare(database, output)
            self.assertEqual(first_files, {p.name: p.read_bytes() for p in output.glob('*.json')})
            with closing(connect(database)) as db:
                self.assertEqual(first, rows(db)); self.assertEqual(before, prior_rows(db))
            bad = copy.deepcopy(self.payload)
            bad['schools'][0]['outcomes']['math'].update(tested=100, valid_score_evidence='Enrollment')
            wrong = folder / 'wrong.json'; wrong.write_text(json.dumps(bad))
            with self.assertRaises(ValueError): houston.prepare(database, output, wrong)
            with closing(connect(database)) as db: self.assertEqual(first, rows(db))
            self.assertEqual(first_files, {p.name: p.read_bytes() for p in output.glob('*.json')})

    def test_canonical_current_history_every_metric_matches_frozen_fits(self):
        self.assertEqual(houston.validate_canonical(self.payload, self.database, self.numerical),
                         dict(schools=212, observations=424, models=3, results=630))
        self.assertEqual(houston.validate_exports(self.payload, self.output, self.numerical),
                         {f'houston-published-2025-ES-{s}': 210 for s in houston.model_audit.SUBJECTS})
        schools = json.loads((self.output / 'schools.json').read_text())
        for school in schools['schools']:
            if school['id'] in MISSING_OUTCOMES:
                self.assertEqual(school['metrics'], {})
                self.assertEqual(set(school['exclusions']), {'math', 'reading', 'combined'})
                self.assertEqual(school['history'][0]['subjects'], {})
            else:
                self.assertEqual(set(school['metrics']), {'math', 'reading', 'combined'})
                self.assertEqual(school['exclusions'], {})
                self.assertEqual(school['metrics']['combined']['actual'],
                    (school['metrics']['math']['actual'] + school['metrics']['reading']['actual']) / 2)
                self.assertTrue(all(v['tested'] is None and v['low'] is None and v['high'] is None and
                                    'variance' not in v for v in school['metrics'].values()))

    def test_canonical_ghosts_foreign_references_count_proxies_and_rate_drift_rejected(self):
        namespace = houston.DATASET
        corruptions = [
            f"UPDATE model_result SET studentized=99 WHERE dataset_id='{namespace}'",
            f"UPDATE assessment_observation SET tested=836 WHERE dataset_id='{namespace}'",
            f"UPDATE assessment_observation SET proficiency=36.68478260869565 WHERE dataset_id='{namespace}' AND school_id='482364001271' AND subject='math'",
            f"UPDATE economic_observation SET percentage=percentage+1e-12 WHERE dataset_id='{namespace}' AND school_id='482364001271'",
            f"UPDATE school SET name='Wrong school' WHERE dataset_id='{namespace}'",
            f"UPDATE assessment_observation SET raw_value='{{}}' WHERE dataset_id='{namespace}'",
            f"INSERT INTO model_run SELECT id||':ghost',dataset_id,definition_id,subject,method_version,input_sha256,summary_json FROM model_run WHERE dataset_id='{namespace}' AND subject='math'",
            f"INSERT INTO economic_definition SELECT id||':ghost',name,definition,source_url FROM economic_definition WHERE id='{namespace}:income'",
            f"INSERT INTO model_result VALUES ('other-model','{namespace}','482364008608',40,45,-1,NULL,NULL)",
            f"INSERT INTO source SELECT id||':ghost','other-tx',path,url,sha256,imported_at FROM source WHERE id='{namespace}:extract'",
            f"INSERT INTO model_run SELECT 'foreign-model','other-tx',definition_id,subject,method_version,input_sha256,summary_json FROM model_run WHERE dataset_id='{namespace}' AND subject='math'",
            f"UPDATE school SET source_id='{namespace}:extract' WHERE dataset_id='other-tx'",
            f"UPDATE economic_observation SET definition_id='{namespace}:income' WHERE dataset_id='other-tx'",
            f"UPDATE economic_observation SET source_id='{namespace}:extract' WHERE dataset_id='other-tx'",
            f"UPDATE assessment_observation SET definition_id=(SELECT id FROM assessment_definition WHERE id LIKE '{namespace}:%') WHERE dataset_id='other-tx'",
            f"UPDATE assessment_observation SET source_id='{namespace}:extract' WHERE dataset_id='other-tx'",
        ]
        with tempfile.TemporaryDirectory(prefix='houston-corrupt-db-', dir=ROOT / 'data/build') as folder:
            wrong = Path(folder) / 'wrong.sqlite'
            for sql in corruptions:
                with closing(connect(self.database)) as source, closing(connect(wrong)) as db:
                    source.backup(db); db.execute(sql); db.commit()
                with self.subTest(sql=sql), self.assertRaises(ValueError):
                    houston.validate_canonical(self.payload, wrong, self.numerical)

    def test_strict_source_scope_floor_counts_and_published_precision_drift_rejected(self):
        mutations = [
            lambda d: d['schools'].pop(),
            lambda d: d['schools'][0].update(id='101912068'),
            lambda d: d['schools'][0]['identity_raw']['native_grade_evidence'].update(scope='mixed'),
            lambda d: d['schools'][0]['outcomes']['math']['raw'].update(sampling_variance=0.),
            lambda d: d['schools'][0]['outcomes']['math'].update(proficiency=36.68478260869565),
            lambda d: d['schools'][0]['outcomes']['math'].update(tested=836, valid_score_evidence='CCD enrollment'),
            lambda d: next(s for s in d['schools'] if s['id'] == '482364008608')['outcomes']['math'].update(proficiency=0.),
            lambda d: d['schools'][0]['income_raw']['original_student_record']['raw'].update(CPNTECOC='0'),
            lambda d: d['cohorts'][0].update(allow_point_only=False),
            lambda d: d['cohorts'][0].update(assessment='Count-ratio STAAR'),
            lambda d: d['source_audit']['excluded_native_configuration_records'].clear(),
            lambda d: d['source_audit']['excluded_operational_roster_records'].clear(),
            lambda d: d['source_audit']['retained_raw_inputs']['stud']['records'][0]['raw'].update(CPNTALLC='0'),
            lambda d: d['source_audit']['release_basis'].update(historical_audits_approved_for_modeling=0),
            lambda d: d['source_audit']['release_basis'].update(ten_valid_scored_floor_certified=True),
            lambda d: d['source_audit']['count_definition_hold'].update(status='resolved'),
            lambda d: d['sources']['numerical_audit'].update(sha256='0' * 64),
            lambda d: d['selection']['directory_school_ids'].pop(),
            lambda d: d.update(statewide=0),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.payload); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): houston.validate(changed, self.expected)
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / 'wrong.json'; wrong.write_text('{}')
            with mock.patch.object(houston.model_audit, 'OUTPUT', wrong), self.assertRaisesRegex(ValueError, 'fingerprint'):
                houston.load_inputs()

    def test_static_extra_models_counts_intervals_geography_and_exclusions_rejected(self):
        originals = {p.name: p.read_bytes() for p in self.output.glob('*.json')}
        with tempfile.TemporaryDirectory(prefix='houston-corrupt-export-', dir=ROOT / 'data/build') as folder:
            folder = Path(folder); descriptor = json.loads(originals['catalog.json'])
            descriptor['regions'][0].update(schools=str((folder / 'schools.json').relative_to(ROOT)),
                audit=str((folder / 'coverage.json').relative_to(ROOT)))
            originals['catalog.json'] = json.dumps(descriptor).encode()
            for filename, mutate in [
                ('schools.json', lambda d: d['models'].update(HS=d['models']['ES'])),
                ('schools.json', lambda d: d['models']['ES']['math'].update(n=210.)),
                ('schools.json', lambda d: d['models']['ES']['math'].update(slope=float('nan'))),
                ('schools.json', lambda d: d['schools'].append(copy.deepcopy(d['schools'][0]))),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(studentized=99.)),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(tested=False)),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(low=0.)),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(cohort_n=210.)),
                ('schools.json', lambda d: d['schools'][0].update(latitude=0.)),
                ('schools.json', lambda d: d['schools'][0].update(hidden_model={})),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id'] == '482364008608')['metrics'].update(math=d['schools'][0]['metrics']['math'])),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id'] == '482364008608')['exclusions'].clear()),
                ('history.json', lambda d: d['models'][0].update(intercept=-99.)),
                ('history.json', lambda d: d['records'][0].update(income_year=2024)),
                ('history.json', lambda d: d['records'][0]['subjects'].update(extra={})),
                ('history.json', lambda d: d['records'][0].update(raw_count_proxy=100)),
                ('history.json', lambda d: d.update(ghost_records=[])),
                ('coverage.json', lambda d: d['cohorts']['grade']['eligible'].update(combined=212)),
                ('coverage.json', lambda d: d['source_audit']['excluded_native_configuration_records'].clear()),
                ('coverage.json', lambda d: d['source_audit']['count_definition_hold'].update(ten_valid_scored_floor_certified=True)),
                ('catalog.json', lambda d: d['regions'][0].update(name='Statewide', statewide=True)),
            ]:
                for name, content in originals.items(): (folder / name).write_bytes(content)
                changed = json.loads((folder / filename).read_text()); mutate(changed)
                (folder / filename).write_text(json.dumps(changed))
                with self.subTest(filename=filename, mutate=mutate), self.assertRaises(ValueError):
                    houston.validate_exports(self.payload, folder, self.numerical)

    def test_offline_extract_repeatability_and_exact_source_model_pins(self):
        with tempfile.TemporaryDirectory(prefix='houston-extract-repeat-', dir=ROOT / 'data/build') as folder:
            first, second = Path(folder) / 'one.json', Path(folder) / 'two.json'
            with mock.patch.object(houston.roster_audit, 'extract_raw_inputs', side_effect=AssertionError('No raw reads')):
                houston.extract(first); houston.extract(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first.read_bytes(), houston.EXTRACT.read_bytes())
        self.assertEqual(hashlib.sha256(houston.model_audit.ROSTER.read_bytes()).hexdigest(), houston.model_audit.ROSTER_SHA)
        self.assertEqual(hashlib.sha256(houston.model_audit.OUTPUT.read_bytes()).hexdigest(), houston.NUMERICAL_SHA)


if __name__ == '__main__':
    unittest.main()
