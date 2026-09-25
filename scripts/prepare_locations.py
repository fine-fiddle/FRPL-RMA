"""Join the NCES 2023–24 location directory through EDC's explicit school-ID crosswalk."""
import hashlib
import json
from pathlib import Path
import polars as pl
from database import ROOT

NCES = 'https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2324/MapServer/0'
BOUNDARY = 'https://data.isgs.illinois.edu/arcgis/rest/services/Reference/Illinois_State_and_County_Boundaries/MapServer/0'


def prepare():
    pages = [ROOT/f'data/raw/nces-il-locations-{i}.json' for i in [1, 2, 3]]
    payloads = [json.loads(p.read_text()) for p in pages]
    if payloads[-1].get('exceededTransferLimit'):
        raise ValueError('Incomplete NCES pagination')
    locations = {}
    for payload in payloads:
        for feature in payload['features']:
            a = feature['attributes']
            if a['NCESSCH'] in locations:
                raise ValueError('Duplicate NCES school ID')
            locations[a['NCESSCH']] = a
    crosswalk_path = ROOT/'data/raw/edc-il-2024.csv'
    crosswalk = pl.read_csv(crosswalk_path, infer_schema=False).filter(pl.col('DataLevel') == 'School').select('StateAssignedSchID', 'NCESSchoolID').unique()
    if crosswalk['StateAssignedSchID'].is_duplicated().any():
        raise ValueError('Ambiguous state-to-NCES crosswalk')
    joined = []
    for row in crosswalk.sort('StateAssignedSchID').iter_rows(named=True):
        a = locations.get(row['NCESSchoolID'])
        if a and a['LAT'] is not None and a['LON'] is not None and 36.9 <= a['LAT'] <= 42.6 and -91.6 <= a['LON'] <= -87:
            joined.append(dict(school_id=row['StateAssignedSchID'], nces_id=a['NCESSCH'], latitude=a['LAT'], longitude=a['LON']))
    boundary_path = ROOT/'data/raw/illinois-boundary.geojson'
    boundary = json.loads(boundary_path.read_text())
    # D3 expects clockwise exterior rings for polygons smaller than a hemisphere.
    for feature in boundary['features']:
        geometry = feature['geometry']
        polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
        for polygon in polygons:
            for i, ring in enumerate(polygon):
                area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))
                if (i == 0 and area > 0) or (i > 0 and area < 0):
                    ring.reverse()
    (ROOT/'data/illinois/boundary.geojson').write_text(json.dumps(boundary, separators=(',', ':')))
    sources = [dict(path=str(p.relative_to(ROOT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [*pages,crosswalk_path,boundary_path]]
    output = dict(year=2024, locations=joined, sources=sources, coordinates_url=NCES,
        boundary_url=BOUNDARY, crosswalk_url='https://eddatacenter.org/api/data/3.1?state=IL&year=2024',
        note='Exact RCDTS-to-NCES ID join; no name matching or guessed coordinates. Missing locations remain absent from the map.')
    (ROOT/'data/source/illinois-locations.json').write_text(json.dumps(output, separators=(',', ':')))
    print(f'{len(joined)} Illinois school locations matched')


if __name__ == '__main__':
    prepare()
