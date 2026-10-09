"""Utah 2024–25 published RISE/Aspire totals and individual NSLP eligibility outside CEP/Provision 2."""
import argparse
import hashlib
import html
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import openpyxl
import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET = 'ut-usbe-2025'
RELEASE_STATUS = 'audit_pending'
YEAR = 2025
RAW = ROOT/'data/raw/utah'
EXTRACT = ROOT/'data/source/utah.json'
OUTPUT = ROOT/'data/utah'
REPORTS = 'https://schools.utah.gov/datastatistics/reports'
DIRECTORY = 'https://www.schools.utah.gov/schoolsdirectory'
REPORTCARD = 'https://reportcard.schools.utah.gov/'
BASE = 'https://schools.utah.gov/datastatistics/_datastatisticsfiles_/_reports_/'
FILES = {
    'ut-rates-2025': ('rates.xlsx', BASE+'_assessments_/RISEAspireProficiencyRates2025.xlsx'),
    'ut-lunch-2025': ('meal-survey.xlsx', BASE+'_cnpnslp_/CNP%20October%20Survey%202024.xlsx'),
    'ut-provisions-2025': ('CEP2025Provision.xlsx', BASE+'_cnpnslp_/CEP2025Provision.xlsx'),
    'ut-cactus-directory': ('cactus-schools.json', 'https://cactus.schools.utah.gov/api/legacy/schools?overrideCache=true'),
    'ut-reportcard-2025': ('reportcard.html', REPORTCARD),
}
ASSESSMENTS = {'ES': 'RISE grades 3–8 · native published 2025',
               'HS': 'Utah Aspire Plus grades 9–10 · native published 2025'}
TYPES = {'RISE (Grades 3-8)': 'ES', 'Utah Aspire Plus (Grades 9-10)': 'HS'}
ECON_DEFINITION = ('Same-year October 31, 2024 NSLP site free and reduced-price individual meal eligibility. '
    'CEP and Provision 2 sites, whose survey rates can be formula or base-year claiming percentages, '
    'are excluded using both native survey flags and the complete SY2025 program roster. '
    'Only uniquely matched public-school sites with authoritative USBE school identifiers are eligible.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def integer(raw):
    if isinstance(raw, bool) or raw is None:
        raise ValueError('Utah identifier must be an exact nonnegative integer')
    text = str(raw)
    if not text.isdigit():
        if not isinstance(raw, (int, float)) or not math.isfinite(raw) or raw != int(raw):
            raise ValueError('Utah identifier must be an exact nonnegative integer')
    value = int(raw)
    if value < 0:
        raise ValueError('Negative Utah identifier')
    return str(value)


def sid(row):
    district = row.get('District ID', row.get('DistrictID'))
    number = row.get('SchoolNumber', row.get('SchoolNbr'))
    return integer(district)+'-'+integer(number)


def site_code(raw):
    # Excel has corrupted several charter codes such as 3E-100 into numeric
    # scientific notation. Those are unavailable IDs; never reconstruct them.
    if not isinstance(raw, str):
        return None
    match = re.fullmatch(r'([A-Z0-9]+)-(\d+)', raw.strip())
    return (match[1].lstrip('0') or '0', integer(match[2])) if match else None


def fraction(raw):
    if raw is None or isinstance(raw, str):
        return None
    value = float(raw)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Invalid Utah published fraction')
    return value


def assessment_values(row):
    value = fraction(row['Percent Proficient'])
    return (100*value, None, None) if value is not None else (None, None, 'Missing or suppressed native proficiency')


def income_values(entry):
    row = entry['raw']
    enrolled = row['Enrollment']
    total = int(enrolled) if isinstance(enrolled, (int, float)) and enrolled == int(enrolled) and enrolled > 0 else None
    free, reduced, combined = [fraction(row[k]) for k in ['Free %', 'Reduced %', 'Free and Reduced %']]
    if free is not None and reduced is not None and combined is not None and abs(free+reduced-combined) > .000151:
        raise ValueError('Utah free and reduced fractions fail source rounding reconciliation')
    return total, None, 100*combined if total and combined is not None and not entry['exclusion'] else None


def income_exclusion(row, code, program_codes, ambiguous_unit):
    if '*' in row['Site Name'] or code in program_codes:
        return 'CEP or Provision 2 claiming/base-year percentage'
    if ambiguous_unit:
        return 'Native SchoolID represents multiple school-number units; NSLP site scope unavailable'
    return None


def workbook_rows(path, sheet=None):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list((workbook[sheet] if sheet else workbook.active).values)
    workbook.close()
    return [(i, dict(zip(rows[0], row))) for i, row in enumerate(rows[1:], 2)]


def extract(raw=RAW, destination=EXTRACT):
    raw = Path(raw)
    sources = {key: dict(path=str((raw/name).relative_to(ROOT)) if (raw/name).is_relative_to(ROOT) else str(raw/name),
                        url=url, sha256=digest(raw/name)) for key, (name, url) in FILES.items()}
    cactus = json.loads((raw/'cactus-schools.json').read_text())['schools']
    crosswalk = defaultdict(list)
    for row in cactus:
        if row['isPrivate']:
            continue
        crosswalk[(integer(row['schoolId']), integer(row['districtId']), integer(row['schoolNumber']))].append(row)
    profiles, unmatched = {}, []
    for attributes, text in re.findall(r'<option\b([^>]*)>(.*?)</option>', (raw/'reportcard.html').read_text(), re.S):
        value = re.search(r'value="([^"]+)"', attributes)
        if not value or 'SchoolID=' not in value[1]:
            continue
        query = {key: values[0] for key, values in parse_qs(urlparse(html.unescape(value[1])).query).items()}
        if query['schoolyearendyear'] != str(YEAR):
            raise ValueError('Utah reportcard school inventory year changed')
        key = sid(query)
        identity = tuple(integer(query[k]) for k in ['SchoolID', 'DistrictID', 'SchoolNbr'])
        matches = crosswalk[identity]
        if len(matches) != 1:
            unmatched.append(dict(school_id=key, raw=query, name=html.unescape(text).strip()))
            continue
        if key in profiles:
            raise ValueError('Duplicate Utah reportcard district/school number')
        profiles[key] = dict(school_id=key, source_row=len(profiles)+1,
            raw=dict(query, name=html.unescape(text).strip()), cactus=matches[0])
    sites = defaultdict(list)
    for key, entry in profiles.items():
        row = entry['cactus']
        sites[(str(row['districtNumber']).lstrip('0') or '0', integer(row['schoolNumber']))].append(key)
    native_units = Counter(integer(e['raw']['SchoolID']) for e in profiles.values())
    programs = []
    for index, row in workbook_rows(raw/'CEP2025Provision.xlsx', 'Data1117 SY25 CEP Provision'):
        if row['Provision Type'] not in ['CEP', 'Provision 2']:
            continue
        row = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in row.items()}
        programs.append(dict(source_row=index, raw=row))
    blocked = {(str(p['raw']['Sponsor Number']).strip().lstrip('0') or '0', integer(p['raw']['Site Number'])) for p in programs}
    incomes, omitted = [], []
    for index, row in workbook_rows(raw/'meal-survey.xlsx'):
        if row['Site Number'] is None:
            continue
        code = site_code(row['Site Number'])
        candidates = sites.get(code, [])
        if len(candidates) != 1:
            omitted.append(dict(source_row=index, raw=row, reason='Unmatched or ambiguous native school site code'))
            continue
        if code[0] != (str(row['Sponsor Number']).strip().lstrip('0') or '0'):
            raise ValueError('Utah survey sponsor and native site code disagree')
        exclusion = income_exclusion(row, code, blocked, native_units[integer(profiles[candidates[0]]['raw']['SchoolID'])] > 1)
        entry = dict(school_id=candidates[0], source_row=index, raw=row, exclusion=exclusion)
        income_values(entry)
        incomes.append(entry)
    observations = []
    for index, row in workbook_rows(raw/'rates.xlsx', 'Results by School'):
        if row['Assessment Type'] not in TYPES or row['Subject Area'] not in ['Mathematics', 'English Language Arts']:
            continue
        if row['School Year'] != YEAR:
            raise ValueError('Utah proficiency source school year changed')
        assessment_values(row)
        observations.append(dict(school_id=sid(row), source_row=index, raw=row))
    payload = dict(schema_version=1, state='UT', year=YEAR, academic_year='2024-25', release_status=RELEASE_STATUS, retrieved=datetime.now(timezone.utc).isoformat(),
        sources=sources, profiles=list(profiles.values()), incomes=incomes, assessments=observations,
        programs=programs, unmatched_profiles=unmatched, unmatched_income_sites=omitted)
    Path(destination).write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    return payload


def level_for(entry, high_ids):
    return 'HS' if entry['raw']['SchoolLevel'] == 'HS' or entry['raw']['IsSplitSchool'] == '1' or entry['school_id'] in high_ids else 'ES'


def import_data(db, payload):
    if (payload['schema_version'], payload['state'], payload['year'], payload['academic_year']) != (1, 'UT', YEAR, '2024-25') or payload.get('release_status') != RELEASE_STATUS:
        raise ValueError('Unexpected Utah source identity or school year')
    profiles = {}
    for entry in payload['profiles']:
        key, row, cactus = entry['school_id'], entry['raw'], entry['cactus']
        if (key != sid(row) or key in profiles or row['schoolyearendyear'] != str(YEAR)
                or row['SchoolLevel'] not in ['K8', 'HS'] or row['IsSplitSchool'] not in ['0', '1']
                or any(integer(row[a]) != integer(cactus[b]) for a,b in [('SchoolID','schoolId'),('DistrictID','districtId'),('SchoolNbr','schoolNumber')])
                or cactus['isPrivate']):
            raise ValueError('Invalid or duplicate Utah authoritative school identity')
        profiles[key] = entry
    program_codes = {(str(p['raw']['Sponsor Number']).strip().lstrip('0') or '0', integer(p['raw']['Site Number'])) for p in payload['programs']}
    native_units = Counter(integer(e['raw']['SchoolID']) for e in profiles.values())
    incomes = {}
    for entry in payload['incomes']:
        key, row = entry['school_id'], entry['raw']
        if key not in profiles or key in incomes:
            raise ValueError('Invalid or duplicate Utah income join')
        c = profiles[key]['cactus']; expected = (str(c['districtNumber']).lstrip('0') or '0', integer(c['schoolNumber']))
        if site_code(row['Site Number']) != expected or expected[0] != (str(row['Sponsor Number']).strip().lstrip('0') or '0'):
            raise ValueError('Utah income must match an authoritative district/school site code')
        exclusion = income_exclusion(row, expected, program_codes, native_units[integer(profiles[key]['raw']['SchoolID'])] > 1)
        if entry['exclusion'] != exclusion:
            raise ValueError('Utah program eligibility exclusion changed')
        income_values(entry); incomes[key] = entry
    seen, raw_observations, ignored, high_ids = set(), [], Counter(), set()
    for entry in payload['assessments']:
        row, key = entry['raw'], entry['school_id']
        if key != sid(row) or row['School Year'] != YEAR or row['Assessment Type'] not in TYPES or row['Subject Area'] not in ['Mathematics', 'English Language Arts']:
            raise ValueError('Utah native assessment population changed')
        level, subject = TYPES[row['Assessment Type']], 'math' if row['Subject Area'] == 'Mathematics' else 'reading'
        if (key, level, subject) in seen:
            raise ValueError('Duplicate Utah assessment identity')
        seen.add((key, level, subject))
        if key not in profiles or integer(row['SchoolID']) != integer(profiles[key]['raw']['SchoolID']):
            ignored['Assessment without an exact native school crosswalk'] += 1; continue
        if level == 'HS':
            high_ids.add(key)
        pct, tested, exclusion = assessment_values(row)
        raw_observations.append(dict(entry, year=YEAR, level=level, subject=subject, assessment=ASSESSMENTS[level],
                                     proficiency=pct, tested=tested, exclusion=exclusion))
    observations = []
    for entry in raw_observations:
        if level_for(profiles[entry['school_id']], high_ids) != entry['level']:
            ignored['RISE rows from high or mixed-grade schools excluded'] += 1; continue
        observations.append(entry)
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?', (DATASET+':%',))
    db.execute('INSERT OR REPLACE INTO dataset VALUES (?,?,?,?,?)', (DATASET, 'UT', 'Utah USBE 2024–25 native totals', 'Separate restricted non-CEP/non-Provision NSLP cohorts', RELEASE_STATUS))
    sources = dict(payload['sources']); sources['ut-extract-2025'] = dict(path=str(EXTRACT.relative_to(ROOT)), url=REPORTS, sha256=digest(EXTRACT))
    for ident, source in sources.items():
        if not re.fullmatch('[0-9a-f]{64}', source['sha256']):
            raise ValueError('Invalid Utah source checksum')
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)', (ident, DATASET, source['path'], source['url'], source['sha256'], payload['retrieved']))
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)', ('ut-nslp-2025', 'Utah individual NSLP eligibility outside CEP/Provision 2', ECON_DEFINITION, REPORTS))
    for level, name in ASSESSMENTS.items():
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)', (definition_id(DATASET, YEAR, name, level), 'UT', name, YEAR, level,
            '3–8' if level == 'ES' else '9–10', 'Native published 2025 Percent Proficient, separate RISE and Utah Aspire Plus rows. Overall Results and DLM excluded. Exact school valid-score counts unavailable; all sampling intervals omitted.', REPORTS))
    for key, entry in profiles.items():
        row, c = entry['raw'], entry['cactus']
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)', (DATASET, key, row['name'], row['DistrictID'], c['leaName'], None, None, json.dumps(entry), 'ut-reportcard-2025', entry['source_row']))
        if key in incomes:
            inc = incomes[key]; total, low, pct = income_values(inc)
            db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (DATASET, key, YEAR, 'ut-nslp-2025', row['name'], total, low, pct,
                'NSLP individual eligibility; CEP/Provision 2 excluded', json.dumps(inc), 'ut-lunch-2025', inc['source_row']))
    for entry in observations:
        db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)', (DATASET, entry['school_id'], definition_id(DATASET, YEAR, entry['assessment'], entry['level']), entry['subject'],
            entry['proficiency'], None, 'reported' if entry['proficiency'] is not None else 'suppressed_or_not_reported', json.dumps(entry['raw']), None, 'ut-rates-2025', entry['source_row']))
    return profiles, incomes, observations, high_ids, dict(ignored)


def prepare(database=DEFAULT_DB, output=OUTPUT):
    payload = json.loads(EXTRACT.read_text())
    with connect(database) as db:
        profiles, incomes, raw_observations, high_ids, ignored = import_data(db, payload)
        observations = pl.DataFrame([{k: r[k] for k in ['school_id','year','level','assessment','subject','proficiency','tested']} for r in raw_observations], infer_schema_length=None)
        income_rows = pl.DataFrame([dict(r) for r in db.execute('SELECT school_id,year,name,enrollment,low_income,percentage FROM economic_observation WHERE dataset_id=?', (DATASET,))], infer_schema_length=None)
        records, models = build_history(observations, income_rows, point_only_assessments=list(ASSESSMENTS.values()))
        if len(models) != 6:
            raise ValueError('Utah lacks an eligible model for a native assessment population')
        save_models(db, records, models, DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Utah foreign key check failed')
    by_key = {(r['school_id'],r['level']):r for r in records}
    for raw in raw_observations:
        if raw['exclusion']:
            by_key[(raw['school_id'],raw['level'])]['exclusions'][raw['subject']] = raw['exclusion']
    schools = []
    for key, entry in profiles.items():
        level = level_for(entry, high_ids); annual = by_key.get((key,level)); row = entry['raw']
        total, _, income = income_values(incomes[key]) if key in incomes else (None,None,None)
        exclusions = dict(annual['exclusions']) if annual else {s:'No applicable native assessment' for s in ['math','reading','combined']}
        if key in incomes and incomes[key]['exclusion']:
            exclusions.update({s:incomes[key]['exclusion'] for s in ['math','reading','combined']})
        schools.append(dict(id=key,name=row['name'],short=row['name'],level=level,program='Unclassified',district=entry['cactus']['leaName'],
            city=None,county=None,income=income,enrollment=total,latitude=None,longitude=None,metrics=annual['subjects'] if annual else {},history=[annual] if annual else [],exclusions=exclusions))
    details = [
        'Separate native published Percent Proficient totals for RISE grades 3–8 and Utah Aspire Plus grades 9–10. Overall Results mix assessment populations and are excluded; DLM, science and ACT are excluded. Published fractions are retained without averaging grade percentages.',
        'Grade-school models exclude schools flagged HS or split-grade in the same-year reportcard inventory and schools with a native Aspire grade-9–10 record. Such schools use only separate Aspire results in high-school models; their RISE rows are excluded.',
        'School valid-score denominators are unavailable. No enrollment or participation count substitutes for valid scores; tested counts and every sampling interval remain unavailable. These are native published proficiency rates, not reconstructed accountability or tested-only rates.',
        ECON_DEFINITION,
        'This is a restricted NSLP population, not every Utah public school. Schools using CEP or Provision 2, without an individual eligibility rate, outside NSLP, with ambiguous site units, or with unavailable native crosswalks are excluded from every model. Utah reportcard demographic percentages and name-only October enrollment tables are not used.',
        'Authoritative joins bind same-year USBE District ID, SchoolNumber and SchoolID to the native CACTUS district/site codes. Excel-corrupted numeric charter codes are unavailable and never reconstructed. Suppressed proficiency ranges and eligibility are missing, never zero. Only 2024–25 is modeled; no admissions classifications or historical map coordinates are provided.',
    ]
    levels = {level:dict(year=YEAR,label='Grade schools · RISE' if level=='ES' else 'High schools · Utah Aspire Plus',assessment=name,
        outcome='Proficient or Highly Proficient',math_label='Math',note='Native RISE grades 3–8' if level=='ES' else 'Native Aspire grades 9–10') for level,name in ASSESSMENTS.items()}
    methodology = dict(summary='Utah 2024–25 native RISE and Aspire totals, with individual NSLP eligibility in schools outside CEP and Provision 2.',details=details,
        sources=[dict(label='USBE proficiency, October31 survey and complete program roster',url=REPORTS),dict(label='Authoritative CACTUS school directory',url=DIRECTORY),dict(label='Same-year USBE reportcard school inventory',url=REPORTCARD),
                 dict(label='RISE assessment',url='https://schools.utah.gov/assessment/assessments/rise'),dict(label='Utah Aspire Plus assessment',url='https://schools.utah.gov/assessment/assessments/utahaspireplus')])
    result = dict(year='2024–25',assessment_year=YEAR,income_label='Individual NSLP eligible',levels=levels,program_options=['Unclassified'],schools=sorted(schools,key=lambda s:s['id']),
        models={level:{subject:next(m for m in models if m['level']==level and m['subject']==subject) for subject in ['math','reading','combined']} for level in levels},history_years=[YEAR],history_models=models,coverage_note=' '.join(details),methodology=methodology)
    audit = dict(year=YEAR,directory_schools=len(schools),ignored_sources=ignored,unmatched_directory_profiles=len(payload['unmatched_profiles']),unmatched_income_sites=len(payload['unmatched_income_sites']),
        native_nslp_sites=len(payload['incomes'])+len(payload['unmatched_income_sites']),program_roster_sites=len(payload['programs']),
        income_exclusions=dict(Counter(e['exclusion'] for e in incomes.values() if e['exclusion'])),
        eligible_models=[{k:m[k] for k in ['level','subject','n','excluded_schools']} for m in models],exclusions=dict(Counter(reason for r in records for reason in r['exclusions'].values())),
        valid_score_counts='Unavailable; all intervals omitted',map_coordinates=0,joins='Native SchoolID + District ID + SchoolNumber and same-year CNP site codes')
    catalog = dict(schema_version=1,prepare_script='scripts/prepare_utah.py',state=dict(id='UT',name='Utah'),regions=[dict(id='utah',name='Statewide · non-CEP NSLP schools',dataset=DATASET,status=RELEASE_STATUS,geography='utah',levels=['ES','HS'],
        schools='data/utah/schools.json',boundaries=None,map_source='Historical school locations are unavailable in the audited 2024–25 sources.',
        comparison='Comparison population: Utah non-CEP/non-Provision NSLP schools · {year} {note}. Separate published RISE/Aspire cohorts; sampling intervals unavailable.',
        model_scope='Separate native published RISE and Aspire populations among individually eligible NSLP sites outside CEP/Provision 2',audit='data/utah/audit.json')])
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for filename,value in [('schools.json',result),('history.json',dict(records=records,models=models)),('audit.json',audit),('catalog.json',catalog)]:
        (output/filename).write_text(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps(audit,indent=2));return result,audit


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract',action='store_true');parser.add_argument('--raw',type=Path,default=RAW)
    parser.add_argument('--database',type=Path,default=DEFAULT_DB);parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    if args.extract:extract(args.raw)
    prepare(args.database,args.output)
