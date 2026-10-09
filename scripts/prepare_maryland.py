"""Maryland native 2024–25 MCAP totals and individual direct certification.

Default rebuilding is offline. --extract reads the four official downloaded ZIPs.
The administrative Tested Count is retained raw, not approved for intervals.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import io
import json
import re
import zipfile

import openpyxl

from audit_national_sources import DIRECTORY, RAW, read_ccd
from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

EXTRACT = ROOT / 'data/source/maryland.json'
OUTPUT = ROOT / 'data/maryland'
BASE = 'https://www.reportcard.msde.maryland.gov/'
DEFINITIONS = BASE + 'Definitions/Index'
FILES = {'mcap': '562', 'enrollment': '541', 'special-services': '561', 'directory': '539'}
ASSESSMENT = 'MCAP regular ELA/math · grade schools · 2025'
ECON = ('Same-year individual direct certification from MSDE Early Attendance: '
    'SNAP/FSP, TANF/TCA, foster care, Medicaid and other qualifying categorical '
    'statuses. Use the native Economically Disadvantaged count and its Total Student '
    'Cnt denominator, not FARMS, meal access, a CEP multiplier or a tested subgroup. '
    'The native Early Attendance denominator differs from the September30 enrollment '
    'file; September grades establish school scope only. Suppressed or ranged income '
    'remains unavailable, with no complement reconstruction or prior-year backfill.')


def identity(row, income=False):
    district, school = (row['LEA Number'], row['School Number']) if income else (row['LEA'], row['School'])
    if not isinstance(district, str) or not re.fullmatch(r'\d{2}', district) or not isinstance(school, str) or not re.fullmatch(r'\d{4}', school):
        raise ValueError('Not an exact native Maryland school identity')
    return district + '-' + school


def count(value):
    return int(value) if re.fullmatch(r'\d+', str(value)) else None


def percentage(value):
    if not re.fullmatch(r'\d+(?:\.\d+)?', str(value)):
        return None
    value = float(value)
    if not 0 <= value <= 100:
        raise ValueError('Invalid Maryland percentage')
    return value


def csv_rows(name, member):
    with zipfile.ZipFile(RAW / f'maryland-{name}-2025.zip') as archive:
        with archive.open(member) as stream:
            yield from enumerate(csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig')), 2)


def excel_rows(archive, member, sheet):
    workbook = openpyxl.load_workbook(io.BytesIO(archive.read(member)), read_only=True, data_only=True)
    rows = workbook[sheet].values
    headers = next(rows)
    for number, values in enumerate(rows, 2):
        if values[0] in ['END OF WORKBOOK', 'END OF SHEET. Continued on the next sheet.']:
            break
        if values[0] is not None:
            yield number, dict(zip(headers, values))
    workbook.close()


def grade_school(profile, ccd, grades):
    if (profile['Grade Span'] not in ['E', 'M', 'EM'] or ccd['ST'] != 'MD' or
            ccd['SCHOOL_YEAR'] != '2024-2025' or ccd['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8'] or
            ccd['IGOFFERED'] != 'As reported' or not re.fullmatch(r'0[3-8]', ccd['GSHI'])):
        return False
    offered = ['G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
    if any(ccd[f] not in ['Yes', 'No'] for f in offered) or any(ccd[f] == 'Yes' for f in offered[-7:]):
        return False
    # Even a suppressed high-grade enrollment row is enough to exclude the school.
    if any(re.fullmatch(r'Grade (?:9|10|11|12)', row['Grade']) for row in grades):
        return False
    return any(row['Grade'] in [f'Grade {g}' for g in range(3, 9)] for row in grades)


def income_value(rows):
    if len({r['School Type'] for r in rows}) != len(rows):
        raise ValueError('Duplicate Maryland economic school/band row')
    if len(rows) > 1:
        candidates = [r for r in rows if r['School Type'] == 'All']
    else:
        candidates = rows
    if len(candidates) != 1:
        return None, None, None, None
    raw = candidates[0]
    n, low, pct = count(raw['Total Student Cnt']), count(raw['Economically Disadvantaged Cnt']), percentage(raw['Economically Disadvantaged Pct'])
    if n is None or n <= 0 or low is None or pct is None:
        return n, None, None, raw
    if low > n or abs(100 * low / n - pct) > .0500001:
        raise ValueError('Maryland individual income count/percentage mismatch')
    return n, low, 100 * low / n, raw


def outcome(row, subject):
    label = 'Mathematics All Grades' if subject == 'math' else 'English Language Arts All Grades'
    if row['Year'] != 2025 or row['Student Group'] != 'All Students' or row['Assessment'].strip() != label:
        raise ValueError('Not the native same-year regular MCAP school total')
    pct = percentage(row['Proficient Pct'])
    # Never derive a suppressed rate from counts or level percentages.
    n, proficient = count(row['Tested Count']), count(row['Proficient Count'])
    if pct is not None and n is not None and proficient is not None:
        if n <= 0 or proficient > n or abs(100 * proficient / n - pct) > .0500001:
            raise ValueError('Maryland native proficiency count/percentage mismatch')
    return dict(proficiency=pct, tested=None, raw=row, raw_tested=row['Tested Count'],
        source='mcap', source_row=row['source_row'],
        exclusion=None if pct is not None else 'Native school proficiency is suppressed or unavailable')


def extract():
    directory = {}
    with zipfile.ZipFile(RAW / 'maryland-directory-2025.zip') as archive:
        for number, row in excel_rows(archive, 'School_Directory_2025.xlsx', 'School Directory'):
            key = identity(row)
            if row['Year'] != 2025 or row['State'] != 'MD' or key in directory:
                raise ValueError('Wrong-year, foreign or duplicate Maryland directory row')
            row['source_row'] = number
            directory[key] = row
    ccd = {row['NCESSCH']: row for row in read_ccd(DIRECTORY) if row['ST'] == 'MD'}
    grades, income, outcomes = defaultdict(list), defaultdict(list), defaultdict(dict)
    for number, row in csv_rows('enrollment', 'Enrollment_By_Grade_2025.csv'):
        if row['Year'] != '2025':
            raise ValueError('Wrong-year Maryland grade enrollment')
        if re.fullmatch(r'\d{2}', row['LEA']) and re.fullmatch(r'\d{4}', row['School']):
            row['source_row'] = number
            grades[identity(row)].append(row)
    for number, row in csv_rows('special-services', '2025_Special_Services.csv'):
        if row['Academic Year'] != '2025':
            raise ValueError('Wrong-year Maryland economic collection')
        if re.fullmatch(r'\d{2}', row['LEA Number']) and re.fullmatch(r'\d{4}', row['School Number']):
            row['source_row'] = number
            income[identity(row, True)].append(row)
    with zipfile.ZipFile(RAW / 'maryland-mcap-2025.zip') as archive:
        for subject, name in [('math', 'MATH'), ('reading', 'ELA')]:
            for number, row in excel_rows(archive, f'2025 MCAP {name} Administrative Data Report Card.xlsx', 'School_Level'):
                if row['Year'] != 2025:
                    raise ValueError('Wrong-year Maryland assessment')
                if row['Assessment'] is None:
                    continue
                if row['Assessment'].strip() == ('Mathematics All Grades' if subject == 'math' else 'English Language Arts All Grades') and row['Student Group'] == 'All Students':
                    key = identity(row)
                    if subject in outcomes[key]:
                        raise ValueError('Duplicate Maryland school/subject total')
                    row['source_row'] = number
                    outcomes[key][subject] = row
    profiles, excluded = [], []
    for key, profile in sorted(directory.items()):
        nces = str(profile['NCES Number'])
        crosswalk = ccd.get(nces)
        if crosswalk is None or not grade_school(profile, crosswalk, grades[key]):
            excluded.append(dict(id=key, reason='No exact historical grade-school scope', directory=profile,
                ccd=crosswalk, grades=grades[key], income=income[key], outcomes=outcomes[key]))
            continue
        n, low, pct, raw = income_value(income[key])
        profiles.append(dict(id=key, cohort='grade', name=profile['School Name'], district_id=profile['LEA'],
            district=profile['LEA Name'], city=profile['City'], enrollment=n, low_income=low, income=pct,
            directory_raw=profile, ccd_raw=crosswalk, grades_raw=grades[key], income_rows_raw=income[key],
            income_raw=raw or {}, income_row=raw['source_row'] if raw else 0, income_source='special-services',
            outcomes={s: outcome(r, s) for s, r in outcomes[key].items()}))
    sources = {name: dict(path=f'data/raw/maryland-{name}-2025.zip', url=BASE+'DataDownloads/FileDownload/'+number,
        sha256=hashlib.sha256((RAW / f'maryland-{name}-2025.zip').read_bytes()).hexdigest()) for name, number in FILES.items()}
    sources['definitions'] = dict(path='data/raw/maryland-definitions.html', url=DEFINITIONS,
        sha256=hashlib.sha256((RAW / 'maryland-definitions.html').read_bytes()).hexdigest())
    sources['ccd'] = dict(path='data/raw/'+DIRECTORY+'.zip', url='https://nces.ed.gov/ccd/Data/zip/'+DIRECTORY+'.zip',
        sha256=hashlib.sha256((RAW / (DIRECTORY+'.zip')).read_bytes()).hexdigest())
    details = [ECON,
        'Native MCAP regular All Grades school performance totals include course-level AlgebraI, Geometry and AlgebraII taken at grade schools. Alternate assessments are published in a separate file and are excluded. Native All Grades avoids averaging grade percentages or omitting accelerated middle-grade math tests.',
        'Every normalized tested count is unavailable. The administrative file labels Tested Count, but its exact valid-score business rules have not been independently established for interval estimation; raw counts remain in provenance. All three models are point-only.',
        'Only same-year native E/M/EM schools with an exact native NCES crosswalk, unadjusted CCD grade offers and no high-grade enrollment are retained. School income and tested populations differ; Early Attendance income denominators must not be replaced by September enrollment.',
        'Retain native disclosure controls. Numeric published proficiency is used as published; suppressed rates are not reconstructed from counts or level percentages. Combined is the equally weighted Math/ELA mean. Separate externally studentized state models describe associations, not causal school effects. One snapshot; no historical connections or map coordinates.']
    payload = dict(schema_version=1, dataset='md-mcap-2025', year=2025, academic_year='2024–25',
        state=dict(id='MD', name='Maryland'), name='Maryland native MCAP and individual direct certification 2024–25',
        region='maryland', prepare_script='scripts/prepare_maryland.py', retrieved=date.today().isoformat(),
        source_url=BASE+'Graphs/#/DataDownloads/datadownload', sources=sources,
        income_definition=dict(label='Individual direct certification', definition=ECON, url=DEFINITIONS),
        model_scope='Maryland regular MCAP native school totals at public grade schools with same-year individual direct certification',
        cohorts=[dict(id='grade', level='ES', assessment=ASSESSMENT, grades='3–8 plus accelerated math courses',
            standard='Native MCAP regular performance Levels3/4 school All Grades totals; includes course-level middle-school mathematics, excludes alternate DLM.',
            source='mcap', source_url=sources['mcap']['url'], label='Grade schools · MCAP', outcome='Proficient',
            note='Regular native totals · accelerated math included · point-only', allow_point_only=True)],
        schools=profiles, excluded=excluded, source_audit=dict(excluded=dict(Counter(r['reason'] for r in excluded)),
            native_directory=len(directory), point_only=True, economic_collection='Native Early Attendance; denominator preserved'),
        coverage_note=f'{len(profiles)} historical grade-school profiles. Native regular MCAP totals and individual direct certification; suppressed values remain unavailable. High schools, intervals, history and map coordinates are unavailable.',
        methodology=dict(summary='Maryland native regular MCAP proficiency with same-year individual direct certification.', details=details,
            sources=[dict(label='MSDE official native files', url=BASE+'Graphs/#/DataDownloads/datadownload'),
                dict(label='MSDE definitions and collections', url=DEFINITIONS)]))
    validate(payload)
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    return payload


def validate(payload):
    if (payload['state']['id'], payload['year'], payload['dataset']) != ('MD', 2025, 'md-mcap-2025'):
        raise ValueError('Wrong Maryland snapshot identity')
    if len(payload['cohorts']) != 1 or payload['cohorts'][0]['assessment'] != ASSESSMENT or not payload['cohorts'][0]['allow_point_only']:
        raise ValueError('Wrong Maryland assessment cohort')
    for school in payload['schools']:
        profile, ccd = school['directory_raw'], school['ccd_raw']
        if (school['id'] != identity(profile) or profile['Year'] != 2025 or profile['State'] != 'MD' or
                str(profile['NCES Number']) != ccd['NCESSCH'] or not grade_school(profile, ccd, school['grades_raw'])):
            raise ValueError('Wrong historical Maryland identity/grade scope')
        if school['cohort'] != 'grade' or any(r['Year'] != '2025' or identity(r) != school['id'] for r in school['grades_raw']):
            raise ValueError('Wrong-year or mismatched Maryland enrollment scope')
        if any(r['Academic Year'] != '2025' or identity(r, True) != school['id'] for r in school['income_rows_raw']):
            raise ValueError('Wrong-year or mismatched Maryland individual income')
        n, low, pct, raw = income_value(school['income_rows_raw'])
        if (school['enrollment'], school['low_income'], school['income'], school['income_raw']) != (n, low, pct, raw or {}):
            raise ValueError('Maryland income must use its exact native individual counts')
        for subject, native in school['outcomes'].items():
            row = native['raw']
            if identity(row) != school['id'] or native['tested'] is not None or native['proficiency'] != outcome(row, subject)['proficiency']:
                raise ValueError('Maryland outcome is not its exact native point-only total')


def prepare(database=DEFAULT_DB):
    payload = json.loads(EXTRACT.read_text())
    validate(payload)
    return prepare_snapshot(payload, EXTRACT, OUTPUT, database)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract:
        extract()
    print(json.dumps(prepare(args.database), indent=2))
