import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from database import connect
from state_snapshot import import_snapshot
import prepare_los_angeles as la

TABLES = ['dataset', 'source', 'school', 'economic_observation', 'assessment_definition',
          'economic_definition', 'assessment_observation', 'model_run', 'model_result']


def seed_other(db):
    """Sentinel rows cover every canonical table, including another CA model."""
    db.execute("INSERT INTO dataset VALUES ('other-ca','CA','Keep release','Keep population','ready')")
    db.execute("INSERT INTO source VALUES ('other-source','other-ca','other.json','https://example.test/source',?, '2025-01-01')", ('1' * 64,))
    db.execute("INSERT INTO assessment_definition VALUES ('other-assessment','CA','Other test',2025,'ES','3','Keep standard','https://example.test/assessment')")
    db.execute("INSERT INTO economic_definition VALUES ('other-income','Keep income','Keep definition','https://example.test/income')")
    db.execute("INSERT INTO school VALUES ('other-ca','other-school','Keep school','other-district','Keep district',NULL,NULL,'{}','other-source',1)")
    db.execute("INSERT INTO economic_observation VALUES ('other-ca','other-school',2025,'other-income','Keep school',100,30,30,'Keep income','{}','other-source',1)")
    db.execute("INSERT INTO assessment_observation VALUES ('other-ca','other-school','other-assessment','math',40,100,'reported','{}','100','other-source',1)")
    db.execute("INSERT INTO model_run VALUES ('other-model','other-ca','other-assessment','math','keep-method',?,'{}')", ('2' * 64,))
    db.execute("INSERT INTO model_result VALUES ('other-model','other-ca','other-school',40,45,-1,-2,0)")


def sentinel(db):
    return {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')
                    if any(isinstance(v, str) and (v.startswith('other-') or v == 'keep-method') for v in r)]
            for table in TABLES}


class LosAngelesIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.numerical = la.load_inputs()
        cls.payload = json.loads(la.EXTRACT.read_text())
        cls.expected = la.build_snapshot(cls.roster, cls.numerical)

    def test_frozen_pure_population_and_native_definitions(self):
        la.validate(self.payload, self.expected)
        self.assertEqual(self.payload['dataset'], 'ca-lausd-2025')
        self.assertEqual(self.payload['release_status'], 'ready')
        self.assertFalse(self.payload['statewide'])
        self.assertEqual(len(self.payload['schools']), 736)
        self.assertEqual(sum(s['cohort'] == 'grade' for s in self.payload['schools']), 589)
        self.assertEqual(sum(s['cohort'] == 'high' for s in self.payload['schools']), 147)
        self.assertEqual(self.payload['cohorts'], la.cohorts())
        self.assertTrue(all(s['district_id'] == 'CA-1964733' for s in self.payload['schools']))
        mixed = {s['school_id'] for s in self.roster['roster_links'] if s.get('scope') == 'mixed'}
        self.assertFalse(mixed.intersection(s['id'] for s in self.payload['schools']))
        selection = dict(self.payload['selection'])
        saved = selection.pop('sha256')
        self.assertEqual(saved, la.roster_audit.fingerprint(selection))
        self.assertFalse(self.roster['approved_for_modeling'])
        self.assertFalse(self.numerical['approved_for_modeling'])

    def test_applicability_missingness_and_native_counts_are_preserved(self):
        no_applicable = {'grade': 0, 'high': 0}
        for school in self.payload['schools']:
            level = 'ES' if school['cohort'] == 'grade' else 'HS'
            native = next(r for r in self.roster['roster_links'] if r['school_id'] == school['id'])
            if not school['outcomes']['math']['raw']['applicable']:
                no_applicable[school['cohort']] += 1
            for subject in ['math', 'reading']:
                observation = school['outcomes'][subject]
                original = native['assessments'][level][subject]
                self.assertEqual(observation['raw']['expected_grade_records'], original['expected_grade_records'])
                self.assertEqual(observation['exclusion'], original['exclusion'])
                if original['usable']:
                    self.assertEqual(observation['tested'], sum(int(r['raw']['Overall Total']) for r in original['expected_grade_records']))
                    self.assertEqual(observation['proficiency'], 100 * sum(int(r['raw']['Count Standard Met and Above']) for r in original['expected_grade_records']) / observation['tested'])
                    self.assertTrue(observation['valid_score_evidence'])
                else:
                    self.assertIsNone(observation['proficiency'])
                    self.assertIsNone(observation['tested'])
                    self.assertIsNone(observation['valid_score_evidence'])
        self.assertEqual(no_applicable, {'grade': 17, 'high': 3})

    def test_import_twice_preserves_every_other_canonical_table_and_namespaces_sources(self):
        db = connect(':memory:')
        self.addCleanup(db.close)
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        seed_other(db)
        before = sentinel(db)
        import_snapshot(db, self.payload, la.EXTRACT)
        first = {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in TABLES}
        import_snapshot(db, self.payload, la.EXTRACT)
        self.assertEqual(first, {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in TABLES})
        self.assertEqual(before, sentinel(db))
        self.assertEqual(db.execute('SELECT count(*) FROM school WHERE dataset_id=?', (la.DATASET,)).fetchone()[0], 736)
        self.assertTrue(all(r['id'].startswith(la.DATASET + ':') for r in db.execute('SELECT id FROM source WHERE dataset_id=?', (la.DATASET,))))
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())

    def test_full_preparation_twice_is_identical_and_keeps_other_release_models(self):
        with tempfile.TemporaryDirectory(prefix='la-test-', dir=ROOT / 'data/build') as folder:
            folder = Path(folder)
            database, output = folder / 'schools.sqlite', folder / 'output'
            with connect(database) as db:
                db.executescript((ROOT / 'scripts/schema.sql').read_text())
                seed_other(db)
                before = sentinel(db)
            la.prepare(database, output)
            first = {p.name: p.read_bytes() for p in output.glob('*.json')}
            la.prepare(database, output)
            self.assertEqual(first, {p.name: p.read_bytes() for p in output.glob('*.json')})
            with connect(database) as db:
                self.assertEqual(before, sentinel(db))
                self.assertEqual(db.execute('SELECT count(*) FROM model_run WHERE dataset_id=?', (la.DATASET,)).fetchone()[0], 6)
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            bad = copy.deepcopy(self.payload)
            bad['schools'][0]['income'] += 1
            bad_path = folder / 'bad-extract.json'
            bad_path.write_text(json.dumps(bad))
            with connect(database) as db:
                before_failure = {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in TABLES}
            with self.assertRaises(ValueError):
                la.prepare(database, output, bad_path)
            with connect(database) as db:
                self.assertEqual(before_failure, {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in TABLES})

    def test_saved_exports_match_every_independent_district_result(self):
        counts = la.validate_exports(self.payload, la.OUTPUT, self.numerical)
        self.assertEqual(sorted(counts.values()), [136, 137, 137, 561, 561, 561])
        descriptor = json.loads((la.OUTPUT / 'catalog.json').read_text())['regions'][0]
        self.assertEqual(descriptor['id'], 'los-angeles')
        self.assertEqual(descriptor['name'], 'Los Angeles Unified')
        self.assertEqual(descriptor['dataset'], la.DATASET)
        self.assertEqual(descriptor['geography'], 'los-angeles')
        self.assertFalse(descriptor['statewide'])
        self.assertTrue(descriptor['comparison'].startswith('Los Angeles Unified'))
        self.assertIsNone(descriptor['boundaries'])
        self.assertEqual(descriptor['audit'], 'data/los-angeles/coverage.json')

    def test_source_scope_policy_or_count_drift_fails_before_import(self):
        mutations = [
            lambda d: d['schools'][0].update(cohort='high'),
            lambda d: d['schools'][0].update(id='19647330000000'),
            lambda d: d['schools'][0]['outcomes']['math'].update(tested=999999),
            lambda d: d['schools'][0]['outcomes']['math']['raw'].update(expected_grades=[13]),
            lambda d: d['sources']['numerical_audit'].update(sha256='0' * 64),
            lambda d: d['selection']['policy'].update(school_types='Drop alternatives'),
            lambda d: d['selection']['directory_school_ids'].pop(),
            lambda d: d.update(statewide=True),
        ]
        for mutation in mutations:
            changed = copy.deepcopy(self.payload)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                la.validate(changed, self.expected)

    def test_drifted_historical_summaries_and_duplicate_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            original = {p.name: p.read_bytes() for p in la.OUTPUT.glob('*.json')}
            for filename, mutate in [
                ('history.json', lambda d: d['models'][0].update(slope=-99)),
                ('schools.json', lambda d: d['history_models'].pop()),
                ('schools.json', lambda d: d['schools'].append(copy.deepcopy(d['schools'][0]))),
                ('schools.json', lambda d: next(s for s in d['schools'] if s['metrics'])['metrics']['math'].update(studentized=999)),
            ]:
                for name, content in original.items():
                    (folder / name).write_bytes(content)
                changed = json.loads((folder / filename).read_text())
                mutate(changed)
                (folder / filename).write_text(json.dumps(changed))
                with self.subTest(filename=filename, mutate=mutate), self.assertRaises(ValueError):
                    la.validate_exports(self.payload, folder, self.numerical)

    def test_historical_audit_fingerprints_remain_immutable(self):
        self.assertEqual(hashlib.sha256(la.roster_audit.OUTPUT.read_bytes()).hexdigest(), la.model_audit.ROSTER_SHA)
        self.assertEqual(hashlib.sha256(la.model_audit.OUTPUT.read_bytes()).hexdigest(), la.NUMERICAL_SHA)


if __name__ == '__main__':
    unittest.main()
