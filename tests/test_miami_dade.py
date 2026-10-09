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
import prepare_miami_dade as miami

TABLES = ['dataset', 'source', 'school', 'economic_observation', 'assessment_definition',
          'economic_definition', 'assessment_observation', 'model_run', 'model_result']


def seed_other(db):
    """Another Florida release uses the same native school ID in every table."""
    db.execute("INSERT INTO dataset VALUES ('other-fl','FL','Keep release','Keep population','ready')")
    db.execute("INSERT INTO source VALUES ('other-source','other-fl','other.json','https://example.test/source',?, '2025-01-01')", ('1' * 64,))
    db.execute("INSERT INTO assessment_definition VALUES ('other-assessment','FL','Other test',2025,'ES','3','Keep standard','https://example.test/assessment')")
    db.execute("INSERT INTO economic_definition VALUES ('other-income','Keep income','Keep definition','https://example.test/income')")
    db.execute("INSERT INTO school VALUES ('other-fl','13-0041','Keep school','other-district','Keep district',NULL,NULL,'{}','other-source',1)")
    db.execute("INSERT INTO economic_observation VALUES ('other-fl','13-0041',2025,'other-income','Keep school',100,30,30,'Keep income','{}','other-source',1)")
    db.execute("INSERT INTO assessment_observation VALUES ('other-fl','13-0041','other-assessment','math',40,100,'reported','{}','100','other-source',1)")
    db.execute("INSERT INTO model_run VALUES ('other-model','other-fl','other-assessment','math','keep-method',?,'{}')", ('2' * 64,))
    db.execute("INSERT INTO model_result VALUES ('other-model','other-fl','13-0041',40,45,-1,-2,0)")


def rows(db):
    return {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in TABLES}


def sentinel(db):
    return {table: [r for r in values if any(isinstance(v, str) and
                    (v.startswith('other-') or v == 'keep-method') for v in r)]
            for table, values in rows(db).items()}


class MiamiDadeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.numerical = miami.load_inputs()
        cls.payload = json.loads(miami.EXTRACT.read_text())
        cls.expected = miami.build_snapshot(cls.roster, cls.numerical)
        cls.native = {r['school_id']: r for r in cls.roster['roster_links']}

    def test_frozen_pure_population_and_exact_native_point_only_definition(self):
        miami.validate(self.payload, self.expected)
        self.assertEqual(self.payload['dataset'], 'fl-miami-dade-2025')
        self.assertEqual(self.payload['state'], {'id': 'FL', 'name': 'Florida'})
        self.assertEqual(self.payload['region'], 'miami-dade')
        self.assertEqual(self.payload['region_name'], 'Miami-Dade County')
        self.assertEqual(self.payload['release_status'], 'ready')
        self.assertFalse(self.payload['statewide'])
        self.assertEqual(len(self.payload['schools']), 370)
        self.assertTrue(all(s['cohort'] == 'grade-schools' and s['district_id'] == 'FL-13'
                            for s in self.payload['schools']))
        self.assertEqual(self.payload['cohorts'], miami.florida.normalize(miami.roster_audit.load_florida())['cohorts'])
        self.assertTrue(self.payload['cohorts'][0]['allow_point_only'])
        selected = {s['id'] for s in self.payload['schools']}
        self.assertEqual(selected, set(self.numerical['frozen_population']['pure_lower_directory_school_ids']))
        self.assertFalse(selected.intersection(self.numerical['frozen_population']['native_grade_schools_with_mixed_offers']))
        selection = dict(self.payload['selection'])
        digest = selection.pop('sha256')
        self.assertEqual(digest, miami.roster_audit.fingerprint(selection))
        self.assertEqual(self.payload['selection']['policy'], miami.model_audit.POLICY)
        self.assertFalse(self.roster['approved_for_modeling'])
        self.assertFalse(self.numerical['approved_for_modeling'])

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
                outcome = school['outcomes'][subject]
                native = source['subjects'][subject]
                self.assertEqual(outcome['exclusion'], native['district_exclusion'])
                self.assertEqual(outcome['raw']['source_contract_exclusion'], native['source_contract_exclusion'])
                self.assertEqual(outcome['proficiency'], native['native_rate'] if native['district_usable'] else None)
                self.assertTrue(all(outcome[k] is None for k in ['tested', 'valid_score_evidence', 'raw_tested']))
                self.assertIsNone(outcome['raw']['valid_score_count'])
                self.assertIsNone(outcome['raw']['sampling_variance'])
                self.assertFalse(outcome['raw']['interval_availability'])
        self.assertEqual(set(primary), {'13-2531', '13-8016', '13-9013', '13-0331', '13-0351'})
        self.assertEqual(set(missing), {'13-4070', '13-6057', '13-6099', '13-0402', '13-0403',
                                       '13-4328', '13-5119', '13-5219'})
        self.assertTrue(protected)
        audit = self.payload['source_audit']
        self.assertEqual(len(audit['excluded_operational_roster_records']), 160)
        self.assertEqual(len(audit['nonoperational_directory']), 14)
        self.assertEqual([r['school_id'] for r in audit['outside_roster_profiles']], ['13-7006'])
        self.assertEqual([(r['id'], r['raw'][3]) for r in audit['provider_specific_virtual_rows']], [('13-7001', '302')])

    def test_import_twice_preserves_same_state_same_native_id_and_namespaces_every_definition(self):
        with closing(connect(':memory:')) as db:
            db.executescript((ROOT / 'scripts/schema.sql').read_text())
            seed_other(db)
            before = sentinel(db)
            import_snapshot(db, self.payload, miami.EXTRACT)
            first = rows(db)
            import_snapshot(db, self.payload, miami.EXTRACT)
            self.assertEqual(first, rows(db))
            self.assertEqual(before, sentinel(db))
            self.assertEqual(db.execute('SELECT count(*) FROM school WHERE dataset_id=?', (miami.DATASET,)).fetchone()[0], 370)
            self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation WHERE dataset_id=?', (miami.DATASET,)).fetchone()[0], 740)
            self.assertTrue(all(r['tested'] is None for r in db.execute('SELECT tested FROM assessment_observation WHERE dataset_id=?', (miami.DATASET,))))
            self.assertTrue(all(r['id'].startswith(miami.DATASET + ':') for r in db.execute('SELECT id FROM source WHERE dataset_id=?', (miami.DATASET,))))
            definition = dict(db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (miami.DATASET + ':%',)).fetchone())
            cohort = self.payload['cohorts'][0]
            self.assertEqual([definition[k] for k in ['state', 'name', 'year', 'level', 'grades', 'standard', 'source_url']],
                             ['FL', cohort['assessment'], 2025, 'ES', cohort['grades'], cohort['standard'], cohort['source_url']])
            self.assertTrue(all(r['definition_id'] == miami.DATASET + ':income' for r in db.execute('SELECT definition_id FROM economic_observation WHERE dataset_id=?', (miami.DATASET,))))
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())

    def test_full_preparation_twice_is_identical_and_failed_validation_cannot_mutate_database(self):
        with tempfile.TemporaryDirectory(prefix='miami-test-', dir=ROOT / 'data/build') as folder:
            folder = Path(folder)
            database, output = folder / 'schools.sqlite', folder / 'output'
            with closing(connect(database)) as db:
                db.executescript((ROOT / 'scripts/schema.sql').read_text())
                seed_other(db)
                before = sentinel(db)
                db.commit()
            miami.prepare(database, output)
            first = {p.name: p.read_bytes() for p in output.glob('*.json')}
            miami.prepare(database, output)
            self.assertEqual(first, {p.name: p.read_bytes() for p in output.glob('*.json')})
            with closing(connect(database)) as db:
                self.assertEqual(before, sentinel(db))
                self.assertEqual(db.execute('SELECT count(*) FROM model_run WHERE dataset_id=?', (miami.DATASET,)).fetchone()[0], 3)
                self.assertEqual(db.execute('SELECT count(*) FROM model_result WHERE dataset_id=?', (miami.DATASET,)).fetchone()[0], 1071)
                self.assertTrue(all(r['low'] is None and r['high'] is None for r in db.execute('SELECT low, high FROM model_result WHERE dataset_id=?', (miami.DATASET,))))
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
                before_failure = rows(db)
            changed = copy.deepcopy(self.payload)
            changed['schools'][0]['outcomes']['math']['tested'] = 100
            wrong = folder / 'wrong.json'
            wrong.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                miami.prepare(database, output, wrong)
            with closing(connect(database)) as db:
                self.assertEqual(before_failure, rows(db))

    def test_saved_exports_match_every_independent_point_and_directory_exclusion(self):
        self.assertEqual(miami.validate_exports(self.payload, miami.OUTPUT, self.numerical),
                         {f'miami-dade-2025-ES-{s}': 357 for s in miami.model_audit.SUBJECTS})
        schools = json.loads((miami.OUTPUT / 'schools.json').read_text())
        self.assertEqual(len(schools['schools']), 370)
        self.assertEqual(sum(bool(s['metrics']) for s in schools['schools']), 357)
        self.assertTrue(all(v['tested'] is None and v['low'] is None and v['high'] is None
                            and 'variance' not in v and 'sampling_variance' not in v
                            for s in schools['schools'] for v in s['metrics'].values()))
        unavailable = [s for s in schools['schools'] if not s['metrics']]
        self.assertEqual(len(unavailable), 13)
        self.assertTrue(all(set(s['exclusions']) == {'math', 'reading', 'combined'} for s in unavailable))
        self.assertTrue(all('Math:' in s['exclusions']['combined'] and 'ELA:' in s['exclusions']['combined'] for s in unavailable))
        region = json.loads((miami.OUTPUT / 'catalog.json').read_text())['regions'][0]
        self.assertEqual((region['id'], region['name'], region['geography'], region['dataset']),
                         ('miami-dade', 'Miami-Dade County', 'miami-dade', miami.DATASET))
        self.assertFalse(region['statewide'])
        self.assertEqual(region['levels'], ['ES'])
        self.assertIsNone(region['boundaries'])

    def test_population_raw_source_count_or_native_definition_drift_fails_before_import(self):
        mutations = [
            lambda d: d['schools'][0].update(cohort='high'),
            lambda d: d['schools'][0].update(id='13-0441'),
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
        ]
        for mutate in mutations:
            changed = copy.deepcopy(self.payload)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                miami.validate(changed, self.expected)
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / 'wrong-audit.json'
            wrong.write_text('{}')
            with mock.patch.object(miami.model_audit, 'OUTPUT', wrong):
                with self.assertRaisesRegex(ValueError, 'fingerprint'):
                    miami.load_inputs()

    def test_browser_model_history_scope_counts_intervals_and_coverage_drift_are_rejected(self):
        originals = {p.name: p.read_bytes() for p in miami.OUTPUT.glob('*.json')}
        with tempfile.TemporaryDirectory(prefix='miami-export-test-', dir=ROOT / 'data/build') as folder:
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
                ('coverage.json', lambda d: d['cohorts']['grade-schools']['eligible'].update(combined=361)),
                ('coverage.json', lambda d: d['source_audit']['release_basis'].update(historical_audits_approved_for_modeling=True)),
            ]
            for filename, mutate in mutations:
                for name, content in originals.items():
                    (folder / name).write_bytes(content)
                changed = json.loads((folder / filename).read_text())
                mutate(changed)
                (folder / filename).write_text(json.dumps(changed))
                with self.subTest(filename=filename, mutate=mutate), self.assertRaises(ValueError):
                    miami.validate_exports(self.payload, folder, self.numerical)

    def test_historical_audits_are_immutable_and_normalized_generation_is_repeatable(self):
        self.assertEqual(hashlib.sha256(miami.roster_audit.OUTPUT.read_bytes()).hexdigest(), miami.model_audit.ROSTER_SHA)
        self.assertEqual(hashlib.sha256(miami.model_audit.OUTPUT.read_bytes()).hexdigest(), miami.NUMERICAL_SHA)
        with tempfile.TemporaryDirectory() as folder:
            one, two = Path(folder) / 'one.json', Path(folder) / 'two.json'
            miami.extract(one)
            miami.extract(two)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            self.assertEqual(one.read_bytes(), miami.EXTRACT.read_bytes())


if __name__ == '__main__':
    unittest.main()
