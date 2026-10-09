"""Rebuild every audited state descriptor from its committed extract, offline."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from database import ROOT, DEFAULT_DB


def adapter_scripts(root=ROOT):
    root=Path(root).resolve()
    scripts=set()
    for descriptor in sorted((root/'data').glob('*/catalog.json')):
        payload=json.loads(descriptor.read_text())
        script=payload.get('prepare_script')
        if payload.get('schema_version') != 1 or not re.fullmatch(r'scripts/prepare_[a-z_]+\.py',script or ''):
            raise ValueError(f'Missing or invalid offline adapter in {descriptor}')
        path=(root/script).resolve()
        if not path.is_relative_to(root/'scripts') or not path.is_file():
            raise ValueError(f'Missing checked-in adapter: {script}')
        scripts.add(path)
    return sorted(scripts)


def prepare(database=DEFAULT_DB):
    database=Path(database).resolve()
    if not database.is_file():
        raise ValueError('Build the canonical SQLite database before rebuilding state adapters')
    scripts=adapter_scripts()
    for script in scripts:
        print(f'Rebuilding {script.stem.removeprefix("prepare_")}',flush=True)
        subprocess.run([sys.executable,str(script),'--database',str(database)],cwd=ROOT,check=True)
    print(f'Rebuilt {len(scripts)} audited adapters; run export_catalog.py to publish the catalog.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,default=DEFAULT_DB)
    args=parser.parse_args()
    prepare(args.database)
