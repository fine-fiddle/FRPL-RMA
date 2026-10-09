"""Indiana's published ILEARN 2025 school totals -> SQLite -> static JSON.

Rebuild offline from the committed extract. --extract reads the official raw files
listed in docs/indiana-data.md; this command never downloads implicitly.
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import zipfile

import openpyxl
import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET = 'in-ilearn'
YEAR = 2025
EXTRACT = ROOT / 'data/source/indiana.json'
PORTAL = 'https://www.in.gov/doe/it/data-center-and-reports/data-reports-archive/'
BASE = 'https://www.in.gov/doe/files/'
NCES = ('https://nces.ed.gov/opengis/rest/services/K12_School_Locations/'
        'EDGE_GEOCODE_PUBLICSCH_2324/MapServer/0')
FILES = {
    'in-assessment-2025': ('in_assessment_2025.xlsx', BASE + 'ILEARN-2025-Grade3-8-Final-School_20250714-2.xlsx'),
    'in-income-2025': ('in_income_history.xlsx', BASE + 'school-enrollment-ethnicity-and-free-reduced-price-meal-status-2006-25-final.xlsx'),
    'in-grades-2025': ('in_grades_history.xlsx', BASE + 'school-enrollment-grade-2006-25.xlsx'),
    'in-directory-2026': ('in_directory_2026.xlsx', BASE + '2025-2026-school-directory-2026-03-23.xlsx'),
    'in-locations-2024': ('in_nces_locations_2024.json', NCES),
    'in-technical-2025': ('in_ilearn_technical_2025.pdf', 'https://www.in.gov/doe/students/assessment/assessment-files/ILEARN%20Summative_Technical%20Report_SP25_Mainbody_Final_v0.1%20%281%29.PDF'),
    'in-frpl-reporting': ('in_frpl_reporting_2025.json', 'https://idoe.atlassian.net/wiki/spaces/IKHTV/pages/473890839'),
    'in-frpl-eligibility': ('in_frpl_eligibility_2025.json', 'https://idoe.atlassian.net/wiki/spaces/IKHTV/pages/407470085'),
    'in-cep-guidance': ('in_cep_guidance_2025.pdf', BASE + 'June-18%2C-2025-School-Nutrition.pdf'),
    'in-boundary': ('cb_2024_us_state_500k.zip', 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_500k.zip'),
}
BANDS = {
    'grade': ('ES', 'ILEARN grades 3–8 · grade schools', 'Grade schools · ILEARN'),
    'mixed': ('HS', 'ILEARN grades 3–8 · mixed-grade schools', 'Mixed-grade schools · ILEARN grades 3–8'),
}
TOTAL_FIELDS = ['below', 'approaching', 'at', 'above', 'proficient', 'tested', 'rate']
ECON_DEFINITION = (
    'Indiana reported Free/Reduced Price Meals enrollment divided by the same school-year '
    'TOTAL ENROLLMENT in IDOE School Enrollment by Ethnicity and Free/Reduced Price Meal '
    'Status, 2025 tab (2024–25). IDOE Pupil Enrollment uses individual eligible School Food '
    'Services program records active on Fall Count Day at the primary school. Individual '
    'eligibility uses household applications or Direct Certification; universal CEP meals do '
    'not confer individual eligibility. At CEP schools, approved alternate applications or '
    'Direct Certification determine individual status. No CEP claiming multiplier is used. '
    'Enrollment includes pre-K and adult grades when reported. Incomplete eligibility '
    'applications/reporting can undercount disadvantage; this is a proxy, not direct income.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public_id(value):
    """Validate an ID from the public enrollment registry, including state institutions."""
    text = str(value).strip() if value is not None else ''
    if isinstance(value, (int, float)) and value == int(value):
        text = f'{int(value):04d}'
    if not re.fullmatch(r'(?:\d{4}|[A-Z]\d{3})', text) or text == '0000':
        raise ValueError(f'Invalid public IDOE school code: {value!r}')
    return text


def number(value):
    if value in (None, '', '***', '*', 'NA', 'N/A'):
        return None
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Non-finite source value')
    return value


def count(value):
    parsed = number(value)
    if parsed is not None and (parsed < 0 or parsed != int(parsed)):
        raise ValueError(f'Invalid student count: {value!r}')
    return int(parsed) if parsed is not None else None


def band_for(grades):
    """Use the same-year grade snapshot, never the current directory's grade range."""
    values = [count(v) for v in grades]
    if len(values) != 15 or any(v is None for v in values):
        raise ValueError('Incomplete same-year grade enrollment')
    has_high = any(values[10:])  # Grade 9 through Grade 12+/Adult.
    has_tested_grade = any(values[4:10])  # Grade 3 through Grade 8.
    return 'mixed' if has_high and has_tested_grade else 'high' if has_high else 'grade'


def result(raw):
    """Validate native school totals without reconstructing masked grade results."""
    if len(raw) != 7:
        raise ValueError('Unexpected native school-total field count')
    counts = [count(v) for v in raw[:6]]
    rate = number(raw[6])
    if rate is None:
        return None, None
    if not 0 <= rate <= 1 or any(v is None for v in counts):
        raise ValueError('Published rate lacks complete performance-level denominators')
    if sum(counts[:4]) != counts[5] or counts[2] + counts[3] != counts[4]:
        raise ValueError('Native school-total performance counts do not reconcile')
    if counts[5] <= 0 or abs(counts[4] / counts[5] - rate) > 1e-8:
        raise ValueError('Published proficiency does not reconcile to valid-score counts')
    return rate * 100, counts[5]


def worksheet(path, name):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return list(workbook[name].values)
    finally:
        workbook.close()


def state_boundary():
    """Read the Census cartographic Indiana exterior; orient it for D3."""
    with zipfile.ZipFile(ROOT / 'data/raw' / FILES['in-boundary'][0]) as archive:
        shp = archive.read('cb_2024_us_state_500k.shp')
        dbf = archive.read('cb_2024_us_state_500k.dbf')
    size = struct.unpack_from('<I', dbf, 4)[0]
    header, record_size = struct.unpack_from('<HH', dbf, 8)
    fields, pos = [], 32
    while dbf[pos] != 13:
        fields.append((dbf[pos:pos + 11].split(b'\0')[0].decode(), dbf[pos + 16]))
        pos += 32
    target = None
    for i in range(size):
        offset = header + i * record_size + 1
        row = {}
        for field, length in fields:
            row[field] = dbf[offset:offset + length].decode('latin1').strip()
            offset += length
        if row['STATEFP'] == '18':
            target = i
            break
    if target is None:
        raise ValueError('Indiana missing from cartographic boundary')
    pos = 100
    for i in range(size):
        _, length = struct.unpack_from('>II', shp, pos)
        content = pos + 8
        if i == target:
            if struct.unpack_from('<I', shp, content)[0] != 5:
                raise ValueError('Unexpected state polygon shape type')
            parts_count, points_count = struct.unpack_from('<II', shp, content + 36)
            parts = struct.unpack_from(f'<{parts_count}I', shp, content + 44)
            coords = struct.unpack_from(f'<{points_count * 2}d', shp, content + 44 + 4 * parts_count)
            rings = []
            for p in range(parts_count):
                start, end = parts[p], parts[p + 1] if p + 1 < parts_count else points_count
                ring = [[round(coords[2 * j], 5), round(coords[2 * j + 1], 5)] for j in range(start, end)]
                if any(not (-88.2 <= x <= -84.7 and 37.7 <= y <= 41.9) for x, y in ring):
                    raise ValueError('Indiana boundary outside expected bounds')
                if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])) > 0:
                    ring.reverse()
                rings.append(ring)
            return dict(type='FeatureCollection', features=[dict(type='Feature',
                properties=dict(STATEFP='18', NAME='Indiana'), geometry=dict(type='Polygon', coordinates=rings))])
        pos = content + length * 2
    raise ValueError('Missing Indiana shape record')


def extract():
    sources = {key: dict(path='data/raw/' + filename, url=url,
                        sha256=digest(ROOT / 'data/raw' / filename))
               for key, (filename, url) in FILES.items()}
    income = worksheet(ROOT / sources['in-income-2025']['path'], '2025')
    grades = worksheet(ROOT / sources['in-grades-2025']['path'], '2025')
    if income[0][11:] != ('Free/Reduced Price Meals', 'Paid Meals', 'TOTAL ENROLLMENT'):
        raise ValueError('Unexpected income workbook layout')
    if grades[0][4:9] != ('Pre-K', 'Kindergarten', 'Grade 1', 'Grade 2', 'Grade 3'):
        raise ValueError('Unexpected grade-enrollment layout')
    grade_map = {}
    for line, row in enumerate(grades[1:], 2):
        key = public_id(row[2])
        if key in grade_map:
            raise ValueError('Duplicate same-year grade ID')
        grade_map[key] = dict(raw=list(row[4:19]), total=count(row[19]), source_row=line)
    schools = []
    seen = set()
    for line, row in enumerate(income[1:], 2):
        key = public_id(row[2])
        if key in seen or key not in grade_map:
            raise ValueError('Duplicate income or missing same-year grade ID')
        seen.add(key)
        free, paid, total = [count(v) for v in row[11:14]]
        if None in (free, paid, total) or free + paid != total or total != grade_map[key]['total']:
            raise ValueError('Income/grade enrollment counts do not reconcile')
        schools.append(dict(school_id=key, district_id=public_id(row[0]),
            name=row[3], district=row[1], identity_raw=list(row[:4]),
            income_raw=list(row[11:14]), income_source_row=line,
            grades=grade_map[key]['raw'], grade_source_row=grade_map[key]['source_row'],
            band=band_for(grade_map[key]['raw'])))
    assessments, excluded, notes = [], [], {}
    for subject, sheet in [('math', 'Math'), ('reading', 'ELA')]:
        rows = worksheet(ROOT / sources['in-assessment-2025']['path'], sheet)
        if rows[4][46] != 'School Total' or 'Total\nTested' not in rows[5][51]:
            raise ValueError('Unexpected ILEARN total layout')
        notes[sheet] = [row[0] for row in rows[:4]]
        subject_ids = set()
        for line, row in enumerate(rows[6:], 7):
            if row[2] is None:
                continue
            key = str(row[2]).strip()
            if key in subject_ids:
                raise ValueError('Duplicate assessment school/subject')
            subject_ids.add(key)
            raw = list(row[46:53])
            result(raw)
            if key not in seen:
                excluded.append(dict(school_id=key, name=row[3], district=row[1], subject=subject,
                    raw=raw, source_row=line, reason='No matching public same-year enrollment'))
                continue
            assessments.append(dict(school_id=key, subject=subject, identity_raw=list(row[:4]),
                                    raw=raw, source_row=line))
    directory_rows = worksheet(ROOT / sources['in-directory-2026']['path'], 'SCHL')
    directory, ambiguous_directory = {}, set()
    for line, row in enumerate(directory_rows[1:], 2):
        key = public_id(row[3])
        if key in directory or key in ambiguous_directory:
            # A current reorganization can list one state code under two districts.
            # Do not pick a crosswalk or location from an ambiguous directory entry.
            ambiguous_directory.add(key)
            directory.pop(key, None)
            continue
        directory[key] = dict(nces_id=row[0], name=row[4], district_id=row[1],
            address=row[8], city=row[9], county=row[13], low_grade=row[16], high_grade=row[17],
            source_row=line)
    location_payload = json.loads((ROOT / sources['in-locations-2024']['path']).read_text())
    if location_payload.get('exceededTransferLimit'):
        raise ValueError('NCES coordinate pagination incomplete')
    locations = {}
    for feature in location_payload['features']:
        row = feature['attributes']
        if row['NCESSCH'] in locations or row['SCHOOLYEAR'] != '2023-2024':
            raise ValueError('Duplicate or wrong-year NCES coordinate')
        lat, lon = number(row['LAT']), number(row['LON'])
        if lat is not None and lon is not None and 37.7 <= lat <= 41.9 and -88.2 <= lon <= -84.7:
            locations[row['NCESSCH']] = dict(latitude=lat, longitude=lon)
    for profile in schools:
        hint = directory.get(profile['school_id'], {})
        profile['directory'] = dict(hint, **locations.get(hint.get('nces_id'), {}))
    payload = dict(year=YEAR, school_year='2024-25', retrieved=date.today().isoformat(),
        sources=sources, schools=schools, assessments=assessments,
        excluded_assessments=excluded, ambiguous_directory_ids=sorted(ambiguous_directory),
        workbook_notes=notes, total_fields=TOTAL_FIELDS,
        income_fields=['Free/Reduced Price Meals', 'Paid Meals', 'TOTAL ENROLLMENT'],
        grade_fields=list(grades[0][4:19]))
    payload['definition_evidence'] = [dict(source=source_id,
        page_id=json.loads((ROOT / sources[source_id]['path']).read_text())['id'],
        version=json.loads((ROOT / sources[source_id]['path']).read_text())['version']['number'])
        for source_id in ['in-frpl-reporting', 'in-frpl-eligibility']]
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))
    folder = ROOT / 'data/indiana'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'boundary.geojson').write_text(json.dumps(state_boundary(), separators=(',', ':')))


def import_data(db, payload):
    if payload['year'] != YEAR or payload['school_year'] != '2024-25':
        raise ValueError('Wrong Indiana source year')
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))
    db.execute('INSERT OR IGNORE INTO dataset VALUES (?,?,?,?,?)',
        (DATASET, 'IN', 'Indiana ILEARN 2025', 'Separate grade-school and mixed-grade public ILEARN grades 3–8 populations', 'ready'))
    sources = dict(payload['sources'], **{'in-extract': dict(path=str(EXTRACT.relative_to(ROOT)),
        url=PORTAL, sha256=digest(EXTRACT))})
    for ident, source in sources.items():
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
            (ident, DATASET, source['path'], source['url'], source['sha256'], payload['retrieved']))
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',
        ('in-frpl-2025', 'Indiana reported Free/Reduced Price Meals enrollment 2024–25',
         ECON_DEFINITION, sources['in-frpl-reporting']['url']))
    for band, (level, assessment, _) in BANDS.items():
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
            (definition_id(DATASET, YEAR, assessment, level), 'IN', assessment, YEAR, level, '3–8',
             'Spring 2025 ILEARN general-assessment native school totals: At + Above Proficiency '
             'divided by the total with performance-level scores. All testers except ESA testers; '
             'school assigned by tested location. I AM alternate assessment excluded. '
             'Grade-school and mixed-grade populations are separate. Not an ELA-and-math intersection.',
             sources['in-assessment-2025']['url']))
    schools = {}
    for order, profile in enumerate(payload['schools']):
        key = public_id(profile['school_id'])
        identity = profile['identity_raw']
        if (key in schools or key != public_id(identity[2])
                or profile['district_id'] != public_id(identity[0])
                or (profile['district'], profile['name']) != (identity[1], identity[3])
                or profile['band'] != band_for(profile['grades'])):
            raise ValueError('Duplicate identity or invalid grade classification')
        schools[key] = profile
        hint = profile['directory']
        free, paid, total = [count(v) for v in profile['income_raw']]
        if None in (free, paid, total) or free + paid != total or total != sum(profile['grades']):
            raise ValueError('Invalid income or grade counts')
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
            (DATASET, key, profile['name'], profile['district_id'], profile['district'],
             hint.get('city'), hint.get('county'), json.dumps(profile), 'in-extract', order))
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (DATASET, key, YEAR, 'in-frpl-2025', profile['name'], total, free,
             100 * free / total if total else None, 'Free/Reduced Price Meals', json.dumps(profile),
             'in-income-2025', profile['income_source_row']))
    observations = {}
    for record in payload['assessments']:
        key = (public_id(record['school_id']), record['subject'])
        if (key in observations or key[0] != public_id(record['identity_raw'][2])
                or key[0] not in schools or key[1] not in ['math', 'reading']):
            raise ValueError('Duplicate or invalid assessment identity')
        result(record['raw'])
        observations[key] = record
    for key, profile in schools.items():
        if profile['band'] == 'high':
            continue
        level, assessment, _ = BANDS[profile['band']]
        for subject in ['math', 'reading']:
            record = observations.get((key, subject), {})
            raw = record.get('raw', [None] * 7)
            pct, tested = result(raw)
            db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (DATASET, key, definition_id(DATASET, YEAR, assessment, level), subject, pct, tested,
                 'reported' if pct is not None else 'suppressed_or_not_reported' if '***' in raw else 'not_reported',
                 None if raw[6] is None else str(raw[6]), None if raw[5] is None else str(raw[5]),
                 'in-assessment-2025', record.get('source_row', 0)))


def prepare(database=DEFAULT_DB):
    payload = json.loads(EXTRACT.read_text())
    with connect(database) as db:
        import_data(db, payload)
        assessments = pl.DataFrame([dict(r) for r in db.execute('''
            SELECT a.school_id, CAST(d.year AS TEXT) AS year, d.level, d.name AS assessment,
                   a.subject, a.proficiency, a.tested FROM assessment_observation a
            JOIN assessment_definition d ON a.definition_id=d.id WHERE a.dataset_id=?''', (DATASET,))])
        incomes = pl.DataFrame([dict(r) for r in db.execute('''
            SELECT school_id, CAST(year AS TEXT) AS year, name, enrollment, low_income, percentage,
                   source_label AS income_label FROM economic_observation WHERE dataset_id=?''', (DATASET,))])
        records, models = build_history(assessments, incomes)
        save_models(db, records, models, DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Foreign key check failed')
    by_id = {r['school_id']: r for r in records}
    lookup = {(r['school_id'], r['subject']): r for r in payload['assessments']}
    regions, coverage = [], {}
    for band, (level, assessment, label) in BANDS.items():
        folder = ROOT / 'data/indiana' / ('mixed' if band == 'mixed' else '')
        folder.mkdir(parents=True, exist_ok=True)
        schools = []
        for profile in payload['schools']:
            if profile['band'] != band:
                continue
            key, hint = profile['school_id'], profile['directory']
            annual = by_id[key]
            for subject in ['math', 'reading']:
                if subject in annual['subjects']:
                    continue
                raw = lookup.get((key, subject), {}).get('raw', [])
                if '***' in raw:
                    annual['exclusions'][subject] = 'IDOE suppressed native school-total proficiency (fewer than 10 students)'
                elif not any(profile['grades'][4:10]):
                    annual['exclusions'][subject] = 'No enrolled ILEARN grades 3–8 in same-year snapshot'
                elif not raw or raw[6] is None:
                    annual['exclusions'][subject] = 'IDOE did not report native school-total proficiency'
            if 'combined' not in annual['subjects']:
                annual['exclusions']['combined'] = '; '.join(
                    f'{"ELA" if s == "reading" else "Math"}: {annual["exclusions"][s]}'
                    for s in ['math', 'reading'] if s in annual['exclusions'])
            schools.append(dict(id=key, name=profile['name'], short=profile['name'], level=level,
                program='Unclassified', programs=['Unclassified'], district=profile['district'],
                city=hint.get('city'), county=hint.get('county'), latitude=hint.get('latitude'),
                longitude=hint.get('longitude'), income=annual['income'], enrollment=annual['enrollment'],
                metrics=annual['subjects'], exclusions=annual['exclusions'], history=[annual]))
        cohort_models = [m for m in models if m['assessment'] == assessment]
        cohort_records = [r for r in records if r['assessment'] == assessment]
        mapped = sum(s['latitude'] is not None and s['longitude'] is not None for s in schools)
        note = (f'{len(schools)} public schools; {mapped} mapped by exact IDOE-to-NCES crosswalk. '
            'Spring 2025 ILEARN grades 3–8 native school totals, general assessment only; '
            'At + Above Proficiency. Income and enrolled grade span use 2024–25 IDOE data. '
            'Mixed-grade schools have a separate regression. School assignment is tested location; '
            'no FAY filter. Suppressed totals remain unavailable. One year only; SAT and I AM '
            'are not included. Directory is 2025–26; coordinates are NCES 2023–24.')
        methodology = dict(summary='Separate Indiana models compare ILEARN grades 3–8 proficiency with same-year reported free/reduced-price meal enrollment.',
            details=[ECON_DEFINITION, 'Use the official School Total fields for each subject. Performance-level counts sum to the score denominator, and At + Above sums to Total Proficient. Suppressed grade results are never reconstructed.',
                'Grade schools have no enrolled grade 9 or above in the 2024–25 snapshot. Mixed-grade schools enroll both grades 3–8 and grade 9 or above; only their grades 3–8 ILEARN scores enter their separate models.',
                'Externally studentized residuals use the complete eligible population for each subject. Combined is the equally weighted mean of math and ELA, not proficiency in both. Sampling intervals use verified score denominators.',
                'Reported enrollment includes pre-K/adult grades where present and differs from tested students. The source reports all spring testers except ESA testers and assigns schools by tested location. Results describe associations; they do not measure causal school effectiveness.',
                '2025–26 directory IDs supply the explicit NCES crosswalk for NCES 2023–24 locations. Neither locations nor current directory grade spans determine model eligibility. Unmatched locations stay list-only.'],
            sources=[dict(label='IDOE source downloads', url=PORTAL),
                     dict(label='ILEARN school totals', url=FILES['in-assessment-2025'][1]),
                     dict(label='Same-year FRPL enrollment', url=FILES['in-income-2025'][1]),
                     dict(label='IDOE individual eligibility reporting', url=FILES['in-frpl-reporting'][1]),
                     dict(label='CEP individual eligibility guidance', url=FILES['in-cep-guidance'][1]),
                     dict(label='Same-year enrolled grades', url=FILES['in-grades-2025'][1]),
                     dict(label='ILEARN technical report', url=FILES['in-technical-2025'][1]),
                     dict(label='IDOE directory crosswalk', url=FILES['in-directory-2026'][1]),
                     dict(label='NCES school coordinates', url=NCES)])
        output = dict(year='2024–25', assessment_year=YEAR, income_label='Reported free/reduced-price meal enrollment',
            levels={level: dict(year=YEAR, label=label, assessment=assessment,
                outcome='At + above proficiency', math_label='Math', note='ILEARN grades 3–8 · native school totals')},
            program_options=['Unclassified'], schools=schools,
            models={level: {s: next((m for m in cohort_models if m['subject'] == s), None)
                           for s in ['math', 'reading', 'combined']}},
            history_years=[YEAR], history_models=cohort_models, coverage_note=note, methodology=methodology)
        (folder / 'schools.json').write_text(json.dumps(output, separators=(',', ':'), allow_nan=False))
        (folder / 'history.json').write_text(json.dumps(dict(records=cohort_records, models=cohort_models,
            exclusions=dict(Counter(reason for r in cohort_records for reason in r['exclusions'].values()))),
            separators=(',', ':'), allow_nan=False))
        path = str(folder.relative_to(ROOT))
        regions.append(dict(id='indiana-mixed' if band == 'mixed' else 'indiana',
            name='Mixed-grade schools' if band == 'mixed' else 'Grade schools', dataset=DATASET,
            status='ready', geography='indiana', levels=[level], schools=path + '/schools.json',
            boundaries='data/indiana/boundary.geojson',
            comparison='Indiana · {year} · ILEARN grades 3–8 · {note}',
            model_scope='Separate public ' + ('mixed-grade' if band == 'mixed' else 'grade-school') + ' ILEARN grades 3–8 cohort',
            map_source='Exact IDOE 2025–26 directory NCES-ID crosswalk to NCES 2023–24 coordinates'))
        coverage[band] = dict(schools=len(schools), mapped=mapped,
            eligible={m['subject']: m['n'] for m in cohort_models})
    (ROOT / 'data/indiana/catalog.json').write_text(json.dumps(dict(schema_version=1, prepare_script='scripts/prepare_indiana.py',
        state=dict(id='IN', name='Indiana'), regions=regions), indent=2) + '\n')
    audit = dict(year=YEAR, bands=coverage, public_enrollment_schools=len(payload['schools']),
        out_of_scope_high_schools=sum(p['band'] == 'high' for p in payload['schools']),
        excluded_unmatched_assessment_rows=len(payload['excluded_assessments']),
        excluded_numeric_public_ids=sorted({r['school_id'] for r in payload['excluded_assessments']
                                          if re.fullmatch(r'\d{4}', r['school_id'])}))
    (ROOT / 'data/indiana/coverage.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract:
        extract()
    prepare(args.database)
