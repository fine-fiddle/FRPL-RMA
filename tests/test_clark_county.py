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
from state_snapshot import import_snapshot, prepare_snapshot
import prepare_clark_county as clark

TABLES = ['dataset', 'source', 'school', 'economic_observation', 'assessment_definition',
          'economic_definition', 'assessment_observation', 'model_run', 'model_result']


def seed_other(db):
    """Another Nevada release uses the same native school ID in every table."""
    db.execute("INSERT INTO dataset VALUES ('other-nv','NV','Keep release','Keep population','ready')")
    db.execute("INSERT INTO source VALUES ('other-source','other-nv','other.json','https://example.test/source',?, '2025-01-01')", ('1' * 64,))
    db.execute("INSERT INTO assessment_definition VALUES ('other-assessment','NV','Other test',2025,'ES','3','Keep standard','https://example.test/assessment')")
    db.execute("INSERT INTO economic_definition VALUES ('other-income','Keep income','Keep definition','https://example.test/income')")
    db.execute("INSERT INTO school VALUES ('other-nv','320006000008','Keep school','other-district','Keep district',NULL,NULL,'{}','other-source',1)")
    db.execute("INSERT INTO economic_observation VALUES ('other-nv','320006000008',2025,'other-income','Keep school',100,30,30,'Keep income','{}','other-source',1)")
    db.execute("INSERT INTO assessment_observation VALUES ('other-nv','320006000008','other-assessment','math',40,100,'reported','{}','100','other-source',1)")
    db.execute("INSERT INTO model_run VALUES ('other-model','other-nv','other-assessment','math','keep-method',?,'{}')", ('2' * 64,))
    db.execute("INSERT INTO model_result VALUES ('other-model','other-nv','320006000008',40,45,-1,-2,0)")


def rows(db):
    return {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in TABLES}


def sentinel(db):
    return {table: [r for r in values if any(isinstance(v, str) and
                    (v.startswith('other-') or v == 'keep-method') for v in r)]
            for table, values in rows(db).items()}


class ClarkCountyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.numerical = clark.load_inputs()
        cls.payload = json.loads(clark.EXTRACT.read_text())
        cls.expected = clark.build_snapshot(cls.roster, cls.numerical)
        cls.native = {r['school_id']: r for r in cls.roster['roster_links']}

    def test_frozen_native_population_and_exact_point_only_definition(self):
        clark.validate(self.payload, self.expected)
        self.assertEqual(self.payload['dataset'], 'nv-clark-county-2025')
        self.assertEqual(self.payload['state'], {'id': 'NV', 'name': 'Nevada'})
        self.assertEqual(self.payload['region'], 'clark-county')
        self.assertEqual(self.payload['region_name'], 'Clark County')
        self.assertEqual(self.payload['release_status'], 'ready')
        self.assertFalse(self.payload['statewide'])
        self.assertEqual(len(self.payload['schools']), 289)
        self.assertTrue(all(s['cohort'] == 'grade' and s['district_id'] == '3200060'
                            for s in self.payload['schools']))
        self.assertEqual(self.payload['cohorts'], clark.roster_audit.load_nevada()['cohorts'])
        self.assertTrue(self.payload['cohorts'][0]['allow_point_only'])
        selected = {s['id'] for s in self.payload['schools']}
        self.assertEqual(selected, set(self.numerical['frozen_population']['native_source_profile_ids']))
        self.assertFalse(selected.intersection(self.numerical['frozen_population']['mixed_offers_with_native_g38_ids']))
        selection = dict(self.payload['selection'])
        digest = selection.pop('sha256')
        self.assertEqual(digest, clark.roster_audit.fingerprint(selection))
        self.assertEqual(self.payload['selection']['policy'], clark.model_audit.POLICY)
        self.assertFalse(self.roster['approved_for_modeling'])
        self.assertFalse(self.numerical['approved_for_modeling'])

    def test_every_native_raw_source_flag_and_all_configurations_remain_auditable(self):
        raw = self.roster['raw_inputs']
        membership = {r['source_row']: r['raw'] for r in raw['membership']['records']}
        lunch = {r['source_row']: r['raw'] for r in raw['lunch']['records']}
        assessment = {r['source_row']: r['raw'] for r in raw['assessment']['records']}
        suppressed = []
        for school in self.payload['schools']:
            source = self.native[school['id']]
            self.assertEqual(school['income_raw']['direct_certification'], lunch[source['income']['direct_source_row']])
            self.assertEqual(school['income_raw']['membership'], membership[source['income']['membership_source_row']])
            self.assertEqual(school['income_row'], source['income']['direct_source_row'])
            self.assertEqual(school['income'], 100 * source['income']['reported_direct_certification'] / source['income']['reported_membership'])
            self.assertEqual(school['identity_raw']['offered_evidence'], source['offered'])
            self.assertEqual(school['identity_raw']['enrolled_evidence'], source['enrolled'])
            self.assertEqual(school['identity_raw']['edc_metadata'], source['edc_metadata'])
            self.assertEqual(source['offered']['ungraded_offered'], 'Yes')
            self.assertEqual(source['enrolled']['ungraded_reported_count'], 0)
            self.assertTrue(source['enrolled']['lower_total_reconciled'])
            if school['outcomes']['math']['proficiency'] is None: suppressed.append(school['id'])
            for subject in ['math', 'reading']:
                outcome, native = school['outcomes'][subject], source['subjects'][subject]
                self.assertEqual(outcome['exclusion'], native['exclusion'])
                self.assertEqual(outcome['proficiency'], native['native_rate'] if native['usable'] else None)
                self.assertEqual(outcome['source_row'], native['source_row'])
                self.assertEqual(outcome['raw']['assessment_raw'], assessment[native['source_row']])
                self.assertEqual(outcome['raw']['raw_tested_unverified'], native['raw_tested'])
                self.assertTrue(outcome['raw']['applicable'])
                self.assertTrue(all(outcome[k] is None for k in ['tested', 'valid_score_evidence', 'raw_tested']))
                self.assertIsNone(outcome['raw']['valid_score_count'])
                self.assertIsNone(outcome['raw']['sampling_variance'])
                self.assertFalse(outcome['raw']['interval_availability'])
        self.assertEqual(set(suppressed), {'320006000010', '320006000099', '320006000607'})
        evidence = self.payload['source_audit']
        self.assertEqual(len(evidence['excluded_operational_roster_records']), 90)
        self.assertEqual(len(evidence['excluded_native_configuration_records']), 13)
        self.assertEqual(len(evidence['outside_native_configuration_records']), 80)
        self.assertEqual(evidence['cohorts']['native_grade_school_configurations']['profiles'], 299)
        self.assertEqual(evidence['cohorts']['native_offered_tested_grade']['profiles'], 298)
        self.assertEqual(len(evidence['nonoperational_directory']), 1)
        self.assertTrue(all(not rows for rows in evidence['outside_operational_roster_records'].values()))
        excluded = {r['school_id']: r for r in evidence['excluded_operational_roster_records']}
        self.assertEqual(excluded['320006000488']['edc_metadata']['math']['SchVirtual'], 'Supplemental virtual')
        self.assertEqual(excluded['320006000949']['income']['direct_status'], 'absent')
        self.assertEqual(excluded['320006000037']['income']['direct_status'], 'Suppressed')

    def test_import_twice_preserves_same_state_same_native_id_and_namespaces_every_definition(self):
        with closing(connect(':memory:')) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text())
            seed_other(db)
            before = sentinel(db)
            import_snapshot(db, self.payload, clark.EXTRACT)
            first = rows(db)
            import_snapshot(db, self.payload, clark.EXTRACT)
            self.assertEqual(first, rows(db))
            self.assertEqual(before, sentinel(db))
            self.assertEqual(db.execute('SELECT count(*) FROM school WHERE dataset_id=?', (clark.DATASET,)).fetchone()[0], 289)
            self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=?', (clark.DATASET,)).fetchone()[0], 578)
            self.assertTrue(all(r['tested'] is None for r in db.execute('SELECT tested FROM assessment_observation WHERE dataset_id=?', (clark.DATASET,))))
            self.assertTrue(all(r['id'].startswith(clark.DATASET + ':') for r in db.execute('SELECT id FROM source WHERE dataset_id=?', (clark.DATASET,))))
            definition = dict(db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (clark.DATASET + ':%',)).fetchone())
            cohort = self.payload['cohorts'][0]
            self.assertEqual([definition[k] for k in ['state', 'name', 'year', 'level', 'grades', 'standard', 'source_url']],
                             ['NV', cohort['assessment'], 2025, 'ES', cohort['grades'], cohort['standard'], cohort['source_url']])
            self.assertTrue(all(r['definition_id'] == clark.DATASET + ':income' for r in db.execute('SELECT definition_id FROM economic_observation WHERE dataset_id=?', (clark.DATASET,))))
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())

    def test_full_preparation_twice_is_identical_and_failed_validation_cannot_mutate_database(self):
        with tempfile.TemporaryDirectory(prefix='clark-test-', dir=ROOT / 'data/build') as folder:
            folder = Path(folder)
            database, output = folder / 'schools.sqlite', folder / 'output'
            with closing(connect(database)) as db:
                db.executescript((ROOT / 'scripts/schema.sql').read_text())
                seed_other(db)
                before = sentinel(db)
                db.commit()
            with closing(connect(database)) as db:
                import_snapshot(db, clark.roster_audit.load_nevada(), clark.roster_audit.nevada.EXTRACT)
                db.commit()
                preserved = {table: [r for r in values if not any(isinstance(v, str) and
                    (v == clark.DATASET or v.startswith(clark.DATASET + ':')) for v in r)]
                    for table, values in rows(db).items()}
            clark.prepare(database, output)
            first = {p.name: p.read_bytes() for p in output.glob('*.json')}
            clark.prepare(database, output)
            self.assertEqual(first, {p.name: p.read_bytes() for p in output.glob('*.json')})
            with closing(connect(database)) as db:
                self.assertEqual(before, sentinel(db))
                after_preserved = {table: [r for r in values if not any(isinstance(v, str) and
                    (v == clark.DATASET or v.startswith(clark.DATASET + ':')) for v in r)]
                    for table, values in rows(db).items()}
                self.assertEqual(preserved, after_preserved)
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(db.execute('SELECT count(*) FROM model_run WHERE dataset_id=?', (clark.DATASET,)).fetchone()[0], 3)
                self.assertEqual(db.execute('SELECT count(*) FROM model_result WHERE dataset_id=?', (clark.DATASET,)).fetchone()[0], 858)
                self.assertTrue(all(r['low'] is None and r['high'] is None for r in db.execute('SELECT low, high FROM model_result WHERE dataset_id=?', (clark.DATASET,))))
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
                before_failure = rows(db)
            changed = copy.deepcopy(self.payload)
            changed['schools'][0]['outcomes']['math']['tested'] = 100
            wrong = folder / 'wrong.json'
            wrong.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                clark.prepare(database, output, wrong)
            with closing(connect(database)) as db:
                self.assertEqual(before_failure, rows(db))

    def test_saved_exports_match_every_independent_point_and_directory_exclusion(self):
        self.assertEqual(clark.validate_exports(self.payload, clark.OUTPUT, self.numerical),
                         {f'clark-county-2025-ES-{s}': 286 for s in clark.model_audit.SUBJECTS})
        schools = json.loads((clark.OUTPUT / 'schools.json').read_text())
        self.assertEqual(len(schools['schools']), 289)
        self.assertEqual(sum(bool(s['metrics']) for s in schools['schools']), 286)
        self.assertTrue(all(v['tested'] is None and v['low'] is None and v['high'] is None
                            and 'variance' not in v and 'sampling_variance' not in v
                            for s in schools['schools'] for v in s['metrics'].values()))
        unavailable = [s for s in schools['schools'] if not s['metrics']]
        self.assertEqual(len(unavailable), 3)
        self.assertTrue(all(set(s['exclusions']) == {'math', 'reading', 'combined'} for s in unavailable))
        self.assertTrue(all('Math:' in s['exclusions']['combined'] and 'ELA:' in s['exclusions']['combined'] for s in unavailable))
        region = json.loads((clark.OUTPUT / 'catalog.json').read_text())['regions'][0]
        self.assertEqual((region['id'], region['name'], region['geography'], region['dataset']),
                         ('clark-county', 'Clark County', 'clark-county', clark.DATASET))
        self.assertFalse(region['statewide'])
        self.assertEqual(region['levels'], ['ES'])
        self.assertIsNone(region['boundaries'])

    def test_population_raw_source_count_or_native_definition_drift_fails_before_import(self):
        mutations = [
            lambda d: d['schools'][0].update(cohort='high'),
            lambda d: d['schools'][0].update(id='320006000740'),
            lambda d: d['schools'][0]['identity_raw']['enrolled_evidence'].update(native_grade_school_contract=False),
            lambda d: d['schools'][0]['identity_raw']['enrolled_evidence'].update(ungraded_reported_count=1),
            lambda d: d['schools'][0]['outcomes']['math'].update(tested=10, valid_score_evidence='Invented denominator'),
            lambda d: d['schools'][0]['outcomes']['math']['raw'].update(sampling_variance=0.),
            lambda d: d['cohorts'][0].update(allow_point_only=False),
            lambda d: d['cohorts'][0].update(standard='High-school ACT standard'),
            lambda d: d['sources']['numerical_audit'].update(sha256='0' * 64),
            lambda d: d['selection']['policy'].update(school_types='Drop alternatives'),
            lambda d: d['selection']['directory_school_ids'].pop(),
            lambda d: d.update(statewide=True),
            lambda d: d.update(statewide=0),
            lambda d: d['source_audit']['release_basis'].update(historical_audits_approved_for_modeling=0),
            lambda d: d['source_audit']['operational_roster'].update(verified_valid_score_counts=False),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.payload)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                clark.validate(changed, self.expected)
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / 'wrong-audit.json'
            wrong.write_text('{}')
            with mock.patch.object(clark.model_audit, 'OUTPUT', wrong):
                with self.assertRaisesRegex(ValueError, 'fingerprint'):
                    clark.load_inputs()

    def test_browser_model_history_scope_counts_intervals_and_coverage_drift_are_rejected(self):
        originals = {p.name: p.read_bytes() for p in clark.OUTPUT.glob('*.json')}
        with tempfile.TemporaryDirectory(prefix='clark-export-test-', dir=ROOT / 'data/build') as folder:
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
                ('schools.json', lambda d: d['schools'].append(copy.deepcopy(d['schools'][0]))),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(studentized=99.)),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(tested=10)),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(low=0.)),
                ('schools.json', lambda d: next(s for s in d['schools'] if not s['metrics'])['exclusions'].update(combined='Both eligible subject results required')),
                ('schools.json', lambda d: d['schools'][0].update(latitude=0.)),
                ('history.json', lambda d: d['records'][0].update(income_year=2024)),
                ('catalog.json', lambda d: d['regions'][0].update(name='Statewide', statewide=True)),
                ('coverage.json', lambda d: d['cohorts']['grade']['eligible'].update(combined=299)),
                ('coverage.json', lambda d: d['source_audit']['release_basis'].update(historical_audits_approved_for_modeling=True)),
                ('coverage.json', lambda d: d['source_audit']['operational_roster'].update(verified_valid_score_counts=False)),
                ('schools.json', lambda d: d.update(income_label='FRPL')),
                ('schools.json', lambda d: d['schools'][0].update(city='Invented place')),
                ('history.json', lambda d: d['records'][0].update(enrollment=0)),
                ('catalog.json', lambda d: d.update(prepare_script='scripts/prepare_ccd_states.py')),
                ('catalog.json', lambda d: d['regions'][0].update(statewide=0)),
            ]
            for filename, mutate in mutations:
                for name, content in originals.items():
                    (folder / name).write_bytes(content)
                changed = json.loads((folder / filename).read_text())
                mutate(changed)
                (folder / filename).write_text(json.dumps(changed))
                with self.subTest(filename=filename, mutate=mutate), self.assertRaises(ValueError):
                    clark.validate_exports(self.payload, folder, self.numerical)

    def test_historical_audits_are_immutable_and_normalized_generation_is_repeatable(self):
        self.assertEqual(hashlib.sha256(clark.roster_audit.OUTPUT.read_bytes()).hexdigest(), clark.model_audit.ROSTER_SHA)
        self.assertEqual(hashlib.sha256(clark.model_audit.OUTPUT.read_bytes()).hexdigest(), clark.NUMERICAL_SHA)
        with tempfile.TemporaryDirectory() as folder:
            one, two = Path(folder) / 'one.json', Path(folder) / 'two.json'
            clark.extract(one)
            clark.extract(two)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            self.assertEqual(one.read_bytes(), clark.EXTRACT.read_bytes())


if __name__ == '__main__':
    unittest.main()
