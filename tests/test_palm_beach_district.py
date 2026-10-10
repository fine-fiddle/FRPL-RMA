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
import prepare_palm_beach as palm

TABLES = ['dataset', 'source', 'school', 'economic_observation', 'assessment_definition',
          'economic_definition', 'assessment_observation', 'model_run', 'model_result']


def seed_other(db):
    """Another Florida release uses the same native school ID in every table."""
    db.execute("INSERT INTO dataset VALUES ('other-fl','FL','Keep release','Keep population','ready')")
    db.execute("INSERT INTO source VALUES ('other-source','other-fl','other.json','https://example.test/source',?, '2025-01-01')", ('1' * 64,))
    db.execute("INSERT INTO assessment_definition VALUES ('other-assessment','FL','Other test',2025,'ES','3','Keep standard','https://example.test/assessment')")
    db.execute("INSERT INTO economic_definition VALUES ('other-income','Keep income','Keep definition','https://example.test/income')")
    db.execute("INSERT INTO school VALUES ('other-fl','50-3441','Keep school','other-district','Keep district',NULL,NULL,'{}','other-source',1)")
    db.execute("INSERT INTO economic_observation VALUES ('other-fl','50-3441',2025,'other-income','Keep school',100,30,30,'Keep income','{}','other-source',1)")
    db.execute("INSERT INTO assessment_observation VALUES ('other-fl','50-3441','other-assessment','math',40,100,'reported','{}','100','other-source',1)")
    db.execute("INSERT INTO model_run VALUES ('other-model','other-fl','other-assessment','math','keep-method',?,'{}')", ('2' * 64,))
    db.execute("INSERT INTO model_result VALUES ('other-model','other-fl','50-3441',40,45,-1,-2,0)")


def rows(db):
    return {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in TABLES}


def sentinel(db):
    return {table: [r for r in values if any(isinstance(v, str) and
                    (v.startswith('other-') or v == 'keep-method') for v in r)]
            for table, values in rows(db).items()}


class PalmBeachIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.numerical = palm.load_inputs()
        cls.payload = json.loads(palm.EXTRACT.read_text())
        cls.expected = palm.build_snapshot(cls.roster, cls.numerical)
        cls.native = {r['school_id']: r for r in cls.roster['roster_links']}
        cls.sandbox = tempfile.TemporaryDirectory(prefix='palm-beach-main-test-', dir=ROOT / 'data/build')
        cls.output = Path(cls.sandbox.name) / 'output'
        database = Path(cls.sandbox.name) / 'schools.sqlite'
        cls.database = database
        with closing(connect(database)) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text())
            db.commit()
        palm.prepare(database, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    def test_frozen_pure_population_and_exact_native_point_only_definition(self):
        palm.validate(self.payload, self.expected)
        self.assertEqual(self.payload['dataset'], 'fl-palm-beach-2025')
        self.assertEqual(self.payload['state'], {'id': 'FL', 'name': 'Florida'})
        self.assertEqual(self.payload['region'], 'palm-beach')
        self.assertEqual(self.payload['region_name'], 'Palm Beach County')
        self.assertEqual(self.payload['release_status'], 'ready')
        self.assertFalse(self.payload['statewide'])
        self.assertEqual(len(self.payload['schools']), 170)
        self.assertTrue(all(s['cohort'] == 'grade-schools' and s['district_id'] == 'FL-50'
                            for s in self.payload['schools']))
        self.assertEqual(self.payload['cohorts'], palm.florida.normalize(palm.roster_audit.load_florida())['cohorts'])
        self.assertTrue(self.payload['cohorts'][0]['allow_point_only'])
        selected = {s['id'] for s in self.payload['schools']}
        self.assertEqual(selected, set(self.numerical['frozen_population']['pure_lower_directory_school_ids']))
        self.assertFalse(selected.intersection(self.numerical['frozen_population']['native_grade_schools_with_mixed_offers']))
        selection = dict(self.payload['selection'])
        digest = selection.pop('sha256')
        self.assertEqual(digest, palm.roster_audit.fingerprint(selection))
        self.assertEqual(self.payload['selection']['policy'], palm.model_audit.POLICY)
        self.assertFalse(self.roster['approved_for_modeling'])
        self.assertFalse(self.numerical['approved_for_modeling'])
        self.assertFalse(self.roster['approved_for_source'])
        self.assertFalse(self.numerical['approved_for_source'])

    def test_every_applicability_missingness_and_raw_source_flag_is_preserved(self):
        primary, missing, protected = [], [], []
        for school in self.payload['schools']:
            source = self.native[school['id']]
            self.assertEqual(school['income_raw'], source['income']['raw'])
            self.assertEqual(school['income_row'], source['income']['source_row'])
            self.assertEqual(school['identity_raw']['grade_raw'], source['profile']['grades'])
            self.assertEqual(school['identity_raw']['offered_evidence'], source['offered'])
            self.assertEqual(school['identity_raw']['enrolled_evidence'], source['enrolled'])
            self.assertEqual(school['identity_raw']['native_assessment_flags'], source['native_assessment_flags'])
            if not school['outcomes']['math']['raw']['applicable']:
                primary.append(school['id'])
            elif school['outcomes']['math']['proficiency'] is None:
                missing.append(school['id'])
            if source['enrolled']['protected_grades']:
                protected.append(school['id'])
            for subject in ['math', 'reading']:
                outcome = school['outcomes'][subject]; native = source['subjects'][subject]
                self.assertEqual(outcome['exclusion'], native['district_exclusion'])
                self.assertEqual(outcome['raw']['source_contract_exclusion'], native['source_contract_exclusion'])
                self.assertEqual(outcome['proficiency'], native['native_rate'] if native['district_usable'] else None)
                self.assertTrue(all(outcome[k] is None for k in ['tested', 'valid_score_evidence', 'raw_tested']))
                self.assertIsNone(outcome['raw']['valid_score_count'])
                self.assertIsNone(outcome['raw']['sampling_variance'])
                self.assertFalse(outcome['raw']['interval_availability'])
        self.assertEqual(set(primary), {'50-1931', '50-3100'})
        self.assertEqual(set(missing), {'50-2791', '50-4100', '50-0040'})
        self.assertTrue(protected)
        audit = self.payload['source_audit']
        self.assertEqual(len(audit['excluded_operational_roster_records']), 64)
        self.assertEqual(len(audit['nonoperational_directory']), 4)
        self.assertEqual(audit['outside_roster_profiles'], [])
        self.assertEqual(audit['income_without_fall_registry_links'], [])
        self.assertEqual(audit['full_directory_records'], self.roster['directory_records'])
        self.assertEqual(audit['native_records'], self.roster['native_records'])
        self.assertEqual(audit['planning_membership_evidence'], self.roster['planning_membership_evidence'])
        self.assertEqual(len(audit['planning_membership_evidence']['records']), 58)
        self.assertEqual(audit['planning_identity_reconciliation']['source_proposed_not_in_planning_ES'], [])
        inventory = audit['cohorts']['exact_operational_pure_lower_directory']
        self.assertEqual((inventory['profiles'], inventory['native_fall_profile_matches']), (170, 170))
        self.assertEqual(len(inventory['offered_tested_school_ids']), 168)
        self.assertEqual(inventory['without_fall_profile_school_ids'], [])
        excluded = {r['id']: r for r in audit['excluded_operational_roster_records']}
        for school in ['50-3081', '50-3931', '50-7023', '50-9063']:
            self.assertFalse(excluded[school]['native_record']['matched'])
            self.assertEqual(excluded[school]['offered_scope'], 'mixed')
            self.assertNotIn('profile', excluded[school]['native_record'])
        for school in ['50-3039', '50-3091']:
            self.assertIsNone(excluded[school]['native_record']['income']['percentage'])
            self.assertEqual(excluded[school]['native_record']['income']['raw'][4:9], ['*'] * 5)
        providers = audit['provider_specific_virtual_rows']
        self.assertEqual([(r['id'], r['row'], r['raw'][3]) for r in providers],
                         [('50-7001', 2712, '302'), ('50-7001', 2713, '309')])
        self.assertEqual([(r['raw'][9], r['raw'][6]) for r in providers], [(67, 81), (38, 56)])
        keyed = {s['id']: s for s in self.payload['schools']}
        for key, total in [('50-2791', 165), ('50-3100', 32)]:
            self.assertEqual((keyed[key]['income'], keyed[key]['low_income'], keyed[key]['enrollment']), (0., 0, total))
            self.assertTrue(all(keyed[key]['outcomes'][s]['proficiency'] is None for s in ['math', 'reading']))
        career = keyed['50-3441']
        self.assertEqual(career['identity_raw']['ccd_flags']['school_type'], 'Career and Technical School')
        self.assertEqual(career['identity_raw']['ccd_flags']['charter'], 'Yes')
        self.assertEqual(career['income'], 350 / 528 * 100)
        self.assertEqual((career['outcomes']['math']['proficiency'], career['outcomes']['reading']['proficiency']), (67., 70.))
        for subject in ['math', 'reading']:
            eligible = [s for s in self.payload['schools'] if s['outcomes'][subject]['proficiency'] is not None]
            self.assertEqual(len(eligible), 165)
            self.assertEqual(sum(s['identity_raw']['ccd_flags']['charter'] == 'Yes' for s in eligible), 24)
            self.assertTrue(all(s['income'] > 0 for s in eligible))
        self.assertTrue(all(keyed[k]['income'] is not None for k in primary))

    def test_import_twice_preserves_same_state_same_native_id_and_namespaces_every_definition(self):
        with closing(connect(':memory:')) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text())
            seed_other(db)
            before = sentinel(db)
            import_snapshot(db, self.payload, palm.EXTRACT)
            first = rows(db)
            import_snapshot(db, self.payload, palm.EXTRACT)
            self.assertEqual(first, rows(db))
            self.assertEqual(before, sentinel(db))
            self.assertEqual(db.execute('SELECT count(*) FROM school WHERE dataset_id=?', (palm.DATASET,)).fetchone()[0], 170)
            self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=?', (palm.DATASET,)).fetchone()[0], 340)
            self.assertTrue(all(r['tested'] is None for r in db.execute('SELECT tested FROM assessment_observation WHERE dataset_id=?', (palm.DATASET,))))
            self.assertTrue(all(r['id'].startswith(palm.DATASET + ':') for r in db.execute('SELECT id FROM source WHERE dataset_id=?', (palm.DATASET,))))
            definition = dict(db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (palm.DATASET + ':%',)).fetchone())
            cohort = self.payload['cohorts'][0]
            self.assertEqual([definition[k] for k in ['state', 'name', 'year', 'level', 'grades', 'standard', 'source_url']],
                             ['FL', cohort['assessment'], 2025, 'ES', cohort['grades'], cohort['standard'], cohort['source_url']])
            self.assertTrue(all(r['definition_id'] == palm.DATASET + ':income' for r in db.execute('SELECT definition_id FROM economic_observation WHERE dataset_id=?', (palm.DATASET,))))
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            primary = db.execute('SELECT enrollment,low_income,percentage FROM economic_observation WHERE dataset_id=? AND school_id=?',
                                 (palm.DATASET, '50-1931')).fetchone()
            self.assertEqual(tuple(primary), (564., 88., 88 / 564 * 100))
            self.assertIsNone(db.execute('SELECT proficiency FROM assessment_observation WHERE dataset_id=? AND school_id=? AND subject=?',
                                        (palm.DATASET, '50-1931', 'math')).fetchone()[0])
            self.assertIsNone(db.execute('SELECT school_id FROM school WHERE dataset_id=? AND school_id=?',
                                        (palm.DATASET, '50-7001')).fetchone())

    def test_full_preparation_twice_is_identical_and_failed_validation_cannot_mutate_database(self):
        with tempfile.TemporaryDirectory(prefix='palm-beach-test-', dir=ROOT / 'data/build') as folder:
            folder = Path(folder)
            database, output = folder / 'schools.sqlite', folder / 'output'
            with closing(connect(database)) as db:
                db.executescript((ROOT / 'scripts/schema.sql').read_text())
                seed_other(db)
                before = sentinel(db)
                db.commit()
            palm.prepare(database, output)
            first = {p.name: p.read_bytes() for p in output.glob('*.json')}
            palm.prepare(database, output)
            self.assertEqual(first, {p.name: p.read_bytes() for p in output.glob('*.json')})
            with closing(connect(database)) as db:
                self.assertEqual(before, sentinel(db))
                self.assertEqual(db.execute('SELECT count(*) FROM model_run WHERE dataset_id=?', (palm.DATASET,)).fetchone()[0], 3)
                self.assertEqual(db.execute('SELECT count(*) FROM model_result WHERE dataset_id=?', (palm.DATASET,)).fetchone()[0], 495)
                self.assertTrue(all(r['low'] is None and r['high'] is None for r in db.execute('SELECT low, high FROM model_result WHERE dataset_id=?', (palm.DATASET,))))
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
                before_failure = rows(db)
            changed = copy.deepcopy(self.payload)
            changed['schools'][0]['outcomes']['math']['tested'] = 100
            wrong = folder / 'wrong.json'
            wrong.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                palm.prepare(database, output, wrong)
            with closing(connect(database)) as db:
                self.assertEqual(before_failure, rows(db))

    def test_saved_exports_match_every_independent_point_and_directory_exclusion(self):
        self.assertEqual(palm.validate_canonical(self.payload, self.database, self.numerical),
                         {'schools': 170, 'observations': 340, 'models': 3, 'results': 495})
        with tempfile.TemporaryDirectory(prefix='palm-beach-canonical-corruption-', dir=ROOT / 'data/build') as folder:
            wrong = Path(folder) / 'wrong.sqlite'
            mutations = [
                "UPDATE model_result SET studentized=99 WHERE dataset_id='fl-palm-beach-2025' AND school_id='50-3441'",
                "UPDATE assessment_observation SET tested=100 WHERE dataset_id='fl-palm-beach-2025' AND school_id='50-3441'",
                "UPDATE economic_observation SET year=2024 WHERE dataset_id='fl-palm-beach-2025' AND school_id='50-3441'",
                "UPDATE school SET name='Different identity' WHERE dataset_id='fl-palm-beach-2025' AND school_id='50-3441'",
                "INSERT INTO economic_observation SELECT dataset_id,school_id,2024,definition_id,name,enrollment,low_income,percentage,source_label,raw_json,source_id,source_order FROM economic_observation WHERE dataset_id='fl-palm-beach-2025' AND school_id='50-3441'",
                "INSERT INTO model_run SELECT id||':ghost',dataset_id,definition_id,subject,method_version,input_sha256,summary_json FROM model_run WHERE dataset_id='fl-palm-beach-2025' AND subject='math'",
            ]
            for sql in mutations:
                with closing(connect(self.database)) as source, closing(connect(wrong)) as db:
                    source.backup(db)
                    db.execute(sql)
                    db.commit()
                with self.subTest(sql=sql), self.assertRaises(ValueError):
                    palm.validate_canonical(self.payload, wrong, self.numerical)
        self.assertEqual(palm.validate_exports(self.payload, self.output, self.numerical),
                         {f'palm-beach-2025-ES-{s}': 165 for s in palm.model_audit.SUBJECTS})
        schools = json.loads((self.output / 'schools.json').read_text())
        self.assertEqual(len(schools['schools']), 170)
        self.assertEqual(sum(bool(s['metrics']) for s in schools['schools']), 165)
        self.assertTrue(all(v['tested'] is None and v['low'] is None and v['high'] is None
                            and 'variance' not in v and 'sampling_variance' not in v
                            for s in schools['schools'] for v in s['metrics'].values()))
        unavailable = [s for s in schools['schools'] if not s['metrics']]
        self.assertEqual(len(unavailable), 5)
        self.assertTrue(all(set(s['exclusions']) == {'math', 'reading', 'combined'} for s in unavailable))
        self.assertTrue(all('Math:' in s['exclusions']['combined'] and 'ELA:' in s['exclusions']['combined'] for s in unavailable))
        region = json.loads((self.output / 'catalog.json').read_text())['regions'][0]
        self.assertEqual((region['id'], region['name'], region['geography'], region['dataset']),
                         ('palm-beach', 'Palm Beach County', 'palm-beach', palm.DATASET))
        self.assertFalse(region['statewide'])
        self.assertEqual(region['levels'], ['ES'])
        self.assertIsNone(region['boundaries'])

    def test_population_raw_source_count_or_native_definition_drift_fails_before_import(self):
        mutations = [
            lambda d: d['schools'][0].update(cohort='high'),
            lambda d: d['schools'][0].update(id='50-7001'),
            lambda d: d['schools'][0]['identity_raw']['enrolled_evidence'].update(native_grade_school_contract=False),
            lambda d: d['schools'][0]['identity_raw']['grade_raw'].__setitem__(14, '*'),
            lambda d: d['schools'][0]['outcomes']['math'].update(tested=10, valid_score_evidence='Invented denominator'),
            lambda d: d['schools'][0]['outcomes']['math']['raw'].update(sampling_variance=0.),
            lambda d: d['cohorts'][0].update(allow_point_only=False),
            lambda d: d['cohorts'][0].update(standard='High-school FAST-only standard'),
            lambda d: d['sources']['numerical_audit'].update(sha256='0' * 64),
            lambda d: d['selection']['policy'].update(school_types='Drop alternatives'),
            lambda d: d['selection']['directory_school_ids'].pop(),
            lambda d: d.update(statewide=True),
            lambda d: d.update(statewide=0),
            lambda d: d['schools'][0]['income_raw'].__setitem__(7, False),
            lambda d: d['source_audit']['release_basis'].update(exact_source_roster_replayed=1),
            lambda d: d['source_audit']['planning_membership_exclusions'][0].update(source_population_exclusion='Remove charter'),
            lambda d: next(s for s in d['schools'] if s['id']=='50-3100').update(income=None),
            lambda d: next(s for s in d['schools'] if s['id']=='50-0040')['outcomes']['math'].update(proficiency=67),
            lambda d: d['source_audit']['cohorts']['exact_operational_pure_lower_directory']['without_fall_profile_school_ids'].append('50-1931'),
            lambda d: next(s for s in d['schools'] if s['id']=='50-3441')['identity_raw']['ccd_flags'].update(school_type='Regular School'),
            lambda d: d['source_audit']['provider_specific_virtual_rows'].pop(),
            lambda d: d['source_audit']['planning_membership_evidence']['records'][0]['raw'].update(STUDENT_COUNT='1', DMS_FLAG='Reported'),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.payload)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                palm.validate(changed, self.expected)
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / 'wrong-audit.json'
            wrong.write_text('{}')
            with mock.patch.object(palm.model_audit, 'OUTPUT', wrong):
                with self.assertRaisesRegex(ValueError, 'fingerprint'):
                    palm.load_inputs()

    def test_browser_model_history_scope_counts_intervals_and_coverage_drift_are_rejected(self):
        originals = {p.name: p.read_bytes() for p in self.output.glob('*.json')}
        with tempfile.TemporaryDirectory(prefix='palm-beach-export-test-', dir=ROOT / 'data/build') as folder:
            folder = Path(folder)
            # Catalog paths are intentionally tied to the output directory.
            descriptor = json.loads(originals['catalog.json'])
            descriptor['regions'][0].update(schools=str((folder / 'schools.json').relative_to(ROOT)),
                                            audit=str((folder / 'coverage.json').relative_to(ROOT)))
            originals['catalog.json'] = json.dumps(descriptor).encode()
            mutations = [
                ('history.json', lambda d: d['models'][0].update(slope=-99.)),
                ('schools.json', lambda d: d['history_models'].pop()),
                ('schools.json', lambda d: d['models'].update(HS=d['models']['ES'])),
                ('schools.json', lambda d: d['models']['ES']['math'].update(n=165.)),
                ('schools.json', lambda d: d['models']['ES']['math'].update(assessed_schools=170.)),
                ('schools.json', lambda d: d['models']['ES']['math'].update(intercept=float('nan'))),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics'].update(HS={})),
                ('history.json', lambda d: d['records'][0]['subjects'].update(extra={})),
                ('schools.json', lambda d: d['schools'].append(copy.deepcopy(d['schools'][0]))),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(studentized=99.)),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(tested=10)),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(low=0.)),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(cohort_n=165.)),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(tested=False)),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(predicted=float('inf'))),
                ('schools.json', lambda d: next(s for s in d['schools'] if not s['metrics'])['exclusions'].update(combined='Both eligible subject results required')),
                ('schools.json', lambda d: d['schools'][0].update(latitude=0.)),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id']=='50-1931').update(income=0.)),
                ('history.json', lambda d: next(s for s in d['records'] if s['school_id']=='50-1931').update(enrollment=0.)),
                ('schools.json', lambda d: d['schools'][0].update(name='Different identity')),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id']=='50-3441').update(income=None)),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['id']=='50-0040')['metrics'].update(math={})),
                ('schools.json', lambda d: d['schools'][0].update(district='Statewide')),
                ('history.json', lambda d: d['records'][0].update(income_year=2024)),
                ('catalog.json', lambda d: d['regions'][0].update(name='Statewide', statewide=True)),
                ('coverage.json', lambda d: d['cohorts']['grade-schools']['eligible'].update(combined=166)),
                ('coverage.json', lambda d: d['source_audit']['release_basis'].update(historical_audits_approved_for_modeling=True)),
                ('coverage.json', lambda d: d['source_audit']['release_basis'].update(historical_audits_approved_for_modeling=0)),
            ]
            for filename, mutate in mutations:
                for name, content in originals.items():
                    (folder / name).write_bytes(content)
                changed = json.loads((folder / filename).read_text())
                mutate(changed)
                (folder / filename).write_text(json.dumps(changed))
                with self.subTest(filename=filename, mutate=mutate), self.assertRaises(ValueError):
                    palm.validate_exports(self.payload, folder, self.numerical)

    def test_historical_audits_are_immutable_and_normalized_generation_is_repeatable(self):
        self.assertEqual(hashlib.sha256(palm.roster_audit.OUTPUT.read_bytes()).hexdigest(), palm.model_audit.ROSTER_SHA)
        self.assertEqual(hashlib.sha256(palm.model_audit.OUTPUT.read_bytes()).hexdigest(), palm.NUMERICAL_SHA)
        with tempfile.TemporaryDirectory() as folder:
            one, two = Path(folder) / 'one.json', Path(folder) / 'two.json'
            palm.extract(one)
            palm.extract(two)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            self.assertEqual(one.read_bytes(), palm.EXTRACT.read_bytes())


if __name__ == '__main__':
    unittest.main()
