"""North Carolina 2025 native regular-test totals + April individual EDS.

Offline rebuilds use the committed audited extract. --extract reads the official
DPI disaggregated ZIP, April EDS workbook and same-year CCD grade metadata.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import io
import json
import re
import zipfile

import openpyxl

from audit_national_sources import RAW, DIRECTORY, MEMBERSHIP, read_ccd, membership_cache, source
from database import ROOT, DEFAULT_DB
from prepare_ccd_states import grade_school
from state_snapshot import prepare_snapshot

EXTRACT = ROOT / 'data/source/north-carolina.json'
OUTPUT = ROOT / 'data/north-carolina'
PERFORMANCE_URL = 'https://accrpt.tops.ncsu.edu/docs/disag_datasets/Disag_2024-25.zip'
INCOME_URL = 'https://www.dpi.nc.gov/eds-all-years-spreadsheet/open'
DEFINITION_URL = 'https://www.dpi.nc.gov/documents/economically-disadvantaged-data-collection/open'
ASSESSMENT = 'NC regular EOG + grade-8 Math 1 · grade schools · 2025'
INCOME_DEFINITION = (
    'April 2025 individual Economically Disadvantaged Students (EDS), as a published '
    'percentage of all currently enrolled students in the school (PK through 13 and '
    'ungraded, with charter PK excluded). Eligibility includes individual direct '
    'certification through SNAP/TANF/FDPIR and qualifying categorical statuses, '
    'including foster, homeless, migrant, Medicaid, Head Start and qualifying pre-K, '
    'plus optional locally verified financial need. CEP or universal free meals '
    'alone do not confer individual EDS eligibility. Use pct_eds from APR 2025, '
    'not meal eligibility pct_nslp, the 1.6 adjusted reimbursement percentage, or '
    'the economically disadvantaged tested subgroup. Retain published precision; '
    'no low-income count is inferred from the rounded percentage.')


def exact_percent(value):
    text = str(value)
    if not re.fullmatch(r'\d+(?:\.\d+)?', text):
        return None
    parsed = float(text)
    return parsed if 0 <= parsed <= 100 else None


def exact_enrollment(value):
    return int(value) if re.fullmatch(r'\d+', str(value)) and int(value) > 0 else None


def agency_id(ccd_id):
    match = re.fullmatch(r'NC-([A-Z0-9]{3})-(\d{3})', ccd_id)
    return ''.join(match.groups()) if match else None


def native_outcome(row, number):
    if (row['subject'] not in ['MA', 'RD'] or row['grade'] != 'GS' or
            row['type'] != 'RG' or row['subgroup'] != 'ALL'):
        raise ValueError('Not an approved native regular-test grade total')
    pct = exact_percent(row['pct_glp'])
    return dict(proficiency=pct, tested=None, raw=row, raw_tested=row['num_tested'],
        source='dpi_performance', source_row=number,
        exclusion=None if pct is not None else 'Native GLP rate is suppressed or unavailable')


def native_grade_school(row):
    return re.fullmatch(r'(?:PK|0K|0[1-8])-0[1-8]', row['grade_span']) is not None


def extract():
    native = defaultdict(dict)
    with zipfile.ZipFile(RAW / 'nc-disaggregated-2025.zip') as z:
        with z.open('Disag_2024-25_Data.txt') as f:
            for number, row in enumerate(csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'), delimiter='\t'), 2):
                if row['subject'] in ['MA', 'RD'] and row['grade'] == 'GS' and row['type'] == 'RG' and row['subgroup'] == 'ALL':
                    subject = 'math' if row['subject'] == 'MA' else 'reading'
                    if subject in native[row['school_code']]:
                        raise ValueError('Duplicate native school/subject total')
                    native[row['school_code']][subject] = (number, row)
    workbook = openpyxl.load_workbook(RAW / 'nc-eds-all-years.xlsx', read_only=True, data_only=True)
    rows = workbook['APR 2025'].values
    headers = next(rows)
    income = {}
    for number, values in enumerate(rows, 2):
        row = dict(zip(headers, values))
        if row['school_code'] in income:
            raise ValueError('Duplicate April school income')
        if row['reporting_year'] != '2025' or row['collection_code'] != 'APR':
            raise ValueError('Wrong-year income collection')
        income[row['school_code']] = (number, row)
    directory = {}
    for row in read_ccd(DIRECTORY):
        if row['ST'] != 'NC':
            continue
        key = agency_id(row['ST_SCHID'])
        if key is not None:
            if key in directory:
                raise ValueError('Ambiguous authoritative school crosswalk')
            directory[key] = row
    member = membership_cache()
    schools, excluded = [], []
    for key, outcomes in sorted(native.items()):
        profile = directory.get(key)
        number, eds = income.get(key, (0, None))
        total = member['totals'].get(profile['NCESSCH']) if profile else None
        grades = member['grades'].get(profile['NCESSCH']) if profile else None
        reason = None
        if profile is None:
            reason = 'Missing exact same-year CCD school identity (includes district/state aggregates)'
        elif profile['SCHOOL_YEAR'] != '2024-2025' or profile['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8']:
            reason = 'School not operational in same-year directory'
        elif not grade_school(profile, grades, total):
            reason = 'Mixed, high, adjusted or unknown grade configuration'
        elif any(not native_grade_school(row) for _, row in outcomes.values()):
            reason = 'Native grade span conflicts with grade-school scope'
        elif set(outcomes) != {'math', 'reading'}:
            reason = 'Missing regular-test native subject pair'
        elif eds is None or exact_percent(eds['pct_eds']) is None or exact_enrollment(eds['den']) is None:
            reason = 'April individual EDS percentage or enrollment is missing or suppressed'
        if reason:
            excluded.append(dict(state_school_id=key, reason=reason,
                outcomes={s:r for s, (_,r) in outcomes.items()}, income=eds))
            continue
        schools.append(dict(id=key, cohort='grade', name=profile['SCH_NAME'],
            district_id=eds['psu_code'], district=eds['psu_name'], city=profile['LCITY'], county=None,
            enrollment=exact_enrollment(eds['den']), income=exact_percent(eds['pct_eds']), low_income=None,
            income_raw=eds, income_source='dpi_income', income_row=number,
            directory_raw=profile, membership_raw=total, membership_grades_raw=grades,
            identity_raw=dict(nces_id=profile['NCESSCH'], ccd_id=profile['ST_SCHID'],
                state_school_id=key, normalization='Exact NC-PSU-SCHOOL parts concatenate to native six-character school_code'),
            outcomes={s:native_outcome(r,n) for s,(n,r) in outcomes.items()}))
    sources = dict(dpi_performance=source(RAW/'nc-disaggregated-2025.zip', PERFORMANCE_URL),
        dpi_description=source(RAW/'nc-disaggregated-description-2025.pdf', PERFORMANCE_URL),
        dpi_income=source(RAW/'nc-eds-all-years.xlsx', INCOME_URL),
        dpi_income_definition=source(RAW/'nc-eds-collection.pdf', DEFINITION_URL),
        dpi_technical=source(RAW/'nc-school-grade-technical-2025.pdf',
            'https://www.dpi.nc.gov/dpischoolgradetechnicalguidedraft2024-25/open'),
        ccd_directory=source(RAW/(DIRECTORY+'.zip'), 'https://nces.ed.gov/ccd/Data/zip/'+DIRECTORY+'.zip'),
        ccd_membership=source(RAW/(MEMBERSHIP+'.zip'), 'https://nces.ed.gov/ccd/Data/zip/'+MEMBERSHIP+'.zip'))
    audit = dict(approved_point_only=True, native_source='Disag_2024-25_Data.txt',
        native_population='subgroup ALL; type RG regular multiple choice; subject MA/RD; grade GS native 3–8 composite',
        native_definition='DPI source description pp1–2 explicitly separates RG, ALL and NCEXTEND1. GS includes NC Math1 EOC at grade8; GLP is Level3 and above.',
        denominator='Source num_tested retained raw only. Valid-score scope not independently verified for intervals; every tested field is null.',
        income_collection='APR 2025', income_precision='Current all-years workbook may revise the earlier report-card copy by 0.1 percentage points; preserve the current APR2025 published value and its checksum.',
        grade_scope='Exact same-year CCD state-ID parts, unadjusted grade offers and reconciled grade membership; excludes all high/mixed/unknown scopes.',
        excluded=dict(Counter(x['reason'] for x in excluded)), native_units=len(native))
    payload = dict(dataset='nc-native-eds', year=2025, academic_year='2024–25',
        state=dict(id='NC', name='North Carolina'), name='North Carolina 2025 regular EOG and individual EDS',
        region='north-carolina', prepare_script='scripts/prepare_north_carolina.py',
        source_url=PERFORMANCE_URL, retrieved=date.today().isoformat(),
        model_scope='North Carolina public grade schools with exact native regular-test totals and April2025 individual EDS',
        income_definition=dict(label='Economically disadvantaged', definition=INCOME_DEFINITION, url=DEFINITION_URL),
        sources=sources, source_audit=audit, schools=schools, excluded=excluded,
        cohorts=[dict(id='grade', level='ES', assessment=ASSESSMENT, grades='3–8',
            standard='GLP Level3 and above, regular EOG reading and mathematics including grade8 NC Math1 EOC',
            source='dpi_performance', source_url=PERFORMANCE_URL, label='Grade schools · NC EOG/Math 1',
            outcome='Grade-level proficient', note='Native regular grades3–8 totals · April individual EDS', allow_point_only=True)],
        coverage_note=f'{len(schools)} grade schools with same-year April individual EDS and native regular-test totals. Suppressed outcomes remain unavailable. High schools and history are unavailable.',
        methodology=dict(summary='Native regular-test proficiency with same-year individual economic disadvantage.',
            details=[INCOME_DEFINITION, audit['native_definition'],
                'Use the published native pct_glp. No grade percentages or performance levels are averaged, and no tested subgroup is used as income.',
                'School Performance Grade and long-term-goal rates can apply the federal 95% denominator rule. This snapshot instead uses DPI disaggregated performance test totals, whose source description reports completed tests and explicitly identifies assessment type.',
                'Every model is point-only: sampling intervals and tested counts are unavailable. Combined is the equally weighted mean of math and ELA. Models are separate from other states and incompatible assessments.',
                audit['income_precision'], 'Enrollment is the April EDS denominator. Fall CCD membership establishes grade configuration only and is never substituted for April economic enrollment.'],
            sources=[dict(label='DPI native disaggregated performance and codebook', url=PERFORMANCE_URL),
                dict(label='DPI individual EDS collections', url=DEFINITION_URL),
                dict(label='DPI April2025 EDS workbook', url=INCOME_URL)]))
    validate(payload)
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    return payload


def validate(payload):
    if payload['year'] != 2025 or payload['academic_year'] != '2024–25' or payload['state']['id'] != 'NC':
        raise ValueError('Wrong-year/state snapshot')
    if len(payload['cohorts']) != 1 or not payload['cohorts'][0]['allow_point_only']:
        raise ValueError('Expected one point-only grade cohort')
    for school in payload['schools']:
        raw, profile = school['income_raw'], school['directory_raw']
        if (raw['reporting_year'] != '2025' or raw['collection_code'] != 'APR' or
                raw['school_code'] != school['id'] or agency_id(profile['ST_SCHID']) != school['id'] or
                profile['ST'] != 'NC' or profile['SCHOOL_YEAR'] != '2024-2025' or
                profile['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8'] or
                profile['NCESSCH'] != school['membership_raw']['NCESSCH'] or
                school['membership_raw']['ST'] != 'NC' or
                school['membership_raw']['ST_SCHID'] != profile['ST_SCHID'] or
                school['cohort'] != 'grade' or not grade_school(profile, school['membership_grades_raw'], school['membership_raw'])):
            raise ValueError('Income identity, year or grade scope is invalid')
        if (school['income'] != exact_percent(raw['pct_eds']) or school['income'] is None or
                school['enrollment'] != exact_enrollment(raw['den']) or school['enrollment'] is None or
                school['low_income'] is not None):
            raise ValueError('Economic values must be exact published individual EDS and April enrollment')
        for subject, outcome in school['outcomes'].items():
            row = outcome['raw']
            expected = native_outcome(row, outcome['source_row'])
            if (row['school_code'] != school['id'] or row['subject'] != ('MA' if subject=='math' else 'RD') or
                    not native_grade_school(row) or outcome['tested'] is not None or outcome['proficiency'] != expected['proficiency']):
                raise ValueError('Outcome is not the exact published point-only regular total')


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
