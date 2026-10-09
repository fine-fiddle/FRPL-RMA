"""Native Hawaii 2024–25 KPI proficiency and individual CCD direct certification.

Default rebuilds use the committed extract. --download obtains the official
public KPI workbook/guide; --extract joins exact historical state IDs to CCD.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import re
import urllib.request

import xlrd

from audit_national_sources import DIRECTORY, LUNCH, MEMBERSHIP, read_ccd, membership_cache, source
from database import ROOT, DEFAULT_DB
from prepare_ccd_states import grade_school, DEFINITION
from prepare_alabama import DIRECTORY_FIELDS
from state_registry import reported_count
from state_snapshot import prepare_snapshot

YEAR = 2025
DATASET = 'hi-kpi-dc-2025'
EXTRACT = ROOT / 'data/source/hawaii.json'
OUTPUT = ROOT / 'data/hawaii'
RAW = ROOT / 'data/raw'
PORTAL = 'https://arch.k12.hi.us/reports/strivehi-performance'
BASE = 'https://doe-arch-prod-reports-repository-565393024988.s3.us-west-2.amazonaws.com/strivehi-performance/2025/'
FILES = {'native': '2024-25KPIMasterDataFileUpdate20251202.xls', 'guide': 'KPI_Technical_Guide_2025.pdf'}
STANDARD = ('Official 2024–25 KPI schoolwide All Students LA/Math proficiency, '
    'including Smarter Balanced, Kaiapuni KĀʻEO and HSA alternate assessments. '
    'The dated KPI Technical Guide pages 3–4 defines the denominator as Full School '
    'Year students taking the test and receiving a valid score, with proficient '
    'students in the numerator. FSY requires enrollment at the same school on '
    'official fall, last Wednesday of January and spring participation count dates. '
    'This is the state KPI valid-score measure, not a federal ESSA achievement '
    'indicator with nonparticipant assignments. Page 8 suppresses groups below 11 '
    'rather than pooling prior years. Whole-number native school totals are '
    'preserved; no grade averages, tested counts or inferred counts are used. '
    'Sampling intervals are unavailable. Grade-school models exclude schools '
    'with high-school offers or any ungraded enrollment of unresolved grade scope.')


def native_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9]\d{2}', value):
        raise ValueError('Invalid native Hawaii three-digit School ID')
    return value


def ccd_id(row):
    match = re.fullmatch(r'HI-001-\d+-([1-9]\d{2})', row['ST_SCHID'])
    if not match or row['ST'] != 'HI' or row['SCHOOL_YEAR'] != '2024-2025':
        raise ValueError('Hawaii CCD state-ID format or year changed')
    return match[1]


def rate(value):
    if value in ['', '--']:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,3}', value) or int(value) > 100:
        raise ValueError('Unexpected native Hawaii KPI rate or suppression token')
    return float(value)


def validate_row(row):
    native_id(row['School ID'])
    if (row['Year'], row['Subgroup Description']) != ('2025', 'All Students'):
        raise ValueError('Hawaii KPI year or population changed')


def cohort(profile):
    d, grades, total = profile['directory'], profile['membership_grades'], profile['membership']
    if d is None or d['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8']:
        return None
    if profile['record']['School Type'] in ['Elementary', 'Middle', 'Elementary-Middle']:
        return 'grade' if grade_school(d, grades, total) else None
    return None


def income(profile):
    d, total, direct = profile['directory'], profile['membership'], profile['direct_certification']
    n, low = reported_count(total), reported_count(direct)
    if n is None or n <= 0 or low is None or low > n:
        return n, None, None, 'Individual same-year CCD direct certification or membership unavailable'
    for r in [total, direct]:
        if (r['SCHOOL_YEAR'], r['ST'], r['NCESSCH'], r['ST_SCHID']) != ('2024-2025', 'HI', d['NCESSCH'], d['ST_SCHID']):
            raise ValueError('Hawaii economic join crossed native identity or year')
    if direct['DATA_GROUP'] != 'Direct Certification' or direct['TOTAL_INDICATOR'] != 'Education Unit Total':
        raise ValueError('Hawaii income is outside the individual school-total category')
    return n, low, 100 * low / n, None


def download():
    for filename in FILES.values():
        (RAW / filename).write_bytes(urllib.request.urlopen(BASE + filename, timeout=60).read())


def extract():
    directory = defaultdict(list)
    for d in read_ccd(DIRECTORY):
        if d['ST'] == 'HI': directory[ccd_id(d)].append(d)
    lunch = {r['NCESSCH']: (i, r) for i, r in enumerate(read_ccd(LUNCH), 2) if r['ST'] == 'HI' and r['DATA_GROUP'] == 'Direct Certification'}
    membership = membership_cache()
    book = xlrd.open_workbook(RAW / FILES['native'])
    sheet = book.sheet_by_name('KPI School Data 2025')
    fields = sheet.row_values(0)
    profiles = []
    for i in range(1, sheet.nrows):
        r = dict(zip(fields, sheet.row_values(i)))
        if r['Subgroup Description'] != 'All Students': continue
        validate_row(r)
        matches = directory.get(r['School ID'], [])
        if len(matches) > 1: raise ValueError('Ambiguous authoritative Hawaii school-ID suffix')
        d = matches[0] if matches else None
        key = None if d is None else d['NCESSCH']
        total = membership['totals'].get(key)
        profiles.append(dict(id=r['School ID'], record=r, source_row=i+1,
            directory=None if d is None else {f: d[f] for f in DIRECTORY_FIELDS},
            membership=None if total is None else dict(total, SCHOOL_YEAR='2024-2025', TOTAL_INDICATOR='Education Unit Total'),
            membership_grades=membership['grades'].get(key),
            direct_certification=lunch.get(key, (0, None))[1], income_row=lunch.get(key, (0, None))[0]))
    sources = {key: source(RAW / filename, BASE + filename) for key, filename in FILES.items()}
    for key, stem in [('ccd_directory', DIRECTORY), ('ccd_membership', MEMBERSHIP), ('ccd_lunch', LUNCH)]:
        sources[key] = source(RAW / (stem + '.zip'), 'https://nces.ed.gov/ccd/Data/zip/' + stem + '.zip')
    sources['ccd_notes'] = source(RAW / 'SY_2024-25_CCD_Final_2a_Data_Notes.xlsx', 'https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx')
    sources['nces_definition'] = source(RAW / 'ccd-lunch-definition.html', 'https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data')
    payload = dict(state='HI', year=YEAR, academic_year='2024-25', retrieved=str(date.today()), sources=sources,
        workbook_sheet=sheet.name, native_advisory=book.sheet_by_name('Data Advisory').cell_value(5, 2), profiles=profiles)
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
    return payload


def normalize(payload):
    if (payload['state'], payload['year'], payload['academic_year'], payload['workbook_sheet']) != ('HI', YEAR, '2024-25', 'KPI School Data 2025'):
        raise ValueError('Wrong Hawaii source year or worksheet')
    schools, seen, excluded = [], set(), Counter()
    for p in payload['profiles']:
        r, d, key = p['record'], p['directory'], p['id']
        validate_row(r)
        if native_id(r['School ID']) != key or key in seen: raise ValueError('Duplicate or mismatched Hawaii native school ID')
        seen.add(key)
        if d is not None and ccd_id(d) != key: raise ValueError('Wrong native Hawaii directory identity')
        group = cohort(p)
        if group is None:
            excluded['Missing exact historical directory or outside verified grade-school scope'] += 1
            continue
        n, low, pct, reason = income(p)
        outcomes = {}
        for subject, field in [('math', 'Math Proficiency (%)'), ('reading', 'LA Proficiency (%)')]:
            proficiency = rate(r[field])
            outcomes[subject] = dict(proficiency=proficiency, tested=None, source='native', source_row=p['source_row'], raw=r,
                exclusion=reason if reason else ('Native KPI proficiency suppressed or missing' if proficiency is None else None))
        schools.append(dict(id=key, name=r['School Name'], district_id=d['LEAID'], district=d['LEA_NAME'], city=d['LCITY'],
            cohort=group, enrollment=n, low_income=low, income=pct, income_source='ccd_lunch', income_row=p['income_row'],
            income_raw=dict(direct_certification=p['direct_certification'], membership=p['membership']), directory_raw=d,
            membership_grades_raw=p['membership_grades'], outcomes=outcomes))
    cohorts = [dict(id=key, level=level, label=label, grades=grades, assessment='Hawaii KPI SBA/KĀʻEO/HSA alternate · ' + grades,
        standard=STANDARD, source='native', source_url=payload['sources']['guide']['url'], outcome='Proficient',
        note='Native FSY valid-score KPI totals · individual CCD DC · intervals unavailable', allow_point_only=True)
        for key, level, label, grades in [('grade', 'ES', 'Grade schools · Hawaii KPI', '3–8')]]
    return dict(dataset=DATASET, state=dict(id='HI', name='Hawaii'), year=YEAR, academic_year='2024–25',
        name='Hawaii native KPI 2024–25 · CCD direct certification', region='hawaii', prepare_script='scripts/prepare_hawaii.py',
        source_url=PORTAL, sources=payload['sources'], retrieved=payload['retrieved'], schools=schools, cohorts=cohorts,
        model_scope='Hawaii verified grade-school FSY KPI population with same-year individual CCD direct certification',
        income_definition=dict(label='Individual direct certification', definition=DEFINITION, url=payload['sources']['nces_definition']['url']),
        coverage_note=STANDARD + ' ' + DEFINITION,
        methodology=dict(summary='Hawaii’s state KPI valid-score proficiency is compared with individual benefits-based direct certification at verified grade schools; no sampling intervals.',
            details=[STANDARD, DEFINITION,
                'Native three-digit School ID matches the unique school-number component of the same-year CCD HI-001-area-school ID. Ambiguity fails closed; names never establish a match. Native school type, complete unadjusted historical grade offers and reconciled grade membership exclude mixed schools and nonzero ungraded enrollment of unresolved grade scope. High-school and mixed-grade comparisons require a separate scope audit. Coordinates are unavailable.',
                'The December 2, 2025 updated native workbook retains whole-number school totals and its below 11 privacy rule. Legacy federal Strive HI 95%-rule achievement and pooled small-group rates are not substituted. Alternate assessments have different achievement standards from general tests.',
                'Models use externally studentized residuals. Combined is the equally weighted mean of math and ELA proficiency. UI filters never refit. State thresholds are not a common national scale; residuals describe association, not causal effectiveness or overall quality.'],
            sources=[dict(label=label, url=payload['sources'][key]['url']) for key, label in [('native','Official 2025 KPI workbook'),('guide','Dated 2025 KPI valid-score technical guide'),('ccd_directory','Same-year authoritative CCD directory'),('ccd_lunch','Same-year individual CCD direct certification'),('nces_definition','NCES economic definitions')]]),
        source_audit=dict(native_profiles=len(seen), included_profiles=len(schools), excluded=dict(excluded),
            cohorts=dict(Counter(s['cohort'] for s in schools)), income_unavailable=sum(s['income'] is None for s in schools),
            native_advisory=payload['native_advisory'], counts_unavailable=True, mapped=0))


def prepare(database=DEFAULT_DB):
    result = prepare_snapshot(normalize(json.loads(EXTRACT.read_text())), EXTRACT, OUTPUT, database)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if args.download: download()
    if args.extract: extract()
    prepare(args.database)
