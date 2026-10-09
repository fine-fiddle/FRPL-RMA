"""Virginia native 2024–25 schoolwide SOL/VAAP pass rates and economic status.

--extract reads saved official School Quality profile pages. The committed extract
supports offline rebuilding; ordinary and mixed grade spans use separate models.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from urllib.parse import urlparse

import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET = 'va-vdoe-2025'
YEAR = 2025
ACADEMIC_YEAR = '2024-2025'
RAW = ROOT/'data/raw/virginia'
EXTRACT = ROOT/'data/source/virginia.json'
OUTPUT = ROOT/'data/virginia'
PROFILE_PAGE = 'https://schoolquality.virginia.gov/'
DOWNLOAD_PAGE = 'https://schoolquality.virginia.gov/download-data'
GLOSSARY = 'https://schoolquality.virginia.gov/glossary'
STANDARDS = 'https://content.govdelivery.com/accounts/VADOE/bulletins/3dc0d1d'
BANDS = {
    'grade': ('ES', 'SOL/VAAP 2025 standards · grade-school totals', 'Grade schools · published totals'),
    'high': ('HS', 'SOL/VAAP 2025 standards · high-school totals', 'High schools · published totals'),
    'mixed': ('HS', 'SOL/VAAP 2025 standards · mixed-grade totals', 'Mixed-grade schools · published totals'),
}
ECON_DEFINITION = ('Same-year September 30 school Fall Membership, individually classified economically '
    'disadvantaged if eligible for free/reduced-price meals, receiving TANF, eligible for Medicaid, '
    'or migrant or experiencing homelessness. This broader student economic-status measure is '
    'distinct from the portal meal-service measure, which counts every student in CEP divisions.')
MISSING = {None, '', '-', '*', '<', '>', 'N/A', 'NA'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(raw, *, integral=False):
    if raw in MISSING:
        return None
    value = float(str(raw).replace(',', ''))
    if not math.isfinite(value) or value < 0 or (integral and value != int(value)):
        raise ValueError('Virginia requires an unsuppressed nonnegative number')
    return int(value) if integral else value


def school_id(raw):
    tokens = [raw.get('division_number'), raw.get('school_number')]
    if any(not isinstance(t, str) or not t.isdigit() for t in tokens):
        raise ValueError('Virginia requires the authoritative division and school numbers')
    division, school = map(int, tokens)
    if not 1 <= division <= 999 or not 1 <= school <= 9999:
        raise ValueError('Invalid Virginia division or school number')
    return f'{division:03d}{school:04d}'


def income_values(raw):
    groups = raw['enrollment_subgroups']
    if any(row.get('sch_yr') != '2024' or row.get('subgroup_type_id') != key for key, row in groups.items()):
        raise ValueError('Virginia economic-status record year or subgroup mismatch')
    total = number(groups.get('5', {}).get('cnt'), integral=True)
    low = number(groups.get('3', {}).get('cnt'), integral=True)
    other = number(groups.get('18', {}).get('cnt'), integral=True)
    published = number(groups.get('3', {}).get('pct'))
    if total is None or total == 0 or low is None or published is None:
        return total, None, None
    if low > total or (other is not None and other > total):
        raise ValueError('Virginia economic status exceeds enrollment')
    years, rows = raw['grade_table']['years'], raw['grade_table']['rows']
    if ACADEMIC_YEAR not in years or other is None or low+other != total:
        return total, None, None
    index = years.index(ACADEMIC_YEAR)
    grade_counts = [number(r['values'][index], integral=True) for r in rows if r['label'] != 'Total Enrollment']
    grade_totals = [number(r['values'][index], integral=True) for r in rows if r['label'] == 'Total Enrollment']
    if (len(grade_totals) != 1 or grade_totals[0] != total or not grade_counts
            or any(c is None for c in grade_counts) or sum(grade_counts) != total):
        return total, None, None
    # Some portal percentages use a stale denominator, including All Students
    # percentages over 100. Use only independently reconciled native counts and
    # retain the displayed percentages for the audit; never infer missing counts.
    return total, low, 100*low/total


def band_for(raw):
    years, rows = raw['grade_table']['years'], raw['grade_table']['rows']
    if ACADEMIC_YEAR not in years:
        return None
    if years.count(ACADEMIC_YEAR) != 1:
        raise ValueError('Duplicate Virginia grade-table school year')
    index = years.index(ACADEMIC_YEAR)
    grades = set()
    seen = set()
    for row in rows:
        label, values = row['label'], row['values']
        if len(values) != len(years) or label in seen:
            raise ValueError('Invalid or duplicate Virginia grade membership')
        seen.add(label)
        if label == 'Total Enrollment':
            continue
        raw_count = values[index]
        count = number(raw_count, integral=True)
        if count == 0 or raw_count in {None, '', '-', '*', 'N/A', 'NA'}:
            continue
        if label in {'Pre-Kindergarten', 'Pre-kindergarten', 'Preschool', 'Pre-K', 'Kindergarten'}:
            grade = 0
        elif re.fullmatch(r'Grade (?:[1-9]|1[0-2])', label):
            grade = int(label.split()[1])
        else:
            # Ungraded membership cannot be assigned to an assessment cohort.
            return None
        grades.add(grade)
    lower = any(3 <= g <= 8 for g in grades)
    high = any(9 <= g <= 12 for g in grades)
    return 'mixed' if lower and high else 'grade' if lower else 'high' if high else None


def assessment_value(raw, subject):
    record = raw['assessments'][subject]
    if record['population'] != 'All Students' or record['test'] != ('Mathematics' if subject == 'math' else 'English Reading'):
        raise ValueError('Virginia requires native All Students subject-area totals')
    years, values = record['years'], record['school_values']
    if years.count(ACADEMIC_YEAR) != 1 or len(years) != len(values):
        raise ValueError('Virginia assessment school-year labels do not match native values')
    value = number(values[years.index(ACADEMIC_YEAR)])
    if value is not None and value > 100:
        raise ValueError('Invalid Virginia published pass percentage')
    return value


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.current, self.cell = [], None, None
    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.current = []
        elif tag in {'td', 'th'} and self.current is not None:
            self.cell = []
    def handle_data(self, value):
        if self.cell is not None:
            self.cell.append(value)
    def handle_endtag(self, tag):
        if tag in {'td', 'th'} and self.cell is not None:
            self.current.append(' '.join(''.join(self.cell).split())); self.cell = None
        elif tag == 'tr' and self.current is not None:
            self.rows.append(self.current); self.current = None


def table_rows(markup):
    parser = TableRows(); parser.feed(markup); return parser.rows


def native_json(markup, variable):
    matches = list(re.finditer(r'\b(?:var|const)\s+'+re.escape(variable)+r'\s*=\s*', markup))
    if len(matches) != 1:
        raise ValueError(f'Virginia profile lacks unique native {variable}')
    value, _ = json.JSONDecoder().raw_decode(markup[matches[0].end():])
    return value


def parse_profile(markup):
    markup = re.sub(r'<!--.*?-->', '', markup, flags=re.S)
    def required(pattern):
        match = re.search(pattern, markup, re.S)
        if not match:
            raise ValueError(f'Virginia native profile is missing {pattern}')
        return unescape(match.group(1)).strip()
    raw = dict(division_number=required(r'<strong>Division Number:</strong>\s*(\d+)'),
        school_number=required(r'<strong>School Number:</strong>\s*(\d+)'),
        name=required(r'<h1[^>]*itemprop="name"[^>]*>(.*?)</h1>'),
        district=required(r'<span itemprop="department">(.*?)</span>'),
        category=required(r'Category:</strong>\s*<span itemprop="description">(.*?)</span>'))
    school_id(raw)
    labels = native_json(markup, 'subgroupLabels')
    for key, label in [('5','All Students'), ('3','Economically Disadvantaged'), ('18','Not Economically Disadvantaged')]:
        if labels.get(key) != label:
            raise ValueError('Virginia economic-status subgroup definitions changed')
    enrollment = native_json(markup, 'enrollmentStats')
    raw['enrollment_subgroups'] = {key: enrollment.get('2024', {}).get(key, {}) for key in ['5','3','18'] if key in enrollment.get('2024', {})}
    start = markup.index('id="dvdoe-fall_membership"')
    grade_markup = markup[start:markup.index('</table>', start)+8]
    grade_rows = table_rows(grade_markup)
    header = next(row for row in grade_rows if row and row[0] == '' and len(row)>1)
    if header[0] != '' or any(not re.fullmatch(r'20\d\d-20\d\d', year) for year in header[1:]):
        raise ValueError('Unexpected Virginia grade-table year header')
    raw['grade_table'] = dict(years=header[1:], rows=[dict(label=row[0], values=row[1:]) for row in grade_rows if row and row[0] != '' and row[0] != 'Grade'])
    raw['assessments'] = {}
    for subject, native, expected in [('math','Math','Mathematics'), ('reading','Reading','English Reading')]:
        start = markup.index(f'var chart{native}ProfData')
        region = markup[start:markup.index('</script>',start)]
        years_match = re.search(r"\['x',\s*((?:'20\d\d-20\d\d',?\s*)+)\]",region)
        if not years_match:
            raise ValueError('Virginia native assessment year labels unavailable')
        years = re.findall(r"'(20\d\d-20\d\d)'",years_match.group(1))
        select = required(r'<select id="'+native+r'test"[^>]*>(.*?)</select>')
        option = re.search(r'<option value="0">(.*?)</option>', select)
        if not option or option.group(1) != expected:
            raise ValueError('Virginia native first chart is not the subject-area total')
        totals = native_json(markup, f'chart{native}ProfData')['5']
        series = totals[0] if isinstance(totals, list) else totals['0']
        school = next(row for row in series if row[0] == 'School')
        thead = required(r"<thead class=['\"]table-data-"+native+r"-0['\"]>(.*?)</thead>")
        table_years = [row[1:] for row in table_rows(thead)][0]
        if table_years != years:
            raise ValueError('Virginia native assessment table and chart year labels differ')
        tbody = required(r"<tbody class=['\"]table-data-"+native+r"-0['\"]>(.*?)</tbody>")
        all_rows = [row for row in table_rows(tbody) if row[0] == 'All Students']
        if not all_rows and all(number(v) is None for v in school[1:]):
            all_row = None
        elif len(all_rows) == 1:
            all_row = all_rows[0]
            if len(all_row) != 1+4*len(years):
                raise ValueError('Virginia native assessment performance columns changed')
            table_pass = [all_row[3+4*i] for i in range(len(years))]
            if any(number(a) != number(b) for a,b in zip(school[1:],table_pass)):
                raise ValueError('Virginia native table and chart pass rates disagree')
        else:
            raise ValueError('Virginia native assessment requires one All Students table row')
        raw['assessments'][subject] = dict(population='All Students', test=expected, years=years,
            school_values=school[1:], table_columns=['Advanced','Proficient','Passed','Failed'], table_all_students=all_row[1:] if all_row else None)
        assessment_value(raw, subject)
    income_values(raw); band_for(raw)
    return raw


def extract(raw=RAW, destination=EXTRACT):
    raw=Path(raw)
    inventory=json.loads((raw/'inventory.json').read_text())
    files=json.loads((raw/'profile-files.json').read_text())
    if set(inventory) != set(files) or len(inventory) != 1812:
        raise ValueError('Incomplete native Virginia school inventory/download coverage')
    sources={}; profiles=[]; seen=set()
    for ordinal,(url,item) in enumerate(sorted(inventory.items()),1):
        if urlparse(url).netloc != 'schoolquality.virginia.gov' or not urlparse(url).path.startswith('/schools/'):
            raise ValueError('Nonofficial Virginia school profile URL')
        path=Path(files[url]); native=parse_profile(path.read_text())
        key=school_id(native)
        if key in seen:
            raise ValueError(f'Duplicate Virginia authoritative school ID: {key}')
        seen.add(key)
        ident='va-profile-'+key
        sources[ident]=dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),url=url,sha256=digest(path))
        profiles.append(dict(school_id=key,source=ident,source_row=ordinal,raw=native))
    payload=dict(schema_version=1,state='VA',year=YEAR,academic_year=ACADEMIC_YEAR,
        retrieved=datetime.now(timezone.utc).isoformat(),sources=sources,profiles=profiles,
        inventory=dict(total_schools=1812,source='Official School Quality native school search',
            urls=json.loads((raw/'inventory-urls.json').read_text())))
    Path(destination).write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n')
    return payload


def import_data(db,payload):
    if (payload['schema_version'],payload['state'],payload['year'],payload['academic_year']) != (1,'VA',YEAR,ACADEMIC_YEAR):
        raise ValueError('Unexpected Virginia source identity or school year')
    profiles={}; observations=[]; ignored=Counter()
    for entry in payload['profiles']:
        raw,key=entry['raw'],entry['school_id']
        if key != school_id(raw) or key in profiles or entry['source'] not in payload['sources']:
            raise ValueError('Invalid or duplicate Virginia authoritative school profile')
        band=band_for(raw); income_values(raw)
        profiles[key]=entry
        for subject in ['math','reading']:
            pct=assessment_value(raw,subject)
            if band is None:
                ignored['No classified grade 3–8 or high-school enrollment population']+=1
                continue
            level,assessment,_=BANDS[band]
            observations.append(dict(school_id=key,year=YEAR,level=level,assessment=assessment,subject=subject,
                proficiency=pct,tested=None,source=entry['source'],source_row=entry['source_row']))
    for table in ['model_run','assessment_observation','economic_observation','school','source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?',(DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?',(DATASET+':%',))
    db.execute('INSERT OR REPLACE INTO dataset VALUES (?,?,?,?,?)',(DATASET,'VA','Virginia School Quality 2024–25',
        'Separate schoolwide SOL/VAAP grade-school, high-school and mixed-grade populations','ready'))
    sources=dict(payload['sources'])
    sources['va-extract-2025']=dict(path=str(EXTRACT.relative_to(ROOT)),url=PROFILE_PAGE,sha256=digest(EXTRACT))
    for ident,source in sources.items():
        if len(source['sha256'])!=64 or any(c not in '0123456789abcdef' for c in source['sha256']):
            raise ValueError('Invalid Virginia source checksum')
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',(ident,DATASET,source['path'],source['url'],source['sha256'],payload['retrieved']))
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',('va-econ-2025','Virginia economic status 2024–25',ECON_DEFINITION,GLOSSARY))
    for band,(level,assessment,_) in BANDS.items():
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',(definition_id(DATASET,YEAR,assessment,level),
            'VA',assessment,YEAR,level,'Schoolwide grade-level and/or end-of-course tests applicable to the grade span',
            'Native All Students subject-area Passed percentages, including proficient and advanced levels, for SOL plus VAAP. '
            '2023 mathematics and 2024 English standards first assessed spring 2025. Exact valid-score denominators '
            'not supplied in the profile; sampling intervals unavailable. Separate ordinary and mixed grade spans.',PROFILE_PAGE))
    for key,entry in profiles.items():
        raw=entry['raw']; total,low,pct=income_values(raw)
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',(DATASET,key,raw['name'],f"{int(raw['division_number']):03d}",
            raw['district'],None,None,json.dumps(raw),entry['source'],entry['source_row']))
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(DATASET,key,YEAR,'va-econ-2025',raw['name'],
            total,low,pct,'Individually classified economic disadvantage',json.dumps(raw['enrollment_subgroups']),entry['source'],entry['source_row']))
    for entry in observations:
        raw=profiles[entry['school_id']]['raw']['assessments'][entry['subject']]
        db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',(DATASET,entry['school_id'],
            definition_id(DATASET,YEAR,entry['assessment'],entry['level']),entry['subject'],entry['proficiency'],None,
            'reported' if entry['proficiency'] is not None else 'suppressed_or_not_reported',json.dumps(raw),None,entry['source'],entry['source_row']))
    return profiles,observations,dict(ignored)


def prepare(database=DEFAULT_DB,output=OUTPUT):
    payload=json.loads(EXTRACT.read_text())
    with connect(database) as db:
        profiles,observations,ignored=import_data(db,payload)
        assessments=pl.DataFrame([{k:r[k] for k in ['school_id','year','level','assessment','subject','proficiency','tested']} for r in observations],infer_schema_length=None)
        incomes=pl.DataFrame([dict(r) for r in db.execute('SELECT school_id,year,name,enrollment,low_income,percentage FROM economic_observation WHERE dataset_id=?',(DATASET,))],infer_schema_length=None)
        records,models=build_history(assessments,incomes,point_only_assessments=[v[1] for v in BANDS.values()])
        if not models:
            raise ValueError('Virginia has no eligible models')
        save_models(db,records,models,DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Virginia foreign key check failed')
    by_key={r['school_id']:r for r in records}
    schools_by_band=defaultdict(list)
    for key,entry in profiles.items():
        raw=entry['raw']; band=band_for(raw)
        if band is None:
            continue
        level,assessment,_=BANDS[band]; annual=by_key[key]
        for subject in ['math','reading']:
            if assessment_value(raw,subject) is None:
                annual['exclusions'][subject]='Virginia suppressed or did not report the native schoolwide pass rate'
        if 'combined' not in annual['subjects']:
            annual['exclusions']['combined']='Math and ELA must both have eligible same-year published rates'
        total,_,income=income_values(raw)
        schools_by_band[band].append(dict(id=key,name=raw['name'],short=raw['name'],level=level,program='Unclassified',
            district=raw['district'],city=None,county=None,income=income,enrollment=total,latitude=None,longitude=None,
            metrics=annual['subjects'],history=[annual],exclusions=annual['exclusions']))
    details=[
        'Proficiency is the directly published schoolwide All Students Passed percentage for Mathematics or English Reading, including proficient and advanced levels. SOL and VAAP results are included as documented by VDOE. Native whole-subject totals are used; grade/course percentages are never averaged.',
        'Same-year grade membership separates schools with grade 3–8 enrollment, high-school-only assessment grades, and mixed schools with both grade 3–8 and grade 9–12 membership. Mixed schools have their own comparison region and regressions; no mixed totals enter ordinary grade-school or high-school models.',
        'The native profiles publish rounded integer pass percentages and no verified exact valid-score denominators. Every tested count and sampling interval is unavailable. Enrollment, CSV Record Count and participation are not substituted for valid scores.',
        ECON_DEFINITION,
        'Economic status is calculated from directly published same-year September 30 All Students and Economically Disadvantaged enrollment counts only when every grade subtotal and the ED plus non-ED counts reconcile exactly to enrollment. Some portal percentages have stale denominators; those display values are retained in the source and flagged in the audit, while verified exact count ratios are used. Missing or suppressed individual counts are never treated as zero or inferred from the complementary group.',
        'School identity uses the native division and school numbers on the same official profile for both assessment and economic status. Whole-school fall enrollment and varying tested grade/course mixes are limitations. Current profile names may postdate results.',
        'This snapshot contains 2024–25 only. New 2023 mathematics and 2024 English standards were first assessed in spring 2025, so the older displayed profile years are excluded. No admissions classifications or authoritative map coordinates are supplied.',
    ]
    methodology=dict(summary='Virginia 2024–25 published schoolwide SOL/VAAP pass rates and same-year individual economic status; separate ordinary and mixed grade spans.',
        details=details,sources=[dict(label='VDOE School Quality native school profiles',url=PROFILE_PAGE),
        dict(label='Native export definitions and subject-area tables',url=DOWNLOAD_PAGE),dict(label='School Quality data definitions',url=GLOSSARY),
        dict(label='Spring 2025 new English and mathematics standards',url=STANDARDS)])
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    regions=[]
    for folder_name,bands in [('', ['grade','high']),('mixed',['mixed'])]:
        folder=output/folder_name; folder.mkdir(parents=True,exist_ok=True)
        cohort_schools=sorted([s for band in bands for s in schools_by_band[band]],key=lambda s:s['id'])
        names={BANDS[band][1] for band in bands}; cohort_models=[m for m in models if m['assessment'] in names]
        cohort_records=[r for r in records if r['assessment'] in names]
        levels={BANDS[band][0]:dict(year=YEAR,label=BANDS[band][2],assessment=BANDS[band][1],outcome='Passed · proficient or advanced',
            math_label='Math',note=BANDS[band][1]+' · published rates · sampling intervals unavailable') for band in bands}
        result=dict(year='2024–25',assessment_year=YEAR,income_label='Economically disadvantaged',levels=levels,program_options=['Unclassified'],
            schools=cohort_schools,models={level:{s:next((m for m in cohort_models if m['level']==level and m['subject']==s),None)
                for s in ['math','reading','combined']} for level in levels},history_years=[YEAR],history_models=cohort_models,
            coverage_note=' '.join(details),methodology=methodology)
        (folder/'schools.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
        (folder/'history.json').write_text(json.dumps(dict(records=cohort_records,models=cohort_models),separators=(',',':'),allow_nan=False)+'\n')
        region=dict(id='virginia-mixed' if folder_name else 'virginia',name='Mixed-grade school totals' if folder_name else 'Statewide school totals',
            dataset=DATASET,status='ready',geography='virginia',levels=list(levels),schools='data/virginia/'+('mixed/' if folder_name else '')+'schools.json',
            boundaries=None,map_source='School coordinates are unavailable in the audited native profile extracts.',
            comparison='Comparison population: Virginia statewide · {year} {note}. Native schoolwide SOL/VAAP pass rates; separate grade spans and no sampling intervals.',
            model_scope='Separate mixed-grade schoolwide SOL/VAAP totals' if folder_name else 'Separate grade-school and high-school schoolwide SOL/VAAP totals',audit='data/virginia/audit.json')
        if cohort_models:
            regions.append(region)
    income_mismatches=[]
    for key,entry in profiles.items():
        _,_,percentage=income_values(entry['raw'])
        if percentage is not None:
            published=number(entry['raw']['enrollment_subgroups']['3']['pct'])
            if abs(published-percentage)>.00051:
                income_mismatches.append(dict(school_id=key,published_percentage=published,verified_count_percentage=percentage))
    audit=dict(year=YEAR,source_schools=len(profiles),directory_schools={band:len(schools) for band,schools in schools_by_band.items()},ignored_sources=ignored,
        eligible_models=[{k:m[k] for k in ['assessment','level','subject','n','excluded_schools']} for m in models],
        exclusions=dict(Counter(reason for r in records for reason in r['exclusions'].values())),map_coordinates=0,
        valid_score_counts='Unavailable in native profile; every sampling interval omitted',joins='Authoritative division/school numbers on same-year profile',
        unavailable_or_unreconciled_income=sum(income_values(e['raw'])[2] is None for e in profiles.values()),
        stale_income_display_percentages=len(income_mismatches),stale_income_display_examples=income_mismatches[:10])
    catalog=dict(schema_version=1,prepare_script='scripts/prepare_virginia.py',state=dict(id='VA',name='Virginia'),regions=regions)
    for name,value in [('audit.json',audit),('catalog.json',catalog)]:
        (output/name).write_text(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps(audit,indent=2)); return audit


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract',action='store_true')
    parser.add_argument('--raw',type=Path,default=RAW)
    parser.add_argument('--database',type=Path,default=DEFAULT_DB)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    if args.extract:
        extract(args.raw)
    prepare(args.database,args.output)
