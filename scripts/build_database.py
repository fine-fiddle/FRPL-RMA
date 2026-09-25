"""Build a reproducible local SQLite database; never download implicitly."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from database import ROOT, DEFAULT_DB, connect, import_chicago, import_illinois


def build(destination=DEFAULT_DB, statewide=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, staging = tempfile.mkstemp(suffix='.sqlite', dir=destination.parent)
    os.close(handle)
    try:
        db = connect(staging)
        try:
            db.executescript((ROOT/'scripts/schema.sql').read_text())
            with db:
                import_chicago(db)
                if statewide:
                    import_illinois(db, Path(statewide))
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            summary = [dict(r) for r in db.execute('''
                SELECT d.id,d.status,count(s.school_id) schools
                FROM dataset d JOIN school s ON d.id=s.dataset_id GROUP BY d.id''')]
        finally:
            db.close()
        os.replace(staging, destination)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--illinois', type=Path, help='Path to official 2024 Report Card XLSX')
    args = parser.parse_args()
    build(args.database, args.illinois)
