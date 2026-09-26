"""Wisconsin DPI/WISEdash public aggregates -> canonical SQLite -> static JSON.

No implicit downloads: place the raw archives listed below under data/raw/.
See docs/wisconsin-data.md for definitions, standards breaks and validation.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import polars as pl
from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET = 'wi-dpi'
EXTRACT = ROOT / 'data/source/wisconsin.json'
GIS_CSV = ROOT / 'data/raw/wi-public-schools.csv'
BOUNDARY_RAW = ROOT / 'data/raw/wi-boundary.geojson'
BOUNDARY = ROOT / 'data/wisconsin/boundary.geojson'
BASE = 'https://dpi.wi.gov/sites/default/files/wise/downloads/'
OLD = 'https://dpi.wi.gov/sites/default/files/imce/zip/'

# year -> raw archive. Wisconsin school-year labels mean the testing year.
FORWARD = {
    '2015-16': BASE + 'forward_certified_2015-16.zip',
    '2016-17': BASE + 'forward_certified_2016-17.zip',
    '2017-18': BASE + 'forward_certified_2017-18.zip',
    '2018-19': BASE + 'forward_certified_2018-19.zip',
    '2020-21': BASE + 'forward_certified_2020-21.zip',
    '2021-22': BASE + 'forward_certified_2021-22.zip',
    '2022-23': BASE + 'forward_certified_2022-23.zip',
    '2023-24': BASE + 'forward_certified_2023-24.zip',
    '2024-25': BASE + 'forward_certified_2024-25.zip',
}
ACT = {
    '2014-15': BASE + 'act_statewide_certified_2014-15.zip',
    '2015-16': BASE + 'act_statewide_certified_2015-16.zip',
    '2016-17': BASE + 'act_statewide_certified_2016-17.zip',
    '2017-18': BASE + 'act_statewide_certified_2017-18.zip',
    '2018-19': OLD + 'act_statewide_certified_2018-19.zip',
    '2019-20': BASE + 'act_statewide_certified_2019-20.zip',
    '2020-21': BASE + 'act_statewide_certified_2020-21.zip',
    '2021-22': BASE + 'act_statewide_certified_2021-22.zip',
    '2022-23': BASE + 'act_statewide_certified_2022-23.zip',
    '2023-24': BASE + 'act_statewide_certified_2023-24.zip',
    '2024-25': BASE + 'act_statewide_certified_2024-25.zip',
}
ENROLLMENT = {year: BASE + f'enrollment_certified_{year}.zip' for year in
              ['2014-15', '2015-16', '2016-17', '2017-18', '2018-19', '2019-20',
               '2020-21', '2021-22', '2022-23', '2023-24', '2024-25']}
GIS_URL = ('https://data-wi-dpi.opendata.arcgis.com/api/download/v1/items/'
           'd383fe81275e46f2a5a5c4f1a0c2eb85/csv?layers=20')
BOUNDARY_URL = ('https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/'
                'State_County/MapServer/0/query?where=STATE%3D%2755%27&outFields=NAME'
                '&returnGeometry=true&outSR=4326&f=geojson')

STRICT = dict(infer_schema_length=20000, schema_overrides={
    'DISTRICT_CODE': pl.Utf8, 'SCHOOL_CODE': pl.Utf8, 'GRADE_LEVEL': pl.Utf8})
# Two comparability eras. DPI recalibrated Forward and ACT performance levels in 2023-24.
LEVELS = {
    'pre': ['Advanced', 'Proficient', 'Basic', 'Below Basic'],
    'post': ['Advanced', 'Meeting', 'Approaching', 'Developing'],
}
FORWARD_NAME = {'pre': 'Forward (pre-2023-24 levels)', 'post': 'Forward (2023-24 levels)'}
ACT_NAME = {'pre': 'ACT (pre-2023-24 levels)', 'post': 'ACT (2023-24 levels)'}
ECON_DEFINITION = (
    'Wisconsin Economically Disadvantaged: identified by Direct Certification, or a household '
    'meeting National School Lunch Program free/reduced-price income guidelines (at or below 185% '
    'of the federal poverty guidelines), or an alternate household income form. Reported for every '
    'student each year, including Community Eligibility Provision schools. Percentage uses the '
    'third-Friday-of-September enrolled count. Suppressed values stay unavailable.')
GRADE_FIELDS = ['3', '4', '5', '6', '7', '8']


def era(year):
    return 'post' if year >= '2023-24' else 'pre'


def sid(district, school):
    return f'S{district}{school}'


def ending_year(school_year):
    """Repository years are school-year ending years: 2024-25 -> 2025."""
    return int(school_year[:4]) + 1


def number(value):
    """Source suppression, blanks and ranges stay unavailable; never imputed."""
    if value is None:
        return None
    text = str(value).strip()
    if text in {'', '*', '[Data Suppressed]', 'N/A', 'NA', '-', '--'}:
        return None
    result = float(text)
    if not math.isfinite(result):
        raise ValueError(f'Non-finite value: {value}')
    return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_entry(path, url):
    return dict(path=str(Path(path).relative_to(ROOT)), url=url, sha256=digest(path))


def archive_csvs(zip_name):
    """Extract a zip's data CSVs to a temporary folder; return paths and the folder."""
    path = ROOT / 'data/raw' / zip_name
    if not path.exists():
        raise FileNotFoundError(f'Missing raw source: {path}')
    target = ROOT / 'data/build/wi-tmp' / zip_name.replace('.zip', '')
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist()
                 if n.endswith('.csv') and 'layout' not in n.lower() and 'disclaimer' not in n.lower()]
        if not names:
            raise ValueError(f'{zip_name}: no data CSV found')
        archive.extractall(target, names)
    return [target / n for n in names], target


def summarize(results, levels, group_count=None):
    """Collapse one school/grade/subject result set; None means redacted or incomplete."""
    if '*' in results or any(number(v) is None for k, v in results.items() if k != '*'):
        return None
    counts = []
    for level in levels:
        value = number(results.get(level))
        if value is None or value != int(value):
            return None
        counts.append(int(value))
    other = 0
    for result, value in results.items():
        if result in levels:
            continue
        parsed = number(value)
        if parsed is None or parsed != int(parsed):
            raise ValueError('Invalid non-level count')
        other += int(parsed)
    published = number(group_count)
    if published is not None and sum(counts) + other != int(published):
        raise ValueError(f'Result counts do not reconcile to GROUP_COUNT: {results} vs {group_count}')
    return counts + [other]


def parse_forward(year, zip_name):
    """Return {(school_id, subject): {grade: [top, second, third, fourth, other] | None}}."""
    levels = LEVELS[era(year)]
    groups = defaultdict(lambda: defaultdict(dict))
    totals = {}
    paths, target = archive_csvs(zip_name)
    try:
        for path in paths:
            rows = (pl.scan_csv(path, **STRICT)
                    .filter((pl.col('GROUP_BY') == 'All Students')
                            & (pl.col('TEST_GROUP') == 'Forward')
                            & (pl.col('TEST_SUBJECT').is_in(['ELA', 'Mathematics']))
                            & (pl.col('DISTRICT_CODE').str.len_chars() == 4)
                            & (pl.col('SCHOOL_CODE').str.len_chars() == 4))
                    .select(['DISTRICT_CODE', 'SCHOOL_CODE', 'TEST_SUBJECT', 'GRADE_LEVEL',
                             'TEST_RESULT', 'STUDENT_COUNT', 'GROUP_COUNT']).collect())
            for r in rows.iter_rows(named=True):
                result = r['TEST_RESULT']
                if result != '*' and result not in set(levels) | {'No Test', 'No Score'}:
                    raise ValueError(f'{zip_name}: unexpected Forward result {result!r}')
                key = (sid(r['DISTRICT_CODE'], r['SCHOOL_CODE']),
                       'reading' if r['TEST_SUBJECT'] == 'ELA' else 'math')
                groups[key][str(r['GRADE_LEVEL'])][result] = r['STUDENT_COUNT']
                totals[(key, str(r['GRADE_LEVEL']))] = r['GROUP_COUNT']
    finally:
        shutil.rmtree(target, ignore_errors=True)
    return {key: {grade: summarize(results, levels, totals[(key, grade)])
                  for grade, results in by_grade.items()}
            for key, by_grade in groups.items()}


def parse_act(year, zip_name):
    """Return {(school_id, subject): [top, second, third, fourth, other] | None}."""
    levels = LEVELS[era(year)]
    groups = defaultdict(lambda: defaultdict(list))
    totals = {}
    paths, target = archive_csvs(zip_name)
    try:
        for path in paths:
            rows = (pl.scan_csv(path, **STRICT)
                    .filter((pl.col('GROUP_BY') == 'All Students')
                            & (pl.col('TEST_GROUP') == 'ACT')
                            & (pl.col('TEST_SUBJECT').is_in(['ELA', 'Mathematics']))
                            & (pl.col('DISTRICT_CODE').str.len_chars() == 4)
                            & (pl.col('SCHOOL_CODE').str.len_chars() == 4))
                    .select(['DISTRICT_CODE', 'SCHOOL_CODE', 'TEST_SUBJECT', 'TEST_RESULT',
                             'STUDENT_COUNT', 'GROUP_COUNT']).collect())
            for r in rows.iter_rows(named=True):
                result = r['TEST_RESULT']
                if result != '*' and result not in set(levels) | {'No Test', 'Not Benchmarked'}:
                    raise ValueError(f'{zip_name}: unexpected ACT result {result!r}')
                key = (sid(r['DISTRICT_CODE'], r['SCHOOL_CODE']),
                       'reading' if r['TEST_SUBJECT'] == 'ELA' else 'math')
                groups[key][result].append(r['STUDENT_COUNT'])
                totals[key] = r['GROUP_COUNT']
    finally:
        shutil.rmtree(target, ignore_errors=True)
    out = {}
    for key, by_result in groups.items():
        # ACT reports Wisconsin performance levels split across college-readiness rows.
        out[key] = summarize({result: None if any(number(v) is None for v in values)
                              else str(sum(number(v) for v in values))
                              for result, values in by_result.items()}, levels, totals[key])
    return out


def parse_enrollment(year, zip_name):
    """Return {school_id: profile} for school-level rows of one annual snapshot."""
    paths, target = archive_csvs(zip_name)
    try:
        rows = pl.concat([
            pl.scan_csv(path, **STRICT)
            .filter((pl.col('GROUP_BY').is_in(['All Students', 'Economic Status', 'Grade Level']))
                    & (pl.col('DISTRICT_CODE').str.len_chars() == 4)
                    & (pl.col('SCHOOL_CODE').str.len_chars() == 4))
            .select(['DISTRICT_CODE', 'SCHOOL_CODE', 'DISTRICT_NAME', 'SCHOOL_NAME', 'AGENCY_TYPE',
                     'GRADE_GROUP', 'CHARTER_IND', 'GROUP_BY', 'GROUP_BY_VALUE', 'STUDENT_COUNT'])
            .collect() for path in paths])
    finally:
        shutil.rmtree(target, ignore_errors=True)
    profiles = {}
    for r in rows.iter_rows(named=True):
        key = sid(r['DISTRICT_CODE'], r['SCHOOL_CODE'])
        profile = profiles.setdefault(key, dict(school_id=key, name=r['SCHOOL_NAME'],
            district_name=r['DISTRICT_NAME'], agency_type=r['AGENCY_TYPE'],
            grade_group=r['GRADE_GROUP'], charter=r['CHARTER_IND'], enrollment=None,
            econ=None, not_econ=None, unknown=None, econ_suppressed=False, grades={}))
        count = number(r['STUDENT_COUNT'])
        if r['GROUP_BY'] == 'All Students':
            profile['enrollment'] = count
        elif r['GROUP_BY'] == 'Economic Status':
            value = r['GROUP_BY_VALUE']
            if value == 'Econ Disadv':
                profile['econ'] = count
            elif value == 'Not Econ Disadv':
                profile['not_econ'] = count
            elif value == 'Unknown':
                profile['unknown'] = count
            else:
                profile['econ_suppressed'] = True
        else:
            profile['grades'][r['GROUP_BY_VALUE']] = count
    for key, profile in profiles.items():
        total, econ = profile['enrollment'], profile['econ']
        if econ is not None and total is not None and econ > total:
            raise ValueError(f'{key} {year}: economic count exceeds enrollment')
        profile['percentage'] = 100 * econ / total if total and econ is not None and 0 <= econ <= total else None
    return profiles


def parse_directory():
    """Official DPI 2026-27 public school points, keyed by DPI unique join code."""
    if not GIS_CSV.exists():
        raise FileNotFoundError(f'Missing raw source: {GIS_CSV}')
    directory = {}
    with GIS_CSV.open(newline='', encoding='utf-8-sig') as source:
        for row in csv.DictReader(source):
            district, school = row['District ID'].strip(), row['School Code'].strip()
            if not re.fullmatch(r'\d{4}', district) or not re.fullmatch(r'\d{4}', school):
                raise ValueError(f'Invalid GIS school code: {district!r} {school!r}')
            key = sid(district, school)
            if key != row['DPI Unique Join Code'].strip():
                raise ValueError(f'GIS join code mismatch for {key}')
            directory[key] = dict(
                name=row['School Name'].strip(), district=row['District'].strip(),
                district_id=district, school_type=row['School Type'].strip(),
                agency_type=row['Agency Type'].strip(), grade_range=row['Grade Range'].strip(),
                high_grade=row['Highest Grade'].strip(), charter=row['Charter?'].strip(),
                city=row['City'].strip(), county=row['County (Physical)'].strip(),
                latitude=number(row['Latitude']), longitude=number(row['Longitude']))
    if not directory:
        raise ValueError('Empty DPI directory')
    return directory


def extract():
    payload_sources = {}
    missing = []
    for kind, years in [('forward', FORWARD), ('act', ACT), ('enrollment', ENROLLMENT)]:
        for year, url in years.items():
            zip_name = url.rsplit('/', 1)[-1]
            payload_sources[f'wi-{kind}-{year}'] = source_entry(ROOT / 'data/raw' / zip_name, url)
            if not (ROOT / 'data/raw' / zip_name).exists():
                missing.append(zip_name)
    if missing:
        raise FileNotFoundError('Missing raw sources: ' + ', '.join(sorted(missing)))
    if not BOUNDARY_RAW.exists():
        raise FileNotFoundError(f'Missing raw source: {BOUNDARY_RAW}')

    enrollment = []
    for year, url in ENROLLMENT.items():
        profiles = parse_enrollment(year, url.rsplit('/', 1)[-1])
        for profile in profiles.values():
            enrollment.append(dict(profile, year=year))
    assessments = []
    for year, url in FORWARD.items():
        for (key, subject), grades in sorted(parse_forward(year, url.rsplit('/', 1)[-1]).items()):
            assessments.append(dict(school_id=key, year=year, level='ES', subject=subject,
                                    assessment=FORWARD_NAME[era(year)], grades=grades))
    for year, url in ACT.items():
        for (key, subject), counts in sorted(parse_act(year, url.rsplit('/', 1)[-1]).items()):
            assessments.append(dict(school_id=key, year=year, level='HS', subject=subject,
                                    assessment=ACT_NAME[era(year)], grades={'11': counts}))
    payload = dict(retrieved='2026-09-26', levels=LEVELS, sources=payload_sources,
                   directory_source=source_entry(GIS_CSV, GIS_URL),
                   boundary_source=source_entry(BOUNDARY_RAW, BOUNDARY_URL),
                   enrollment=sorted(enrollment, key=lambda r: (r['school_id'], r['year'])),
                   assessments=assessments, directory=parse_directory())
    EXTRACT.parent.mkdir(parents=True, exist_ok=True)
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))
    boundary = json.loads(BOUNDARY_RAW.read_text())
    for feature in boundary['features']:
        rings = feature['geometry']['coordinates']
        for i, ring in enumerate(rings):
            area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
            if (i == 0 and area > 0) or (i > 0 and area < 0):
                ring.reverse()
            ring[:] = [[round(x, 5), round(y, 5)] for x, y in ring]
    BOUNDARY.parent.mkdir(parents=True, exist_ok=True)
    BOUNDARY.write_text(json.dumps(boundary, separators=(',', ':')))
    print(f'Extracted {len(enrollment)} enrollment, {len(assessments)} assessment records, '
          f'{len(payload["directory"])} directory schools')


def aggregate(record, expected):
    """Tested/proficient counts for one school-year-subject, or (None, None)."""
    grades = record['grades'] or {}
    if not grades or any(value is None for value in grades.values()):
        return None, None
    if set(grades) != set(expected):
        return None, None
    tested = sum(sum(value[:4]) for value in grades.values())
    proficient = sum(value[0] + value[1] for value in grades.values())
    if tested <= 0:
        return None, None
    return tested, 100 * proficient / tested


def profile_level(profile, directory):
    """Directory level follows the snapshot's grade enrollment, then the GIS range."""
    grades = profile.get('grades', {})
    if any((number(grades.get(str(g))) or 0) > 0 for g in range(9, 13)):
        return 'HS'
    if any(str(g) in grades for g in range(9, 13)):
        return 'ES'
    high = directory.get('high_grade', '')
    return 'HS' if high.isdigit() and int(high) >= 9 else 'ES'


def import_data(db, payload):
    enrollment = payload['enrollment']
    directory = payload['directory']
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (DATASET,))
    db.execute("DELETE FROM assessment_definition WHERE id LIKE ?", (f'{DATASET}:%',))
    db.execute("DELETE FROM economic_definition WHERE id LIKE 'wi-econ-%'")
    db.execute('INSERT OR IGNORE INTO dataset VALUES (?,?,?,?,?)',
               (DATASET, 'WI', 'Wisconsin statewide', 'Wisconsin DPI assessment cohorts', 'ready'))
    db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
               ('wi-extract', DATASET, str(EXTRACT.relative_to(ROOT)),
                'https://dpi.wi.gov/wisedash/public/download-files',
                digest(EXTRACT), payload['retrieved']))
    for source_id, source in [('wi-directory', payload['directory_source']),
                              ('wi-boundary', payload['boundary_source'])]:
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
                   (source_id, DATASET, source['path'], source['url'], source['sha256'],
                    payload['retrieved']))
    for source_id, source in payload['sources'].items():
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
                   (source_id, DATASET, source['path'], source['url'], source['sha256'],
                    payload['retrieved']))
    # Directory-first profiles, enriched by annual enrollment snapshots.
    latest = {}
    for record in enrollment:
        key = record['school_id']
        if key not in latest or record['year'] > latest[key]['year']:
            latest[key] = record
        directory.setdefault(key, dict(name=record['name'], district=record['district_name'],
                                       district_id=key[1:5], city=None, county=None,
                                       latitude=None, longitude=None, high_grade='', charter=None))
    for order, (key, hint) in enumerate(sorted(directory.items())):
        profile = dict(hint)
        snapshot = latest.get(key)
        if snapshot:
            profile.update(name=snapshot['name'], district_name=snapshot['district_name'],
                           agency_type=snapshot['agency_type'], grade_group=snapshot['grade_group'],
                           charter=snapshot['charter'], enrollment=snapshot['enrollment'],
                           econ=snapshot['econ'], percentage=snapshot['percentage'])
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, key, profile.get('name'), profile.get('district_id'),
                    profile.get('district') or profile.get('district_name'), profile.get('city'),
                    profile.get('county'), json.dumps(profile), 'wi-extract', order))
    for order, record in enumerate(enrollment):
        year = record['year']
        definition = f'wi-econ-{year}'
        db.execute('INSERT OR IGNORE INTO economic_definition VALUES (?,?,?,?)',
                   (definition, f'Wisconsin Economically Disadvantaged {year}', ECON_DEFINITION,
                    payload['sources'][f'wi-enrollment-{year}']['url']))
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, record['school_id'], ending_year(year), definition, record['name'],
                    record['enrollment'], record['econ'], record['percentage'],
                    'Econ Disadv', json.dumps(record), f'wi-enrollment-{year}', order))
    grades_by_school = defaultdict(dict)
    for record in enrollment:
        grades_by_school[record['school_id']][record['year']] = record['grades']
    cohorts = defaultdict(dict)
    for record in payload['assessments']:
        if record['level'] == 'ES':
            grades = grades_by_school.get(record['school_id'], {}).get(record['year'], {})
            expected = [g for g in GRADE_FIELDS if (number(grades.get(g)) or 0) > 0]
        else:
            # ACT Statewide is the grade-11 administration; its file is the denominator source.
            expected = ['11']
        subject = record['subject']
        cohorts[(record['year'], record['school_id'], record['level'], record['assessment'])][subject] = \
            aggregate(record, expected)
    definitions = {}
    order = 0
    for (year, school, level, assessment), subjects in sorted(cohorts.items()):
        cohort = (year, level, assessment)
        if cohort not in definitions:
            ident = definition_id(DATASET, ending_year(year), assessment, level)
            source_key = f'wi-forward-{year}' if level == 'ES' else f'wi-act-{year}'
            if era(year) == 'post':
                standard = (f'{assessment} at the 2023-24 performance levels; '
                            'top two levels are Advanced + Meeting.' if level == 'ES' else
                            'ACT Statewide at the 2023-24 performance levels; '
                            'top two levels are Advanced + Meeting.')
            else:
                standard = (f'{assessment} under the pre-2023-24 performance levels; '
                            'top two levels are Advanced + Proficient.' if level == 'ES' else
                            'ACT Statewide under the pre-2023-24 performance levels; '
                            'top two levels are Advanced + Proficient.')
            db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
                       (ident, 'WI', assessment, ending_year(year), level,
                        '3–8' if level == 'ES' else '11',
                        f'{"Forward ELA and mathematics, grades 3–8" if level == "ES" else "ACT Statewide ELA and mathematics, grade 11"}, '
                        'general assessment (DLM excluded), tested students only. ' + standard,
                        payload['sources'][source_key]['url']))
            definitions[cohort] = ident
        ident = definitions[cohort]
        source_key = f'wi-forward-{year}' if level == 'ES' else f'wi-act-{year}'
        for subject, (tested, proficiency) in sorted(subjects.items()):
            status = 'reported' if proficiency is not None else 'suppressed_or_not_reported'
            db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (DATASET, school, ident, subject, proficiency, tested, status,
                        None if proficiency is None else f'{proficiency:.6f}',
                        str(tested) if tested else None, source_key, order))
            order += 1


def prepare(database=DEFAULT_DB):
    payload = json.loads(EXTRACT.read_text())
    with connect(database) as db:
        import_data(db, payload)
        assessments = pl.DataFrame([dict(r) for r in db.execute(
            """SELECT a.school_id, CAST(d.year AS TEXT) AS year, d.level, d.name AS assessment,
                      a.subject, a.proficiency, a.tested
               FROM assessment_observation a JOIN assessment_definition d ON a.definition_id=d.id
               WHERE a.dataset_id=?""", (DATASET,))], infer_schema_length=None)
        incomes = pl.DataFrame([dict(r) for r in db.execute(
            """SELECT school_id, CAST(year AS TEXT) AS year, name, enrollment, low_income, percentage
               FROM economic_observation WHERE dataset_id=?""", (DATASET,))], infer_schema_length=None)
        records, models = build_history(assessments, incomes)
        save_models(db, records, models, DATASET)
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    snapshot = max(int(m['year']) for m in models)
    directory = payload['directory']
    latest = {}
    for record in payload['enrollment']:
        key = record['school_id']
        if key not in latest or record['year'] > latest[key]['year']:
            latest[key] = record
    enrollment_lookup = {(r['school_id'], ending_year(r['year'])): r for r in payload['enrollment']}
    histories = defaultdict(list)
    for record in records:
        histories[record['school_id']].append(record)
    schools = []
    for key, history in sorted(histories.items()):
        hint = directory.get(key, {})
        profile = latest.get(key, {})
        level = profile_level(profile, hint)
        annual = [r for r in history if r['level'] == level]
        if not annual:
            # Mixed-grade schools with only the other level's history stay in that cohort.
            level = history[0]['level']
            annual = [r for r in history if r['level'] == level]
        current = next((r for r in annual if r['year'] == snapshot), None)
        current_income = enrollment_lookup.get((key, snapshot))
        name = hint.get('name') or profile.get('name') or (current or {}).get('name') or key
        schools.append(dict(
            id=key, name=name, short=name, level=level, program='Unclassified',
            programs=['Unclassified'], district=hint.get('district') or profile.get('district_name'),
            city=hint.get('city'), county=hint.get('county'),
            income=current_income['percentage'] if current_income else None,
            enrollment=current_income['enrollment'] if current_income else None,
            latitude=hint.get('latitude'), longitude=hint.get('longitude'),
            metrics=current['subjects'] if current else {}, history=annual))
    levels = {
        'ES': dict(year=snapshot, label='Grade schools · Forward', assessment='Forward',
                   outcome='Proficiency', math_label='Math',
                   note='Forward ELA and mathematics, grades 3–8 · tested students'),
        'HS': dict(year=snapshot, label='High schools · ACT', assessment='ACT',
                   outcome='Proficiency', math_label='Math',
                   note='ACT Statewide ELA and mathematics, grade 11 · tested students'),
    }
    exclusions = Counter(reason for r in records for reason in r['exclusions'].values())
    output = dict(
        year='2024–25', assessment_year=snapshot, income_label='Economically disadvantaged',
        levels=levels, program_options=['Unclassified'], schools=schools,
        models={level: {subject: next(m for m in models if m['year'] == snapshot
                                      and m['level'] == level and m['subject'] == subject)
                        for subject in ['math', 'reading', 'combined']}
                for level in ['ES', 'HS']},
        history_years=sorted({int(r['year']) for r in records}), history_models=models,
        coverage_note=(
            f'Wisconsin DPI public files: {len(schools)} schools in the directory. '
            f'Forward grades 3–8 and ACT grade 11, test administration years 2014-15 through 2024-25; '
            'Forward 2019-20 is absent because the administration was waived. Performance levels changed '
            'in 2023-24, so history breaks between the two assessment identities. Income is same-school-year '
            'Wisconsin Economically Disadvantaged enrollment. Suppressed income or results are unavailable, '
            'never imputed. School results are FAY students; grade-school members must have complete, '
            'non-redacted results for every enrolled grade 3–8. DLM is excluded. Locations use the DPI '
            '2026-27 public school points, so they may be newer than the assessment snapshot.'))
    folder = ROOT / 'data/wisconsin'
    folder.mkdir(exist_ok=True)
    (folder / 'schools.json').write_text(json.dumps(output, separators=(',', ':'), allow_nan=False))
    (folder / 'history.json').write_text(json.dumps(
        dict(records=records, models=models, exclusions=exclusions), separators=(',', ':'),
        allow_nan=False))
    print(json.dumps(dict(
        schools=len(schools), mapped=sum(s['latitude'] is not None for s in schools),
        snapshot=snapshot,
        models={level: {s: m['n'] for s, m in subjects.items()} for level, subjects in output['models'].items()},
        exclusions=exclusions), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract:
        extract()
    prepare(args.database)
