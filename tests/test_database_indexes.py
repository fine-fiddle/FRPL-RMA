import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from database import connect, IMPORT_INDEXES


class DatabaseIndexTests(unittest.TestCase):
    def test_old_store_gets_child_indexes_without_changing_rows_or_constraints(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'store.sqlite'
            with sqlite3.connect(path) as db:
                db.executescript((ROOT / 'scripts/schema.sql').read_text())
                for name in IMPORT_INDEXES:
                    db.execute(f'DROP INDEX {name}')
                db.execute("INSERT INTO dataset VALUES ('keep','IL','Existing','Existing','ready')")
            with connect(path) as db:
                self.assertEqual(tuple(db.execute('SELECT * FROM dataset').fetchone()),
                    ('keep', 'IL', 'Existing', 'Existing', 'ready'))
                self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0], 1)
                plan = ' '.join(str(r[3]) for r in db.execute(
                    'EXPLAIN QUERY PLAN SELECT 1 FROM model_result WHERE dataset_id=? AND school_id=?', ('keep', '1')))
                self.assertIn('model_result_by_school', plan)
                self.assertNotIn('SCAN', plan)
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            with connect(path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM dataset').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
