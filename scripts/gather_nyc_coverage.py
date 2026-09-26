"""Gather and audit NYC expansion sources without changing published models.

--extract reads the official downloads listed in SOURCES (mdbtools required).
Without it, rebuild the coverage audit solely from the committed extract.
NYSED identifiers and definitions remain separate from NYCPS's DBN series.
"""
import argparse
from collections import Counter
import csv
import hashlib
from html.parser import HTMLParser
import json
import re
import subprocess
import zipfile

import polars as pl
from database import ROOT

RAW = ROOT / 'data/raw'
EXTRACT = ROOT / 'data/source/nyc-expansion.json'
AUDIT = ROOT / 'data/nyc/expansion-coverage.json'
SOURCES = {
    'assessment': ('ny-src2025.zip', 'https://data.nysed.gov/files/essa/24-25/SRC2025.zip'),
    'enrollment': ('ny-enrollment2025.zip', 'https://data.nysed.gov/files/enrollment/24-25/ENROLLMENT_2025.zip'),
    'charters': ('ny-charter-directory2025.xlsx', 'https://www.nysed.gov/sites/default/files/programs/charter-schools/nys-charter-school-directory-as-of-09-02-2025.xlsx'),
    'admissions': ('nyc-admissions2021.json', 'https://data.cityofnewyork.us/resource/8b6c-7uty.json?$limit=5000'),
    'admissions_metadata': ('nyc-admissions2021-metadata.json', 'https://data.cityofnewyork.us/api/views/8b6c-7uty.json'),
}
DIRECTORY_SOURCES = {
    'crosswalk': ('nyc-lcgms.xls', 'https://www.nycenet.edu/PublicApps/LCGMS.aspx'),
    'charter_admissions': ('nyc-charter-admissions.html', 'https://www.schools.nyc.gov/enrollment/enroll-in-charter-schools/how-to-enroll-in-charter-schools'),
}
BOROUGHS = {'31', '32', '33', '34', '35'}
REGENTS = {'Regents Common Core English Language Art', 'Regents Common Core Algebra I', 'Regents Algebra I'}


def admissions_rows(schools):
    rows = []
    for school in schools:
        for key in sorted(school):
            match = re.fullmatch(r'program(\d+)', key)
            if match:
                i = match[1]
                rows.append(dict(dbn=school['dbn'], school_name=school['school_name'],
                    program=school[key], code=school.get('code'+i), method=school.get('method'+i),
                    directory_year=2021,
                    # Source has priorities 1–4, followed by program slot 1–12.
                    # Do not attach program 11's priority 1 to program 1.
                    priorities={k:v for k,v in school.items() if re.fullmatch(r'admissionspriority[1-4]'+i, k)}))
    return rows


def read_crosswalk(path):
    # The official .xls download is an HTML table with omitted closing TR tags.
    class Table(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows, self.row, self.cell = [], [], None

        def handle_starttag(self, tag, attrs):
            if tag == 'tr':
                if self.row:
                    self.rows.append(self.row)
                self.row = []
            if tag in ('td', 'th'):
                self.cell = ''

        def handle_data(self, data):
            if self.cell is not None:
                self.cell += data

        def handle_endtag(self, tag):
            if tag in ('td', 'th'):
                self.row.append(self.cell.strip())
                self.cell = None
            if tag in ('tr', 'table') and self.row:
                self.rows.append(self.row)
                self.row = []

    table = Table()
    table.feed(path.read_text(encoding='utf-16'))
    fields = ['ATS System Code', 'BEDS Number', 'Location Name', 'Managed By Name',
              'Location Category Description', 'Grades', 'Status Description']
    if not set(fields) <= set(table.rows[0]):
        raise ValueError('LCGMS columns changed')
    rows = []
    for values in table.rows[1:]:
        if len(values) != len(table.rows[0]):
            raise ValueError('Malformed LCGMS row')
        r = dict(zip(table.rows[0], values))
        if re.fullmatch(r'\d{2}[MKQRX]\d{3}', r['ATS System Code']):
            rows.append({k:r[k] for k in fields})
    return rows


def enrich_directories(payload):
    for key, (filename, url) in {**DIRECTORY_SOURCES, **{k:SOURCES[k] for k in ['admissions','admissions_metadata']}}.items():
        path = RAW / filename
        with path.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        payload['sources'][key] = dict(path=str(path.relative_to(ROOT)), url=url, sha256=checksum)
    payload['crosswalk'] = read_crosswalk(RAW / DIRECTORY_SOURCES['crosswalk'][0])
    payload['admissions'] = admissions_rows(json.loads((RAW / SOURCES['admissions'][0]).read_text()))
    payload['admissions_metadata'] = json.loads((RAW / SOURCES['admissions_metadata'][0]).read_text())
    payload['charter_admissions'] = dict(
        method='Open enrollment; random selection when oversubscribed',
        source=DIRECTORY_SOURCES['charter_admissions'][1],
        retrieved='2026-09-26', school_specific_priorities='Not collected',
        note='General charter admissions framework, not a claim that all applicants have equal priority.')
    return payload


def mdb_rows(path, table):
    process = subprocess.Popen(['mdb-export', str(path), table], stdout=subprocess.PIPE, text=True)
    try:
        yield from csv.DictReader(process.stdout)
    finally:
        process.stdout.close()
        code = process.wait()
        if code:
            raise RuntimeError(f'mdb-export failed for {table}: {code}')


def extract():
    import openpyxl
    sources = {}
    for key, (filename, url) in SOURCES.items():
        path = RAW / filename
        with path.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        sources[key] = dict(path=str(path.relative_to(ROOT)), url=url,
                            sha256=checksum)
    databases = {}
    for key in ['assessment', 'enrollment']:
        with zipfile.ZipFile(RAW / SOURCES[key][0]) as archive:
            members = [n for n in archive.namelist() if n.endswith('.mdb')]
            if len(members) != 1:
                raise ValueError('Expected one MDB per archive')
            folder = RAW / f'nyc-expansion-{key}'
            folder.mkdir(exist_ok=True)
            databases[key] = folder / members[0]
            archive.extract(members[0], folder)
    institutions = [r for r in mdb_rows(databases['assessment'], 'Institution Grouping')
                    if r['GROUP_CODE'] == '6' and r['ENTITY_CD'][:2] in BOROUGHS]
    ids = {r['ENTITY_CD'] for r in institutions}
    assessments = []
    for table in ['Annual EM ELA', 'Annual EM MATH', 'Annual Regents Exams']:
        for r in mdb_rows(databases['assessment'], table):
            name = r.get('ASSESSMENT_NAME', r.get('SUBJECT'))
            if (r['ENTITY_CD'] in ids and r['SUBGROUP_NAME'] == 'All Students'
                    and (name.upper() in {'ELA3_8', 'MATH3_8'} or name in REGENTS)):
                assessments.append(dict(table=table, **r))
    demographics = [r for r in mdb_rows(databases['enrollment'], 'Demographic Factors') if r['ENTITY_CD'] in ids]
    enrollment = [r for r in mdb_rows(databases['enrollment'], 'BEDS Day Enrollment') if r['ENTITY_CD'] in ids]
    workbook = openpyxl.load_workbook(RAW / SOURCES['charters'][0], read_only=True, data_only=True)
    charters = []
    for row in list(workbook.active.values)[2:]:
        if row[6] == 'New York City':
            charters.append(dict(beds=str(int(row[2])), institution_id=str(int(row[1])), name=row[3],
                                 district=row[4], county=row[5], opened=row[7], authorizer=row[8]))
    workbook.close()
    payload = dict(retrieved='2026-09-26', sources=sources, institutions=institutions,
                   assessments=assessments, demographics=demographics, enrollment=enrollment,
                   charters=charters)
    EXTRACT.write_text(json.dumps(enrich_directories(payload), separators=(',', ':'), allow_nan=False))


def numeric(raw):
    if raw in ('', 's', '-', '*', None):
        return None
    if not re.fullmatch(r'\d+(?:\.\d+)?', str(raw)):
        raise ValueError(f'Unexpected numeric value {raw!r}')
    return float(raw)


def unique(rows, keys):
    frame = pl.DataFrame(rows, infer_schema_length=None)
    if frame.select(keys).is_duplicated().any():
        raise ValueError(f'Duplicate source identity: {keys}')


def audit(payload):
    unique(payload['institutions'], ['ENTITY_CD'])
    unique(payload['demographics'], ['ENTITY_CD', 'YEAR'])
    unique(payload['enrollment'], ['ENTITY_CD', 'YEAR'])
    unique(payload['assessments'], ['ENTITY_CD', 'YEAR', 'table', 'ASSESSMENT_NAME', 'SUBJECT'])
    unique(payload['charters'], ['beds'])
    unique(payload['admissions'], ['dbn', 'program', 'code'])
    charter_ids = {r['beds'] for r in payload['charters']}
    school_ids = {r['ENTITY_CD'] for r in payload['institutions']}
    income = {(r['ENTITY_CD'], r['YEAR']):r for r in payload['demographics']}
    enrollment = {(r['ENTITY_CD'], r['YEAR']):r for r in payload['enrollment']}
    counts = Counter()
    for r in payload['assessments']:
        sid, year = r['ENTITY_CD'], r['YEAR']
        name = r.get('ASSESSMENT_NAME', r.get('SUBJECT'))
        sector = 'directory_charter' if sid in charter_ids else 'other_public'
        key = (year, name, sector)
        n, k, p = [numeric(r[c]) for c in [('TESTED' if r['table']=='Annual Regents Exams' else 'NUM_TESTED'), 'NUM_PROF', 'PER_PROF']]
        if any(v is not None and (v < 0 or v != int(v)) for v in [n, k]):
            raise ValueError('Invalid assessment count')
        if k is not None and n is not None and k > n:
            raise ValueError('Proficient count exceeds valid-score count')
        if p is not None and not 0 <= p <= 100:
            raise ValueError('Invalid assessment rate')
        if n and k is not None and p is not None and abs(p-100*k/n) > .50001:
            raise ValueError('Published whole-percent proficiency does not reconcile')
        economic = income.get((sid,year), {})
        percent = numeric(economic.get('PER_ECDIS'))
        low = numeric(economic.get('NUM_ECDIS'))
        total = numeric(enrollment.get((sid,year),{}).get('K12'))
        if percent is not None and not 0 <= percent <= 100:
            raise ValueError('Invalid economic-disadvantage rate')
        if total and low is not None and percent is not None and abs(percent-100*low/total) > .50001:
            raise ValueError('Economic-disadvantage percentage does not reconcile')
        counts[key+('source_rows',)] += 1
        if p is None:
            counts[key+('missing_or_suppressed_proficiency',)] += 1
        if percent is None:
            counts[key+('missing_or_suppressed_income',)] += 1
        if n is None or n < 10:
            counts[key+('missing_or_small_tested_count',)] += 1
        if p is not None and percent is not None and n is not None and n >= 10:
            counts[key+('numeric_join_with_valid_count',)] += 1
    groups = sorted({k[:3] for k in counts})
    summary = [dict(year=int(y), assessment=a, sector=s,
                    **{field:counts[(y,a,s,field)] for field in ['source_rows', 'numeric_join_with_valid_count',
                       'missing_or_suppressed_proficiency','missing_or_suppressed_income','missing_or_small_tested_count']})
               for y,a,s in groups]
    website_ids = {s['id'] for s in json.loads((ROOT/'data/nyc/schools.json').read_text())['schools']}
    matched = {r['dbn'] for r in payload['admissions']} & website_ids
    crosswalk = {}
    for r in payload.get('crosswalk', []):
        if re.fullmatch(r'\d{12}', r['BEDS Number']):
            crosswalk.setdefault(r['BEDS Number'], set()).add(r['ATS System Code'])
    return dict(status='gathered_not_published', retrieved=payload['retrieved'],
        source_urls={k:v['url'] for k,v in payload['sources'].items()},
        charter_directory_schools=len(charter_ids), charter_directory_matched_institution=len(charter_ids & school_ids),
        charter_directory_unmatched=sorted(charter_ids-school_ids), assessment_coverage=summary,
        crosswalk=dict(vintage='Retrieved 2026-09-26; current LCGMS, not historical identity evidence',
            charter_beds_with_one_dbn=sum(len(crosswalk.get(sid, set())) == 1 for sid in charter_ids),
            charter_beds_without_dbn=sorted(sid for sid in charter_ids if sid not in crosswalk),
            ambiguous_beds={sid:sorted(dbns) for sid,dbns in sorted(crosswalk.items()) if len(dbns)>1}),
        admissions=dict(directory_year=2021, schools=len({r['dbn'] for r in payload['admissions']}),
            programs=len(payload['admissions']), matched_website_schools=len(matched),
            methods=dict(sorted(Counter(r['method'] or 'Unavailable' for r in payload['admissions']).items())),
            current_program_coverage='Unavailable; historical directory is not current admissions evidence'),
        limitations=[
            'NYSED BEDS IDs are retained alongside the official current LCGMS crosswalk. Missing or ambiguous mappings are not inferred.',
            'NYSED economic disadvantage and NYCPS Poverty are separate definitions. Do not append one to the other model.',
            'NYSED MATH3_8 includes Regents mathematics results; it is not the NYCPS NYSTP-only outcome.',
            '2024 Regents has old and new Algebra I examinations; do not add their counts or average rates across overlapping takers.',
            '2025-26 charter directory is a dated identification source, not a complete historical charter roster.',
            'A numeric join indicates source readiness, not authorization to publish a mixed-cohort ranking.',
            'Current charter lottery framework is verified, but school-specific priorities and current district program admissions are not fully covered.',
        ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--directories', action='store_true', help='Refresh only the current crosswalk and charter admissions evidence')
    args = parser.parse_args()
    if args.extract:
        extract()
    elif args.directories:
        payload = enrich_directories(json.loads(EXTRACT.read_text()))
        EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))
    result = audit(json.loads(EXTRACT.read_text()))
    AUDIT.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
