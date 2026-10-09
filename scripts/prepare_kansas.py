"""Kansas 2025 native KAP+DLM school totals and individual enrolled ED.

Rebuild offline from the committed extract. --download-income captures the public
Report Card demographic API; --extract reads those captures and the official
native assessment workbook and same-year CCD directory/membership metadata.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import json
import math
import re
import urllib.parse
import urllib.request

import openpyxl

from audit_national_sources import RAW, DIRECTORY, MEMBERSHIP, read_ccd, membership_cache, source
from database import ROOT, DEFAULT_DB
from prepare_ccd_states import grade_school
from state_registry import reported_count
from state_snapshot import prepare_snapshot

EXTRACT = ROOT / 'data/source/kansas.json'
OUTPUT = ROOT / 'data/kansas'
PERFORMANCE_URL = 'https://ksreportcard.ksde.gov/2024_2025_Assessment_Full_File.xlsx'
INCOME_URL = 'https://ksreportcard.ksde.gov/services/dataService.svc/getDemoChart'
DEFINITION_URL = 'https://kidsweb.ksde.gov/LinkClick.aspx?fileticket=Bjstg5HkxZ0%3d&tabid=92&portalid=0&mid=484'
SCOPE_URL = 'https://www.youtube.com/live/gWQrChUA9Mg?t=6097'
MINUTES_URL = 'https://www.ksde.gov/docs/default-source/state-board/september-9-and-10-2025-kansas-state-board-of-education-minutes-with-time-stamps.pdf?sfvrsn=7db47387_2'
INCOME_CACHE = RAW / 'ks-income-2025'
INCOME_CAPTURE = RAW / 'ks-school-income-captures-2025.json'
INCOME_DEFINITION = (
    'Published 2024–25 Kansas Building Report Card Economically Disadvantaged '
    'percentage of all enrolled students. Individual eligibility is reported in '
    'KIDS D34 through NSLP applications, direct certification including qualifying '
    'Medicaid, or the KSDE Household Economic Survey. The dated 2024–25 KIDS '
    'specification requires CEP schools to retain individual direct-certification '
    'or survey eligibility codes; universal free meals are not individual '
    'eligibility. The September 20, 2024 ENRL collection feeds Building Report Card '
    'enrollment reporting. Retain the native published percentage; no eligible '
    'count or its exact denominator is inferred. Displayed enrollment comes '
    'separately from reported same-year CCD fall membership, not the demographic '
    'percentage denominator.')


def exact_percent(value):
    if isinstance(value, bool) or not re.fullmatch(r'\d+(?:\.\d+)?', str(value)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) and 0 <= parsed <= 100 else None


def native_key(org, building):
    org, building = str(org).strip(), str(building).strip()
    if not re.fullmatch(r'D\d{4}', org) or not re.fullmatch(r'\d{4}', building):
        return None
    return org + '-' + building


def ccd_key(value):
    match = re.fullmatch(r'KS-(D\d{4})-(\d{4})', value)
    return '-'.join(match.groups()) if match else None


def cohort(profile, grades, total):
    if grade_school(profile, grades, total):
        # A tested grade is required, not just a preschool/K–2 grade span.
        return 'grade' if any(reported_count(grades.get(f'Grade {g}')) for g in range(3, 9)) else None
    if (profile['IGOFFERED'] != 'As reported' or profile['GSLO'] not in ['09', '10'] or
            profile['GSHI'] not in ['10', '11', '12'] or not grades):
        return None
    fields = ['G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
    if any(profile[f] not in ['Yes', 'No'] for f in fields):
        return None
    if any(profile[f] == 'Yes' for f in ['G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 9)] + ['G_13_OFFERED', 'G_AE_OFFERED']):
        return None
    expected = [f'Grade {g}' for g in range(9, 13)]
    values = [reported_count(r) for g, r in grades.items() if g in expected]
    if (not values or any(v is None for v in values) or
            sum(values) != reported_count(total) or not reported_count(grades.get('Grade 10'))):
        return None
    for grade, row in grades.items():
        if grade not in expected and (row['STUDENT_COUNT'] != '0' or row['DMS_FLAG'] not in ['Reported', 'Derived']):
            return None
    return 'high'


def assessment_rows():
    workbook = openpyxl.load_workbook(RAW/'ks-assessment-2025.xlsx', read_only=True, data_only=True)
    rows = iter(workbook['2025'].values)
    headers = next(rows)
    native = defaultdict(dict)
    for number, values in enumerate(rows, 2):
        row = dict(zip(headers, values))
        key = native_key(row['Org. No.'], row['Bldg. No.'])
        if key and row['Student Subgroup'] == 'All Students' and row['Grade'] == 'All Grades' and row['Subject'] in ['ELA', 'Math']:
            subject = 'reading' if row['Subject'] == 'ELA' else 'math'
            if subject in native[key]:
                raise ValueError('Duplicate native school/subject total')
            native[key][subject] = (number, row)
    workbook.close()
    return native


def directory_rows():
    profiles = {}
    for row in read_ccd(DIRECTORY):
        if row['ST'] != 'KS':
            continue
        key = ccd_key(row['ST_SCHID'])
        if key:
            if key in profiles:
                raise ValueError('Ambiguous exact official Kansas school crosswalk')
            profiles[key] = row
    return profiles


def income_url(key):
    org, building = key.split('-')
    return INCOME_URL + '?' + urllib.parse.urlencode(dict(orgNo=org, bldgNo=building, progYear=2025, demoType=3, rptType=1))


def download_income():
    native, profiles, membership = assessment_rows(), directory_rows(), membership_cache()
    keys = []
    for key in sorted(native):
        profile = profiles.get(key)
        if profile and profile['UPDATED_STATUS'] in ['1', '3', '4', '5', '8'] and cohort(profile, membership['grades'].get(profile['NCESSCH']), membership['totals'].get(profile['NCESSCH'])):
            keys.append(key)
    INCOME_CACHE.mkdir(exist_ok=True)
    def fetch(key):
        path = INCOME_CACHE / (key + '.json')
        url = income_url(key)
        if not path.exists():
            with urllib.request.urlopen(url, timeout=60) as response:
                data = json.loads(response.read())
            path.write_text(json.dumps(dict(school_id=key, year=2025, url=url, response=data), separators=(',', ':'))+'\n')
        return key
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, future in enumerate(as_completed([pool.submit(fetch, key) for key in keys]), 1):
            future.result()
            if i % 100 == 0:
                print(f'Captured {i}/{len(keys)} native enrolled-income rows', flush=True)
    captures = [json.loads((INCOME_CACHE/(key+'.json')).read_text()) for key in keys]
    INCOME_CAPTURE.write_text(json.dumps(captures, separators=(',', ':'))+'\n')
    print(f'Captured {len(keys)} native enrolled-income rows', flush=True)


def native_income(capture):
    if (capture['year'] != 2025 or capture['url'] != income_url(capture['school_id'])):
        raise ValueError('Income request is not the exact school/year enrolled ED')
    rows = json.loads(capture['response']['d'])
    if not rows:
        return None
    if len(rows) != 2 or {r['title'] for r in rows} != {'Econ. Disadvantaged', 'Non-Econ. Disadvantaged'}:
        raise ValueError('Unexpected enrolled economic population')
    values = {r['title']:exact_percent(r['value']) for r in rows}
    if any(v is None for v in values.values()):
        return None
    if abs(sum(values.values()) - 100) > .11:
        raise ValueError('Economic categories do not reconcile to all enrolled students')
    return values['Econ. Disadvantaged']


def native_outcome(row, number, subject):
    if (row['School Year'] != 2025 or row['Student Subgroup'] != 'All Students' or
            row['Grade'] != 'All Grades' or row['Subject'] != ('Math' if subject=='math' else 'ELA')):
        raise ValueError('Not the native same-year school assessment total')
    third, fourth = exact_percent(row['Pct. Level 3']), exact_percent(row['Pct. Level 4'])
    pct = round(third+fourth, 10) if third is not None and fourth is not None else None
    if pct is not None and pct > 100:
        raise ValueError('Native proficient categories exceed 100 percent')
    return dict(proficiency=pct, tested=None, raw=row, raw_tested=None,
        source='ksde_performance', source_row=number,
        exclusion=None if pct is not None else 'One or both native proficient categories are suppressed or unavailable')


def extract():
    native, profiles, membership = assessment_rows(), directory_rows(), membership_cache()
    captures = {c['school_id']:c for c in json.loads(INCOME_CAPTURE.read_text())}
    schools, excluded = [], []
    for key, outcomes in sorted(native.items()):
        profile, capture = profiles.get(key), captures.get(key)
        total = membership['totals'].get(profile['NCESSCH']) if profile else None
        grades = membership['grades'].get(profile['NCESSCH']) if profile else None
        kind = cohort(profile, grades, total) if profile else None
        income = native_income(capture) if capture else None
        reason = None
        if profile is None:
            reason = 'Missing exact same-year public-school identity (including private schools)'
        elif profile['SCHOOL_YEAR'] != '2024-2025' or profile['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8']:
            reason = 'School not operational in same-year CCD directory'
        elif kind is None:
            reason = 'Mixed, untested, adjusted or unknown grade configuration'
        elif set(outcomes) != {'math', 'reading'}:
            reason = 'Missing native all-grades subject pair'
        elif income is None or not reported_count(total):
            reason = 'Native enrolled ED rate or reported same-year membership is unavailable'
        if reason:
            excluded.append(dict(state_school_id=key, reason=reason,
                outcomes={s:r for s,(_,r) in outcomes.items()}, income=capture,
                directory=profile, membership=total, membership_grades=grades))
            continue
        example = next(iter(outcomes.values()))[1]
        schools.append(dict(id=key, cohort=kind, name=example['Building'],
            district_id=key.split('-')[0], district=example['Organization'],
            city=profile['LCITY'], county=None, enrollment=reported_count(total),
            income=income, low_income=None, income_raw=capture,
            income_source='ksde_income', income_row=len(schools)+1,
            directory_raw=profile, membership_raw=total, membership_grades_raw=grades,
            identity_raw=dict(nces_id=profile['NCESSCH'], ccd_state_id=profile['ST_SCHID'],
                normalization='Exact KS-ORG-BUILDING parts join native string Org. No. and Bldg. No.'),
            outcomes={s:native_outcome(r,n,s) for s,(n,r) in outcomes.items()}))
    sources = {
        'ksde_performance':source(RAW/'ks-assessment-2025.xlsx', PERFORMANCE_URL),
        'ksde_income':source(INCOME_CAPTURE, INCOME_URL),
        'ksde_demographics_help':source(RAW/'ks-demographics.html', 'https://ksreportcard.ksde.gov/demographics.aspx?org_no=State&rptType=3'),
        'ksde_assessment_help':source(RAW/'ks-assessment.html', 'https://ksreportcard.ksde.gov/assessment_results.aspx?org_no=State&rptType=3'),
        'ksde_assessment_year':source(RAW/'ks-assessment_results.js', 'https://ksreportcard.ksde.gov/Scripts/pagejs/assessment_results.js'),
        'ksde_kids_definition':source(RAW/'ks-kids-collection-2025.pdf', DEFINITION_URL),
        'ksde_enrollment_handbook':source(RAW/'ks-enrollment-handbook-2025.pdf', 'https://www.ksde.gov/Portals/0/Auditing/Guidelines/Enrollment%20Handbook%20FY25.pdf'),
        'ksde_assessment_scope':source(RAW/'ks-board-video-2025.en.json3', SCOPE_URL),
        'ksde_scope_minutes':source(RAW/'ks-board-september-2025.pdf', MINUTES_URL),
        'ksde_kap_technical':source(RAW/'ks-kap-technical-2025.pdf', 'https://ksassessments.org/sites/default/files/documents/technical-manuals/KAP_Technical_Manual_2025.pdf'),
        'ccd_directory':source(RAW/(DIRECTORY+'.zip'), 'https://nces.ed.gov/ccd/Data/zip/'+DIRECTORY+'.zip'),
        'ccd_membership':source(RAW/(MEMBERSHIP+'.zip'), 'https://nces.ed.gov/ccd/Data/zip/'+MEMBERSHIP+'.zip'),
    }
    audit = dict(approved_point_only=True, native_units=len(native),
        native_population='2025 sheet, All Students, All Grades, Math/ELA; native Report Card KAP+DLM combined assessment population.',
        assessment_scope_evidence='Official September 9,2025 KSBE meeting video, KSDE/KU state assessment score reports: 1:41:37 KSDE adds DLM to KU general results; 1:41:53 combines both; 1:42:01 says public report card includes alternate students. Official minutes p5 identify the presenting KSDE/KU team and planned release. Preserve source captions and primary video URL.',
        proficient='Sum the independently published unsuppressed school-total Level3 and Level4 percentages only. Published levels are rounded; do not reconstruct masked levels, counts, grades or rates from complementary categories.',
        denominator='Native four-level performance percentages; published Not Tested is separate. No valid-score count is established for this extract. Every tested field is null and every model is point-only.',
        income='Report Card native demographic API, year2025, demoType3, rptType1: all enrolled students. KIDS2024–25v1.15 p8 ties ENRL September20 to Report Card; p35 defines individual D34 including CEP direct certification/HES. FY25 Enrollment Handbook p38 requires individual eligibility, not automatic universal free meals.',
        grades='Exact same-year CCD KS-ORG-BUILDING crosswalk; unadjusted grade offers and reconciled grade membership. Separate pure grade and pure high schools, excluding all mixed/unknown configurations.',
        standards='2025 is a refreshed general assessment with new scale scores and cut scores. Combined native totals include DLM alternate academic standards. No history is joined.',
        excluded=dict(Counter(x['reason'] for x in excluded)))
    cohorts = [dict(id=kind, level=level, grades=testgrades,
        assessment=f'Kansas native KAP + DLM · {label} · 2025',
        standard='Native Level3 proficient or Level4 advanced; general and alternate academic achievement standards; refreshed 2025 KAP',
        source='ksde_performance', source_url=PERFORMANCE_URL, label=label+' · KAP + DLM',
        outcome='Proficient or advanced', note='Native school total · individual enrolled ED · point-only',
        allow_point_only=True)
        for kind,level,testgrades,label in [('grade','ES','3–8','Grade schools'),('high','HS','10','High schools')]]
    payload = dict(dataset='ks-native-ed', year=2025, academic_year='2024–25',
        state=dict(id='KS',name='Kansas'),name='Kansas 2025 native assessments and individual enrolled disadvantage',
        region='kansas',prepare_script='scripts/prepare_kansas.py',source_url=PERFORMANCE_URL,
        retrieved=date.today().isoformat(),model_scope='Kansas public pure grade and pure high schools, separate native all-grades KAP+DLM cohorts with same-year individual enrolled economic disadvantage; mixed grades excluded',
        income_definition=dict(label='Economically disadvantaged',definition=INCOME_DEFINITION,url=DEFINITION_URL),
        sources=sources,source_audit=audit,schools=schools,excluded=excluded,cohorts=cohorts,
        coverage_note=f'{len(schools)} public grade and high schools with native assessment totals and same-year individual enrolled economic disadvantage. Mixed schools, unavailable income and suppressed levels limit coverage. New2025 assessment scale; no history or sampling intervals.',
        methodology=dict(summary='Native KAP + DLM school totals and same-year individual enrolled economic disadvantage.',
            details=[INCOME_DEFINITION,audit['native_population'],audit['assessment_scope_evidence'],audit['proficient'],audit['denominator'],audit['grades'],audit['standards'],
                'Combined is the equal mean of Math and ELA. State and school-level cohorts have independent externally studentized models; results are associations, not causal effectiveness.'],
            sources=[dict(label='KSDE2024–25native full assessment workbook',url=PERFORMANCE_URL),
                dict(label='KSDE demographic source and all-enrolled population',url='https://ksreportcard.ksde.gov/demographics.aspx?org_no=State&rptType=3'),
                dict(label='KIDS2024–25 individual eligibility specification',url=DEFINITION_URL),
                dict(label='Official2025 board explanation of KAP+DLM report-card scope',url=SCOPE_URL)]))
    validate(payload)
    EXTRACT.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n')
    return payload


def validate(payload):
    if payload['year'] != 2025 or payload['academic_year'] != '2024–25' or payload['state']['id'] != 'KS':
        raise ValueError('Wrong-year/state snapshot')
    if {c['id']:c['level'] for c in payload['cohorts']} != {'grade':'ES','high':'HS'} or not all(c['allow_point_only'] for c in payload['cohorts']):
        raise ValueError('Expected separate point-only grade and high cohorts')
    for school in payload['schools']:
        profile = school['directory_raw']
        if (profile['SCHOOL_YEAR'] != '2024-2025' or ccd_key(profile['ST_SCHID']) != school['id'] or
                school['income_raw']['school_id'] != school['id'] or
                cohort(profile,school['membership_grades_raw'],school['membership_raw']) != school['cohort']):
            raise ValueError('School identity, year or grade scope is invalid')
        if (school['income'] != native_income(school['income_raw']) or school['income'] is None or
                school['low_income'] is not None or school['enrollment'] != reported_count(school['membership_raw']) or not school['enrollment']):
            raise ValueError('Economic values are not native individual enrolled ED')
        if set(school['outcomes']) != {'math','reading'}:
            raise ValueError('Missing native subject pair')
        for subject,outcome in school['outcomes'].items():
            raw = outcome['raw']
            if (native_key(raw['Org. No.'],raw['Bldg. No.']) != school['id'] or outcome['tested'] is not None or
                    outcome['proficiency'] != native_outcome(raw,outcome['source_row'],subject)['proficiency']):
                raise ValueError('Outcome is not the point-only published proficient category sum')


def prepare(database=DEFAULT_DB):
    payload = json.loads(EXTRACT.read_text())
    validate(payload)
    return prepare_snapshot(payload,EXTRACT,OUTPUT,database)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-income',action='store_true')
    parser.add_argument('--extract',action='store_true')
    parser.add_argument('--database',default=DEFAULT_DB)
    args=parser.parse_args()
    if args.download_income:
        download_income()
    if args.extract:
        extract()
    if EXTRACT.exists():
        print(json.dumps(prepare(args.database),indent=2))
