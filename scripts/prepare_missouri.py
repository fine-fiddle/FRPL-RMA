"""Missouri regular MAP grade aggregates and non-CEP individual January FRL.

Offline rebuilds use the committed extract. --extract reads the audited native
workbooks, public-report comparison samples and EDC 2025 file listed in the guide.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
import csv
import hashlib
import json
import math
from pathlib import Path
import re

import openpyxl

from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

YEAR = 2025
DATASET = 'mo-map-2025'
EXTRACT = ROOT / 'data/source/missouri.json'
OUTPUT = ROOT / 'data/missouri'
RAW = ROOT / 'data/raw/missouri'
PORTAL = 'https://apps.dese.mo.gov/MCDS/home.aspx?categoryid=2&view=2'
REPORT = ('https://apps.dese.mo.gov/MCDS/Reports/SSRS_Print.aspx?'
          'Reportid=e7546486-3e0e-437f-902b-767f33fb0fc3')
DOWNLOAD = 'https://apps.dese.mo.gov/MCDS/FileDownloadWebHandler.ashx?filename='
FILES = {
    'income': ('income.xlsx', DOWNLOAD + 'fb61ee1c-5613Free%20and%20Reduced%20Priced%20Lunch%20Percentage%20by%20Building%202009-10%20to%202025-26%20%281%29.xlsx'),
    'grades': ('apr-supporting.xlsx', DOWNLOAD + 'd07d9e08-a6f1Supporting%20Building%20Report.xlsx'),
    'enrollment': ('enrollment.xlsx', DOWNLOAD + '419d81bf-4a37Building%20Enrollment.xlsx'),
    'definitions': ('map-documentation.xlsx', DOWNLOAD + 'b5a8c206-07062024_MAP_Data_Download_Supporting-Documentation.xlsx'),
    'public_audit_lafayette': ('performance-lafayette.csv', REPORT),
    'public_audit_integrated': ('performance-grades.csv', REPORT),
}
EDC = ROOT / 'data/raw/edc-2025/mo.csv'
EDC_URL = 'https://www.eddatacenter.org/api/data/3.1?state=MO&year=2025'
STANDARD = (
    'Regular Missouri MAP grades 3–8, Spring 2025, All Students/Total. '
    'Each school subject combines only its complete offered tested-grade range '
    'using published Proficient and Advanced counts divided by the sum of '
    'verified reportable MAP-score counts. Both proficiency components must be '
    'unsuppressed in every grade; suppressed components and third-party combined '
    'values never recover missing cells. The native Performance Level report '
    'defines reportable as students receiving a MAP score, excluding no-score '
    'and invalid-attempt records. Accountable enrollment and participation are '
    'not substituted. MAP alternate, EOC, high-school and mixed-grade populations '
    'are excluded. Published counts support sampling intervals.')
INCOME = (
    'Published 2024–25 DESE building January Free/Reduced Price Lunch percentage. '
    'The numerator is individually eligible January State FTE FRL, and the '
    'denominator is native January Membership submitted in the February Core '
    'Data cycle. FTE measures instructional time and is not a student headcount. '
    'The workbook identifies CEP buildings and explicitly reports all students '
    'as free there; every flagged CEP building is excluded from the regression. '
    'The remaining individual eligibility measure differs from fall enrollment '
    'and from the tested population. Native percentages are preserved, with '
    'fractional FTE and membership retained for audit; no low-income headcount '
    'is manufactured. CEP exclusions substantially limit population coverage.')
GRADES = {'Third Grade': 'G03', 'Fourth Grade': 'G04', 'Fifth Grade': 'G05',
          'Sixth Grade': 'G06', 'Seventh Grade': 'G07', 'Eighth Grade': 'G08'}


def school_id(district, building):
    def component(value, width):
        if isinstance(value, bool):
            raise ValueError('Boolean Missouri school identity')
        if isinstance(value, (int, float)):
            if not math.isfinite(value) or value != int(value):
                raise ValueError('Noninteger Missouri school identity')
            value = str(int(value))
        if not isinstance(value, str) or not re.fullmatch(r'\d{1,' + str(width) + r'}', value):
            raise ValueError('Invalid Missouri school identity')
        value = value.zfill(width)
        if int(value) <= 0:
            raise ValueError('Empty Missouri school identity')
        return value
    return component(district, 6) + '-' + component(building, 4)


def count(value):
    if isinstance(value, bool):
        raise ValueError('Boolean Missouri student count')
    if value in [None, '', '*', 'NULL', '--']:
        return None
    if isinstance(value, str) and not re.fullmatch(r'\d+', value):
        raise ValueError('Unexpected Missouri count or suppression token')
    number = float(value)
    if not math.isfinite(number) or number < 0 or number != int(number):
        raise ValueError('Invalid Missouri student count')
    return int(number)


def offered(value):
    if isinstance(value, str) and value.strip() in ['PK', 'K']:
        return -1 if value.strip() == 'PK' else 0
    number = count(value)
    if number is None or not 0 <= number <= 12:
        raise ValueError('Unresolved native Missouri offered grade')
    return number


def eligible_grades(profile):
    r, e = profile['directory'], profile['enrollment']
    lo, hi = offered(r['BEG_GRADE']), offered(r['END_GRADE'])
    if lo > hi:
        raise ValueError('Reversed native Missouri grade range')
    if hi > 8 or hi < 3 or e is None:
        return None
    if any((count(e[f'ENROLLMENT_GRADES_{g:02}']) or 0) > 0 for g in range(9, 13)):
        return None
    # Native APR offers disambiguate '*' outside the served grade range; those
    # cells are never interpreted as numeric zero or used as weights.
    return {f'G{g:02}' for g in range(max(3, lo), hi + 1)}


def income(raw):
    if raw is None:
        return None, 'Missing same-year native individual eligibility'
    flag = raw['Community Eligiblity Provision (CEP) Participating Building']
    if flag is not None and str(flag).strip() != 'Yes':
        raise ValueError('Unexpected native Missouri CEP flag')
    if flag is not None:
        return None, 'CEP building reports schoolwide free meals, not individual eligibility'
    pct = raw['2025 F&RL Percentage']
    if pct in [None, '', '*', 'NULL']:
        return None, 'Native January individual eligibility percentage unavailable'
    if not isinstance(pct, (int, float)) or not math.isfinite(pct) or not 0 <= pct <= 1:
        raise ValueError('Invalid native Missouri income percentage')
    numerator, denominator = raw['January State FTE F&RL Count'], raw['January Membership']
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in [numerator, denominator]):
        return None, 'Native January FTE or membership unavailable'
    if numerator < 0 or denominator <= 0 or numerator > denominator:
        return None, 'Native January FTE and membership outside valid range'
    return 100 * pct, None


def aggregate(rows, required):
    if len({r['GradeLevel'] for r in rows}) != len(rows):
        raise ValueError('Duplicate Missouri subject/grade observation')
    if {r['GradeLevel'] for r in rows} != required:
        return None, None, 'Incomplete native offered tested-grade coverage'
    tested, proficient = 0, 0
    for r in rows:
        n, p, a = [count(r[field]) for field in
                   ['StudentSubGroup_TotalTested', 'Lev3_count', 'Lev4_count']]
        if any(v is None for v in [n, p, a]):
            return None, None, 'Native proficiency component or valid-score count suppressed'
        if n <= 0 or p + a > n:
            raise ValueError('Invalid Missouri valid-score proficiency counts')
        lower = [count(r[field]) for field in ['Lev1_count', 'Lev2_count']]
        if all(v is not None for v in lower) and sum(lower) + p + a != n:
            raise ValueError('Missouri native four-level counts do not reconcile')
        tested += n
        proficient += p + a
    return 100 * proficient / tested, tested, None


def worksheet(path, sheet=None):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        yield from (book[sheet] if sheet else book.worksheets[0]).iter_rows(values_only=True)
    finally:
        book.close()


def source(path, url):
    return dict(path=str(path.relative_to(ROOT)), url=url,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def validate_assessment(r, key):
    if (r['StateAbbrev'], r['SchYear'], r['DataLevel'], r['AssmtName'], r['AssmtType'],
        r['StudentGroup'], r['StudentSubGroup'], r['ProficiencyCriteria']) != (
            'MO', '2024-25', 'School', 'MAP', 'Regular', 'All Students', 'All Students', 'Levels 3-4'):
        raise ValueError('Missouri source crossed year, assessment or population')
    if r['StateAssignedSchID'] != key or school_id(*key.split('-')) != key:
        raise ValueError('Missouri assessment identity mismatch')
    if r['StateAssignedDistID'] != key[:6] or r['Subject'] not in ['ela', 'math'] or r['GradeLevel'] not in {f'G{g:02}' for g in range(3, 9)}:
        raise ValueError('Missouri source crossed district, grade or subject')
    if r['StudentGroup_TotalTested'] != r['StudentSubGroup_TotalTested']:
        raise ValueError('Missouri All Students valid-score totals disagree')


def audit_public(rows):
    edc = {(r['StateAssignedSchID'], r['Subject'], r['GradeLevel']): r for r in rows}
    evidence, comparisons = [], 0
    for file, district in [('performance-lafayette.csv', '048914'), ('performance-grades.csv', '048927')]:
        for number, r in enumerate(csv.DictReader((RAW / file).open(encoding='utf-8-sig')), 2):
            code = re.search(r'\((\d{4})\)$', r['SchoolName'])
            if code is None or (r['YEAR'], r['CATEGORY'], r['TYPE']) != ('2025', 'Total', 'Total'):
                raise ValueError('Public Missouri audit changed identity or population')
            key = school_id(district, code[1])
            subject = {'Eng. Language Arts': 'ela', 'Mathematics': 'math'}[r['CONTENT_AREA']]
            grade = GRADES[r['GRADE_SUBJECT']]
            e = edc[key, subject, grade]
            for native, field in [('REPORTABLE', 'StudentSubGroup_TotalTested'), ('BELOW_BASIC', 'Lev1_count'),
                                  ('BASIC', 'Lev2_count'), ('PROFICIENT', 'Lev3_count'), ('ADVANCED', 'Lev4_count')]:
                if r[native] != e[field]:
                    raise ValueError('EDC differs from observed native MAP counts or suppression')
                comparisons += 1
            evidence.append(dict(id=key, subject=subject, grade=grade, raw=r, source_row=number, file=file))
    return dict(rows=evidence, comparison_cells=comparisons, differences=0)


def extract():
    rows = [r for r in csv.DictReader(EDC.open(encoding='utf-8-sig'))
            if r['DataLevel']=='School' and r['StudentGroup']=='All Students' and
            r['StudentSubGroup']=='All Students' and r['Subject'] in ['ela', 'math']]
    assessments = defaultdict(list)
    for r in rows:
        validate_assessment(r, r['StateAssignedSchID'])
        assessments[r['StateAssignedSchID']].append(r)
    native_audit = audit_public(rows)
    income_rows = list(worksheet(RAW / 'income.xlsx', '2024-2025'))
    headers = income_rows[9][:8]
    if headers[6] != '2025 F&RL Percentage' or 'All students in these buildings are reported as free lunch.' not in income_rows[7][1]:
        raise ValueError('Missouri native income year or CEP definition changed')
    incomes = {}
    for i, r in enumerate(income_rows[10:], 11):
        if not isinstance(r[0], (int, float)):
            continue
        key = school_id(r[0], r[2])
        if key in incomes: raise ValueError('Duplicate native Missouri income identity')
        incomes[key] = (i, dict(zip(headers, r[:8])))
    enrollments, erows = {}, iter(worksheet(RAW / 'enrollment.xlsx'))
    fields = next(erows)
    for i, r in enumerate(erows, 2):
        if r[0] != YEAR: continue
        if r[3] == 0: continue  # Native district-total row, not a building ID.
        key = school_id(r[1], r[3])
        if key in enrollments: raise ValueError('Duplicate Missouri grade enrollment')
        enrollments[key] = dict(zip(fields, r))
    profiles, seen, drows = [], set(), iter(worksheet(RAW / 'apr-supporting.xlsx'))
    fields = next(drows)[:7]
    for i, r in enumerate(drows, 2):
        if r[0] != YEAR: raise ValueError('Wrong native Missouri APR year')
        key = school_id(r[1], r[3])
        if key in seen: raise ValueError('Duplicate native Missouri directory identity')
        seen.add(key)
        profiles.append(dict(id=key, directory=dict(zip(fields, r[:7])), directory_row=i,
            enrollment=enrollments.get(key), income=incomes.get(key, (0,None))[1],
            income_row=incomes.get(key, (0,None))[0], assessments=assessments.get(key, [])))
    sources = {k: source(RAW / filename, url) for k, (filename, url) in FILES.items()}
    sources['assessment'] = source(EDC, EDC_URL)
    payload = dict(state='MO', year=YEAR, academic_year='2024-25', retrieved=str(date.today()),
        sources=sources, income_notes=[r[1] for r in income_rows[1:8] if r[1]],
        native_audit=native_audit, profiles=profiles,
        unmatched_assessment_ids=sorted(set(assessments)-seen),
        native_income_records=len(incomes), native_cep_records=sum(v[1][headers[7]] is not None for v in incomes.values()))
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    return payload


def normalize(payload):
    if (payload['state'], payload['year'], payload['academic_year']) != ('MO', YEAR, '2024-25'):
        raise ValueError('Wrong Missouri source state or year')
    if payload['native_audit']['differences'] != 0 or payload['native_audit']['comparison_cells'] < 100:
        raise ValueError('Native Missouri valid-score/suppression audit unavailable')
    schools, seen, excluded = [], set(), Counter()
    for p in payload['profiles']:
        key, d, e = p['id'], p['directory'], p['enrollment']
        if school_id(d['COUNTY_DISTRICT_CODE'], d['SCHOOL_CODE']) != key or key in seen or d['YEAR'] != YEAR:
            raise ValueError('Missouri native directory identity/year mismatch')
        seen.add(key)
        if e is not None and (e['YEAR'] != YEAR or school_id(e['COUNTY_DISTRICT_CODE'], e['SCHOOL_CODE']) != key):
            raise ValueError('Missouri enrollment identity/year mismatch')
        if p['income'] is not None and school_id(p['income']['District Code'],p['income']['BLDG. NO.']) != key:
            raise ValueError('Missouri income identity mismatch')
        required = eligible_grades(p)
        if required is None:
            excluded['Outside verified grade-school MAP scope or missing grade enrollment'] += 1
            continue
        pct, reason = income(p['income'])
        groups = defaultdict(list)
        for r in p['assessments']:
            validate_assessment(r, key)
            groups[r['Subject']].append(r)
        outcomes = {}
        for subject, native in [('math','math'), ('reading','ela')]:
            proficiency, tested, outcome_reason = aggregate(groups[native], required)
            outcomes[subject] = dict(proficiency=proficiency, tested=tested,
                valid_score_evidence='Native MAP Performance Level REPORTABLE definition and 130 directly verified public count/suppression cells',
                source='assessment', source_row=0, raw=groups[native], raw_tested=groups[native], exclusion=reason or outcome_reason)
        enrollment = count(e['ENROLLMENT_GRADES_PK_12'])
        schools.append(dict(id=key, name=d['SCHOOL_NAME'], district_id=d['COUNTY_DISTRICT_CODE'],
            district=d['DISTRICT_NAME'], cohort='grade', enrollment=enrollment, low_income=None, income=pct,
            income_source='income', income_row=p['income_row'], income_raw=p['income'],
            directory_raw=d, membership_grades_raw=e, outcomes=outcomes))
    return dict(dataset=DATASET, state=dict(id='MO',name='Missouri'), year=YEAR, academic_year='2024–25',
        name='Missouri MAP 2025 · individual non-CEP January FRL', region='missouri', prepare_script='scripts/prepare_missouri.py',
        source_url=PORTAL, sources=payload['sources'], retrieved=payload['retrieved'], schools=schools,
        cohorts=[dict(id='grade',level='ES',label='Grade schools · regular MAP',grades='3–8',
            assessment='MAP regular grades 3–8 · complete grade schools',standard=STANDARD,source='assessment',
            source_url=payload['sources']['definitions']['url'],outcome='Proficient or Advanced',
            note='Verified grade-count aggregation · non-CEP individual January FRL FTE')],
        model_scope='Missouri regular MAP grade schools with complete unsuppressed proficiency counts and native non-CEP individual January FRL',
        income_definition=dict(label='Individual January FRL FTE',definition=INCOME,url=payload['sources']['income']['url']),
        coverage_note=STANDARD+' '+INCOME,
        methodology=dict(summary='Missouri’s regular MAP proficiency uses verified grade-score counts and native individual January FRL outside CEP; suppression and CEP exclusions limit coverage.',
            details=[STANDARD,INCOME,
                'Native county-district six-digit plus school four-digit codes establish all same-year joins. The 2025 APR file supplies grade offers only; its accountability MPI and points are not proficiency. Native fall grade enrollment corroborates scope. Maps are unavailable.',
                'EDC 2025 regular MAP grade counts are checked against 26 native public report rows and 130 count/suppression cells. EDC combined values are ignored when either native proficiency component is suppressed. Complete grade coverage is mandatory; no missing grade is filled or averaged.',
                'Separate state, year, assessment and subject models use externally studentized residuals. Combined is the equally weighted mean of math and ELA proficiency. Filters never refit. State standards are incompatible national scales; associations do not establish causal school effectiveness or overall quality.'],
            sources=[dict(label=label,url=payload['sources'][k]['url']) for k,label in
                [('income','Official same-year individual/CEP income workbook'),('grades','Official 2025 building grade offers'),
                 ('definitions','Official MAP valid-score definitions'),('public_audit_lafayette','Native public MAP report'),
                 ('assessment','EDC 2025 MAP count extract')]]),
        source_audit=dict(native_directory=len(seen), grade_profiles=len(schools), excluded=dict(excluded),
            native_income_records=payload['native_income_records'],native_cep_records=payload['native_cep_records'],
            native_count_comparisons=payload['native_audit']['comparison_cells'],
            unmatched_assessment_ids=payload['unmatched_assessment_ids'],
            income_unavailable=sum(s['income'] is None for s in schools),mapped=0))


def prepare(database=DEFAULT_DB):
    result = prepare_snapshot(normalize(json.loads(EXTRACT.read_text())), EXTRACT, OUTPUT, database)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract: extract()
    prepare(args.database)
