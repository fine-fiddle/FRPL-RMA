"""Audited 2024–25 California Smarter Balanced and Census Day FRPM models.

Only published valid-score counts support grade aggregation. Raw ZIP/XLSX inputs
are downloaded explicitly; the committed compact extract supports offline rebuilds.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import zipfile

import openpyxl
import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET = 'ca-cde-2025'
YEAR = 2025
ACADEMIC_YEAR = '2024-2025'
EXTRACT = ROOT / 'data/source/california.json'
RAW = ROOT / 'data/raw/california'
OUTPUT = ROOT / 'data/california'
RESEARCH_URL = 'https://caaspp-elpac.ets.org/caaspp/ResearchFileListSB?lstCounty=00&lstDistrict=00000&lstTestType=B&lstTestYear=2025&ps=true'
ASSESSMENT_URL = 'https://caaspp-elpac.ets.org/caaspp/researchfiles/sb_ca2025_1_csv_v1.zip'
INCOME_URL = 'https://www.cde.ca.gov/Ds/ad/documents/frpm2425.xlsx'
LAYOUT_URL = 'https://caaspp-elpac.ets.org/caaspp/docs/2025_SBAC_Research%20File%20Layout.xlsx'
INCOME_INFO_URL = 'https://www.cde.ca.gov/ds/ad/filesspfrpm.asp'
ASSESSMENTS = {'ES': 'Smarter Balanced grades 3–8', 'HS': 'Smarter Balanced grade 11'}
SUBJECTS = {'1': 'reading', '2': 'math'}
SCHOOL_TYPES = {'7', '9', '10'}
FIELDS = [
    'County Code', 'District Code', 'School Code', 'School Name', 'District Name',
    'Type ID', 'Test Year', 'Test Type', 'Test ID', 'Student Group ID', 'Grade',
    'Total Students Tested', 'Total Students Tested with Scores', 'Overall Total',
    'Count Standard Met and Above', 'Percentage Standard Met and Above',
]
PROFILE_FIELDS = [
    'Academic Year', 'County Code', 'District Code', 'School Code', 'County Name',
    'District Name', 'School Name', 'District Type', 'School Type', 'Low Grade',
    'High Grade', 'Enrollment (K-12)', 'FRPM Count (K-12)',
    'Percent (%) Eligible FRPM (K-12)', 'Charter School (Y/N)',
    'California Longitudinal Pupil Achievement Data System (CALPADS) Fall 1 Certification Status',
]
ECON_DEFINITION = (
    'Same-year CALPADS Census Day K–12 FRPM eligibility divided by K–12 enrollment. '
    'Eligibility includes household applications or alternate income forms, direct '
    'certification, and categorical eligibility. This is eligibility, not the share '
    'receiving universally available meals, and is not the LCFF unduplicated pupil count.'
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cds(row):
    parts = [row[k] for k in ['County Code', 'District Code', 'School Code']]
    if any(not isinstance(v, str) or not v.isdigit() or len(v) != size
           for v, size in zip(parts, [2, 5, 7])):
        raise ValueError(f'Invalid authoritative CDS components: {parts}')
    return ''.join(parts)


def integer(value):
    if value in (None, '', '*'):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0 or result != int(result):
        raise ValueError(f'Invalid source count: {value!r}')
    return int(result)


def grade(value):
    if value in ['K', 'P']:
        return 0
    return int(value) if str(value).isdigit() and 0 <= int(value) <= 12 else None


def profile_span(profile):
    low, high = grade(profile['Low Grade']), grade(profile['High Grade'])
    if profile['School Type'] == 'N/A' or low is None or high is None or low > high:
        return None
    return low, high


def income_values(profile):
    if profile['Academic Year'] != ACADEMIC_YEAR:
        raise ValueError('Income must describe the assessment school year')
    enrollment, low = integer(profile['Enrollment (K-12)']), integer(profile['FRPM Count (K-12)'])
    raw = profile['Percent (%) Eligible FRPM (K-12)']
    fraction = None if raw in (None, '', '*') else float(raw)
    if fraction is not None and (not math.isfinite(fraction) or not 0 <= fraction <= 1):
        raise ValueError('Invalid California FRPM fraction')
    if low is not None and enrollment is not None and low > enrollment:
        raise ValueError('FRPM exceeds enrollment')
    if enrollment and low is not None and fraction is not None and abs(low/enrollment-fraction) > 1e-8:
        raise ValueError('Published FRPM fraction does not reconcile to Census Day counts')
    return enrollment, low, 100*fraction if fraction is not None and enrollment else None


def validate_grade(row):
    """Overall Total is the documented valid-score performance-level denominator."""
    n = integer(row['Overall Total'])
    scores = integer(row['Total Students Tested with Scores'])
    met = integer(row['Count Standard Met and Above'])
    raw_rate = row['Percentage Standard Met and Above']
    if n is None or met is None or scores is None or raw_rate in (None, '', '*'):
        return None, 'Missing or suppressed grade valid-score counts or proficiency'
    if n < 11:
        return None, 'Fewer than 11 valid scores under California reporting rules'
    if n != scores or met > n:
        raise ValueError('California valid-score count reconciliation failed')
    rate = float(raw_rate)
    if not math.isfinite(rate) or not 0 <= rate <= 100 or abs(rate-100*met/n) > .0051:
        raise ValueError('California published grade rate does not reconcile to counts')
    return (n, met), None


def aggregate(rows, expected):
    """Require every expected tested grade; never recover suppression from totals."""
    by_grade = {}
    for row in rows:
        g = int(row['Grade'])
        if g in by_grade:
            raise ValueError('Duplicate California school/subject/grade record')
        by_grade[g] = row
    if not expected or not set(expected).issubset(by_grade):
        return None, None, 'Missing an expected tested grade in the same-year school grade span'
    values = []
    for g in expected:
        value, reason = validate_grade(by_grade[g])
        if reason:
            return None, None, reason
        values.append(value)
    tested = sum(v[0] for v in values)
    proficient = sum(v[1] for v in values)
    return 100*proficient/tested, tested, None


def extract(raw=RAW, destination=EXTRACT):
    raw = Path(raw)
    sources = {}
    for ident, filename, url in [
        ('ca-sb-2025', 'sb_ca2025_1_csv_v1.zip', ASSESSMENT_URL),
        ('ca-frpm-2025', 'frpm2425.xlsx', INCOME_URL),
        ('ca-sb-layout-2025', '2025_SBAC_Research_File_Layout.xlsx', LAYOUT_URL),
    ]:
        path = raw / filename
        sources[ident] = dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                              url=url, sha256=digest(path))
    workbook = openpyxl.load_workbook(raw/'frpm2425.xlsx', read_only=True, data_only=True)
    iterator = iter(workbook['FRPM School-Level Data'].values)
    next(iterator)
    headers = [' '.join(str(v).split()) for v in next(iterator)]
    if not set(PROFILE_FIELDS).issubset(headers):
        raise ValueError('California FRPM workbook structure changed')
    profiles = []
    seen = set()
    for number, values in enumerate(iterator, 3):
        row = dict(zip(headers, values))
        row = {k: row[k] for k in PROFILE_FIELDS}
        key = cds(row)
        if key in seen:
            raise ValueError('Duplicate FRPM school identity')
        seen.add(key)
        income_values(row)
        profiles.append(dict(school_id=key, source_row=number, raw=row))
    workbook.close()
    observations = []
    with zipfile.ZipFile(raw/'sb_ca2025_1_csv_v1.zip') as archive:
        with archive.open('sb_ca2025_1_csv_v1.txt') as source:
            reader = csv.DictReader(io.TextIOWrapper(source, encoding='cp1252'), delimiter='^')
            if not set(FIELDS).issubset(reader.fieldnames):
                raise ValueError('California CAASPP research-file structure changed')
            for number, row in enumerate(reader, 2):
                if row['Type ID'] not in SCHOOL_TYPES:
                    continue
                if row['Test Year'] != str(YEAR) or row['Test Type'] != 'B' or row['Student Group ID'] != '1':
                    raise ValueError('Unexpected assessment year, test, or student group')
                if row['Test ID'] not in SUBJECTS or row['Grade'] not in {'3', '4', '5', '6', '7', '8', '11', '13'}:
                    raise ValueError('Unexpected assessment subject or grade')
                cds(row)
                observations.append([number, *[row[k] for k in FIELDS]])
    payload = dict(schema_version=1, state='CA', year=YEAR, academic_year=ACADEMIC_YEAR,
                   retrieved=datetime.now(timezone.utc).isoformat(), sources=sources,
                   assessment_fields=FIELDS, profiles=profiles, assessments=observations)
    Path(destination).write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    return payload


def normalized(payload):
    if (payload['schema_version'], payload['state'], payload['year'], payload['academic_year']) != (1, 'CA', YEAR, ACADEMIC_YEAR):
        raise ValueError('Unexpected California extract identity')
    if payload['assessment_fields'] != FIELDS:
        raise ValueError('Unexpected California extracted fields')
    profiles = {}
    ignored = Counter()
    seen_profiles = set()
    for entry in payload['profiles']:
        p, key = entry['raw'], entry['school_id']
        if key != cds(p) or key in seen_profiles:
            raise ValueError('Invalid or duplicate California profile ID')
        seen_profiles.add(key)
        income_values(p)
        if profile_span(p) is None:
            ignored['Unsupported or nonpublic school grade span'] += 1
            continue
        profiles[key] = entry
    raw_groups = defaultdict(list)
    seen = set()
    for values in payload['assessments']:
        if len(values) != len(FIELDS)+1:
            raise ValueError('Invalid extracted assessment row length')
        row = dict(zip(FIELDS, values[1:]))
        key = cds(row)
        if row['Type ID'] not in SCHOOL_TYPES or row['Test Year'] != str(YEAR) or row['Test Type'] != 'B' or row['Student Group ID'] != '1':
            raise ValueError('Invalid extracted school assessment scope')
        subject, g = SUBJECTS[row['Test ID']], int(row['Grade'])
        ident = (key, subject, g)
        if ident in seen:
            raise ValueError('Duplicate California assessment school/subject/grade')
        seen.add(ident)
        row['source_row'] = values[0]
        if key not in profiles:
            ignored['Assessment without supported same-year public school profile'] += 1
            continue
        raw_groups[(key, subject)].append(row)
    observations = []
    for key, entry in profiles.items():
        low, high = profile_span(entry['raw'])
        for level, expected in [('ES', list(range(max(low, 3), min(high, 8)+1))),
                                ('HS', [11] if low <= 11 <= high else [])]:
            if not expected:
                continue
            for subject in ['math', 'reading']:
                rows = raw_groups[(key, subject)]
                pct, tested, reason = aggregate(rows, expected)
                observations.append(dict(school_id=key, year=YEAR, level=level,
                    assessment=ASSESSMENTS[level], subject=subject, proficiency=pct, tested=tested,
                    exclusion=reason, expected_grades=expected, raw=rows))
    return profiles, observations, dict(ignored)


def import_data(db, payload):
    profiles, observations, ignored = normalized(payload)
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?', (DATASET+':%',))
    db.execute('INSERT OR REPLACE INTO dataset VALUES (?,?,?,?,?)',
               (DATASET, 'CA', 'California 2024–25 Smarter Balanced',
                'Separate statewide Smarter Balanced grades 3–8 and grade 11 annual cohorts', 'ready'))
    sources = dict(payload['sources'])
    sources['ca-extract-2025'] = dict(path=str(EXTRACT.relative_to(ROOT)), url=RESEARCH_URL, sha256=digest(EXTRACT))
    for ident, source in sources.items():
        if len(source['sha256']) != 64 or any(c not in '0123456789abcdef' for c in source['sha256']):
            raise ValueError('Invalid California source checksum')
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
                   (ident, DATASET, source['path'], source['url'], source['sha256'], payload['retrieved']))
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',
               ('ca-frpm-2025', 'California FRPM eligibility 2024–25', ECON_DEFINITION, INCOME_INFO_URL))
    for level, assessment in ASSESSMENTS.items():
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
                   (definition_id(DATASET, YEAR, assessment, level), 'CA', assessment, YEAR, level,
                    '3–8' if level == 'ES' else '11',
                    '2024–25 CAASPP Smarter Balanced Standard Met or Exceeded (Levels 3+4); '
                    'all students, valid scores only. California alternate assessments are excluded. '
                    'Exact proficient and valid-score counts are summed across complete tested grades.', LAYOUT_URL))
    for key, entry in profiles.items():
        p = entry['raw']
        total, low, pct = income_values(p)
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, key, p['School Name'], key[:7], p['District Name'], None,
                    p['County Name'], json.dumps(p), 'ca-frpm-2025', entry['source_row']))
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, key, YEAR, 'ca-frpm-2025', p['School Name'], total, low, pct,
                    'FRPM eligibility (K-12)', json.dumps(p), 'ca-frpm-2025', entry['source_row']))
    for order, row in enumerate(observations):
        db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, row['school_id'], definition_id(DATASET, YEAR, row['assessment'], row['level']),
                    row['subject'], row['proficiency'], row['tested'],
                    'reported' if row['proficiency'] is not None else 'suppressed_or_not_reported',
                    json.dumps(dict(expected_grades=row['expected_grades'], exclusion=row['exclusion'], rows=row['raw'])),
                    json.dumps([r['Overall Total'] for r in row['raw']]), 'ca-sb-2025', order))
    return profiles, observations, ignored


def prepare(database=DEFAULT_DB, output=OUTPUT):
    payload = json.loads(EXTRACT.read_text())
    with connect(database) as db:
        profiles, raw_observations, ignored = import_data(db, payload)
        observations = pl.DataFrame([{k: r[k] for k in ['school_id', 'year', 'level', 'assessment', 'subject', 'proficiency', 'tested']}
                                      for r in raw_observations], infer_schema_length=None)
        incomes = pl.DataFrame([dict(r) for r in db.execute(
            'SELECT school_id,year,name,enrollment,low_income,percentage FROM economic_observation WHERE dataset_id=?', (DATASET,))], infer_schema_length=None)
        records, models = build_history(observations, incomes)
        if not models:
            raise ValueError('California has no eligible models; do not publish a ready dataset')
        save_models(db, records, models, DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('California foreign key validation failed')
    by_key = {(r['school_id'], r['level']): r for r in records}
    for raw in raw_observations:
        if raw['exclusion']:
            by_key[(raw['school_id'], raw['level'])]['exclusions'][raw['subject']] = raw['exclusion']
    schools = []
    for key, entry in profiles.items():
        p = entry['raw']
        low, high = profile_span(p)
        if high < 3:
            continue
        level = 'HS' if high >= 9 else 'ES'
        annual = by_key.get((key, level))
        total, _, income = income_values(p)
        schools.append(dict(id=key, name=p['School Name'], short=p['School Name'], level=level,
            program='Unclassified', district=p['District Name'], county=p['County Name'], city=None,
            income=income, enrollment=total, latitude=None, longitude=None,
            metrics=annual['subjects'] if annual else {}, exclusions=annual['exclusions'] if annual else
                {s: 'No applicable tested-grade result for this school level' for s in ['math', 'reading', 'combined']},
            history=[annual] if annual else []))
    levels = {level: dict(year=YEAR, label='Grade schools · Smarter Balanced' if level == 'ES' else 'High schools · Smarter Balanced',
                assessment=assessment, outcome='Standard met or exceeded', math_label='Math',
                note=assessment+' · valid scores · California alternate assessments excluded')
              for level, assessment in ASSESSMENTS.items()}
    coverage = ('California 2024–25 Smarter Balanced only. Every grade in the same-year school grade span '
                'must have unsuppressed valid-score and proficient counts. Grade 11 is modeled separately '
                'from grades 3–8. Schools serving any high-school grades appear only in the high-school list; '
                'their eligible grades 3–8 results still enter that statewide assessment cohort. '
                'FRPM is same-year Census Day K–12 eligibility. Alternate assessments are excluded. '
                'This release contains one year, no verified admissions classifications and no map coordinates.')
    methodology = dict(summary='California Smarter Balanced Standard Met or Exceeded with same-year FRPM eligibility.', details=[
        'Proficiency is the exact number at Standard Met or Exceeded divided by the exact valid-score total. '
        'Grades 3–8 require every expected grade in the published same-year grade span. Any missing or suppressed component excludes that subject; schoolwide totals never reconstruct suppressed grades.',
        'Grade 11 and grades 3–8 have separate regressions. Mixed-grade schools contribute independently to eligible assessment cohorts, while grade-school list filters exclude schools serving high-school grades. Grade mix and whole-school versus tested-grade enrollment remain limitations.',
        ECON_DEFINITION,
        'This is a single-year 2024–25 snapshot. California alternate assessments are outside these Smarter Balanced files. Suppression remains unavailable. No verified admissions classification or school coordinates are included. State standards and FRPM definitions are not a national comparison scale.',
    ], sources=[dict(label='CDE CAASPP research files and suppression rules', url=RESEARCH_URL),
                dict(label='Official 2025 research-file field definitions', url=LAYOUT_URL),
                dict(label='Official 2024–25 FRPM workbook and field definitions', url=INCOME_URL),
                dict(label='CDE FRPM eligibility definition', url=INCOME_INFO_URL)])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    result = dict(year='2024–25', assessment_year=YEAR, income_label='FRPM eligible', levels=levels,
                  program_options=['Unclassified'], schools=sorted(schools, key=lambda s: s['id']),
                  models={level: {s: next((m for m in models if m['level'] == level and m['subject'] == s), None)
                                  for s in ['math', 'reading', 'combined']} for level in levels},
                  history_years=[YEAR], history_models=models, coverage_note=coverage, methodology=methodology)
    audit = dict(year=YEAR, directory_schools=len(schools), ignored_sources=ignored,
                 eligible_models=[{k: m[k] for k in ['level', 'subject', 'n', 'excluded_schools']} for m in models],
                 exclusions=dict(Counter(reason for r in records for reason in r['exclusions'].values())),
                 joins='Authoritative 14-digit CDS code and school year ending 2025 only', map_coordinates=0)
    catalog = dict(schema_version=1, prepare_script='scripts/prepare_california.py', state=dict(id='CA', name='California'), regions=[dict(
        id='california', name='Statewide', dataset=DATASET, status='ready', geography='california', levels=['ES', 'HS'],
        schools='data/california/schools.json', boundaries=None,
        comparison='Comparison population: California statewide · {year} {note}. Same-year FRPM eligibility; separate grades 3–8 and grade 11 assessment cohorts.',
        model_scope='California all-students Smarter Balanced valid-score cohorts; separate tested grades',
        map_source='School coordinates are unavailable in the audited California sources.', audit='data/california/audit.json')])
    for filename, value in [('schools.json', result), ('history.json', dict(records=records, models=models)),
                            ('audit.json', audit), ('catalog.json', catalog)]:
        (output/filename).write_text(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')
    print(json.dumps(audit, indent=2))
    return result, audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--raw', type=Path, default=RAW)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.extract:
        extract(args.raw)
    prepare(args.database, args.output)
