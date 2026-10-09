"""Official Colorado 2024–25 CMAS school totals, SAT grade 11, and FRL eligibility."""
import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET = 'co-cde-2025'
YEAR = 2025
RAW = ROOT/'data/raw/colorado'
EXTRACT = ROOT/'data/source/colorado.json'
OUTPUT = ROOT/'data/colorado'
HOST = 'https://ed.cde.state.co.us'
CMAS_PAGE = HOST+'/assessment/cmas-dataandresults-2025'
SAT_PAGE = HOST+'/assessment/sat-psat/sat-psat-data'
INCOME_PAGE = HOST+'/cdereval/pupilmembership-statistics/data-insights-resources-archives'
ELIGIBILITY_PAGE = HOST+'/nutrition/manage-program-operations/determine-program-eligibility'
FILES = {
    'co-cmas-2025': ('cmas2025.xlsx', HOST+'/fs/resource-manager/view/5c130960-c90c-444a-98dc-41b35c11431b'),
    'co-sat-2025': ('sat2025.xlsx', HOST+'/fs/resource-manager/view/37066be1-57a4-40f4-8235-3c1b10cb0e75'),
    'co-frl-2025': ('frl2025.xlsx', HOST+'/fs/resource-manager/view/edf7f72b-6728-4b48-a3aa-ae75ab2ad968'),
    'co-grades-2025': ('grades2025.xlsx', HOST+'/fs/resource-manager/view/7efacffc-8335-4735-9b12-fee840351810'),
    'co-cmas-layout-2025': ('cmas2025-layout.pdf', HOST+'/fs/resource-manager/view/f6b76141-39d7-4787-b7e9-5a5777952cb7'),
    'co-sat-layout-2025': ('sat2025-layout.pdf', HOST+'/fs/resource-manager/view/7bd1ffa6-490b-44b9-9dee-933d32a9c0c7'),
}
GRADE_FIELDS = {g: f'{g}{"st" if g == 1 else "nd" if g == 2 else "rd" if g == 3 else "th"}' for g in range(1, 13)}
ECON_DEFINITION = ('Same-year Student October Count K–12 free or reduced-price lunch eligibility. '
    'Household income applications, alternate forms, direct certification and categorical eligibility '
    'support eligibility. No-cost meals through Healthy School Meals for All are available regardless '
    'of eligibility and do not establish universal economic disadvantage.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(raw):
    value = str(raw).strip() if raw is not None else ''
    if value in ['', '*', '- -', '--', 'N/A'] or value.startswith('<'):
        return None
    result = float(value.replace(',', ''))
    if not math.isfinite(result):
        raise ValueError('Non-finite Colorado source number')
    return result


def count(raw):
    result = number(raw)
    if result is not None and (result < 0 or result != int(result)):
        raise ValueError('Colorado count must be an exact nonnegative integer')
    return int(result) if result is not None else None


def sid(row):
    district = row.get('Organization Code', row.get('District Code'))
    school = row['School Code']
    if any(not isinstance(v, str) or len(v) != 4 or not v.isdigit() for v in [district, school]):
        raise ValueError('Colorado requires authoritative four-digit district and school codes')
    return district+school


def workbook_rows(path, header_row, upper_row=None):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.values)
    headers = [' '.join(str(v).split()) if v is not None else None for v in rows[header_row-1]]
    if upper_row:
        headers = [value or ' '.join(str(rows[upper_row-1][i]).split()) for i, value in enumerate(headers)]
    result = [(i, {key: v for key, v in zip(headers, row) if key})
              for i, row in enumerate(rows[header_row:], header_row+1)]
    workbook.close()
    return result


def income_values(row):
    total, low = count(row['K-12 Count']), count(row['Free and Reduced Count'])
    fraction = number(row['% Free and Reduced'])
    if total is not None and low is not None and low > total:
        raise ValueError('Colorado FRL eligibility exceeds K–12 enrollment')
    if fraction is not None and not 0 <= fraction <= 1:
        raise ValueError('Invalid Colorado FRL fraction')
    if total and low is not None and fraction is not None and abs(low/total-fraction) > .00051:
        raise ValueError('Published Colorado FRL fraction fails its three-decimal rounding check')
    return total, low, 100*fraction if total and fraction is not None else None


def assessment_values(row, level):
    n_field, met_field, pct_field = (('Number of Valid Scores', 'Number Met or Exceeded Expectations', '2025')
        if level == 'ES' else ('Number of Valid Scores 2025', 'Number Met or Exceeded Expectations 2025',
                              'Percent Met or Exceeded Expectations 2025'))
    n, met, pct = count(row[n_field]), count(row[met_field]), number(row[pct_field])
    if n is None or met is None or pct is None:
        return None, None, 'Missing or suppressed school proficiency or valid-score counts'
    if n < 16:
        return None, None, 'Fewer than 16 valid scores under Colorado reporting rules'
    if met > n or not 0 <= pct <= 100 or abs(pct-100*met/n) > .051:
        raise ValueError('Colorado published school proficiency does not reconcile to valid-score counts')
    return 100*met/n, n, None


def extract(raw=RAW, destination=EXTRACT):
    raw = Path(raw)
    sources = {ident: dict(path=str((raw/filename).relative_to(ROOT)) if (raw/filename).is_relative_to(ROOT) else str(raw/filename),
                           url=url, sha256=digest(raw/filename)) for ident, (filename, url) in FILES.items()}
    profiles = []
    for number, row in workbook_rows(raw/'grades2025.xlsx', 3):
        if not isinstance(row.get('Organization Code'), str) or not row['Organization Code'].isdigit():
            continue
        key = sid(row)
        if key == '99999999':
            continue
        profiles.append(dict(school_id=key, source_row=number, raw=row))
    incomes = []
    for number, row in workbook_rows(raw/'frl2025.xlsx', 3):
        if not isinstance(row.get('Organization Code'), str) or not row['Organization Code'].isdigit():
            continue
        key = sid(row)
        if key == '99999999':
            continue
        income_values(row)
        incomes.append(dict(school_id=key, source_row=number, raw=row))
    observations = []
    for level, filename, header, upper in [('ES', 'cmas2025.xlsx', 18, None), ('HS', 'sat2025.xlsx', 17, 16)]:
        for number, row in workbook_rows(raw/filename, header, upper):
            if row.get('Level') != 'SCHOOL':
                continue
            allowed = {'English Language Arts': 'reading', 'Mathematics': 'math'} if level == 'ES' else {'Reading and Writing': 'reading', 'Mathematics': 'math'}
            if row.get('Content') not in allowed or row.get('Grade') != ('All Grades' if level == 'ES' else 'SAT Grade 11'):
                continue
            assessment_values(row, level)
            observations.append(dict(school_id=sid(row), level=level, subject=allowed[row['Content']],
                                     source_row=number, raw=row))
    payload = dict(schema_version=1, state='CO', year=YEAR, academic_year='2024-2025',
                   retrieved=datetime.now(timezone.utc).isoformat(), sources=sources,
                   profiles=profiles, incomes=incomes, assessments=observations)
    Path(destination).write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    return payload


def import_data(db, payload):
    if (payload['schema_version'], payload['state'], payload['year'], payload['academic_year']) != (1, 'CO', YEAR, '2024-2025'):
        raise ValueError('Unexpected Colorado source identity or school year')
    profiles = {}
    for entry in payload['profiles']:
        key, row = entry['school_id'], entry['raw']
        if key != sid(row) or key in profiles:
            raise ValueError('Invalid or duplicate Colorado directory ID')
        if any(count(row[field]) is None for field in GRADE_FIELDS.values()):
            raise ValueError('Unusable Colorado grade membership data')
        profiles[key] = entry
    incomes = {}
    for entry in payload['incomes']:
        key, row = entry['school_id'], entry['raw']
        if key != sid(row) or key in incomes:
            raise ValueError('Invalid or duplicate Colorado income ID')
        income_values(row)
        incomes[key] = entry
    observations, seen, ignored = [], set(), Counter()
    for entry in payload['assessments']:
        key, level, subject, raw = entry['school_id'], entry['level'], entry['subject'], entry['raw']
        if key != sid(raw) or (key, level, subject) in seen:
            raise ValueError('Invalid or duplicate Colorado assessment identity')
        seen.add((key, level, subject))
        if (level not in ['ES', 'HS'] or subject not in ['math', 'reading'] or raw['Level'] != 'SCHOOL'
                or raw['Grade'] != ('All Grades' if level == 'ES' else 'SAT Grade 11')
                or raw['Content'] != ('Mathematics' if subject == 'math' else 'English Language Arts' if level == 'ES' else 'Reading and Writing')):
            raise ValueError('Colorado assessment population changed')
        if key not in profiles:
            ignored['Assessment without same-year grade membership'] += 1
            continue
        pct, tested, exclusion = assessment_values(raw, level)
        observations.append(dict(entry, year=YEAR, assessment='CMAS 2020 standards' if level == 'ES' else 'Digital SAT grade 11',
                                 proficiency=pct, tested=tested, exclusion=exclusion))
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?', (DATASET+':%',))
    db.execute('INSERT OR REPLACE INTO dataset VALUES (?,?,?,?,?)',
               (DATASET, 'CO', 'Colorado 2024–25 CMAS and SAT', 'Separate statewide CMAS and grade-11 SAT cohorts', 'ready'))
    sources = dict(payload['sources'])
    sources['co-extract-2025'] = dict(path=str(EXTRACT.relative_to(ROOT)), url=CMAS_PAGE, sha256=digest(EXTRACT))
    for ident, source in sources.items():
        if len(source['sha256']) != 64 or any(c not in '0123456789abcdef' for c in source['sha256']):
            raise ValueError('Invalid Colorado source checksum')
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
                   (ident, DATASET, source['path'], source['url'], source['sha256'], payload['retrieved']))
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',
               ('co-frl-2025', 'Colorado K–12 FRL eligibility 2024–25', ECON_DEFINITION, ELIGIBILITY_PAGE))
    for level, name in [('ES', 'CMAS 2020 standards'), ('HS', 'Digital SAT grade 11')]:
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
                   (definition_id(DATASET, YEAR, name, level), 'CO', name, YEAR, level,
                    '3–8' if level == 'ES' else '11',
                    '2025 CMAS Met or Exceeded Expectations; 2020 Colorado Academic Standards; ELA only, CSLA and CoAlt excluded.'
                    if level == 'ES' else '2025 digital SAT Met or Exceeded Expectations; published Colorado Reading and Writing and math categories; PSAT excluded.',
                    CMAS_PAGE if level == 'ES' else SAT_PAGE))
    for key, entry in profiles.items():
        p = entry['raw']
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, key, p['School Name'], key[:4], p['Organization Name'], None, None,
                    json.dumps(p), 'co-grades-2025', entry['source_row']))
        if key in incomes:
            income = incomes[key]
            total, low, pct = income_values(income['raw'])
            db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (DATASET, key, YEAR, 'co-frl-2025', p['School Name'], total, low, pct,
                        'K–12 FRL eligibility', json.dumps(income['raw']), 'co-frl-2025', income['source_row']))
    for row in observations:
        db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, row['school_id'], definition_id(DATASET, YEAR, row['assessment'], row['level']), row['subject'],
                    row['proficiency'], row['tested'], 'reported' if row['proficiency'] is not None else 'suppressed_or_not_reported',
                    json.dumps(row['raw']), str(row['raw']['Number of Valid Scores' if row['level'] == 'ES' else 'Number of Valid Scores 2025']),
                    'co-cmas-2025' if row['level'] == 'ES' else 'co-sat-2025', row['source_row']))
    return profiles, incomes, observations, dict(ignored)


def prepare(database=DEFAULT_DB, output=OUTPUT):
    payload = json.loads(EXTRACT.read_text())
    with connect(database) as db:
        profiles, incomes, raw_observations, ignored = import_data(db, payload)
        observations = pl.DataFrame([{k: r[k] for k in ['school_id', 'year', 'level', 'assessment', 'subject', 'proficiency', 'tested']}
                                     for r in raw_observations], infer_schema_length=None)
        income_frame = pl.DataFrame([dict(r) for r in db.execute(
            'SELECT school_id,year,name,enrollment,low_income,percentage FROM economic_observation WHERE dataset_id=?', (DATASET,))], infer_schema_length=None)
        records, models = build_history(observations, income_frame)
        if not models:
            raise ValueError('Colorado has no eligible models')
        save_models(db, records, models, DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Colorado foreign key check failed')
    by_key = {(r['school_id'], r['level']): r for r in records}
    for raw in raw_observations:
        if raw['exclusion']:
            by_key[(raw['school_id'], raw['level'])]['exclusions'][raw['subject']] = raw['exclusion']
    schools = []
    for key, entry in profiles.items():
        p = entry['raw']
        if not any(count(p[GRADE_FIELDS[g]]) for g in range(3, 13)):
            continue
        level = 'HS' if any(count(p[GRADE_FIELDS[g]]) for g in range(9, 13)) else 'ES'
        total, _, income = income_values(incomes[key]['raw']) if key in incomes else (None, None, None)
        annual = by_key.get((key, level))
        schools.append(dict(id=key, name=p['School Name'], short=p['School Name'], level=level,
            program='Unclassified', district=p['Organization Name'], city=None, county=None,
            income=income, enrollment=total, latitude=None, longitude=None,
            metrics=annual['subjects'] if annual else {}, history=[annual] if annual else [],
            exclusions=annual['exclusions'] if annual else {s: 'No applicable published school assessment total' for s in ['math', 'reading', 'combined']}))
    levels = {
        'ES': dict(year=YEAR, label='Grade schools · CMAS', assessment='CMAS 2020 standards', outcome='Met or exceeded expectations',
                   math_label='Math', note='CMAS grades 3–8 · 2020 Colorado Academic Standards · English ELA only'),
        'HS': dict(year=YEAR, label='High schools · SAT', assessment='Digital SAT grade 11', outcome='Met or exceeded expectations',
                   math_label='Math', note='Digital SAT grade 11 · Colorado published performance categories · PSAT excluded'),
    }
    details = [
        'Grade schools use official CMAS All Grades school totals covering grades 3–8. These are directly published totals; no grade percentages are averaged or suppressed grade components recovered. English ELA is separate from Spanish Language Arts; CSLA and CoAlt are outside these models.',
        'High schools use only the separate SAT Grade 11 rows. PSAT grades 9 and 10, the PSAT/SAT All Grades aggregate, and average scores are excluded. The source labels the outcome Met or Exceeded Expectations. Digital SAT began in 2024; this release includes only 2025.',
        'Exact published Number Met or Exceeded Expectations is divided by Number of Valid Scores, checked against the rounded published percentage. Participation records, no-score counts and enrollment never replace valid-score denominators. Suppressed and bounded values remain unavailable.',
        ECON_DEFINITION,
        'School IDs join the exact four-digit organization and school codes in the same academic year. Any school with enrolled high-school grades appears only in the high-school list, while eligible CMAS results from mixed-grade schools still fit their separate assessment cohort. Whole-school income, assessed-grade mix, participation and representativeness remain limitations. No admissions classifications or map coordinates are included.',
    ]
    methodology = dict(summary='Colorado 2024–25 CMAS grades 3–8 and separate digital SAT grade 11, with same-year K–12 FRL eligibility.',
        details=details, sources=[dict(label='CDE 2025 CMAS results and definitions', url=CMAS_PAGE),
        dict(label='CDE 2025 PSAT/SAT school results', url=SAT_PAGE), dict(label='CDE 2024–25 FRL and grade membership sources', url=INCOME_PAGE),
        dict(label='CDE meal eligibility and Healthy School Meals for All', url=ELIGIBILITY_PAGE)])
    result = dict(year='2024–25', assessment_year=YEAR, income_label='FRL eligible', levels=levels,
        program_options=['Unclassified'], schools=sorted(schools, key=lambda s: s['id']),
        models={level: {s: next((m for m in models if m['level'] == level and m['subject'] == s), None)
                        for s in ['math', 'reading', 'combined']} for level in levels},
        history_years=[YEAR], history_models=models, coverage_note=' '.join(details), methodology=methodology)
    audit = dict(year=YEAR, directory_schools=len(schools), ignored_sources=ignored,
        eligible_models=[{k: m[k] for k in ['level', 'subject', 'n', 'excluded_schools']} for m in models],
        exclusions=dict(Counter(reason for r in records for reason in r['exclusions'].values())), map_coordinates=0,
        joins='Authoritative four-digit organization plus four-digit school code; 2024–25 only')
    catalog = dict(schema_version=1, prepare_script='scripts/prepare_colorado.py', state=dict(id='CO', name='Colorado'), regions=[dict(
        id='colorado', name='Statewide', dataset=DATASET, status='ready', geography='colorado', levels=['ES', 'HS'],
        schools='data/colorado/schools.json', boundaries=None, map_source='School coordinates are unavailable in the audited Colorado sources.',
        comparison='Comparison population: Colorado statewide · {year} {note}. Separate assessment cohorts and same-year K–12 FRL eligibility.',
        model_scope='Colorado CMAS school totals and separate grade-11 digital SAT valid-score cohorts', audit='data/colorado/audit.json')])
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    for filename, value in [('schools.json', result), ('history.json', dict(records=records, models=models)), ('audit.json', audit), ('catalog.json', catalog)]:
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
