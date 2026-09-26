"""Validate historical official CPS IDs against the 2024 NCES/state-ID crosswalk."""
import hashlib
import json
from collections import Counter
import polars as pl
from database import ROOT

OUTPUT = ROOT/'data/source/cps-illinois-crosswalk.json'
URL = 'https://data.cityofchicago.org/resource/c7jj-qjvh.json?$limit=5000'


def validate(rows, profiles, locations):
    cps_counts = Counter(r.get('schoolid') for r in rows)
    state_counts = Counter(r.get('isbe_id') for r in rows)
    matches, rejected = [], []
    for row in rows:
        cps, sid = row.get('schoolid'), row.get('isbe_id')
        nces = row.get('nces_id', '').removesuffix('.0')
        reason = ('Missing identifier' if not cps or not sid or not nces else
                  'Ambiguous historical mapping' if cps_counts[cps] != 1 or state_counts[sid] != 1 else
                  'Absent from 2024 CPS profiles' if cps not in profiles else
                  'Absent from 2024 state/NCES crosswalk' if sid not in locations else
                  'NCES ID disagrees with 2024 crosswalk' if nces != locations[sid]['nces_id'] else None)
        evidence = dict(cps_id=cps, school_id=sid, nces_id=nces or None)
        if reason:
            rejected.append(dict(**evidence, reason=reason))
        else:
            matches.append(evidence)
    return sorted(matches, key=lambda r:r['school_id']), rejected


def prepare():
    original = ROOT/'data/raw/cps-identifiers-2014.json'
    profile_path = ROOT/'data/source/cps-profile-sy2324.csv'
    location_path = ROOT/'data/source/illinois-locations.json'
    profiles = {r['School_ID']:r for r in pl.read_csv(profile_path, infer_schema=False).to_dicts()}
    locations = {r['school_id']:r for r in json.loads(location_path.read_text())['locations']}
    rows = json.loads(original.read_text())
    if len(rows) >= 5000:
        raise ValueError('Crosswalk may be truncated by API limit')
    matches, rejected = validate(rows, profiles, locations)
    output = dict(source_year=2014, validation_year=2024, matches=matches, rejected=rejected,
                  sources=[dict(path=str(p.relative_to(ROOT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                           for p in [original,profile_path,location_path]], url=URL,
                  note='Official historical CPS/state/NCES identifiers; only unique mappings with a current CPS profile and the same NCES/state ID pair in the 2024 crosswalk are accepted. No name matching. Does not merge model populations or establish continuity for every intervening year.')
    OUTPUT.write_text(json.dumps(output, separators=(',', ':'), allow_nan=False))
    print(json.dumps(dict(accepted=len(matches), excluded=dict(Counter(r['reason'] for r in rejected))), indent=2))


if __name__ == '__main__':
    prepare()
