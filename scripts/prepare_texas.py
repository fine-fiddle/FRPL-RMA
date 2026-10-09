"""Texas 2024–25 native TAPR grades 3–8 snapshot. Offline rebuild by default."""
import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

DATASET = 'tx-tapr-2025'
YEAR = 2025
EXTRACT = ROOT/'data/source/texas.json'
OUTPUT = ROOT/'data/texas'
PORTAL = 'https://rptsvr1.tea.texas.gov/perfreport/tapr/2025/index.html'
GLOSSARY = 'https://tea.texas.gov/school-and-district-leaders/accountability/academic-accountability/performance-reporting/2024-25-comprehensive-tapr-glossary-0.pdf'
INCOME_GUIDE = 'https://www.texasstudentdatasystem.org/sites/texasstudentdatasystem.org/files/TEDS_Data_Submission_Requirements_Student_Identification_and_Demographics_Domain.pdf'
MASKING = 'https://rptsvr1.tea.texas.gov/perfreport/tapr/2025/masking.html'
GRADES = ['CPNTGEEC','CPNTGPKC','CPNTGKNC']+[f'CPNTG{g:02}C' for g in range(1,13)]
FIELDS = {s: [f'CDA38A{letter}0E025D',f'CDA38A{letter}0E225N',f'CDA38A{letter}0E225R'] for s,letter in [('math','M'),('reading','R')]}
KEYS = {
    'ref':['GRDSPAN','GRDTYPE','COUNTY|CNTYNAME','CFLALTED'],
    'stud':['ETALL|NTALL','NTECO|NTNED|NT504|NTLEP|NTDSL|NTFOS|NTHOM|NTIMM|NTMIG|NTTT1|NTMLC|NTRSK|NTBIL',
            'ETECO|ETNED|ET504|ETLEP|ETDIS|ETDSL|ETFOS|ETHOM|ETIMM|ETMIG|ETTT1|ETMLC|ETRSK',
            'NTGEEC|NTGEEP|NTGPKC|NTGPKP|NTGP3C|NTGP3P|NTGP4C|NTGP4P|NTGKNC|NTGKNP|NTG01C|NTG01P|NTG02C|NTG02P|NTG03C|NTG03P|NTG04C|NTG04P|NTG05C|NTG05P|NTG06C|NTG06P|NTG07C|NTG07P|NTG08C|NTG08P|NTG09C|NTG09P|NTG10C|NTG10P|NTG11C|NTG11P|NTG12C|NTG12P'],
    'assessment':['38AR0E2|38AR0E0','38AM0E2|38AM0E0'],
}


def download_url(kind):
    p=dict(_service='marykay',_program='perfrept.perfmast.sas',_debug='0',ccyy='2025',tapr='all_c',sumlev='C',
           level='Campus',id='',prgopt='reports/tapr/dd/dd_tapr_step_7.sas',datafmt='csv',
           dsname='STAAR_GR38' if kind=='assessment' else kind.upper(),key=KEYS[kind])
    if kind!='ref':p['var_type']=['N','D','R']
    return 'https://rptsvr1.tea.texas.gov/cgi/sas/broker/?'+urlencode(p,doseq=True)


DICT_URL = 'https://rptsvr1.tea.texas.gov/cgi/sas/broker?'+urlencode(dict(_service='marykay',_program='perfrept.perfmast.sas',
    _debug='0',ccyy='2025',sumlev='C',dsname='STAAR_GR38',dd='performance',asvab='',prgopt='reports/tapr/dd/dd_tapr_dictionary.sas'))
FILES = {**{k:(f'tx_{k}_2025.csv',download_url(k)) for k in KEYS},
         'glossary':('tx_glossary_2025.pdf',GLOSSARY),'income-guide':('tx_income_reporting_2025.pdf',INCOME_GUIDE),
         'masking':('tx_masking_2025.html',MASKING),'dictionary':('tx_dictionary_2025.html',DICT_URL)}
ECON = ('Texas 2024–25 October 25 PEIMS Fall enrollment: individual free/reduced-price meal eligibility or other economic '
        'disadvantage (codes 01,02,99), divided by all enrolled students, early childhood through grade 12. '
        'TEDS requires individual direct certification and annual local income surveys at CEP schools; '
        'Provision 2 retains base-year eligibility for continuously enrolled students and surveys new/returning students. '
        'This is current-year reported administrative status, whose Provision 2 eligibility can lag current family income. '
        'Universal meals do not make all children disadvantaged. Missing surveys can be coded 00; undercount is unknown. '
        'This state-specific proxy includes other public assistance and is not uniform FRPL or direct income.')
STANDARD = ('2025 native TAPR enrolled-grades 3–8 Reading Including EOC and Math Including EOC, All Students, '
        'At Meets Grade Level or Above. Accountability subset: same campus on fall snapshot and testing date, including '
        'STAAR with/without accommodations, Spanish STAAR and STAAR Alternate 2; subject totals include corresponding '
        'English I/II or Algebra I EOC for students enrolled in grades 3–8. Uses exact unsuppressed numerator/denominator '
        'only when the published rate is also unmasked. This is not the separate participation denominator or the '
        'percentage passing both subjects. Grade schools enroll no grades 9–12 in the same-year fall registry.')


def number(value):
    if value in (None,'','•','*','**'):return None
    value=float(value)
    if value in (-1,-2,-3):return None
    if not 0<=value or value==float('inf'):raise ValueError('Invalid Texas number')
    return value


def count(value):
    value=number(value)
    if value is not None and value!=int(value):raise ValueError('Non-integral Texas count')
    return None if value is None else int(value)


def sid(row):
    key=row['CAMPUS']
    if not isinstance(key,str) or not re.fullmatch(r'\d{9}',key) or row['DISTRICT']!=key[:6]:
        raise ValueError('Texas needs exact nine-digit CAMPUS and corresponding district')
    return key


def income(row):
    total,low,other=[count(row[k]) for k in ['CPNTALLC','CPNTECOC','CPNTNEDC']]
    pct=number(row['CPNTECOP'])
    if None in (total,low,other,pct) or total==0:return total,None,None
    if low+other!=total or not 0<=pct<=100 or abs(100*low/total-pct)>.050001:
        raise ValueError('Texas same-year individual income does not reconcile')
    return total,low,100*low/total


def grade_school(row):
    values=[count(row[k]) for k in GRADES]
    if None in values or sum(values)!=count(row['CPNTALLC']):raise ValueError('Texas enrolled grade registry is incomplete')
    return not any(values[-4:])


def outcome(raw):
    tested,passed=count(raw[0]),count(raw[1]);pct=number(raw[2])
    if None in (tested,passed,pct):
        return None,None,'TAPR native school-total result missing or masked; suppression is preserved'
    if tested<5 or passed>tested or not 0<=pct<=100 or abs(100*passed/tested-pct)>.500001:
        raise ValueError('TAPR valid-score counts do not reconcile with unmasked rate')
    return 100*passed/tested,tested,None


def csv_file(filename,required):
    with (ROOT/'data/raw'/filename).open(newline='',encoding='utf-8-sig') as f:
        it=csv.reader(f);labels=next(it);codes=next(it)
        if len(set(codes))!=len(codes) or not set(required)<=set(codes):raise ValueError('Texas download schema changed')
        if any('2024' in labels[codes.index(k)] and '2024-25' not in labels[codes.index(k)] for k in required if k not in ['CAMPUS','DISTRICT']):
            raise ValueError('Unexpected historical Texas column')
        if any('2025' not in labels[codes.index(k)] for k in required if k.startswith(('CPNT','CDA'))):
            raise ValueError('Texas download is not the required same-year snapshot')
        rows={}
        for i,values in enumerate(it,3):
            row=dict(zip(codes,values));key=sid(row)
            if key in rows or len(values)!=len(codes):raise ValueError('Duplicate/malformed Texas CSV school')
            rows[key]=(i,row)
    return rows,dict(zip(codes,labels))


def extract():
    profiles,labels=csv_file(FILES['stud'][0],['CAMPUS','DISTRICT','CPNTALLC','CPNTECOC','CPNTECOP','CPNTNEDC']+GRADES)
    refs,_=csv_file(FILES['ref'][0],['CAMPUS','DISTRICT','GRDTYPE','GRDSPAN','COUNTY','CNTYNAME'])
    results,assessment_labels=csv_file(FILES['assessment'][0],['CAMPUS','DISTRICT']+sum(FIELDS.values(),[]))
    if profiles.keys()!=refs.keys() or profiles.keys()!=results.keys():raise ValueError('Texas sources lack matching same-year authoritative campus IDs')
    raw=[]
    for key,(i,row) in profiles.items():
        raw.append(dict(id=key,profile={k:row[k] for k in ['CAMPUS','CAMPNAME','DISTRICT','DISTNAME','CPNTALLC','CPNTECOC','CPNTECOP','CPNTNEDC']+GRADES},
            profile_row=i,reference=refs[key][1],reference_row=refs[key][0],outcomes={s:[results[key][1][k] for k in fields] for s,fields in FIELDS.items()},assessment_row=results[key][0]))
    sources={k:dict(path='data/raw/'+fn,url=url,sha256=hashlib.sha256((ROOT/'data/raw'/fn).read_bytes()).hexdigest()) for k,(fn,url) in FILES.items()}
    payload=dict(state='TX',year=YEAR,academic_year='2024-25',retrieved=str(date.today()),sources=sources,
        columns=dict(profile={k:labels[k] for k in raw[0]['profile']},assessment={k:assessment_labels[k] for k in sum(FIELDS.values(),[])}),profiles=raw)
    EXTRACT.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n')
    return payload


def normalize(payload):
    if (payload['state'],payload['year'],payload['academic_year'])!=('TX',YEAR,'2024-25'):raise ValueError('Wrong Texas source year/state')
    schools=[];seen=set();excluded=Counter()
    for p in payload['profiles']:
        r=p['profile'];key=sid(r)
        if key!=p['id'] or key!=sid(p['reference']) or key in seen:raise ValueError('Wrong or duplicate Texas school identity')
        seen.add(key);total,low,pct=income(r)
        if not grade_school(r):excluded['High/mixed grade campus enrolling grades 9–12']+=1;continue
        outcomes={}
        for s in ['math','reading']:
            rate,tested,reason=outcome(p['outcomes'][s])
            outcomes[s]=dict(proficiency=rate,tested=tested,raw=p['outcomes'][s],raw_tested=p['outcomes'][s][0],
                valid_score_evidence='Native TAPR performance numerator and # of Tests denominator, not participation; source glossary pp2–3.',
                source='assessment',source_row=p['assessment_row'],exclusion=reason)
        schools.append(dict(id=key,name=r['CAMPNAME'],district_id=r['DISTRICT'],district=r['DISTNAME'],county=p['reference']['CNTYNAME'],cohort='grade-schools',
            income=pct,enrollment=total,low_income=low,income_raw=p,income_source='stud',income_row=p['profile_row'],outcomes=outcomes))
    assessment='STAAR + Alternate 2 grades 3–8 including EOC · grade schools'
    scope='Texas public grade schools; native TAPR accountability-subset subject totals for enrolled grades 3–8'
    return dict(dataset=DATASET,state=dict(id='TX',name='Texas'),year=YEAR,academic_year='2024–25',name='Texas TAPR 2024–25',model_scope=scope,
        region='texas',prepare_script='scripts/prepare_texas.py',source_url=PORTAL,retrieved=payload['retrieved'],sources=payload['sources'],schools=schools,
        income_definition=dict(label='Individual reported economic disadvantage',definition=ECON,url=INCOME_GUIDE),
        cohorts=[dict(id='grade-schools',level='ES',assessment=assessment,grades='3–8 including corresponding EOC',standard=STANDARD,
            source_url=FILES['assessment'][1],source='assessment',label='Grade schools · STAAR',outcome='Meets Grade Level or Above',note='Native grades 3–8 totals · accountability subset')],
        coverage_note=STANDARD+' '+ECON+' One year only; school coordinates unavailable.',
        methodology=dict(summary='Texas grade-school models use native TAPR enrolled-grades 3–8 subject counts and individual same-year October economic status.',
            details=[ECON,STANDARD,'Combined is the equally weighted mean of Math and ELA proficiency, not the source measure passing both. Exact unsuppressed count ratios replace display rounding. Externally studentized residuals fit separate full statewide subject populations; associations do not estimate causal school effectiveness or overall quality.',
                'All eligible records have verified score denominators, so sampling intervals use every model member. No suppression is reconstructed. Grade membership and income use fall enrollment, including early childhood/pre-K; missing locations do not alter eligibility. No authoritative coordinate crosswalk has been imported.'],
            sources=[dict(label='TAPR 2025 data and downloads',url=PORTAL),dict(label='2024–25 TEDS individual economic eligibility',url=INCOME_GUIDE),dict(label='TAPR 2025 assessment and enrollment definitions',url=GLOSSARY),dict(label='TAPR 2025 masking rules',url=MASKING)]),
        source_audit=dict(public_campuses=len(seen),grade_school_profiles=len(schools),excluded=dict(excluded),mapped=0))


def prepare(database=DEFAULT_DB):
    result=prepare_snapshot(normalize(json.loads(EXTRACT.read_text())),EXTRACT,OUTPUT,database)
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--extract',action='store_true');parser.add_argument('--download',action='store_true')
    parser.add_argument('--database',type=Path,default=DEFAULT_DB);args=parser.parse_args()
    if args.download:
        for filename,url in FILES.values():
            (ROOT/'data/raw'/filename).write_bytes(urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=60).read())
    if args.extract or args.download:extract()
    prepare(args.database)
