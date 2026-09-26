"""Verified, multi-label NYC school types from public MySchools and LCGMS.

--download refreshes public directory pages; --extract creates the compact source.
Normal site rebuilds only read the committed source via classifications().
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import re
import subprocess

from database import ROOT

RAW = ROOT/'data/raw/nyc-types'
SOURCE = ROOT/'data/source/nyc-types.json'
PROCESSES = {'high-school':1, 'kindergarten':4, 'middle-school':6, 'gt-app':8}
TYPES = ['Zoned', 'Unzoned / Open', 'Gifted & Talented', 'Screened',
         'Specialized High School', 'Audition / Arts', 'Charter', 'Other / Special program', 'Unclassified']
METHODS = {
    'Zoned':'Zoned', 'Zone Priority':'Zoned', 'Zoned Priority':'Zoned', 'Zoned Guarantee':'Zoned',
    'Non-Zoned':'Unzoned / Open', 'Open':'Unzoned / Open',
    'District G&T':'Gifted & Talented', 'Citywide G&T':'Gifted & Talented',
    'Screened':'Screened', 'Screened With Assessment':'Screened',
    'Screened: Language & Academics':'Screened',
    'Audition':'Audition / Arts',
    'Ed. Opt.':'Other / Special program', 'Educational Option':'Other / Special program',
    'Language Criteria':'Other / Special program', 'Screened: Language':'Other / Special program',
    'D75 Special Education Inclusive Services':'Other / Special program',
    'ASD/ACES Program':'Other / Special program', 'Transfer':'Other / Special program',
    'Talent Test':'Other / Special program',
}


def endpoint(process, page):
    return f'https://www.myschools.nyc/en/api/v2/schools/process/{PROCESSES[process]}/?page={page}'


def download():
    RAW.mkdir(exist_ok=True)
    def fetch(task):
        process, page = task
        subprocess.run(['curl','--retry','2','--max-time','60','-fsSL',endpoint(process,page),
                        '-o',str(RAW/f'{process}-{page}.json')], check=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, [(p,1) for p in PROCESSES]))
        rest = []
        for p in PROCESSES:
            first = json.loads((RAW/f'{p}-1.json').read_text())
            rest.extend((p,n) for n in range(2, math.ceil(first['count']/len(first['results']))+1))
        list(pool.map(fetch, rest))


def extract():
    pages, schools = [], []
    for process in PROCESSES:
        first = json.loads((RAW/f'{process}-1.json').read_text())
        total = first['count']; size = len(first['results']); records = []
        for page in range(1, math.ceil(total/size)+1):
            path = RAW/f'{process}-{page}.json'
            raw = path.read_bytes(); payload = json.loads(raw)
            if payload['count'] != total:
                raise ValueError('Directory changed during pagination; download again')
            pages.append(dict(url=endpoint(process,page), sha256=hashlib.sha256(raw).hexdigest()))
            records.extend(payload['results'])
        if len(records) != total or len({r['id'] for r in records}) != total:
            raise ValueError('Incomplete or duplicate directory pages')
        for r in records:
            s = r['school']
            if not re.fullmatch(r'\d{2}[MKQRX]\d{3}',s['dbn']):
                raise ValueError('Invalid DBN')
            programs = []
            for p in r['programs']:
                method = (p.get('admissions_method') or {}).get('name')
                programs.append(dict(id=p['id'], code=p['program']['code'], name=p['name'],
                    method=method, is_shs=p['program'].get('is_shs',False),
                    is_lg=p['program'].get('is_lg',False), is_gt=p['program'].get('is_gt',False)))
            schools.append(dict(dbn=s['dbn'], name=s['name'], school_year=s['school_year'],
                process=process, school_type=(s['school_type'] or {}).get('name'), programs=programs))
    expansion = json.loads((ROOT/'data/source/nyc-expansion.json').read_text())
    charters = sorted({r['ATS System Code'] for r in expansion['crosswalk'] if r['Managed By Name']=='Charter'})
    output = dict(retrieved='2026-09-26', pages=pages, schools=schools, charter_dbns=charters,
        charter_source=expansion['sources']['crosswalk'],
        note='Public MySchools school records label their vintage 2025–26. Retrieved September 26, 2026. Methods describe programs, not every student or historical cohort. The 2021 directory is not used.')
    classifications(output)  # Reject unrecognized source methods before writing.
    SOURCE.write_text(json.dumps(output,separators=(',',':'),allow_nan=False))


def program_types(p):
    labels = set()
    if p['is_shs'] or p['is_lg']:
        labels.add('Specialized High School')
    if p['is_lg']:
        labels.add('Audition / Arts')
    if p['is_gt']:
        labels.add('Gifted & Talented')
    method = p['method']
    if method in METHODS:
        labels.add(METHODS[method])
    elif method == 'Test' and p['is_shs']:
        pass
    elif method:
        raise ValueError(f'Unmapped MySchools method: {method!r}')
    return labels


def classifications(payload=None):
    payload = payload or json.loads(SOURCE.read_text())
    labels, evidence = defaultdict(set), defaultdict(list)
    for school in payload['schools']:
        sid = school['dbn']
        for p in school['programs']:
            tags = program_types(p)
            labels[sid].update(tags)
            if tags:
                evidence[sid].append(dict(code=p['code'], name=p['name'], method=p['method'],
                    types=sorted(tags), school_year=school['school_year'], process=school['process'],
                    url=f"https://www.myschools.nyc/en/schools/{school['process']}/{sid}/"))
    for sid in payload['charter_dbns']:
        labels[sid].add('Charter')
        evidence[sid].append(dict(types=['Charter'], school_year='Current LCGMS, retrieved 2026-09-26',
                                 url=payload['charter_source']['url']))
    return {sid:dict(types=[t for t in TYPES if t in tags], evidence=evidence[sid]) for sid,tags in labels.items() if tags}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--extract',action='store_true')
    args=parser.parse_args()
    if args.download:
        download()
    if args.extract:
        extract()
    if SOURCE.exists():
        result=classifications()
        print(json.dumps({t:sum(t in r['types'] for r in result.values()) for t in TYPES},indent=2))
