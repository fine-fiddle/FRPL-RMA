"""Oregon 2025 native Assessment Group Reports + spring individual poverty.

The committed extract rebuilds offline. --extract reads official native school
totals, spring enrollment and the same-year AAG school grade directory.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import json
import math
import re

import openpyxl

from audit_national_sources import RAW, source
from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

EXTRACT = ROOT / 'data/source/oregon.json'
OUTPUT = ROOT / 'data/oregon'
BASE = 'https://www.oregon.gov/ode/educator-resources/assessment/Documents/TestResults2425/'
ELA_URL = BASE + 'pagr_schools_ela_all_2425.xlsx'
MATH_URL = BASE + 'pagr_schools_math_all_2425.xlsx'
INCOME_URL = 'https://www.oregon.gov/ode/reports-and-data/students/Documents/spring_student_enrollment_20242025.xlsx'
DIRECTORY_URL = 'https://www.ode.state.or.us/data/ReportCard/Media/DownloadFile?schlYr=26&fldr=stateData&flNm=AAGmediaSchoolsAggregate'
CODEBOOK_URL = 'https://www.ode.state.or.us/data/ReportCard/Media/DataDoc/2025'
RULES_URL = 'https://www.oregon.gov/ode/schools-and-districts/reportcards/reportcards/Documents/asmtinclusionrules2425.pdf'
TOTAL = 'Total Population (All Students)'
INCOME_DEFINITION = (
    'Students Experiencing Poverty (SEP), as the published percentage of school '
    'students enrolled on the first school day in May 2025 who, at any time in '
    '2024–25, received SNAP or TANF, were in foster care, experienced homelessness '
    'or received migrant education services. This individual administrative '
    'measure replaced Oregon Economically Disadvantaged in 2023–24. It is not a '
    'meal claiming percentage or a tested-subgroup proportion. Enrollment and '
    'actual SEP count come from the same spring enrollment school row; preserve '
    'the published rounded percentage rather than reconstructing it from counts.')


def exact_percent(value):
    if isinstance(value, bool) or not re.fullmatch(r'\d+(?:\.\d+)?', str(value)):
        return None
    number = float(value)
    return number if math.isfinite(number) and 0 <= number <= 100 else None


def exact_count(value):
    return int(value) if not isinstance(value, bool) and re.fullmatch(r'\d+', str(value)) else None


def school_id(value):
    number = exact_count(value)
    if number is None or number <= 0:
        raise ValueError('Missing exact native institution ID')
    return str(number)


def grade_cohort(value):
    match = re.fullmatch(r'Grade\(s\) (K|\d{1,2})-(K|\d{1,2})', value)
    if not match:
        return None
    low, high = [0 if part == 'K' else int(part) for part in match.groups()]
    if not 0 <= low <= high <= 12:
        return None
    if high <= 8 and high >= 3:
        return 'grade'
    if low >= 9 and high >= 11:
        return 'high'
    return None


def native_outcome(row, number, subject):
    expected = 'Mathematics' if subject == 'math' else 'English Language Arts'
    if (row['Academic Year'] != '2024-2025' or row['Student Group'] != TOTAL or
            row['Grade Level'] != 'All Grades' or row['Subject'] != expected):
        raise ValueError('Not an approved same-year native school total')
    pct = exact_percent(row['Percent Proficient'])
    return dict(proficiency=pct, tested=None, raw=row,
        raw_tested=row['Number of Participants'], source='ode_' + subject,
        source_row=number,
        exclusion=None if pct is not None else 'Native school-total rate is suppressed or unavailable')


def workbook_rows(path, sheet):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = iter(workbook[sheet].values)
    headers = next(rows)
    for number, values in enumerate(rows, 2):
        yield number, dict(zip(headers, values))
    workbook.close()


def extract():
    native = defaultdict(dict)
    for subject, filename, sheet in [
            ('reading', 'or-ela-2025.xlsx', 'Schools_ELA_AllGrades_2425'),
            ('math', 'or-math-2025.xlsx', 'Schools_Math_AllGrades_2425')]:
        for number, row in workbook_rows(RAW / filename, sheet):
            if row['Student Group'] != TOTAL:
                continue
            key = school_id(row['School ID'])
            if subject in native[key]:
                raise ValueError('Duplicate native school/subject total')
            native_outcome(row, number, subject)
            native[key][subject] = (number, row)
    income = {}
    for number, row in workbook_rows(RAW / 'or-enrollment-spring-2025.xlsx', 'Schools'):
        if row['Report Year'] != 20242025:
            raise ValueError('Wrong-year spring enrollment')
        key = school_id(row['School ID'])
        if key in income:
            raise ValueError('Duplicate native school income')
        income[key] = (number, row)
    profiles = {}
    with (RAW / 'or-aag-2025.csv').open(newline='', encoding='utf-8-sig') as f:
        for number, row in enumerate(csv.DictReader(f), 2):
            key = school_id(row['School ID'])
            if key in profiles:
                raise ValueError('Duplicate school grade metadata')
            profiles[key] = (number, row)
    schools, excluded = [], []
    for key, outcomes in sorted(native.items(), key=lambda item:int(item[0])):
        profile_row, profile = profiles.get(key, (0, None))
        number, eds = income.get(key, (0, None))
        cohort = grade_cohort(profile['Grades']) if profile else None
        reason = None
        if profile is None or eds is None:
            reason = 'Missing exact native same-year school income or grade identity'
        elif cohort is None:
            reason = 'Mixed, untested or unknown native grade span'
        elif any(school_id(r['District ID']) != school_id(profile['District ID']) for _, r in outcomes.values()) or school_id(eds['District ID']) != school_id(profile['District ID']):
            reason = 'Native institution district identity conflicts'
        elif set(outcomes) != {'math', 'reading'}:
            reason = 'Missing native subject pair'
        elif exact_percent(eds['Percentage Students Experiencing Poverty']) is None or not exact_count(eds['Total Number of Students']):
            reason = 'Spring individual poverty rate or enrollment is missing or suppressed'
        count = exact_count(eds['Students Experiencing Poverty']) if eds else None
        enrollment = exact_count(eds['Total Number of Students']) if eds else None
        if reason is None and count is not None and count > enrollment:
            reason = 'Individual poverty count exceeds school enrollment'
        if reason:
            excluded.append(dict(state_school_id=key, reason=reason,
                outcomes={s:r for s, (_,r) in outcomes.items()}, income=eds, directory=profile))
            continue
        schools.append(dict(id=key, cohort=cohort, name=eds['School Name'],
            district_id=school_id(eds['District ID']), district=eds['District Name'],
            city=None, county=profile['County'], enrollment=enrollment,
            income=exact_percent(eds['Percentage Students Experiencing Poverty']), low_income=count,
            income_raw=eds, income_source='ode_income', income_row=number,
            directory_raw=profile, directory_row=profile_row,
            outcomes={s:native_outcome(r,n,s) for s,(n,r) in outcomes.items()}))
    sources = {
        'ode_math': source(RAW/'or-math-2025.xlsx', MATH_URL),
        'ode_reading': source(RAW/'or-ela-2025.xlsx', ELA_URL),
        'ode_income': source(RAW/'or-enrollment-spring-2025.xlsx', INCOME_URL),
        'ode_directory': source(RAW/'or-aag-2025.csv', DIRECTORY_URL),
        'ode_codebook': source(RAW/'or-aag-codebook-2025', CODEBOOK_URL),
        'ode_rules': source(RAW/'or-assessment-inclusion-2025.pdf', RULES_URL),
        'ode_media_year': source(RAW/'or-GetStateDocLinks-2025.json', 'https://www.ode.state.or.us/data/ReportCard/Media/GetStateDocLinks'),
    }
    audit = dict(approved_point_only=True, native_units=len(native),
        assessment='ODE native school All Grades Assessment Group Reports, Total Population (All Students), published Percent Proficient; Level 3 or 4, including Oregon Extended assessments.',
        denominator='AGR performance is the resolved valid-score population enrolled May 1, excluding beginning EL and invalid/nonattempt/opt-out scores; valid partial tests are included. Manual table 11 printed 14 separates AGR performance from participation and the AAG/Accountability 95%-rule denominator. Counts are raw only and every tested field is null.',
        high_school='Current grade 11 resolved-score population includes prior-year passing high-school scores under the state highest-score rule, not only tests administered in 2025.',
        income='Same-year spring school enrollment and individual SEP administrative flags; source codebook column M states enrolled May 2025 and qualifying status at any time in 2024–25.',
        directory='School ID and District ID are native institution keys in all three files. AAG media school-year 26 is 2024–25. Use only native Grades, not its accountability proficiency fields.',
        source_caveats=[
            'AGR workbook Definitions still says district special-education program students are excluded. The dated June 2025 inclusion manual printed 5 explicitly supersedes this: SB 923 requires their school assignment and inclusion.',
            'The 2025 media codebook enrollment row retains a 2023 date, whereas the spring enrollment Notes and Report Year explicitly identify 2024–25. Income uses the spring workbook, not that stale enrollment sentence.',
            'The manual contains conflicting older calendar dates in some general EL paragraphs; use the explicit beginning-EL A/B flag exclusion and 2024–25 AGR calculation table, without inferring a cutoff from stale prose.',
        ], excluded=dict(Counter(x['reason'] for x in excluded)))
    cohorts = []
    for key, level, grades, label, assessment in [
        ('grade', 'ES', '3–8', 'Grade schools · OSAS + Extended', 'Oregon OSAS + Extended · grade schools · 2025'),
        ('high', 'HS', '11', 'High schools · OSAS resolved scores + Extended', 'Oregon OSAS resolved grade 11 + Extended · 2025')]:
        cohorts.append(dict(id=key, level=level, grades=grades, assessment=assessment,
            standard='Published Level 3 or 4, academic and alternate standards; native AGR resolved valid-score population',
            source='ode_math', source_url=MATH_URL, label=label, outcome='Proficient',
            note='May 1 individual poverty · native published total · point-only' + (' · prior passing scores included' if key=='high' else ''),
            allow_point_only=True))
    payload = dict(dataset='or-native-sep', year=2025, academic_year='2024–25',
        state=dict(id='OR', name='Oregon'), name='Oregon 2025 native assessment and individual poverty',
        region='oregon', prepare_script='scripts/prepare_oregon.py', source_url=MATH_URL,
        retrieved=date.today().isoformat(),
        model_scope='Oregon accountable public grade and high schools, separate native AGR assessment cohorts with same-year spring individual poverty; mixed grades excluded',
        income_definition=dict(label='Students experiencing poverty', definition=INCOME_DEFINITION, url=INCOME_URL),
        schools=schools, excluded=excluded, sources=sources, source_audit=audit, cohorts=cohorts,
        coverage_note=f'{len(schools)} grade and high schools with native totals and same-year individual poverty. Mixed grades, untested grade spans, missing income and suppression limit coverage. High-school resolved totals include prior passing scores. History is unavailable.',
        methodology=dict(summary='Native school assessment totals with same-year spring individual poverty.',
            details=[INCOME_DEFINITION,
                'Use published All Grades Total Population rates from Assessment Group Reports, which include the Oregon Extended alternate assessment. Grade schools and high schools have separate models. Native grade spans exclude mixed schools.',
                'AGR performance uses students enrolled May 1 with resolved valid scores; beginning English Learners are excluded. The state accepts qualifying partial tests. Nonattempts and opt-outs are excluded from performance. No full-academic-year filter or 95% accountability denominator adjustment is substituted.',
                audit['high_school'],
                'Every model is point-only. Number of Participants includes a different population (e.g. first-year EL credit) and is never used as tested. No count, rate or grade weighting is reconstructed. Combined is the equal mean of Math and ELA.',
                *audit['source_caveats']],
            sources=[dict(label='ODE school Math native totals', url=MATH_URL),
                dict(label='ODE school ELA native totals', url=ELA_URL),
                dict(label='ODE spring 2025 school enrollment and individual poverty', url=INCOME_URL),
                dict(label='ODE 2024–25 assessment inclusion rules', url=RULES_URL),
                dict(label='ODE 2025 school metadata codebook', url=CODEBOOK_URL)]))
    validate(payload)
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    return payload


def validate(payload):
    if payload['year'] != 2025 or payload['academic_year'] != '2024–25' or payload['state']['id'] != 'OR':
        raise ValueError('Wrong-year/state snapshot')
    if {c['id']:c['level'] for c in payload['cohorts']} != {'grade':'ES', 'high':'HS'} or not all(c['allow_point_only'] for c in payload['cohorts']):
        raise ValueError('Expected separate point-only grade and high cohorts')
    for school in payload['schools']:
        row, profile = school['income_raw'], school['directory_raw']
        if (row['Report Year'] != 20242025 or school_id(row['School ID']) != school['id'] or
                school_id(profile['School ID']) != school['id'] or
                school_id(row['District ID']) != school['district_id'] or
                school_id(profile['District ID']) != school['district_id'] or
                grade_cohort(profile['Grades']) != school['cohort']):
            raise ValueError('Native school identity, year or grade scope is invalid')
        count, enrollment = exact_count(row['Students Experiencing Poverty']), exact_count(row['Total Number of Students'])
        if (school['income'] != exact_percent(row['Percentage Students Experiencing Poverty']) or school['income'] is None or
                school['enrollment'] != enrollment or not enrollment or school['low_income'] != count or
                count is not None and count > enrollment):
            raise ValueError('Economic values are not exact native individual spring poverty')
        if set(school['outcomes']) != {'math', 'reading'}:
            raise ValueError('Missing native subject pair')
        for subject, outcome in school['outcomes'].items():
            raw = outcome['raw']
            expected = native_outcome(raw, outcome['source_row'], subject)
            if (school_id(raw['School ID']) != school['id'] or school_id(raw['District ID']) != school['district_id'] or
                    outcome['tested'] is not None or outcome['proficiency'] != expected['proficiency']):
                raise ValueError('Outcome is not the exact published point-only school total')


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
