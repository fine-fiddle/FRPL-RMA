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
import prepare_fairfax as fairfax

TABLES = ['dataset', 'source', 'assessment_definition', 'economic_definition', 'school',
          'economic_observation', 'assessment_observation', 'model_run', 'model_result']
MISSING_INCOME = {'0290110', '0290560', '0291590', '0290290', '0290390',
                  '0292209', '0291860', '0290140', '0291650', '0292030'}


def rows(db):
    return {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')]
            for table in TABLES}


def prior_rows(db):
    return {table: [r for r in records if not any(isinstance(v, str) and
            (v == fairfax.DATASET or v.startswith(fairfax.DATASET + ':')) for v in r)]
            for table, records in rows(db).items()}


def seed_other(db):
    """Same-state, same native identity, independent release across all nine tables."""
    db.execute("INSERT INTO dataset VALUES ('other-va','VA','Keep release','Keep population','ready')")
    db.execute("INSERT INTO source VALUES ('other-source','other-va','other.json','https://example.test/source',?,'2025-01-01')", ('1' * 64,))
    db.execute("INSERT INTO assessment_definition VALUES ('other-assessment','VA','Other test',2025,'ES','3','Keep standard','https://example.test/assessment')")
    db.execute("INSERT INTO economic_definition VALUES ('other-income','Keep income','Keep definition','https://example.test/income')")
    db.execute("INSERT INTO school VALUES ('other-va','0290033','Keep school','other-district','Keep district',NULL,NULL,'{}','other-source',1)")
    db.execute("INSERT INTO economic_observation VALUES ('other-va','0290033',2025,'other-income','Keep school',100,30,30,'Keep income','{}','other-source',1)")
    db.execute("INSERT INTO assessment_observation VALUES ('other-va','0290033','other-assessment','math',40,100,'reported','{}','100','other-source',1)")
    db.execute("INSERT INTO model_run VALUES ('other-model','other-va','other-assessment','math','keep-method',?,'{}')", ('2' * 64,))
    db.execute("INSERT INTO model_result VALUES ('other-model','other-va','0290033',40,45,-1,-2,0)")


class FairfaxIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.numerical = fairfax.load_inputs()
        cls.payload = json.loads(fairfax.EXTRACT.read_text())
        cls.expected = fairfax.build_snapshot(cls.roster, cls.numerical)
        cls.native = {r['school_id']: r for r in cls.roster['raw_inputs']['native_profiles']['records']}
        cls.links = {r['school_id']: r for r in cls.roster['roster_links']}
        cls.sandbox = tempfile.TemporaryDirectory(prefix='fairfax-test-', dir=ROOT / 'data/build')
        cls.output = Path(cls.sandbox.name) / 'output'
        cls.database = Path(cls.sandbox.name) / 'schools.sqlite'
        with closing(connect(cls.database)) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text()); seed_other(db); db.commit()
        fairfax.prepare(cls.database, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    def test_exact_grade_population_and_independent_definition(self):
        fairfax.validate(self.payload, self.expected)
        self.assertEqual(self.payload['dataset'], 'va-fairfax-2025')
        self.assertEqual(self.payload['state'], {'id': 'VA', 'name': 'Virginia'})
        self.assertEqual((self.payload['region'], self.payload['region_name'], self.payload['release_status']),
                         ('fairfax', 'Fairfax County', 'ready'))
        self.assertIs(self.payload['statewide'], False)
        selected = {r['id'] for r in self.payload['schools']}
        self.assertEqual(len(selected), 162)
        self.assertEqual(selected, set(self.numerical['frozen_population']['native_grade_school_configuration_ids']))
        self.assertFalse(selected.intersection(self.numerical['frozen_population']['native_high_school_ids']))
        self.assertFalse(selected.intersection(self.numerical['frozen_population']['native_mixed_school_ids']))
        self.assertFalse(selected.intersection(self.numerical['frozen_population']['native_unclassified_school_ids']))
        self.assertFalse(selected.intersection(self.numerical['frozen_population']['missing_native_school_ids']))
        cohort = self.payload['cohorts'][0]
        self.assertEqual(cohort['assessment'], 'SOL/VAAP 2025 standards · grade-school totals')
        self.assertEqual(cohort['standard'], fairfax.model_audit.STANDARD)
        self.assertTrue(cohort['allow_point_only'])
        native = self.payload['source_audit']['native_assessment_definition']
        self.assertEqual([cohort[k] for k in ['assessment', 'level', 'grades', 'source_url']],
                         [native[k] for k in ['name', 'level', 'grades', 'source_url']])
        self.assertIn('2023 mathematics and 2024 English standards', native['standard'])
        self.assertEqual(self.payload['income_definition']['definition'], fairfax.roster_audit.virginia.ECON_DEFINITION)
        for audit in [self.roster, self.numerical]:
            self.assertIs(audit['approved_for_source'], False)
            self.assertIs(audit['approved_for_modeling'], False)
        selection = dict(self.payload['selection']); digest = selection.pop('sha256')
        self.assertEqual(digest, fairfax.roster_audit.fingerprint(selection))
        self.assertEqual(len(self.payload['sources']), 202)

    def test_full_raw_sources_held_populations_and_missing_income_never_zero(self):
        evidence = self.payload['source_audit']
        self.assertEqual(fairfax.roster_audit.fingerprint(evidence['retained_raw_inputs']), fairfax.roster_audit.RAW_INPUT_SHA)
        self.assertEqual([len(evidence['retained_raw_inputs'][s]['records']) for s in
                          ['directory', 'membership', 'lunch', 'native_profiles']], [223, 1689, 965, 195])
        self.assertEqual(evidence['state_definition_evidence'], self.roster['state_definition_evidence'])
        self.assertEqual(evidence['planning_identity_reconciliation'], self.roster['planning_identity_reconciliation'])
        self.assertEqual(len(evidence['excluded_operational_roster_records']), 61)
        self.assertEqual(len(evidence['excluded_native_configuration_records']), 10)
        self.assertEqual(len(evidence['missing_native_profiles']), 28)
        lake = next(r for r in evidence['excluded_operational_roster_records'] if r['school_id'] == '0290090')
        self.assertEqual(lake['native_grade']['positive_unrecognized_grades'], ['Post Graduate'])
        self.assertIsNone(lake['native_grade']['native_band'])
        self.assertEqual({k for k, v in evidence['held_populations'].items() if v}, {'high', 'mixed', 'unclassified', 'missing_native'})
        unavailable = {s['id'] for s in self.payload['schools'] if s['income'] is None}
        self.assertEqual(unavailable, MISSING_INCOME)
        for school in self.payload['schools']:
            original = self.native[school['id']]
            raw = original['raw']
            self.assertEqual(school['name'], raw['name'])
            self.assertEqual(school['income_source'], original['source'])
            self.assertEqual(school['income_row'], original['source_row'])
            self.assertEqual(school['identity_raw']['native_profile'], original)
            self.assertEqual(school['income_raw']['enrollment_subgroups'], raw['enrollment_subgroups'])
            self.assertEqual(school['income_raw']['grade_table'], raw['grade_table'])
            self.assertEqual(school['income'], fairfax.roster_audit.virginia.income_values(raw)[2])
            if school['id'] in MISSING_INCOME:
                self.assertIsNone(school['low_income'])
                self.assertEqual(school['income_raw']['reconciled_income_evidence']['exclusion'],
                                 'At least one native same-year grade count is missing or suppressed')
            for subject in ['math', 'reading']:
                outcome = school['outcomes'][subject]
                self.assertEqual(outcome['proficiency'], fairfax.roster_audit.virginia.assessment_value(raw, subject))
                self.assertEqual(outcome['raw']['assessment_raw'], raw['assessments'][subject])
                self.assertTrue(all(outcome[k] is None for k in ['tested', 'valid_score_evidence', 'raw_tested']))
                self.assertIsNone(outcome['raw']['sampling_variance'])
                self.assertIsNone(outcome['raw']['valid_score_count'])

    def test_repeat_import_preserves_same_state_same_identity_all_nine_tables(self):
        with closing(connect(':memory:')) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text()); seed_other(db)
            before = prior_rows(db)
            import_snapshot(db, self.payload, fairfax.EXTRACT); first = rows(db)
            import_snapshot(db, self.payload, fairfax.EXTRACT)
            self.assertEqual(first, rows(db)); self.assertEqual(before, prior_rows(db))
            additions = {t: len(rows(db)[t]) - len(before[t]) for t in TABLES}
            self.assertEqual(additions, dict(dataset=1, source=203, assessment_definition=1,
                economic_definition=1, school=162, economic_observation=162,
                assessment_observation=324, model_run=0, model_result=0))
            self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=? AND status="reported"',
                                       (fairfax.DATASET,)).fetchone()[0], 324)
            self.assertEqual(db.execute('SELECT count(*) FROM economic_observation WHERE dataset_id=? AND percentage IS NULL',
                                       (fairfax.DATASET,)).fetchone()[0], 10)
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_prepare_twice_preserves_native_virginia_and_fails_before_source_mutation(self):
        with tempfile.TemporaryDirectory(prefix='fairfax-repeat-', dir=ROOT / 'data/build') as folder:
            folder = Path(folder); database = folder / 'schools.sqlite'; output = folder / 'output'
            with closing(connect(database)) as db:
                db.executescript((ROOT / 'scripts/schema.sql').read_text()); seed_other(db)
                fairfax.roster_audit.virginia.import_data(db, fairfax.roster_audit.load_virginia())
                db.commit(); before = prior_rows(db)
            fairfax.prepare(database, output)
            first_files = {p.name: p.read_bytes() for p in output.glob('*.json')}
            with closing(connect(database)) as db: first = rows(db)
            fairfax.prepare(database, output)
            self.assertEqual(first_files, {p.name: p.read_bytes() for p in output.glob('*.json')})
            with closing(connect(database)) as db:
                self.assertEqual(first, rows(db)); self.assertEqual(before, prior_rows(db))
            bad = copy.deepcopy(self.payload)
            bad['schools'][0]['outcomes']['math'].update(tested=100, valid_score_evidence='Enrollment')
            wrong = folder / 'wrong.json'; wrong.write_text(json.dumps(bad))
            with self.assertRaises(ValueError): fairfax.prepare(database, output, wrong)
            with closing(connect(database)) as db: self.assertEqual(first, rows(db))
            self.assertEqual(first_files, {p.name: p.read_bytes() for p in output.glob('*.json')})

    def test_all_canonical_current_history_metrics_match_frozen_district_fits(self):
        self.assertEqual(fairfax.validate_canonical(self.payload, self.database, self.numerical),
                         {'schools': 162, 'observations': 324, 'models': 3, 'results': 456})
        self.assertEqual(fairfax.validate_exports(self.payload, self.output, self.numerical),
                         {f'fairfax-2025-ES-{s}': 152 for s in fairfax.model_audit.SUBJECTS})
        schools = json.loads((self.output / 'schools.json').read_text())
        self.assertEqual(len(schools['schools']), 162)
        for school in schools['schools']:
            if school['id'] in MISSING_INCOME:
                self.assertEqual(school['metrics'], {})
                self.assertIsNone(school['income'])
                self.assertEqual(set(school['exclusions']), {'math', 'reading', 'combined'})
                self.assertEqual(school['history'][0]['subjects'], {})
            else:
                self.assertEqual(set(school['metrics']), {'math', 'reading', 'combined'})
                self.assertEqual(school['exclusions'], {})
                self.assertTrue(all(v['tested'] is None and v['low'] is None and v['high'] is None
                                    and 'variance' not in v for v in school['metrics'].values()))
        with closing(connect(self.database)) as db:
            self.assertEqual({t: len(rows(db)[t]) - 1 for t in TABLES}, dict(dataset=1, source=203,
                assessment_definition=1, economic_definition=1, school=162, economic_observation=162,
                assessment_observation=324, model_run=3, model_result=456))

    def test_canonical_ghosts_orphan_results_raw_drift_and_count_proxies_rejected(self):
        corruptions = [
            "UPDATE model_result SET studentized=99 WHERE dataset_id='va-fairfax-2025' AND school_id='0290033'",
            "UPDATE assessment_observation SET tested=545 WHERE dataset_id='va-fairfax-2025' AND school_id='0290110'",
            "UPDATE assessment_observation SET proficiency=NULL,status='suppressed_or_not_reported' WHERE dataset_id='va-fairfax-2025' AND school_id='0290110'",
            "UPDATE economic_observation SET percentage=0,low_income=0 WHERE dataset_id='va-fairfax-2025' AND school_id='0290110'",
            "UPDATE economic_observation SET percentage=percentage+1e-12 WHERE dataset_id='va-fairfax-2025' AND school_id='0290033'",
            "UPDATE school SET name='Wrong school' WHERE dataset_id='va-fairfax-2025' AND school_id='0290033'",
            "UPDATE assessment_observation SET raw_value='{}' WHERE dataset_id='va-fairfax-2025' AND school_id='0290110'",
            "INSERT INTO economic_observation SELECT dataset_id,school_id,2024,definition_id,name,enrollment,low_income,percentage,source_label,raw_json,source_id,source_order FROM economic_observation WHERE dataset_id='va-fairfax-2025' AND school_id='0290033'",
            "INSERT INTO model_run SELECT id||':ghost',dataset_id,definition_id,subject,method_version,input_sha256,summary_json FROM model_run WHERE dataset_id='va-fairfax-2025' AND subject='math'",
            "INSERT INTO economic_definition SELECT id||':ghost',name,definition,source_url FROM economic_definition WHERE id='va-fairfax-2025:income'",
            "INSERT INTO assessment_definition SELECT id||':ghost',state,name,year,level,grades,standard,source_url FROM assessment_definition WHERE id LIKE 'va-fairfax-2025:%'",
            "INSERT INTO model_result VALUES ('other-model','va-fairfax-2025','0290110',91,90,1,NULL,NULL)",
            "INSERT INTO source SELECT id||':ghost','other-va',path,url,sha256,imported_at FROM source WHERE id='va-fairfax-2025:extract'",
            "INSERT INTO model_run SELECT id||':ghost','other-va',definition_id,subject,method_version,input_sha256,summary_json FROM model_run WHERE dataset_id='va-fairfax-2025' AND subject='math'",
            "INSERT INTO model_run SELECT 'foreign-model','other-va',definition_id,subject,method_version,input_sha256,summary_json FROM model_run WHERE dataset_id='va-fairfax-2025' AND subject='math'",
            "UPDATE school SET source_id='va-fairfax-2025:extract' WHERE dataset_id='other-va'",
            "UPDATE economic_observation SET definition_id='va-fairfax-2025:income' WHERE dataset_id='other-va'",
            "UPDATE economic_observation SET source_id='va-fairfax-2025:extract' WHERE dataset_id='other-va'",
            "UPDATE assessment_observation SET definition_id=(SELECT id FROM assessment_definition WHERE id LIKE 'va-fairfax-2025:%') WHERE dataset_id='other-va'",
            "UPDATE assessment_observation SET source_id='va-fairfax-2025:extract' WHERE dataset_id='other-va'",
        ]
        with tempfile.TemporaryDirectory(prefix='fairfax-corrupt-db-', dir=ROOT / 'data/build') as folder:
            wrong = Path(folder) / 'wrong.sqlite'
            for sql in corruptions:
                with closing(connect(self.database)) as source, closing(connect(wrong)) as db:
                    source.backup(db); db.execute(sql); db.commit()
                with self.subTest(sql=sql), self.assertRaises(ValueError):
                    fairfax.validate_canonical(self.payload, wrong, self.numerical)

    def test_strict_normalized_source_exclusions_category_sums_and_metadata_drift_rejected(self):
        mutations = [
            lambda d: d['schools'].pop(),
            lambda d: d['schools'][0].update(id='0290090'),
            lambda d: d['schools'][0]['identity_raw']['native_grade_evidence'].update(year=2024),
            lambda d: d['schools'][0]['identity_raw']['ccd_flags'].update(charter='Yes'),
            lambda d: d['schools'][0]['outcomes']['math']['raw'].update(sampling_variance=0.),
            lambda d: d['schools'][0]['outcomes']['reading'].update(proficiency=99.),
            lambda d: d['schools'][0]['outcomes']['math'].update(tested=100, valid_score_evidence='CCD membership'),
            lambda d: next(s for s in d['schools'] if s['id'] == '0290110').update(income=0., low_income=0),
            lambda d: next(s for s in d['schools'] if s['id'] == '0290110')['income_raw']['grade_table']['rows'][0]['values'].__setitem__(0, '0'),
            lambda d: d['cohorts'][0].update(allow_point_only=False),
            lambda d: d['cohorts'][0].update(assessment='Old standards'),
            lambda d: d['source_audit']['excluded_native_configuration_records'].clear(),
            lambda d: d['source_audit']['missing_native_profiles'].clear(),
            lambda d: d['source_audit']['held_populations'].clear(),
            lambda d: d['source_audit']['retained_raw_inputs']['membership']['records'][0]['raw'].update(STUDENT_COUNT='0'),
            lambda d: d['source_audit']['release_basis'].update(historical_audits_approved_for_modeling=0),
            lambda d: d['sources']['numerical_audit'].update(sha256='0' * 64),
            lambda d: d['selection']['directory_school_ids'].pop(),
            lambda d: d.update(statewide=0),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.payload); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): fairfax.validate(changed, self.expected)
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / 'wrong.json'; wrong.write_text('{}')
            with mock.patch.object(fairfax.model_audit, 'OUTPUT', wrong), self.assertRaisesRegex(ValueError, 'fingerprint'):
                fairfax.load_inputs()

    def test_static_extra_models_hidden_fields_and_missing_income_promotion_rejected(self):
        originals = {p.name: p.read_bytes() for p in self.output.glob('*.json')}
        with tempfile.TemporaryDirectory(prefix='fairfax-corrupt-export-', dir=ROOT / 'data/build') as folder:
            folder = Path(folder); descriptor = json.loads(originals['catalog.json'])
            descriptor['regions'][0].update(schools=str((folder / 'schools.json').relative_to(ROOT)),
                audit=str((folder / 'coverage.json').relative_to(ROOT)))
            originals['catalog.json'] = json.dumps(descriptor).encode()
            for filename, mutate in [
                ('schools.json', lambda d: d['models'].update(HS=d['models']['ES'])),
                ('schools.json', lambda d: d['models']['ES']['math'].update(n=152.)),
                ('schools.json', lambda d: d['models']['ES']['math'].update(slope=float('nan'))),
                ('schools.json', lambda d: d['schools'].append(copy.deepcopy(d['schools'][0]))),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(studentized=99.)),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(tested=False)),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(low=0.)),
                ('schools.json', lambda d: d['schools'][0]['metrics']['math'].update(cohort_n=152.)),
                ('schools.json', lambda d: d['schools'][0].update(latitude=0.)),
                ('schools.json', lambda d: d['schools'][0].update(hidden_model={})),
                ('schools.json', lambda d: d.update(hidden_history=[])),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id'] == '0290110')['metrics'].update(math=d['schools'][0]['metrics']['math'])),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id'] == '0290110')['exclusions'].clear()),
                ('history.json', lambda d: d['models'][0].update(intercept=-99.)),
                ('history.json', lambda d: d['records'][0].update(income_year=2024)),
                ('history.json', lambda d: d['records'][0]['subjects'].update(extra={})),
                ('history.json', lambda d: d['records'][0].update(raw_count_proxy=100)),
                ('history.json', lambda d: d.update(ghost_records=[])),
                ('coverage.json', lambda d: d['cohorts']['grade']['eligible'].update(combined=162)),
                ('coverage.json', lambda d: d['source_audit']['excluded_native_configuration_records'].clear()),
                ('catalog.json', lambda d: d['regions'][0].update(name='Statewide', statewide=True)),
            ]:
                for name, content in originals.items(): (folder / name).write_bytes(content)
                changed = json.loads((folder / filename).read_text()); mutate(changed)
                (folder / filename).write_text(json.dumps(changed))
                with self.subTest(filename=filename, mutate=mutate), self.assertRaises(ValueError):
                    fairfax.validate_exports(self.payload, folder, self.numerical)

    def test_offline_extract_repeatability_keeps_historical_pins_immutable(self):
        with tempfile.TemporaryDirectory(prefix='fairfax-extract-repeat-', dir=ROOT / 'data/build') as folder:
            first, second = Path(folder) / 'one.json', Path(folder) / 'two.json'
            with mock.patch.object(fairfax.roster_audit.zipfile, 'ZipFile', side_effect=AssertionError('No raw ZIP')):
                fairfax.extract(first); fairfax.extract(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first.read_bytes(), fairfax.EXTRACT.read_bytes())
        self.assertEqual(hashlib.sha256(fairfax.model_audit.ROSTER.read_bytes()).hexdigest(), fairfax.model_audit.ROSTER_SHA)
        self.assertEqual(hashlib.sha256(fairfax.model_audit.OUTPUT.read_bytes()).hexdigest(), fairfax.NUMERICAL_SHA)


if __name__ == '__main__':
    unittest.main()
