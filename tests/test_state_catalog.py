import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from state_catalog import check_catalog_preservation, local_asset, merge_state_exports


class StateCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'data/indiana'
        self.folder.mkdir(parents=True)
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript((ROOT / 'scripts/schema.sql').read_text())
        self.db.execute("INSERT INTO dataset VALUES ('in-2025','IN','Indiana','ILEARN','ready')")
        self.db.execute("INSERT INTO assessment_definition VALUES ('in-test','IN','ILEARN',2025,'ES','3–8','State standards','https://example.org')")
        self.model = dict(year=2025, level='ES', assessment='ILEARN', subject='combined', n=12,
                          intercept=70, slope=-.3, r2=.5)
        self.db.execute('INSERT INTO model_run VALUES (?,?,?,?,?,?,?)',
                        ('in-model', 'in-2025', 'in-test', 'combined', 'ols-studentized-v1', 'a'*64,
                         json.dumps(self.model)))
        self.db.execute("INSERT INTO source VALUES ('in-source','in-2025','data/source/in.json','https://example.org',?, '2026-10-09')", ('a'*64,))
        self.metric = dict(actual=60, predicted=65, residual=-5, studentized=-.75, low=-1.1, high=-.4,
                           tested=100, cohort_n=12)
        for i in range(1, 13):
            key = f'{i:03}'
            self.db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                ('in-2025', key, key, '1', 'District', None, None, '{}', 'in-source', i))
            for subject, count in [('math', 100), ('reading', 120)]:
                self.db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    ('in-2025', key, 'in-test', subject, 60, count, 'reported', None, None, 'in-source', i))
            self.db.execute('INSERT INTO model_result VALUES (?,?,?,?,?,?,?,?)',
                ('in-model', 'in-2025', key, 60, 65, -.75, -1.1, -.4))
        self.output = dict(schools=[dict(id='001', level='ES', metrics={'combined': dict(self.metric)})],
                           levels={'ES': dict(year=2025, assessment='ILEARN')},
                           models={'ES': dict(math=None, reading=None, combined=self.model)},
                           methodology=dict(summary='State source definitions'))
        self.payload = dict(schema_version=1, state=dict(id='IN', name='Indiana'), regions=[dict(
            id='indiana', name='Grade schools', dataset='in-2025', status='ready',
            geography='indiana', comparison='Indiana ILEARN', model_scope='Public schools',
            map_source='Map unavailable', levels=['ES'], schools='data/indiana/schools.json',
            boundaries=None)])
        self.write_files()

    def write_files(self):
        (self.folder / 'schools.json').write_text(json.dumps(self.output))
        (self.folder / 'catalog.json').write_text(json.dumps(self.payload))

    def catalog(self):
        return dict(states=[dict(id='IL', name='Illinois', regions=[dict(id='chicago', status='ready')]),
                            dict(id='NY', name='New York', regions=[dict(id='nyc', status='ready')]),
                            dict(id='WI', name='Wisconsin', regions=[dict(id='wisconsin', status='ready')])])

    def test_adds_ready_state_and_preserves_existing_regions(self):
        catalog = self.catalog()
        merge_state_exports(self.db, catalog, self.root)
        self.assertEqual([s['id'] for s in catalog['states']], ['IL', 'IN', 'NY', 'WI'])
        self.assertEqual(catalog['states'][0]['regions'], [dict(id='chicago', status='ready')])
        region = catalog['states'][1]['regions'][0]
        self.assertTrue(region['statewide'])
        self.assertEqual(region['levels'], ['ES'])

    def test_missing_dataset_is_not_published_and_stale_models_fail(self):
        self.db.execute("UPDATE dataset SET status='awaiting_source'")
        catalog = self.catalog()
        merge_state_exports(self.db, catalog, self.root)
        self.assertEqual(len(catalog['states']), 3)
        self.db.execute("UPDATE dataset SET status='ready'")
        self.output['models']['ES']['combined'] = dict(self.model, n=13)
        self.write_files()
        with self.assertRaisesRegex(ValueError, 'differs from SQLite'):
            merge_state_exports(self.db, self.catalog(), self.root)

    def test_summary_must_match_the_year_level_assessment_and_subject_slot(self):
        original = copy.deepcopy(self.output)
        for field, value in [('year', 2024), ('assessment', 'Other assessment')]:
            with self.subTest(field=field):
                self.output = copy.deepcopy(original)
                self.output['levels']['ES'][field] = value
                self.write_files()
                with self.assertRaisesRegex(ValueError, 'Exported model differs'):
                    merge_state_exports(self.db, self.catalog(), self.root)
        self.output = copy.deepcopy(original)
        self.output['models']['ES']['math'] = dict(self.model)
        self.write_files()
        with self.assertRaisesRegex(ValueError, 'Exported model differs'):
            merge_state_exports(self.db, self.catalog(), self.root)

    def test_corrupted_or_missing_served_points_fail_but_directory_subset_is_valid(self):
        # The full fitted population has twelve results, while the served
        # directory intentionally displays only one. It must still match exactly.
        merge_state_exports(self.db, self.catalog(), self.root)
        original = copy.deepcopy(self.output)
        for field in ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'tested', 'cohort_n']:
            with self.subTest(field=field):
                self.output = copy.deepcopy(original)
                self.output['schools'][0]['metrics']['combined'][field] = 999
                self.write_files()
                with self.assertRaisesRegex(ValueError, 'school metric differs'):
                    merge_state_exports(self.db, self.catalog(), self.root)
        self.output = copy.deepcopy(original)
        self.output['schools'][0]['metrics'] = {}
        self.write_files()
        with self.assertRaisesRegex(ValueError, 'Missing exported school metric'):
            merge_state_exports(self.db, self.catalog(), self.root)

    def test_historical_served_points_and_protected_counts_match_canonical(self):
        self.db.execute("UPDATE assessment_observation SET tested=NULL WHERE school_id='001' AND subject='math'")
        self.db.execute("UPDATE model_result SET low=NULL,high=NULL WHERE model_id='in-model'")
        metric = dict(self.metric, tested=None, low=None, high=None)
        self.output['schools'][0]['metrics']['combined'] = dict(metric)
        self.output['schools'][0]['history'] = [dict(school_id='001', year=2025,
            level='ES', assessment='ILEARN', subjects={'combined': dict(metric)})]
        self.write_files()
        merge_state_exports(self.db, self.catalog(), self.root)
        self.output['schools'][0]['history'][0]['subjects']['combined']['studentized'] = 999
        self.write_files()
        with self.assertRaisesRegex(ValueError, 'school metric differs'):
            merge_state_exports(self.db, self.catalog(), self.root)

    def test_rejects_wrong_state_and_nonlocal_or_missing_assets(self):
        self.db.execute("UPDATE dataset SET state='OH'")
        with self.assertRaisesRegex(ValueError, 'differs from SQLite'):
            merge_state_exports(self.db, self.catalog(), self.root)
        for value in ['/tmp/schools.json', '../schools.json', 'data/../schools.json',
                      'https://example.org/schools.json', 'data/missing.json']:
            with self.assertRaises(ValueError):
                local_asset(self.root, value)

    def test_reduced_catalog_requires_explicit_override(self):
        destination = self.root / 'manifest.json'
        previous = self.catalog()
        destination.write_text(json.dumps(previous))
        reduced = dict(states=previous['states'][:1])
        with self.assertRaisesRegex(ValueError, 'NY/nyc'):
            check_catalog_preservation(reduced, destination)
        self.assertEqual(json.loads(destination.read_text()), previous)
        check_catalog_preservation(reduced, destination, allow_reduced=True)


if __name__ == '__main__':
    unittest.main()
