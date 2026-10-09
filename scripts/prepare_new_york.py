"""NYSED native 2024–25 grades 3–8 totals and same-year enrolled poverty status."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

RAW = ROOT / 'data/raw'
EXTRACT = ROOT / 'data/source/new-york.json'
YEAR = 2025
PORTAL = 'https://data.nysed.gov/downloads.php'
SRC_URL = 'https://data.nysed.gov/files/essa/24-25/SRC2025.zip'
ENROLL_URL = 'https://data.nysed.gov/files/enrollment/24-25/ENROLLMENT_2025.zip'
MANUAL_URL = 'https://www.nysed.gov/sites/default/files/programs/information-reporting-services/sirs-manual-2024-2025.pdf'
FILES = {
    'assessment': ('nysed-SRC2025.zip', SRC_URL),
    'enrollment': ('nysed-ENROLLMENT_2025.zip', ENROLL_URL),
    'manual': ('nysed-sirs-manual-2024-2025.pdf', MANUAL_URL),
}
GRADE_FIELDS = ['KHALF', 'KFULL', *map(str, range(1, 13)), 'UGE', 'UGS']
DEFINITION = ('Same-year BEDS-day K–12 enrollment classified under SIRS poverty service code 0198, '
    'divided by native K–12 enrollment including ungraded pupils. Individual/family participation '
    'in FRPL, SSI, SNAP, foster care, refugee assistance, EITC, HEAP, Safety Net Assistance, '
    'BIA or TANF can qualify. NYSED requires individual eligibility in CEP schools; universal '
    'meals alone do not qualify. This broader state poverty definition differs from the NYC '
    'economic-need indicator and from other states. Suppressed counts remain unavailable.')
STANDARD = ('Native NYSED Annual EM school totals ELA3_8 and MATH3_8, All Students. '
    'ELA proficiency is Levels 3–4; math is Levels 3 and above, including middle-grade Regents '
    'results in NYSED’s published total. NYSAA alternate results are separate and excluded. '
    'Rates use directly reported NUM_PROF / NUM_TESTED; NUM_TESTED means valid scores. '
    'TOTAL_COUNT includes students without a valid score and is never a tested denominator. '
    'No grade aggregation or reconstruction of suppressed cells.')


def identity(row):
    key = row['ENTITY_CD']
    if not isinstance(key, str) or not re.fullmatch(r'\d{12}', key):
        raise ValueError('Invalid NYSED BEDS entity code')
    return key


def count(value):
    return int(value) if isinstance(value, (str, int)) and re.fullmatch(r'\d+', str(value)) else None


def percentage(value):
    if not re.fullmatch(r'\d+(?:\.\d+)?', str(value)):
        return None
    result = float(value)
    if not 0 <= result <= 100:
        raise ValueError('Invalid NYSED percentage')
    return result


def cohort(row):
    values = {g: count(row[g]) for g in GRADE_FIELDS}
    if any(v is None for v in values.values()):
        return None
    if sum(values.values()) != count(row['K12']):
        raise ValueError('NYSED enrolled grade counts do not reconcile to K12')
    if not any(values[str(g)] for g in range(3, 9)):
        return None
    return 'mixed' if values['UGS'] or any(values[str(g)] for g in range(9, 13)) else 'grade'


def income(row, enrollment):
    numerator, published = count(row['NUM_ECDIS']), percentage(row['PER_ECDIS'])
    if numerator is None or published is None or not enrollment:
        return None, None
    if numerator > enrollment or abs(published - 100 * numerator / enrollment) > .5000001:
        raise ValueError('NYSED individual poverty count/percentage does not reconcile')
    return 100 * numerator / enrollment, numerator


def outcome(row, subject):
    tested, proficient = count(row['NUM_TESTED']), count(row['NUM_PROF'])
    published = percentage(row['PER_PROF'])
    rate = None
    if tested is not None and proficient is not None and published is not None:
        if proficient > tested or tested == 0:
            if tested or proficient or published:
                raise ValueError('Invalid NYSED valid-score proficiency count')
        else:
            rate = 100 * proficient / tested
            if abs(rate - published) > .5000001:
                raise ValueError('NYSED native total does not reconcile to published rate')
            levels = [count(row.get(f'LEVEL{g}_COUNT')) for g in range(1, 6 if subject == 'math' else 5)]
            if all(v is not None for v in levels) and (sum(levels) != tested or sum(levels[2:]) != proficient):
                raise ValueError('NYSED native performance counts do not reconcile')
    return dict(proficiency=rate, tested=tested, raw=row, raw_tested=row['NUM_TESTED'],
        source='assessment', valid_score_evidence='SRC2025 ReadMe pp.17–18: NUM_TESTED is students with valid scores; NUM_PROF is Levels3 and above',
        exclusion='Missing or suppressed native grades3–8 school total or proficiency count' if rate is None else None)


def native_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as stream:
        for number, row in enumerate(csv.DictReader(stream), 2):
            if row['YEAR'] == str(YEAR):
                identity(row)
                yield number, row


def export_tables():
    # mdbtools is needed only to reproduce the normalized source extract.
    mappings = [('nysed-ENROLLMENT_2025.zip', 'ENROLL2025_20251217.mdb', 'nysed-enrollment-2025',
                 [('BEDS Day Enrollment', 'beds'), ('Demographic Factors', 'demographics'), ('BOCES and N/RC', 'directory')]),
                ('nysed-SRC2025.zip', 'SRC2025_Group4.mdb', 'nysed-src-2025',
                 [('Annual EM ELA', 'ela'), ('Annual EM MATH', 'math')])]
    for archive, member, directory, tables in mappings:
        destination = RAW / directory
        destination.mkdir(exist_ok=True)
        with zipfile.ZipFile(RAW / archive) as z:
            z.extract(member, destination)
            for name in z.namelist():
                if name.endswith('.pdf'):
                    z.extract(name, destination)
        for table, name in tables:
            with open(RAW / f'nysed-{name}-2025.csv', 'w') as stream:
                subprocess.run(['mdb-export', str(destination / member), table], stdout=stream, check=True)


def extract():
    sources = {key: dict(path=str((RAW / name).relative_to(ROOT)), url=url,
        sha256=hashlib.sha256((RAW / name).read_bytes()).hexdigest()) for key, (name, url) in FILES.items()}
    directories = {identity(r): (number, r) for number, r in native_rows(RAW / 'nysed-directory-2025.csv')}
    if len(directories) != sum(1 for _ in native_rows(RAW / 'nysed-directory-2025.csv')):
        raise ValueError('Duplicate NYSED school directory identity/year')
    profiles, excluded = {}, Counter()
    seen = set()
    for number, row in native_rows(RAW / 'nysed-beds-2025.csv'):
        key = identity(row)
        if key in seen:
            raise ValueError('Duplicate NYSED BEDS day school/year')
        seen.add(key)
        if key not in directories:
            excluded['Not in same-year public school directory'] += 1
            continue
        band = cohort(row)
        if band is None:
            excluded['No supported enrolled grade3–8 or unknown grade counts'] += 1
            continue
        directory_number, directory = directories[key]
        profiles[key] = dict(id=key, name=directory['SCHOOL_NAME'],
            district_id=directory['DISTRICT_CD'], district=directory['DISTRICT_NAME'],
            county=directory['COUNTY_NAME'], enrollment=count(row['K12']), cohort=band,
            grades_raw=row, grade_row=number, directory_raw=directory, directory_row=directory_number,
            income=None, low_income=None, income_raw={}, income_row=0, income_source='enrollment', outcomes={})
    seen = set()
    for number, row in native_rows(RAW / 'nysed-demographics-2025.csv'):
        key = identity(row)
        if key in seen:
            raise ValueError('Duplicate NYSED poverty school/year')
        seen.add(key)
        if key in profiles:
            p = profiles[key]
            pct, low = income(row, p['enrollment'])
            p.update(income=pct, low_income=low, income_raw=row, income_row=number)
    for subject, name, assessment in [('reading', 'ela', 'ELA3_8'), ('math', 'math', 'MATH3_8')]:
        seen = set()
        for number, row in native_rows(RAW / f'nysed-{name}-2025.csv'):
            if row['SUBGROUP_NAME'] != 'All Students' or row['ASSESSMENT_NAME'] != assessment:
                continue
            key = identity(row)
            if key in seen:
                raise ValueError('Duplicate NYSED native school/subject/year total')
            seen.add(key)
            if key in profiles:
                profiles[key]['outcomes'][subject] = dict(outcome(row, subject), source_row=number)
    payload = dict(schema_version=1, state=dict(id='NY', name='New York'), year=YEAR,
        academic_year='2024–25', retrieved='2026-10-09', source_url=PORTAL, sources=sources,
        schools=list(profiles.values()), source_audit=dict(excluded_profiles=dict(excluded)),
        income_definition=dict(label='Economically disadvantaged K–12 enrollment', definition=DEFINITION, url=MANUAL_URL))
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
    return payload


def prepare(database=DEFAULT_DB):
    original = json.loads(EXTRACT.read_text())
    if (original['state']['id'], original['year']) != ('NY', YEAR):
        raise ValueError('Wrong New York snapshot')
    for school in original['schools']:
        if school['id'] != identity(school['grades_raw']) or school['cohort'] != cohort(school['grades_raw']):
            raise ValueError('NYSED profile/cohort mismatch')
        for row in [school['grades_raw'], school['directory_raw'], school['income_raw']]:
            if row and (identity(row) != school['id'] or row['YEAR'] != str(YEAR)):
                raise ValueError('NYSED school/year mismatch')
        if school['income_raw'] and income(school['income_raw'], school['enrollment']) != (school['income'], school['low_income']):
            raise ValueError('NYSED economic normalization mismatch')
        for subject, result in school['outcomes'].items():
            row = result['raw']
            expected = 'MATH3_8' if subject == 'math' else 'ELA3_8'
            if (identity(row), row['YEAR'], row['SUBGROUP_NAME'], row['ASSESSMENT_NAME']) != (school['id'], str(YEAR), 'All Students', expected):
                raise ValueError('NYSED assessment identity/year/population mismatch')
            normalized = outcome(row, subject)
            if any(result[field] != normalized[field] for field in ['proficiency', 'tested']):
                raise ValueError('NYSED assessment normalization mismatch')
    audits = {}
    for band, level, region in [('grade', 'ES', 'new-york'), ('mixed', 'HS', 'new-york-mixed')]:
        payload = dict(original, schools=[dict(s, cohort=level) for s in original['schools'] if s['cohort'] == band],
            dataset=f'ny-src-2025-{band}', name=f'New York {band} schools, 2024–25',
            region=region, prepare_script='scripts/prepare_new_york.py',
            model_scope=f'Separate New York {band}-school native grade3–8 total models')
        label = 'Grade schools · NYSTP/Regents 3–8' if band == 'grade' else 'Mixed-grade schools · NYSTP/Regents 3–8'
        payload['cohorts'] = [dict(id=level, level=level, assessment=f'NYSTP/middle-grade Regents 3–8 · {band} schools',
            grades='3–8', standard=STANDARD, source='assessment', source_url=SRC_URL,
            label=label, outcome='Proficient', note=f'Native grades3–8 total · {band} schools')]
        payload['coverage_note'] = ('NYSED 2024–25 native grades3–8 public-school totals; individual enrolled poverty status from the same BEDS year. '
            + ('Schools with high-school or ungraded-secondary enrollment are in a separate mixed-grade region.' if band == 'grade' else
               'Mixed-grade schools form a separate population; results cover grades3–8, not high-school achievement.')
            + ' NYSAA excluded; no admissions classifications, imported coordinates or history. Existing NYC definitions and models remain separate.')
        payload['methodology'] = dict(summary=payload['coverage_note'], details=[STANDARD, DEFINITION,
            'Exact 12-digit BEDS entity codes join the same-year school directory, grade enrollment, poverty and assessment records. K12 includes ungraded elementary/secondary students and excludes pre-K.',
            'Only native unsuppressed NUM_PROF and NUM_TESTED totals are used; their exact ratio retains greater precision than NYSED’s displayed whole-percent rate. No suppressed count is recovered from other cells. Models require at least10 valid scores.',
            'School income covers enrolled K–12 pupils while proficiency covers assessed grades3–8. Schools with grade9–12 or ungraded-secondary enrollment form separate mixed-grade models. Pure high schools and schools without known enrolled grades3–8 are excluded.',
            'Sampling intervals use verified valid-score counts and propagate every model member’s uncertainty. Combined equally weights math and ELA. Externally studentized residuals describe associations; state standards are separate and do not support a national ranking.'],
            sources=[dict(label='NYSED public downloads', url=PORTAL), dict(label='Report Card Database and ReadMe', url=SRC_URL),
                     dict(label='Same-year enrollment and demographic database', url=ENROLL_URL), dict(label='SIRS2024–25 manual, pp.59 and253', url=MANUAL_URL)])
        audits[band] = prepare_snapshot(payload, EXTRACT, ROOT / 'data' / region, database)
        descriptor = ROOT / 'data' / region / 'catalog.json'
        catalog = json.loads(descriptor.read_text())
        if band == 'mixed':
            catalog['regions'][0]['name'] = 'Mixed-grade schools · grades 3–8'
            descriptor.write_text(json.dumps(catalog, indent=2) + '\n')
    print(json.dumps(audits, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--extract', action='store_true', help='Normalize previously exported official tables')
    parser.add_argument('--export-tables', action='store_true', help='Extract the downloaded official MDBs with mdbtools')
    args = parser.parse_args()
    if args.export_tables:
        export_tables()
    if args.extract or args.export_tables:
        extract()
    prepare(args.database)
