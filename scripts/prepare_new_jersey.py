"""Audited 2024–25 NJ school totals: NJSLA/DLM grades 3–8 and NJGPA grade 11."""
import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

YEAR = 2025
SCHOOL_YEAR = '2024-25'
EXTRACT = ROOT/'data/source/new-jersey.json'
RAW = ROOT/'data/raw/new-jersey'
PORTAL = 'https://www.nj.gov/education/spr/download/'
BASE = 'https://www.nj.gov/education/sprreports/download/DataFiles/2024-2025/'
GUIDE = 'https://nj.gov/education/spr/resources/doc/SPR_ReferenceGuide.pdf'
FILES = {
    'database': ('Database_SchoolDetail.xlsx', BASE+'Database_SchoolDetail.xlsx'),
    'layout': ('Database_SchoolLayout.xlsx', BASE+'Database_SchoolLayout.xlsx'),
    'guide': ('SPR_ReferenceGuide.pdf', GUIDE),
    'income-guidance': ('Income_Guidance.pdf', 'https://www.nj.gov/education/broadcasts/2024/july/10/GuidelinesforReportingEnrollmentIncomeStatus.pdf'),
    'cep-guidance': ('CEP_Guidance.pdf', 'https://www.nj.gov/education/broadcasts/2021/july/7/CommunityEligibleProvisionSurveyandDocumentsfor2021-2022NowAvailable.pdf'),
}
IDENTITY = ['CountyCode', 'CountyName', 'DistrictCode', 'DistrictName', 'SchoolCode', 'SchoolName']
GRADES = ['GradePK', 'GradeKG', *[f'Grade{g:02}' for g in range(1,13)]]
INCOME_FIELD = 'Economically Disadvantaged Students'
DEFINITION = ('Published same-year end-of-year enrollment percentage classified as economically '
    'disadvantaged (eligible for free or reduced-price lunch), from NJ SMART. NJDOE requires '
    'individual household-income applications/surveys or direct certification for CEP reporting; '
    'universal meal access alone is not eligibility. The 2024–25 income guidance distinguishes '
    'federal free/reduced eligibility from the expanded New Jersey free-meal category. '
    'We retain the published percentage; no exact eligible count is inferred from rounding.')


def identity(row):
    parts = [row[k] for k in ['CountyCode', 'DistrictCode', 'SchoolCode']]
    if any(not isinstance(v,str) or not re.fullmatch(r'\d{'+str(n)+'}',v)
           for v,n in zip(parts,[2,4,3])):
        raise ValueError(f'Invalid NJ county/district/school identity: {parts}')
    return ''.join(parts)


def percentage(raw):
    if raw is None or not isinstance(raw,(str,int,float)):
        return None
    text = str(raw).strip()
    if not re.fullmatch(r'\d+(?:\.\d+)?%?', text):
        return None
    value = float(text.rstrip('%'))
    if not 0 <= value <= 100:
        raise ValueError('Invalid NJ published percentage')
    return value


def count(raw):
    if raw is None or not re.fullmatch(r'\d+(?:,\d{3})*',str(raw)):
        return None
    return int(str(raw).replace(',',''))


def cohort(grades):
    values = [count(v) for v in grades]
    if any(v is None for v in values):
        return None
    if any(values[10:]):  # PK, KG, 1..8 precede high-school grades.
        return 'HS' if values[12] else None
    return 'ES' if any(values[4:10]) else None


def workbook_rows(workbook, name, fields, all_students=False):
    iterator = workbook[name].iter_rows(min_row=4,values_only=True)
    headers = next(iterator)
    if not set(fields).issubset(headers):
        raise ValueError(f'NJ {name} columns changed')
    for number, values in enumerate(iterator,5):
        row = dict(zip(headers,values))
        if row.get('SchoolYear') != SCHOOL_YEAR:
            continue
        if all_students and row['StudentGroup'] != 'All Students':
            continue
        row = {key:row[key] for key in fields}
        identity(row)
        yield number,row


def outcome(row, subject, high):
    rate_key = ('MathGraduationReadyPct_School' if subject=='math' else 'ELAGraduationReadyPct_School') if high else 'MetExceededExpectations_School'
    n_key = ('MathValidScores_School' if subject=='math' else 'ELAValidScores_School') if high else 'ValidScores_School'
    rate, tested = percentage(row[rate_key]), count(row[n_key])
    if tested is not None and tested < 10:
        raise ValueError('Published NJ result below its valid-score reporting threshold')
    if tested == 0 and rate is not None:
        raise ValueError('Proficiency without valid scores')
    return dict(proficiency=rate, tested=tested, raw=row,
        raw_tested=row[n_key], source='database',
        valid_score_evidence='NJDOE School Layout field '+n_key+'; Reference Guide pp.14 and20',
        exclusion='NJDOE did not publish an exact unsuppressed school proficiency rate' if rate is None else None)


def extract(raw=RAW, destination=EXTRACT):
    sources = {key:dict(path=str((Path(raw)/name).relative_to(ROOT)),url=url,
        sha256=hashlib.sha256((Path(raw)/name).read_bytes()).hexdigest())
        for key,(name,url) in FILES.items()}
    w = openpyxl.load_workbook(Path(raw)/FILES['database'][0],read_only=True,data_only=True)
    profiles, exclusions = {}, Counter()
    fields = IDENTITY+['SchoolYear',*GRADES,'Total']
    for number,row in workbook_rows(w,'EnrollmentTrendsbyGrade',fields):
        key=identity(row)
        if key in profiles:
            raise ValueError('Duplicate NJ same-year enrolled school')
        band=cohort([row[g] for g in GRADES])
        if band is None:
            exclusions['No supported tested grade or unknown enrolled grade span']+=1
            continue
        profiles[key]=dict(id=key,name=row['SchoolName'],district_id=key[:6],
            district=row['DistrictName'],county=row['CountyName'],cohort=band,
            enrollment=count(row['Total']),grades_raw=row,grade_row=number,
            income=None,income_raw={},income_row=0,income_source='database',outcomes={})
    seen=set()
    for number,row in workbook_rows(w,'EnrollmentTrendsByStudentGroup',IDENTITY+['SchoolYear',INCOME_FIELD]):
        key=identity(row)
        if key in seen:
            raise ValueError('Duplicate NJ same-year income observation')
        seen.add(key)
        if key in profiles:
            profiles[key].update(income=percentage(row[INCOME_FIELD]),income_raw=row,income_row=number)
    total_fields=IDENTITY+['SchoolYear','StudentGroup','ValidScores_School',
        'MetExceededExpectations_School','ParticipationRate_School','FederalProficiencyRate_School']
    unmatched=[]
    for subject,sheet in [('math','MathParticipationPerformance'),('reading','ELAParticipationPerformance')]:
        seen=set()
        for number,row in workbook_rows(w,sheet,total_fields,True):
            key=identity(row)
            if key in seen:
                raise ValueError('Duplicate NJ school/subject total')
            seen.add(key)
            if key not in profiles:
                unmatched.append(dict(sheet=sheet,source_row=number,raw=row))
                continue
            if profiles[key]['cohort'] != 'ES':
                continue  # Broad mixed/high-school accountability totals are outside the ES cohort.
            profiles[key]['outcomes'][subject]=dict(outcome(row,subject,False),source_row=number)
    high_fields=IDENTITY+['SchoolYear','StudentGroup','ELAValidScores_School',
        'ELAGraduationReadyPct_School','MathValidScores_School','MathGraduationReadyPct_School']
    seen=set()
    for number,row in workbook_rows(w,'NJGPA',high_fields,True):
        key=identity(row)
        if key in seen:
            raise ValueError('Duplicate NJGPA school total')
        seen.add(key)
        if key not in profiles:
            unmatched.append(dict(sheet='NJGPA',source_row=number,raw=row))
            continue
        if profiles[key]['cohort'] != 'HS':
            raise ValueError('NJGPA result without same-year grade 11 enrollment')
        for subject in ['math','reading']:
            profiles[key]['outcomes'][subject]=dict(outcome(row,subject,True),source_row=number)
    w.close()
    standards = ('Native NJSLA and DLM combined school totals, grades 3–8 at schools without '
        'high-school enrollment. NJSLA Levels4/5 and DLM Levels3/4; valid-score proficiency, '
        'not FederalProficiencyRate or participation. Accountability school assignment and '
        'half-year attendance rules apply. No grade-level reconstruction.')
    coverage = ('2024–25 NJDOE school reports. Grade schools use published NJSLA/DLM totals '
        'without the federal participation adjustment. High schools use NJGPA grade11 '
        'graduation-ready rates. Same-year end-of-year ED enrollment; suppressed and ranged '
        'values remain unavailable. Accountability and attending-school populations may differ. '
        'One year; no admissions classifications or audited coordinates.')
    payload=dict(schema_version=1,state=dict(id='NJ',name='New Jersey'),dataset='nj-spr-2025',
        name='New Jersey School Performance Reports 2024–25',year=YEAR,academic_year='2024–25',
        region='new-jersey',prepare_script='scripts/prepare_new_jersey.py',
        model_scope='Separate NJSLA/DLM grade-school and NJGPA grade11 public-school cohorts',
        retrieved=datetime.now(timezone.utc).isoformat(),source_url=PORTAL,sources=sources,
        income_definition=dict(label='Economically disadvantaged enrollment',definition=DEFINITION,url=GUIDE),
        cohorts=[dict(id='ES',level='ES',assessment='NJSLA/DLM grades 3–8 · valid scores',grades='3–8',
            standard=standards,source='database',source_url=GUIDE,label='Grade schools · NJSLA/DLM',
            outcome='Met or exceeded expectations',note='NJSLA/DLM · valid scores · half-year attendance'),
            dict(id='HS',level='HS',assessment='NJGPA grade 11',grades='11',
            standard='Published grade11 NJGPA graduation-ready valid-score rate; grade12 make-ups excluded. ELA grade10 standards; math AlgebraI and Geometry. Separate from NJSLA/DLM accountability outcomes.',
            source='database',source_url=GUIDE,label='High schools · NJGPA',
            outcome='Graduation ready',note='NJGPA · grade 11 · valid scores')],
        schools=list(profiles.values()),coverage_note=coverage,
        source_audit=dict(excluded_grade_profiles=dict(exclusions),unmatched_assessments=unmatched),
        methodology=dict(summary='New Jersey uses separate published grade-school NJSLA/DLM and high-school NJGPA results.',
            details=[standards,DEFINITION,'NJGPA measures grade11 graduation readiness. Grade12 make-ups are excluded; its ELA and mathematics standards differ from the NJSLA/DLM cohort.',
                'Enrollment is reported at the attending school at year end; assessment results use accountable schools. Students placed in receiving schools can be assigned to sending public schools. Partial-attendance exclusions and whole-school income versus tested-grade populations limit interpretation.',
                'Exact school totals avoid aggregating grade percentages or recovering suppressed cells. Values such as <10% remain unavailable. Verified valid-score counts support approximate sampling intervals; any eligible member missing its denominator disables intervals for its complete model.',
                'Combined is the equally weighted mean of math and ELA rates. Models use externally studentized residuals and describe associations, not causal effectiveness. State standards do not form a national scale.'],
            sources=[dict(label='NJDOE school report downloads',url=PORTAL),dict(label='Source field layout',url=FILES['layout'][1]),
                dict(label='Assessment and enrollment definitions',url=GUIDE),dict(label='2024–25 income reporting guidance',url=FILES['income-guidance'][1]),
                dict(label='CEP individual eligibility reporting',url=FILES['cep-guidance'][1])]))
    Path(destination).write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n')
    return payload


def prepare(database=DEFAULT_DB):
    payload=json.loads(EXTRACT.read_text())
    if (payload['state']['id'],payload['year'],payload['dataset']) != ('NJ',YEAR,'nj-spr-2025'):
        raise ValueError('Wrong NJ extract identity')
    for school in payload['schools']:
        if school['id'] != identity(school['grades_raw']) or school['grades_raw']['SchoolYear'] != SCHOOL_YEAR:
            raise ValueError('NJ profile identity/year mismatch')
        if school['cohort'] != cohort([school['grades_raw'][g] for g in GRADES]):
            raise ValueError('NJ cohort differs from same-year enrolled grades')
        if school['income_raw']:
            if identity(school['income_raw']) != school['id'] or school['income_raw']['SchoolYear'] != SCHOOL_YEAR or school['income'] != percentage(school['income_raw'][INCOME_FIELD]):
                raise ValueError('NJ income identity/year/value mismatch')
        for subject,observation in school['outcomes'].items():
            row=observation['raw']
            if identity(row) != school['id'] or row['SchoolYear'] != SCHOOL_YEAR or row['StudentGroup'] != 'All Students':
                raise ValueError('NJ assessment identity/year/group mismatch')
            checked=outcome(row,subject,school['cohort']=='HS')
            if any(observation[k] != checked[k] for k in ['proficiency','tested']):
                raise ValueError('NJ normalized outcome differs from source')
    return prepare_snapshot(payload,EXTRACT,ROOT/'data/new-jersey',database)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract',action='store_true')
    parser.add_argument('--database',type=Path,default=DEFAULT_DB)
    args=parser.parse_args()
    if args.extract:
        extract()
    print(json.dumps(prepare(args.database),indent=2))
