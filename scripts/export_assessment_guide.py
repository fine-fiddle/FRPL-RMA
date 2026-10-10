"""Export a source-bound explanation of released assessments and a 50-state map.

This reads the committed catalog/registry and served model descriptions. It does
not import observations, approve blocked states, or change any fitted model.
Ordinary rebuilding is offline; --extract-boundaries requires the audited Census
archive, while subsequent runs retain and verify the committed geometry.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from urllib.parse import urlencode
import zipfile

from database import ROOT

BOUNDARY_ARCHIVE = ROOT / 'data/raw/cb_2024_us_state_500k.zip'
BOUNDARY_URL = 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_500k.zip'
BOUNDARY_SHA256 = '3e81cbb6cf5f60d9b01ef3e730afa14d61ce5f784252a0b33a696135e71447bc'
SIMPLIFICATION_DEGREES = .008
PSAT_SOURCE_ID = 'mi-psat8-2025:psat8_levels'
PSAT_SOURCE_SHA256 = 'e0636c07a99d476e1a8a96b636494514e712bd4f8e67fb8a4cab5b20c2e1f69f'
PSAT_SOURCE_URL = ('https://www.michigan.gov/mde/-/media/Project/Websites/mde/OEAA/PSAT/'
                   'PSAT-8_9-for-Grade-8-Performance-Level-Information.pdf?'
                   'hash=5262B1C6A190B3DEE23168F8015F123B&rev=ae6c6e11dc744013bd37b586f30c2b16')
PROVIDER_EVIDENCE_PATH = 'data/source/assessment-provider-evidence.json'
PROVIDER_EVIDENCE_SHA256 = '4f33aeea601ffe679a53bcfef01cc7212d44e484e2220a097aa93dae01aae6e2'
DESCRIPTION = (
    'Latest assessments included in this project, separately by released dataset '
    'and model population. A year is the ending year of the school year. Test '
    'names, grades and proficiency definitions describe those source populations; '
    'they are not a common achievement scale or a ranking of state ambition. '
    'Shared colors identify an explicitly named test family, not equivalent '
    'thresholds. Provider identities and relative threshold comparisons remain '
    'unavailable unless supported by separately audited evidence. States '
    'without released comparisons remain visible with their source-audit status.'
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def registry_states(registry):
    states = registry.get('states', [])
    if len(states) != 50 or len({s['id'] for s in states}) != 50:
        raise ValueError('Expected exactly 50 unique registry states')
    if len({s['fips'] for s in states}) != 50:
        raise ValueError('Duplicate registry FIPS')
    for state in states:
        if not re.fullmatch(r'[A-Z]{2}', state['id']) or not re.fullmatch(r'\d{2}', state['fips']):
            raise ValueError('Invalid registry state identifier')
        if state['id'] in {'DC', 'PR', 'GU', 'VI', 'AS', 'MP'}:
            raise ValueError('Non-state in 50-state registry')
    return sorted(states, key=lambda s: s['name'])


def local_path(root, value):
    """Catalog assets must stay inside the repository; never follow remote URLs."""
    if not isinstance(value, str) or not value or '://' in value or '?' in value or '#' in value:
        raise ValueError('Expected a repository-relative asset')
    root = Path(root).resolve()
    path = (root / value).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError('Asset outside repository')
    return path


def assessment_family(name):
    """Group explicitly named Smarter Balanced/SBAC, without guessing lineage.

    The remaining native names are minimally shortened for a filter label. ISAT,
    OSAS, MCAS/RICAS and PARCC descendants are not presumed to be one test.
    """
    if re.search(r'\b(?:Smarter Balanced|SBAC)\b', name):
        return 'Smarter Balanced'
    family = name.split(' · ', 1)[0]
    family = re.sub(r'\s+grades?\s+\d+(?:[–−-]\d+)?(?:\s.*)?$', '', family)
    family = re.sub(r'\s+\((?:pre-)?\d{4}-\d{2} (?:levels|standards)\)$', '', family)
    return family


def load_provider_evidence(path=ROOT / PROVIDER_EVIDENCE_PATH):
    """Use the reviewed extract offline; changed evidence needs a new audit."""
    if digest(path) != PROVIDER_EVIDENCE_SHA256:
        raise ValueError('Assessment provider evidence changed; a new source audit is required')
    evidence = json.loads(Path(path).read_text())
    if evidence.get('schema_version') != 1:
        raise ValueError('Unsupported assessment provider evidence schema')
    return evidence


def provider_binding(definition, evidence):
    """Bind a role to an exact audited definition, never inherit it by name."""
    binding = next((b for b in evidence['bindings']
                    if b['definition']['id'] == definition['id']), None)
    if binding and any(definition.get(key) != value
                       for key, value in binding['definition'].items()):
        raise ValueError('Audited assessment provider definition changed')
    return binding


def build_guide(manifest, registry, root=ROOT):
    states = registry_states(registry)
    known = {s['id'] for s in states}
    source_by_id = {s['id']: s for s in manifest.get('sources', [])}
    provider_evidence = load_provider_evidence(local_path(root, PROVIDER_EVIDENCE_PATH))
    provider_evidence_sources = {s['id']: s for s in provider_evidence['sources']}
    ready_regions = {}
    model_keys = {}
    for state in manifest['states']:
        if state['id'] not in known:
            raise ValueError('Catalog state outside registry')
        for region in state['regions']:
            if region['status'] != 'ready':
                continue
            dataset = region['dataset']
            ready_regions.setdefault((state['id'], dataset), []).append(region)
            # A dataset can serve distinct ordinary/mixed populations. Exact
            # model descriptions bind links to the relevant regional export.
            payload = json.loads(local_path(root, region['schools']).read_text())
            keys = set()
            for level, subjects in payload.get('models', {}).items():
                for model in subjects.values():
                    if model:
                        keys.add((model['year'], level, model['assessment']))
            model_keys[(state['id'], region['id'])] = keys

    ready_definitions = []
    latest = {}
    for definition in manifest['assessments']:
        dataset = definition['id'].split(':', 1)[0]
        if (definition['state'], dataset) not in ready_regions:
            continue
        ready_definitions.append((dataset, definition))
        key = (dataset, definition['level'])
        latest[key] = max(latest.get(key, 0), definition['year'])

    rows_by_state = {s['id']: [] for s in states}
    provider_sources = {}
    for dataset, definition in ready_definitions:
        if definition['year'] != latest[(dataset, definition['level'])]:
            continue
        regions = []
        for region in ready_regions[(definition['state'], dataset)]:
            if (definition['year'], definition['level'], definition['name']) not in model_keys[(definition['state'], region['id'])]:
                continue
            regions.append(dict(id=region['id'], name=region['name'],
                                url='./?' + urlencode(dict(state=definition['state'], region=region['id'],
                                                          level=definition['level'])),
                                model_scope=region.get('model_scope')))
        if not regions:
            raise ValueError(f'Latest assessment has no matching served model: {definition["id"]}')
        row = dict(definition, dataset_id=dataset,
                   family=assessment_family(definition['name']), provider=None,
                   provider_source_url=None, provider_role=None,
                   provider_evidence_ids=[],
                   ambition_comparison=None, regions=regions)
        binding = provider_binding(definition, provider_evidence)
        if binding:
            row.update(provider=binding['provider'], provider_role=binding['provider_role'],
                       provider_source_url=provider_evidence_sources[binding['primary_source']]['url'],
                       provider_evidence_ids=binding['evidence_sources'])
            for source_id in binding['evidence_sources']:
                provider_sources[source_id] = dict(provider_evidence_sources[source_id],
                    role=provider_evidence_sources[source_id].get('role',
                        'Audited consortium developer and 2024–25 role-scope evidence'))
        if dataset == 'mi-psat8-2025' and definition['year'] == 2025:
            if definition['state'] != 'MI' or definition['name'] != 'Michigan PSAT 8/9 · grade 8 · 2025':
                raise ValueError('Michigan PSAT owner evidence is bound to its audited definition')
            evidence = source_by_id.get(PSAT_SOURCE_ID)
            if not evidence or evidence.get('sha256') != PSAT_SOURCE_SHA256 or evidence.get('url') != PSAT_SOURCE_URL:
                raise ValueError('Missing or changed audited Michigan PSAT provider evidence')
            row.update(provider='College Board', provider_source_url=evidence['url'],
                       provider_role='Assessment owner and publisher',
                       provider_evidence_ids=[PSAT_SOURCE_ID])
            provider_sources[PSAT_SOURCE_ID] = dict(evidence, role='Audited PSAT owner and grade-8 benchmark evidence')
        rows_by_state[definition['state']].append(row)

    output_states = []
    for state in states:
        blocker = state.get('blocker_evidence', {})
        guide = state.get('existing_release', {}).get('guide') or blocker.get('guide')
        if guide:
            local_path(root, guide)
        rows = sorted(rows_by_state[state['id']], key=lambda r: (r['level'], r['dataset_id'], r['name'], r['id']))
        output_states.append(dict(id=state['id'], name=state['name'], fips=state['fips'],
                                  status=state['status'], guide=guide,
                                  blocker_summary=blocker.get('summary'), assessments=rows))
    # Avoid a changing count in the explanatory text when more states are audited.
    unavailable = sum(not s['assessments'] for s in output_states)
    description = DESCRIPTION.replace('The 11 states', f'The {unavailable} states')
    return dict(schema_version=1, description=description,
                sources=[dict(id='released-assessment-definitions', path='data/manifest.json',
                              role='Exact stored proficiency definitions and source URLs'),
                         dict(id='50-state-expansion-registry', path='data/source/state-expansion.json',
                              role='State identifiers, publication status and audit guides'),
                         *provider_sources.values()], states=output_states)


def signed_area(ring):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])) / 2


def distance_squared(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = dx * dx + dy * dy
    t = max(0, min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length)) if length else 0
    return (point[0] - start[0] - t * dx) ** 2 + (point[1] - start[1] - t * dy) ** 2


def simplify_line(points, tolerance):
    """Iterative Ramer-Douglas-Peucker with a documented geographic tolerance."""
    keep = {0, len(points) - 1}
    pending = [(0, len(points) - 1)]
    while pending:
        first, last = pending.pop()
        farthest, distance = None, tolerance * tolerance
        for i in range(first + 1, last):
            value = distance_squared(points[i], points[first], points[last])
            if value > distance:
                farthest, distance = i, value
        if farthest is not None:
            keep.add(farthest)
            pending.extend([(first, farthest), (farthest, last)])
    return [points[i] for i in sorted(keep)]


def simplify_ring(points, tolerance=SIMPLIFICATION_DEGREES):
    if len(points) < 4 or points[0] != points[-1] or signed_area(points) == 0:
        raise ValueError('Invalid native boundary ring')
    # Two open arcs avoid collapsing a closed ring to its repeated endpoint.
    split = max(range(1, len(points) - 1), key=lambda i: distance_squared(points[i], points[0], points[0]))
    simplified = simplify_line(points[:split + 1], tolerance) + simplify_line(points[split:], tolerance)[1:]
    original_area = signed_area(points)
    # Preserve tiny islands, winding, and rings whose area is materially altered.
    if (len(simplified) < 4 or signed_area(simplified) * original_area <= 0
            or abs(signed_area(simplified) - original_area) > abs(original_area) * .1):
        simplified = points
    result = [[round(x, 5), round(y, 5)] for x, y in simplified]
    if len({tuple(p) for p in result[:-1]}) < 3 or signed_area(result) == 0:
        result = [list(p) for p in simplified]
    # GeoJSON consumed by D3 needs clockwise exterior rings for small polygons.
    if signed_area(result) > 0:
        result.reverse()
    return result


def dbf_records(data):
    count = struct.unpack_from('<I', data, 4)[0]
    header, record_size = struct.unpack_from('<HH', data, 8)
    fields, position = [], 32
    while data[position] != 13:
        fields.append((data[position:position + 11].split(b'\0')[0].decode(), data[position + 16]))
        position += 32
    rows = []
    for i in range(count):
        start = header + i * record_size
        if data[start] != 32:
            raise ValueError('Unexpected deleted Census record')
        offset, row = start + 1, {}
        for field, length in fields:
            row[field] = data[offset:offset + length].decode('utf-8').strip()
            offset += length
        rows.append(row)
    return rows


def extract_boundaries(registry, archive=BOUNDARY_ARCHIVE):
    states = registry_states(registry)
    by_fips = {s['fips']: s for s in states}
    if digest(archive) != BOUNDARY_SHA256:
        raise ValueError('Census boundary archive changed; a new source audit is required')
    with zipfile.ZipFile(archive) as source:
        shp = source.read('cb_2024_us_state_500k.shp')
        rows = dbf_records(source.read('cb_2024_us_state_500k.dbf'))
    position, features, record_index, native_points, served_points = 100, [], 0, 0, 0
    while position < len(shp):
        number, length = struct.unpack_from('>II', shp, position)
        content = position + 8
        if number != record_index + 1 or record_index >= len(rows):
            raise ValueError('Census shape and attributes do not align')
        row = rows[record_index]
        if row['STATEFP'] in by_fips:
            state = by_fips[row['STATEFP']]
            if (row['STUSPS'], row['NAME']) != (state['id'], state['name']):
                raise ValueError('Census state identity differs from registry')
            if struct.unpack_from('<I', shp, content)[0] != 5:
                raise ValueError('Unexpected Census boundary shape type')
            part_count, point_count = struct.unpack_from('<II', shp, content + 36)
            offsets = struct.unpack_from(f'<{part_count}I', shp, content + 44)
            values = struct.unpack_from(f'<{point_count * 2}d', shp, content + 44 + 4 * part_count)
            polygons = []
            for i, start in enumerate(offsets):
                end = offsets[i + 1] if i + 1 < part_count else point_count
                ring = [[values[2 * j], values[2 * j + 1]] for j in range(start, end)]
                # This pinned shoreline-clipped source contains exterior rings
                # only. Fail on a newly introduced hole instead of misassigning it.
                if signed_area(ring) >= 0:
                    raise ValueError('Unexpected non-exterior Census ring; review polygon topology')
                native_points += len(ring)
                ring = simplify_ring(ring)
                served_points += len(ring)
                polygons.append([ring])
            features.append(dict(type='Feature', id=state['id'],
                                 properties=dict(id=state['id'], name=state['name'], fips=state['fips'],
                                                 STATEFP=row['STATEFP'], STUSPS=row['STUSPS'], NAME=row['NAME']),
                                 geometry=dict(type='MultiPolygon', coordinates=polygons)))
        record_index += 1
        position = content + length * 2
    if record_index != len(rows):
        raise ValueError('Census shape/attribute record count differs')
    result = dict(type='FeatureCollection', sources=[dict(url=BOUNDARY_URL,
                  path='data/raw/cb_2024_us_state_500k.zip', sha256=BOUNDARY_SHA256,
                  vintage=2024, description='US Census shoreline-clipped cartographic state boundaries')],
                  simplification=dict(method='Ramer-Douglas-Peucker on two arcs per ring',
                    tolerance_degrees=SIMPLIFICATION_DEGREES, coordinate_decimals=5,
                    native_points=native_points, served_points=served_points,
                    retention='All native exterior rings/islands retained; original rings retained if simplified area differs by more than 10%. Exterior winding is clockwise for D3. For an overview map, not precise boundary analysis.'),
                  features=sorted(features, key=lambda f: f['properties']['name']))
    validate_boundaries(result, registry)
    return result


def validate_boundaries(geometry, registry):
    states = registry_states(registry)
    expected = {(s['id'], s['fips'], s['name']) for s in states}
    features = geometry.get('features', [])
    actual = {(f['properties']['id'], f['properties']['fips'], f['properties']['name']) for f in features}
    if geometry.get('type') != 'FeatureCollection' or len(features) != 50 or actual != expected:
        raise ValueError('Boundary must contain exactly the 50 registry states')
    if not geometry.get('sources') or geometry['sources'][0].get('sha256') != BOUNDARY_SHA256:
        raise ValueError('Boundary source provenance is missing or changed')
    for feature in features:
        native = feature['properties']
        if (native['STUSPS'], native['STATEFP'], native['NAME']) != (native['id'], native['fips'], native['name']):
            raise ValueError('Boundary native identifiers differ')
        if feature['id'] != native['id'] or feature['geometry']['type'] != 'MultiPolygon':
            raise ValueError('Boundary feature identifier or geometry invalid')
        polygons = feature['geometry']['coordinates']
        if not polygons:
            raise ValueError('Empty state boundary')
        for polygon in polygons:
            if len(polygon) != 1:
                raise ValueError('Unexpected boundary hole')
            ring = polygon[0]
            if len(ring) < 4 or ring[0] != ring[-1] or signed_area(ring) >= 0:
                raise ValueError('Boundary ring closure or D3 exterior winding invalid')
            if any(not (math.isfinite(x) and math.isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90) for x, y in ring):
                raise ValueError('Boundary coordinates invalid')


def export(root=ROOT, extract=False):
    root = Path(root)
    manifest = json.loads((root / 'data/manifest.json').read_text())
    registry = json.loads((root / 'data/source/state-expansion.json').read_text())
    guide = build_guide(manifest, registry, root)
    boundary_path = root / 'data/us-states.geojson'
    if extract:
        geometry = extract_boundaries(registry, root / 'data/raw/cb_2024_us_state_500k.zip')
    else:
        geometry = json.loads(boundary_path.read_text())
        validate_boundaries(geometry, registry)
    guide['sources'].append(dict(path='data/us-states.geojson', url=BOUNDARY_URL,
                                 sha256=BOUNDARY_SHA256, role='50-state map source archive'))
    (root / 'data/assessment-guide.json').write_text(json.dumps(guide, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    if extract:
        boundary_path.write_text(json.dumps(geometry, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    counts = dict(states=len(guide['states']), released_states=sum(bool(s['assessments']) for s in guide['states']),
                  assessments=sum(len(s['assessments']) for s in guide['states']), boundary_features=len(geometry['features']))
    print(json.dumps(counts))
    return guide


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract-boundaries', action='store_true', help='Re-extract the pinned ignored Census archive')
    args = parser.parse_args()
    export(extract=args.extract_boundaries)
