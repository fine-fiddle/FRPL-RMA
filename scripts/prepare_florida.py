"""Florida 2024–25 native school-grade achievement and individual lunch eligibility."""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.request import Request,urlopen

import openpyxl

from database import ROOT,DEFAULT_DB
from state_snapshot import prepare_snapshot

DATASET='fl-schoolgrades-2025'
YEAR=2025
EXTRACT=ROOT/'data/source/florida.json'
OUTPUT=ROOT/'data/florida'
PORTAL='https://www.fldoe.org/accountability/accountability-reporting/school-grades/archives.stml'
LUNCH_GUIDE='https://www.fldoe.org/core/fileparse.php/20744/urlt/2425-146025.pdf'
GRADE_GUIDE='https://www.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf'
FILES={
    'assessment':('fl_assessment_2025.xlsx','https://cdn.fldoe.org/file/18534/SchoolGrades25.xlsx'),
    'income':('fl_income_2025.xlsx','https://cdn.fldoe.org/file/7584/2425LunchStatusFS2-3.xlsx'),
    'grades':('fl_grades_2025.xlsx','https://cdn.fldoe.org/file/7584/2425MembBySchoolByGrade.xlsx'),
    'grade-guide':('fl_guide_2025.pdf','https://cdn.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf'),
    'lunch-guide':('fl_lunch_definition_2025.pdf','https://cdn.fldoe.org/core/fileparse.php/20744/urlt/2425-146025.pdf'),
}
ECON=('Florida 2024–25 Final Survey 3 (February) raw individual Lunch Status counts: D/F free eligibility + '
      '3/E reduced eligibility + C/R CEP direct certification, divided by same-survey enrolled students (PK–12). '
      'Never uses the USDA 1.6-adjusted federal funding numerator or published school-grade economic percentage. '
      'CEP N means not individually identified eligible and is excluded from the numerator. Provision 2 code 4 '
      'reports all enrolled students, so schools with nonzero or masked code 4 have unavailable income. '
      'At CEP schools this proxy counts direct certification/household extension rather than a complete income '
      'survey of all families; undercount and reporting coverage are unknown. No other-year backfill.')
STANDARD=('2024–25 native School Grades English Language Arts Achievement and Mathematics Achievement '
          'components: Level 3 or above / valid assessed students under Florida full-year-enrollment and '
          'home-zoned attribution rules, including eligible FAA Performance Task but excluding FAA Datafolio. '
          'ELA FAST PM3 grades 3–10 and Math FAST PM3 grades 3–8 plus B.E.S.T./Access Algebra 1/Geometry EOCs; '
          'this cohort enrolls no grades 9–12 in the same-year Survey 2 registry. ELL included after two US-school years; '
          'medical/extraordinary exemptions excluded. Components require at least 10 eligible students. '
          'Native whole-percent rates only; score denominators absent, so all model sampling intervals unavailable. '
          'Collocated combined results and provider-specific virtual rates are excluded from individual-school matches.')


def code(value,width):
    if isinstance(value,(int,float)) and value==int(value):value=str(int(value))
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,'+str(width)+'}',value):raise ValueError('Invalid Florida authoritative code')
    return value.zfill(width)


def sid(row):return code(row[0],2)+'-'+code(row[2],4)


def number(value):
    if value in (None,'','*','**','***','N/A'):return None
    value=float(value)
    if not math.isfinite(value) or value<0:raise ValueError('Invalid Florida source number')
    return value


def count(value):
    value=number(value)
    if value is not None and value!=int(value):raise ValueError('Non-integral Florida count')
    return None if value is None else int(value)


def income(raw):
    if raw is None:return None,None,None,'Same-year Survey 3 individual lunch eligibility not reported'
    if len(raw)!=12:raise ValueError('Florida lunch schema changed')
    total=count(raw[4]);values=[count(raw[i]) for i in [5,6,7,8]]
    if values[2]!=0:return total,None,None,'Provision 2 code 4 counts all students or is masked; individual income unavailable'
    if total in (None,0) or None in values:return total,None,None,'Individual lunch eligibility counts suppressed or missing'
    low=values[0]+values[1]+values[3]
    if low>total:raise ValueError('Florida individual lunch eligibility exceeds enrollment')
    return total,low,100*low/total,None


def scope(raw):
    if len(raw)!=18:raise ValueError('Florida enrolled grade schema changed')
    # Asterisk means protected positive membership, never zero. Require explicit
    # zero in every high-school grade; do not reconstruct suppressed grade counts.
    return all(count(v)==0 for v in raw[14:18])


def outcome(row,subject):
    if row is None:return None,'Native School Grades achievement component not reported'
    if row[3] not in ('',None):return None,'Provider-specific virtual school achievement lacks matching provider income'
    if row[47]=='Y':return None,'Combined collocated-school result does not match one school income record'
    if row[47]!='N':raise ValueError('Unknown Florida collocated status')
    value=number(row[9 if subject=='math' else 6])
    if value is None:return None,'Native achievement component unavailable or fewer than 10 eligible students'
    if value>100:raise ValueError('Invalid native Florida proficiency')
    return value,None


def rows(filename,sheet):
    book=openpyxl.load_workbook(ROOT/'data/raw'/filename,read_only=True,data_only=True)
    try:return list(book[sheet].values)
    finally:book.close()


def extract():
    grade=rows(FILES['grades'][0],'School');lunch=rows(FILES['income'][0],'2425 FS3_Schl')
    assess=rows(FILES['assessment'][0],'School Grades 2025')
    if '2024-25' not in grade[0][0] or grade[1][4:]!=('PK','KG',1,2,3,4,5,6,7,8,9,10,11,12):raise ValueError('Wrong-year Florida enrolled grades')
    if '2024-25, Final Survey 3' not in lunch[0][0] or 'Codes D&F' not in lunch[2][5] or 'Code 4' not in lunch[2][7] or 'Codes C&R' not in lunch[2][8]:raise ValueError('Wrong Florida individual lunch fields')
    if '2024-25 School Grades' not in assess[0][2] or assess[3][6]!='English Language Arts Achievement' or assess[3][9]!='Mathematics Achievement':raise ValueError('Wrong native Florida assessment scope')
    profiles={};assessment_rows=[];unmatched_income=[];income_ids=set()
    for i,r in enumerate(grade[2:],3):
        if r[0] is None:continue
        key=sid(r)
        if key in profiles:raise ValueError('Duplicate Florida enrolled-school identity')
        scope(r);profiles[key]=dict(id=key,grades=list(r),grade_row=i,income_raw=None,income_row=0)
    for i,r in enumerate(lunch[3:],4):
        if r[0] is None:continue
        key=sid(r)
        if key in income_ids:raise ValueError('Duplicate Florida individual-income school ID')
        income_ids.add(key);income(r)
        if key not in profiles:
            unmatched_income.append(dict(id=key,row=i,raw=list(r),reason='February Survey 3 school lacks Fall Survey 2 enrolled-grade registry'));continue
        profiles[key].update(income_raw=list(r),income_row=i)
    for i,r in enumerate(assess[4:],5):
        if r[0] is None:continue
        key=sid(r)
        for s in ['math','reading']:outcome(r,s)
        assessment_rows.append(dict(id=key,row=i,raw=list(r)))
    sources={k:dict(path='data/raw/'+fn,url=url,sha256=hashlib.sha256((ROOT/'data/raw'/fn).read_bytes()).hexdigest()) for k,(fn,url) in FILES.items()}
    payload=dict(state='FL',year=YEAR,academic_year='2024-25',retrieved=str(date.today()),sources=sources,profiles=list(profiles.values()),assessments=assessment_rows,
        unmatched_income=unmatched_income,source_notes=dict(lunch=[list(r) for r in rows(FILES['income'][0],'NOTES')],assessment=[list(r) for r in assess[:4]],grade=[list(r) for r in grade[:2]]))
    EXTRACT.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n');return payload


def normalize(payload):
    if (payload['state'],payload['year'],payload['academic_year'])!=('FL',YEAR,'2024-25'):raise ValueError('Wrong Florida state/year')
    assessments={};unmatched=set();seen=set();excluded=Counter();schools=[]
    for entry in payload['assessments']:
        key=entry['id'];r=entry['raw']
        if key!=sid(r) or len(r)!=54:raise ValueError('Florida native school identity/schema changed')
        if r[3] not in ('',None):excluded['Provider-specific virtual assessment rows']+=1;continue
        if key in assessments:raise ValueError('Duplicate Florida campus-level native total')
        assessments[key]=entry
    for p in payload['profiles']:
        r=p['grades'];key=sid(r)
        if key!=p['id'] or key in seen or p['income_raw'] is not None and key!=sid(p['income_raw']):raise ValueError('Florida grade/income school identity changed')
        seen.add(key)
        if not scope(r):excluded['Enrolled grades 9–12 or protected high-school grade membership']+=1;continue
        total,low,pct,income_reason=income(p['income_raw']);a=assessments.get(key);raw=None if a is None else a['raw'];outcomes={}
        for s in ['math','reading']:
            rate,reason=outcome(raw,s)
            outcomes[s]=dict(proficiency=rate,tested=None,raw=None if raw is None else dict(achievement=raw[9 if s=='math' else 6],collocated=raw[47],provider=raw[3],school_type=raw[52]),raw_tested=None,
                source='assessment',source_row=0 if a is None else a['row'],exclusion='; '.join(filter(None,[income_reason,reason])) if rate is None or pct is None else None)
        schools.append(dict(id=key,name=r[3],district_id=code(r[0],2),district=r[1],cohort='grade-schools',income=pct,enrollment=total,low_income=low,
            income_raw=p,income_source='income',income_row=p['income_row'],outcomes=outcomes))
    unmatched=set(assessments)-seen
    assessment='Florida School Grades FAST + FAA + Math EOC · grade schools'
    model_scope='Florida public grade schools; separate native full-year school-grade achievement components and raw individual lunch eligibility'
    return dict(dataset=DATASET,state=dict(id='FL',name='Florida'),year=YEAR,academic_year='2024–25',name='Florida School Grades 2024–25',model_scope=model_scope,
        region='florida',prepare_script='scripts/prepare_florida.py',source_url=PORTAL,retrieved=payload['retrieved'],sources=payload['sources'],schools=schools,
        income_definition=dict(label='Individual reported FRPL/direct-certification eligibility',definition=ECON,url=LUNCH_GUIDE),
        cohorts=[dict(id='grade-schools',level='ES',assessment=assessment,grades='Grade schools: FAST3–8, FAA, Math EOC and source-attributed students',standard=STANDARD,source_url=GRADE_GUIDE,
            source='assessment',label='Grade schools · FAST/FAA',outcome='Level 3 or above',note='Native school-grade achievement · full-year rules',allow_point_only=True)],
        coverage_note=STANDARD+' '+ECON+' One year only; school coordinates unavailable.',
        methodology=dict(summary='Florida models native school-grade achievement rates against same-year raw individual lunch eligibility, excluding Provision 2 income and collocated aggregates.',
            details=[ECON,STANDARD,'The income and outcome populations differ: February school enrollment versus full-year achievement, including prescribed home-zoned attribution. Published economic-disadvantage percentages can use USDA multipliers and are not imported. No score counts are manufactured from enrollment or percent tested.',
                'Separate full statewide subject populations use externally studentized residuals. Combined is the equally weighted mean of Math and ELA; no UI filter refits. Sampling intervals are unavailable for every member because the native outcome file has no score denominators. Associations do not estimate causal effectiveness or overall quality.',
                'Fall Survey 2 grade enrollment requires explicit zero in every grade 9–12. Protected positive grade counts remain protected. No authoritative school-coordinate crosswalk is imported; all retained profiles remain available in lists and charts.'],
            sources=[dict(label='2025 native School Grades',url=FILES['assessment'][1]),dict(label='2024–25 final individual Lunch Status counts',url=FILES['income'][1]),dict(label='2024–25 same-year enrolled grades',url=FILES['grades'][1]),dict(label='2024–25 Lunch Status definitions',url=LUNCH_GUIDE),dict(label='2024–25 achievement inclusion rules',url=GRADE_GUIDE)]),
        source_audit=dict(public_enrolled_profiles=len(seen),grade_school_profiles=len(schools),native_assessment_rows=len(payload['assessments']),excluded=dict(excluded),
            unmatched_native_assessment_ids=sorted(unmatched),income_without_fall_grade_registry=len(payload['unmatched_income']),
            income_exclusions=dict(Counter(income(p['income_raw'])[3] for p in payload['profiles'] if scope(p['grades']) and income(p['income_raw'])[3])),mapped=0))


def prepare(database=DEFAULT_DB):
    result=prepare_snapshot(normalize(json.loads(EXTRACT.read_text())),EXTRACT,OUTPUT,database)
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--extract',action='store_true');parser.add_argument('--download',action='store_true')
    parser.add_argument('--database',type=Path,default=DEFAULT_DB);args=parser.parse_args()
    if args.download:
        for filename,url in FILES.values():(ROOT/'data/raw'/filename).write_bytes(urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=60).read())
    if args.extract or args.download:extract()
    prepare(args.database)
