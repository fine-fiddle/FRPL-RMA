import json
from pathlib import Path
import sqlite3
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from database import connect, import_chicago, import_illinois, chicago_frames, save_models
from prepare_data import build_history


class DatabaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = connect(':memory:')
        cls.db.executescript((ROOT/'scripts/schema.sql').read_text())
        import_chicago(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_chicago_inputs_round_trip_without_type_order_or_value_changes(self):
        actual = chicago_frames(self.db)
        for frame, filename in zip(actual, ['cps-profile-sy2324.csv', 'assessments-history.csv', 'income-history.csv']):
            expected = pl.read_csv(ROOT/'data/source'/filename, infer_schema=False)
            self.assertEqual(frame.to_dicts(), expected.to_dicts())

    def test_all_historical_results_equal_committed_baseline(self):
        _, observations, income = chicago_frames(self.db)
        records, models = build_history(observations, income)
        expected = json.loads((ROOT/'data/history.json').read_text())
        self.assertEqual(records, expected['records'])
        self.assertEqual(models, expected['models'])
        save_models(self.db, records, models)
        self.assertEqual(self.db.execute('SELECT count(*) FROM model_run').fetchone()[0], 51)
        expected_results = sum(len(r['subjects']) for r in records)
        self.assertEqual(self.db.execute('SELECT count(*) FROM model_result').fetchone()[0], expected_results)
        save_models(self.db, records, models)
        self.assertEqual(self.db.execute('SELECT count(*) FROM model_result').fetchone()[0], expected_results)

    def test_database_rejects_duplicate_observations_and_invalid_percentages(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('INSERT INTO economic_observation SELECT * FROM economic_observation LIMIT 1')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('UPDATE assessment_observation SET proficiency=101 WHERE rowid=1')
        self.assertFalse(self.db.execute('PRAGMA foreign_key_check').fetchall())

    def test_ids_and_raw_missing_values_are_preserved(self):
        self.assertGreater(self.db.execute(
            "SELECT count(*) FROM assessment_observation WHERE proficiency IS NULL").fetchone()[0], 0)
        self.assertTrue(all(len(row[0]) == 6 for row in self.db.execute('SELECT school_id FROM school')))

    def test_statewide_adapter_keeps_missing_counts_and_separate_assessments(self):
        db = connect(':memory:')
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        headers = ['RCDTS', 'Type', 'School Name', 'District', 'City', 'County', 'School Type',
                   'Grades Served', '# Student Enrollment', '# Student Enrollment - Low Income',
                   '% Student Enrollment - Low Income']
        sid = '010010010260001'
        sheets = {'General': [headers,
            [sid, 'School', 'Example', 'District', 'City', 'County', 'High School', '7 - 12', '200', '75', '37.5'],
            ['010010010260000', 'District', None, 'District', 'City', 'County', None, None, '200', '75', '37.5']]}
        for assessment in ['IAR', 'SAT']:
            sheets[assessment] = [
                ['RCDTS', 'Type', f'{assessment} Math Proficiency Rate - Total', f'{assessment} ELA Proficiency Rate - Total'],
                [sid, 'School', '0.0' if assessment == 'IAR' else '*', '50.0']]
        workbook = MagicMock()
        workbook.__getitem__.side_effect = lambda sheet: SimpleNamespace(values=iter(sheets[sheet]))
        with patch('openpyxl.load_workbook', return_value=workbook):
            import_illinois(db, ROOT/'data/source/income-history.csv')
        self.assertEqual(db.execute('SELECT count(*) FROM school').fetchone()[0], 1)
        self.assertEqual(db.execute('SELECT count(*) FROM assessment_observation').fetchone()[0], 4)
        self.assertEqual(db.execute('SELECT count(tested) FROM assessment_observation').fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT proficiency FROM assessment_observation WHERE raw_value='0.0'").fetchone()[0], 0)
        suppressed = db.execute("SELECT proficiency,status FROM assessment_observation WHERE raw_value='*'").fetchone()
        self.assertEqual(tuple(suppressed), (None, 'suppressed_or_not_reported'))
        self.assertEqual(db.execute('SELECT status FROM dataset').fetchone()[0], 'awaiting_tested_counts')
        db.close()


if __name__ == '__main__':
    unittest.main()
