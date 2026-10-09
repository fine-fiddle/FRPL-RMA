"""Arizona 2024–25 native AASA/MSAA grade-school totals, ACT grade 11 and enrolled income eligibility."""
import argparse
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET='az-ade-2025'
YEAR=2025
RAW=ROOT/'data/raw/arizona'
EXTRACT=ROOT/'data/source/arizona.json'
OUTPUT=ROOT/'data/arizona'
PAGE='https://www.azed.gov/accountability-research/data'
ASSESSMENT_URL='https://www.azed.gov/sites/default/files/2025/10/math_ela_assessmentsfy25.xlsx'
ENROLLMENT_URL='https://www.azed.gov/sites/default/files/2025/04/Oct1EnrollmentFY2025.xlsx'
INCOME_GUIDANCE='https://www.azed.gov/sites/default/files/2024/10/October%202024%20Staying%20on%20Track%20QA%20for%20Event%20Follow-Up%20.pdf'
ASSESSMENTS={'ES':'AASA/MSAA grades 3–8 · native totals 2025','HS':'ACT grade 11 · native regular results 2025'}
ECON_DEFINITION=('October 1, 2024 AzEDS enrolled students individually identified with Income Eligibility 1 or 2. '
    'Individual household-income forms, meal applications, direct certification and categorical eligibility '
    'support the flags. CEP schoolwide meal access does not establish individual eligibility. '
    'CEP schools without alternative household forms may report only directly certified students, which can understate broader individual eligibility. '
    'The numerator and denominator are native Income Eligibility 1 or 2 and All Students counts from the same enrollment table.')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sid(row):
    value=row['School Entity ID']
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value!=int(value) or value<=0:
        raise ValueError('Arizona requires a positive exact authoritative school entity ID')
    return str(int(value))


def number(raw):
    if raw is None or isinstance(raw,str):return None
    value=float(raw)
    if not math.isfinite(value):raise ValueError('Non-finite Arizona source number')
    return value


def count(raw):
    value=number(raw)
    if value is not None and (value<0 or value!=int(value)):raise ValueError('Arizona count must be an exact nonnegative integer')
    return int(value) if value is not None else None


def level_for(entry):
    row=entry['raw']
    if any(row[str(g)]=='*' or (count(row[str(g)]) or 0)>0 for g in range(9,13)):return 'HS'
    return 'ES' if any(row[str(g)]=='*' or (count(row[str(g)]) or 0)>0 for g in range(3,9)) else None


def income_values(entry):
    all_row,low_row=entry.get('all_students'),entry.get('income')
    total=count(all_row['raw']['Total']) if all_row else None
    low=count(low_row['raw']['Total']) if low_row else None
    if low is not None and total is not None and low>total:raise ValueError('Arizona individual eligibility exceeds same-table enrolled population')
    return total,low,100*low/total if total and low is not None else None


def assessment_values(row):
    pct,n=number(row['Percent Passing']),count(row['Number Tested'])
    if pct is None:return None,n,'Missing or suppressed native proficiency'
    if not 0<=pct<=100:raise ValueError('Invalid Arizona proficiency')
    if n is not None and n<=0:raise ValueError('Arizona proficiency has no valid results')
    bands=[number(row[f'Percent Proficiency Level {g}']) for g in range(1,5)]
    if any(v is not None and not 0<=v<=100 for v in bands):raise ValueError('Invalid Arizona proficiency band')
    # ADE uses largest-remainder rounding for the four bands. Percent Passing
    # may round independently by one percentage point; no numerator is inferred.
    if all(v is not None for v in bands) and abs(sum(bands)-100)>.001:raise ValueError('Arizona rounded proficiency bands do not sum to 100')
    if bands[2] is not None and bands[3] is not None and abs(pct-bands[2]-bands[3])>1.001:raise ValueError('Arizona passing rate does not reconcile to published bands')
    return pct,n,None


def rows(workbook,sheet):
    iterator=iter(workbook[sheet].values);headers=[str(v) for v in next(iterator)]
    for index,row in enumerate(iterator,2):yield index,dict(zip(headers,row))


def extract(raw=RAW,destination=EXTRACT):
    raw=Path(raw)
    sources={key:dict(path=str((raw/name).relative_to(ROOT)) if (raw/name).is_relative_to(ROOT) else str(raw/name),url=url,sha256=digest(raw/name))
             for key,name,url in [('az-assessment-2025','assessments.xlsx',ASSESSMENT_URL),('az-enrollment-2025','enrollment.xlsx',ENROLLMENT_URL)]}
    metadata={}
    for name in ['assessments','enrollment']:
        workbook=openpyxl.load_workbook(raw/(name+'.xlsx'),read_only=True,data_only=True)
        metadata[name]={sheet:[[v for v in row[:3] if v is not None] for row in workbook[sheet].values if any(v is not None for v in row[:3])]
                        for sheet in ['Introduction','Data Dictionary','Subgroup Dictionary']}
        if name=='enrollment':
            profiles={}
            for index,row in rows(workbook,'School by Grade'):
                if row['School Entity ID']=='Arizona':continue
                key=sid(row)
                if key in profiles or row['Fiscal Year']!=YEAR:raise ValueError('Duplicate Arizona grade profile or wrong year')
                profiles[key]=dict(school_id=key,source_row=index,raw=row)
            for index,row in rows(workbook,'School by Subgroup'):
                if row['School Entity ID']=='Arizona' or row['Subgroup'] not in ['All Students','Income Eligibility 1 or 2']:continue
                key=sid(row);field='all_students' if row['Subgroup']=='All Students' else 'income'
                if key not in profiles or field in profiles[key] or row['Fiscal Year']!=YEAR:raise ValueError('Arizona enrollment subgroup lacks a unique same-year profile')
                profiles[key][field]=dict(source_row=index,raw=row)
        else:
            # Stream the large native School sheet, retaining selected all-student
            # rows before any population decisions. Never load all 701k rows.
            native_rows=[]
            for index,row in rows(workbook,'School'):
                if row['Subgroup']=='All Students' and row['FAY Status']=='All' and row['Subject'] in ['Mathematics','English Language Arts'] and row['Test Level'] in ['All Assessments','ELA Grade 11','Math Grade 11']:
                    native_rows.append(dict(school_id=sid(row),source_row=index,raw=row))
        workbook.close()
    if 'Valid test results were included' not in json.dumps(metadata['assessments']['Introduction']):raise ValueError('Arizona valid-results population definition changed')
    payload=dict(schema_version=1,state='AZ',year=YEAR,academic_year='2024-2025',retrieved=datetime.now(timezone.utc).isoformat(),
        sources=sources,metadata=metadata,profiles=list(profiles.values()),assessments=native_rows)
    Path(destination).write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n');return payload


def import_data(db,payload):
    if (payload['schema_version'],payload['state'],payload['year'],payload['academic_year'])!=(1,'AZ',YEAR,'2024-2025'):raise ValueError('Unexpected Arizona school year or identity')
    if 'Valid test results were included' not in json.dumps(payload['metadata']['assessments']['Introduction']):raise ValueError('Arizona valid-results source definition is missing')
    profiles={}
    for entry in payload['profiles']:
        key,row=entry['school_id'],entry['raw']
        if key!=sid(row) or key in profiles or row['Fiscal Year']!=YEAR:raise ValueError('Invalid or duplicate Arizona profile')
        level_for(entry)
        for field,group in [('all_students','All Students'),('income','Income Eligibility 1 or 2')]:
            if field in entry:
                native=entry[field]['raw']
                if key!=sid(native) or native['Fiscal Year']!=YEAR or native['Subgroup']!=group or native['LEA Entity ID']!=row['LEA Entity ID']:raise ValueError('Arizona income must join the native same-year school ID')
        income_values(entry);profiles[key]=entry
    seen,observations,ignored=set(),[],Counter()
    for entry in payload['assessments']:
        key,row=entry['school_id'],entry['raw']
        subject='math' if row['Subject']=='Mathematics' else 'reading'
        if (key!=sid(row) or row['FiscalYear']!=YEAR or row['Subgroup']!='All Students' or row['FAY Status']!='All'
                or row['Subject'] not in ['Mathematics','English Language Arts'] or row['Test Level'] not in ['All Assessments','ELA Grade 11','Math Grade 11']):raise ValueError('Arizona assessment population changed')
        identity=(key,row['Test Level'],subject)
        if identity in seen:raise ValueError('Duplicate Arizona school/test/subject')
        seen.add(identity)
        if key not in profiles:ignored['Assessment without same-year native enrollment']+=1;continue
        if row['District Entity ID']!=profiles[key]['raw']['LEA Entity ID']:ignored['Assessment and enrollment native district IDs differ']+=1;continue
        level=level_for(profiles[key])
        expected='All Assessments' if level=='ES' else 'Math Grade 11' if subject=='math' else 'ELA Grade 11'
        if level is None or row['Test Level']!=expected:ignored['Mixed schoolwide totals or non-applicable grade population']+=1;continue
        pct,n,reason=assessment_values(row)
        observations.append(dict(entry,year=YEAR,level=level,subject=subject,assessment=ASSESSMENTS[level],proficiency=pct,tested=n,exclusion=reason))
    for table in ['model_run','assessment_observation','economic_observation','school','source']:db.execute(f'DELETE FROM {table} WHERE dataset_id=?',(DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?',(DATASET+':%',))
    db.execute('INSERT OR REPLACE INTO dataset VALUES (?,?,?,?,?)',(DATASET,'AZ','Arizona ADE 2024–25 native results','Separate native grade-school AASA/MSAA and regular grade-11 ACT populations','ready'))
    sources=dict(payload['sources']);sources['az-extract-2025']=dict(path=str(EXTRACT.relative_to(ROOT)),url=PAGE,sha256=digest(EXTRACT))
    for ident,source in sources.items():
        if not re.fullmatch('[0-9a-f]{64}',source['sha256']):raise ValueError('Invalid Arizona source checksum')
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',(ident,DATASET,source['path'],source['url'],source['sha256'],payload['retrieved']))
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',('az-income-2025','Arizona individually enrolled income eligibility 1 or 2',ECON_DEFINITION,INCOME_GUIDANCE))
    for level,name in ASSESSMENTS.items():
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',(definition_id(DATASET,YEAR,name,level),'AZ',name,YEAR,level,'3–8' if level=='ES' else '11',
            'Native All Students, FAY Status All; valid Spring 2025 test results, highest repeated score; published integer Percent Passing (levels 3+4), largest-remainder rounding. '+
            ('Native All Assessments includes AASA and MSAA; restricted to schools without enrolled grades 9–12. Alternate standards included in the published total.' if level=='ES' else 'Separate regular ACT grade 11; MSAA and mixed all-assessment school totals excluded. Some valid-score counts are suppressed, so every high-school sampling interval is unavailable.'),PAGE))
    for key,entry in profiles.items():
        row=entry['raw']
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',(DATASET,key,row['School Name'],str(row['LEA Entity ID']),row['LEA Name'],None,None,json.dumps(entry),'az-enrollment-2025',entry['source_row']))
        total,low,pct=income_values(entry)
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(DATASET,key,YEAR,'az-income-2025',row['School Name'],total,low,pct,'October1 individual income eligibility; all enrolled grades',json.dumps(entry),'az-enrollment-2025',entry.get('income',{}).get('source_row',entry['source_row'])))
    for entry in observations:
        db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',(DATASET,entry['school_id'],definition_id(DATASET,YEAR,entry['assessment'],entry['level']),entry['subject'],entry['proficiency'],entry['tested'],
            'reported' if entry['proficiency'] is not None else 'suppressed_or_not_reported',json.dumps(entry['raw']),str(entry['raw']['Number Tested']),'az-assessment-2025',entry['source_row']))
    return profiles,observations,dict(ignored)


def prepare(database=DEFAULT_DB,output=OUTPUT):
    payload=json.loads(EXTRACT.read_text())
    with connect(database) as db:
        profiles,raw_observations,ignored=import_data(db,payload)
        observations=pl.DataFrame([{k:r[k] for k in ['school_id','year','level','assessment','subject','proficiency','tested']} for r in raw_observations],infer_schema_length=None)
        incomes=pl.DataFrame([dict(r) for r in db.execute('SELECT school_id,year,name,enrollment,low_income,percentage FROM economic_observation WHERE dataset_id=?',(DATASET,))],infer_schema_length=None)
        records,models=build_history(observations,incomes,point_only_assessments=list(ASSESSMENTS.values()))
        if len(models)!=6:raise ValueError('Arizona lacks an eligible native assessment model')
        save_models(db,records,models,DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Arizona foreign key check failed')
    by_key={(r['school_id'],r['level']):r for r in records}
    for raw in raw_observations:
        if raw['exclusion']:by_key[(raw['school_id'],raw['level'])]['exclusions'][raw['subject']]=raw['exclusion']
    schools=[]
    for key,entry in profiles.items():
        level=level_for(entry)
        if level is None:continue
        row=entry['raw'];total,_,income=income_values(entry);annual=by_key.get((key,level))
        schools.append(dict(id=key,name=row['School Name'],short=row['School Name'],level=level,program='Unclassified',district=row['LEA Name'],city=None,county=None,income=income,enrollment=total,
            latitude=None,longitude=None,metrics=annual['subjects'] if annual else {},history=[annual] if annual else [],exclusions=annual['exclusions'] if annual else {s:'No applicable native assessment' for s in ['math','reading','combined']}))
    details=[
        'The official Spring 2025 workbook includes valid test results and retains the highest score for repeated tests. All Students and FAY Status All are used; FAY-only and non-FAY subsets are excluded. Results belong to the school where the test was administered, while income belongs to the enrolled school, a population limitation.',
        'Grade schools use directly published All Assessments totals only where October 2024 membership has no grades 9–12, limiting the native cohort to AASA/MSAA grades 3–8. MSAA alternate achievement standards are included in the native total. High and mixed-grade schools use separate regular ACT grade 11 only, excluding MSAA and their mixed All Assessments totals. No grade percentages are averaged.',
        'Percent Passing is the native percentage at proficiency levels 3 or 4. ADE uses largest-remainder rounding for performance bands and publishes integer percentages. Bounds and suppression are unavailable; zero, midpoint and suppressed complements are never inferred. Verified Number Tested values belong to valid test results, not enrollment or expected participation.',
        ECON_DEFINITION,
        'Income uses only published same-table All Students and Income Eligibility 1 or 2 enrollment counts. Missing or suppressed individual counts are not reconstructed from other subgroups. Enrollment includes all enrolled grades, including preschool where present; its grade mix differs from the assessment population.',
        'All grade-school model members have valid-score denominators, so their intervals propagate every member\'s sampling uncertainty. Some high-school members have published proficiency but suppressed tested counts. Every high-school model interval is omitted; other schools\' counts cannot replace those missing denominators.',
        'Joins use authoritative ADE School Entity ID and same-year native LEA Entity ID. Cross-district mismatches and assessments without October membership are excluded. This release has one year, no admissions classifications and no audited school coordinates.',
    ]
    levels={level:dict(year=YEAR,label='Grade schools · AASA/MSAA' if level=='ES' else 'High schools · ACT',assessment=name,outcome='Proficient or Highly Proficient',math_label='Math',
        note='Native AASA/MSAA grades 3–8 totals' if level=='ES' else 'Separate regular ACT grade 11; sampling intervals unavailable') for level,name in ASSESSMENTS.items()}
    methodology=dict(summary='Arizona 2024–25 native AASA/MSAA grade-school totals and separate ACT grade 11, with same-year individually enrolled income eligibility.',details=details,
        sources=[dict(label='ADE native assessment and enrollment workbooks',url=PAGE),dict(label='October 2024 AzEDS individual eligibility guidance, including CEP',url=INCOME_GUIDANCE),
                 dict(label='FY2025 alternative household income eligibility form',url='https://www.azed.gov/sites/default/files/2024/07/2025-%20Alternative%20Form%20for%20Income-Based%20Eligibility.pdf'),
                 dict(label='AASA and Arizona assessment standards',url='https://www.azed.gov/assessment/aasa')])
    result=dict(year='2024–25',assessment_year=YEAR,income_label='Income Eligibility 1 or 2',levels=levels,program_options=['Unclassified'],schools=sorted(schools,key=lambda s:s['id']),
        models={level:{subject:next(m for m in models if m['level']==level and m['subject']==subject) for subject in ['math','reading','combined']} for level in levels},history_years=[YEAR],history_models=models,coverage_note=' '.join(details),methodology=methodology)
    audit=dict(year=YEAR,directory_schools=len(schools),native_grade_profiles=len(profiles),ignored_sources=ignored,eligible_models=[{k:m[k] for k in ['level','subject','n','excluded_schools']} for m in models],
        exclusions=dict(Counter(reason for r in records for reason in r['exclusions'].values())),valid_score_counts='Native valid-result Number Tested; high-school missing counts omit intervals for all model members',map_coordinates=0,
        joins='Authoritative native ADE School Entity ID + same-year LEA Entity ID; 2024–25 only')
    catalog=dict(schema_version=1,prepare_script='scripts/prepare_arizona.py',state=dict(id='AZ',name='Arizona'),regions=[dict(id='arizona',name='Statewide',dataset=DATASET,status='ready',geography='arizona',levels=['ES','HS'],
        schools='data/arizona/schools.json',boundaries=None,map_source='School locations are unavailable in the audited native workbooks.',comparison='Comparison population: Arizona statewide · {year} {note}. Separate AASA/MSAA and ACT cohorts.',
        model_scope='Native grade-school totals including MSAA alternate standards, and separate regular ACT grade 11 in high and mixed-grade schools',audit='data/arizona/audit.json')])
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for filename,value in [('schools.json',result),('history.json',dict(records=records,models=models)),('audit.json',audit),('catalog.json',catalog)]:
        (output/filename).write_text(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps(audit,indent=2));return result,audit


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract',action='store_true');parser.add_argument('--raw',type=Path,default=RAW);parser.add_argument('--database',type=Path,default=DEFAULT_DB);parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    if args.extract:extract(args.raw)
    prepare(args.database,args.output)
