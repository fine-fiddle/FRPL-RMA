"""South Carolina 2024–25 actual FAY score counts and individual Day135 PIP."""
import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import re

import openpyxl

from audit_national_sources import DIRECTORY, MEMBERSHIP, read_ccd, membership_cache, source
from database import ROOT, DEFAULT_DB
from prepare_ccd_states import grade_school
from state_snapshot import prepare_snapshot

DATASET = 'sc-fay-scored-pip-2025'
YEAR = 2025
EXTRACT = ROOT / 'data/source/south-carolina.json'
OUTPUT = ROOT / 'data/south-carolina'
PORTAL = 'https://screportcards.com/files/2025/data-files/'
NATIVE = 'https://screportcards.com/files/2025/data-files/report-cards-data-for-researchers-2024-25/'
INCOME = 'https://www.ed.sc.gov/data/other/student-counts/active-student-headcounts/2024-25-active-student-headcounts/135-day-school-headcount-by-gender-ethnicity-and-pupils-in-poverty/'
GRADES = 'https://www.ed.sc.gov/data/other/student-counts/active-student-headcounts/2024-25-active-student-headcounts/135-day-school-headcount-by-grade/'
MANUAL = 'https://www.eoc.sc.gov/sites/eoc/files/Documents/Acct%20Manual%2024%2025/FINAL%20Accountability%20Manual%20SY%202024-25%20%28UPDATED%202025%2003%2030%3B%20REDLINE%29.pdf'
DIRECTORY_FIELDS = ['SCHOOL_YEAR', 'ST', 'NCESSCH', 'ST_SCHID', 'LEAID', 'SCH_NAME',
    'LEA_NAME', 'LCITY', 'UPDATED_STATUS', 'GSLO', 'GSHI', 'IGOFFERED',
    'G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
LEVEL_FIELDS = ['NbrME', 'NbrExceeding', 'NbrReady', 'NbrClose', 'NbrInNeedOfSupport']
ECON = ('Individual Pupils in Poverty (PIP) Yes counts divided by positive same-record active/funded '
    'enrollment in the official 2024–25 Day135 headcount, including pre-K where enrolled. The workbook '
    'labels its April 2025 QDC3 extraction and school-year snapshot. Historical 2024–25 EFA/report-card '
    'definitions identify transient, runaway, foster and homeless students or those Medicaid-eligible '
    'or qualified for SNAP/TANF within the last three years. This is individual current-membership '
    'PIP with an explicit three-year eligibility lookback, not household-income FRPL, CCD DC or every '
    'universal-free-meal recipient. No CEP multiplier, prior-year importer backfill or tested-subgroup '
    'ratio is used. The income workbook and same-day grade workbook must agree on enrollment; '
    'disagreements remain unavailable. The income snapshot covers all active/funded students while '
    'the response is the narrower continuously enrolled scored population.')
STANDARD = ('2024–25 native FAY SC READY + SC-Alt school score-level counts from the research workbook '
    'supply an actual scored-student fraction: independently visible NbrME divided by the sum of '
    'NbrExceeding, NbrReady, NbrClose and NbrInNeedOfSupport. The historical manual pp.29–31 '
    'affirmatively describes each separate level as students who scored at that level, and reports '
    'Not Tested separately. All four counts and the published ME numerator must be visible; ME '
    'must equal the top two levels. Masked Not Tested remains masked and is never reconstructed. '
    'Native NbrTOT and PctME include eligible nonparticipants and are audit evidence, not this response '
    'or denominator. No 95% participation count or accountability points are used. This is the '
    'manual-defined FAY population enrolled continuously from day45 through day160 and in the '
    'testing window, subject to authorized exclusions including recently arrived multilingual learners. '
    'SC READY Levels 3/4 and SC-Alt Meets/Exceeds are combined as native thresholds at verified '
    'grade schools with tested grades 3–8; alternate tests are not silently described as regular-only. '
    'Profiles with separate E/M report cards are excluded pending complete band-union audit. '
    'ELA assesses revised 2023 standards in 2025; this is a single-year snapshot without connected '
    'earlier history. Complete actual score-level counts support sampling intervals.')
VALID_SCORE = MANUAL + ' pp.29–31: actual separate achievement-level counts; Not Tested is separate'


def school_id(value):
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 10**7:
        return str(value).zfill(7)
    if isinstance(value, str) and re.fullmatch(r'\d{7}', value):
        return value
    raise ValueError('Invalid authoritative South Carolina seven-digit SIDN')


def count(value):
    if value in [None, '', '*', '***', 'N/A', '---'] or isinstance(value, str) and (re.search(r'[<>]', value) or re.fullmatch(r'\d+\s*-\s*\d+', value)):
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError('Invalid South Carolina native integer count')
    return value


def workbook(path, sheet):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(book[sheet].values)
    book.close()
    return rows


def extract():
    directory = {r['ST_SCHID']: r for r in read_ccd(DIRECTORY) if r['ST'] == 'SC'}
    membership = membership_cache()
    income_rows = workbook(ROOT / 'data/raw/sc_income_2025.xlsx', 'school by gender race pip')
    grade_rows = workbook(ROOT / 'data/raw/sc_headcount_2025.xlsx', 'school by grade')
    if income_rows[1][0] != '2024–2025 135-Day Headcount' or grade_rows[1][0] != '2024-2025 135-Day Headcount' or 'April, 2025 (QDC3)' not in income_rows[3][0] or 'April, 2025 (QDC3)' not in grade_rows[3][0]:
        raise ValueError('South Carolina native income/headcount academic year changed')
    incomes = {r[0]: (i, r) for i, r in enumerate(income_rows[7:], 8) if isinstance(r[0], str) and re.fullmatch(r'\d{7}', r[0])}
    headcounts = {r[0]: (i, r) for i, r in enumerate(grade_rows[7:], 8) if isinstance(r[0], str) and re.fullmatch(r'\d{7}', r[0])}
    native_rows = workbook(ROOT / 'data/raw/sc_research_2025.xlsx', '2a.AchievPrepSuccessELEMMIDD')
    header, grouped = native_rows[0], defaultdict(list)
    for i, values in enumerate(native_rows[1:], 2):
        row = dict(zip(header, values))
        if row['SCHOOLTYPECD'] in ['E', 'M']:
            if row['ReportCardYear'] != YEAR:
                raise ValueError('South Carolina native assessment year changed')
            grouped[school_id(row['SCHOOLID'])].append(dict(row, source_row=i))
    profiles = []
    for key, records in grouped.items():
        d = directory.get('SC-' + key[:4] + '-' + key[4:])
        nces = None if d is None else d['NCESSCH']
        total = membership['totals'].get(nces)
        profiles.append(dict(id=key, records=records,
            directory=None if d is None else {f: d[f] for f in DIRECTORY_FIELDS},
            membership=total, membership_grades=membership['grades'].get(nces),
            income_row=incomes.get(key, (0, None))[0], income_record=incomes.get(key, (0, None))[1],
            headcount_row=headcounts.get(key, (0, None))[0], headcount_record=headcounts.get(key, (0, None))[1]))
    sources = {key: source(ROOT / 'data/raw' / filename, url) for key, filename, url in [
        ('native', 'sc_research_2025.xlsx', NATIVE), ('income', 'sc_income_2025.xlsx', INCOME), ('headcount', 'sc_headcount_2025.xlsx', GRADES),
        ('manual', 'sc_manual_2025.pdf', MANUAL),
        ('unused_poverty_index', 'sc_poverty_2025.xlsx', 'https://screportcards.com/files/2025/data-files/2025-report-card-poverty-index/'),
        ('unused_all_tested', 'sc_ready_2025.xlsx', 'https://ed.sc.gov/data/test-scores/state-assessments/sc-ready/sc-ready-data-files/2024-2025-sc-ready-data/'),
        ('unused_extra', 'sc_extra_2025.xlsx', 'https://screportcards.com/files/2025/data-files/report-cards-data-additional-info-for-2024-25/'),
        ('ccd_directory', DIRECTORY + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + DIRECTORY + '.zip'),
        ('ccd_membership', MEMBERSHIP + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + MEMBERSHIP + '.zip')]}
    payload = dict(state='SC', year=YEAR, academic_year='2024-25', retrieved=str(date.today()), sources=sources,
        native_sheet='2a.AchievPrepSuccessELEMMIDD', native_header=header, profiles=profiles,
        income_headers=income_rows[:7], headcount_headers=grade_rows[:7],
        headcount_audit=dict(income_schools=len(incomes), grade_schools=len(headcounts),
            enrollment_disagreements=sum(incomes[k][1][3] != headcounts[k][1][3] for k in incomes if k in headcounts)))
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
    return payload


def income(profile):
    row, grades = profile['income_record'], profile['headcount_record']
    if row is None or grades is None:
        return None, None, None, 'Missing same-year individual Day135 PIP/headcount record'
    if school_id(row[0]) != profile['id'] or school_id(grades[0]) != profile['id']:
        raise ValueError('South Carolina native income crossed school identity')
    n, low = count(row[3]), count(row[15])
    if n is None or n <= 0 or low is None:
        return n, None, None, 'Individual Day135 PIP or enrollment unavailable'
    if low > n:
        return n, None, None, 'Individual Day135 PIP exceeds membership'
    if count(grades[3]) != n or any(count(v) is None for v in grades[4:]) or sum(grades[4:]) != n:
        return n, None, None, 'Same-day grade and PIP enrollment do not reconcile'
    if any(v != 0 for v in grades[14:]):
        return n, None, None, 'Same-day native grade enrollment contains high-school students'
    return n, low, 100 * low / n, None


def outcome(row, subject):
    values = [count(row[subject + '_' + f]) for f in LEVEL_FIELDS]
    if any(v is None for v in values):
        return None, None, 'Protected or unavailable native actual score-level/ME count'
    proficient, exceed, meet, close, low = values
    if proficient != exceed + meet:
        raise ValueError('South Carolina ME does not match actual top-two counts')
    valid = exceed + meet + close + low
    if valid <= 0:
        return None, None, 'Zero native actual score-level count'
    total, not_tested = count(row[subject + '_NbrTOT']), count(row[subject + '_NbrNotTest'])
    if total is not None and (valid > total or not_tested is not None and valid + not_tested != total):
        raise ValueError('South Carolina separate score and Not Tested bins do not reconcile')
    return 100 * proficient / valid, valid, None


def normalize(payload):
    if (payload['state'], payload['year'], payload['academic_year'], payload['native_sheet']) != ('SC', YEAR, '2024-25', '2a.AchievPrepSuccessELEMMIDD'):
        raise ValueError('Wrong South Carolina state/year/native sheet')
    if payload['income_headers'][1][0] != '2024–2025 135-Day Headcount' or payload['headcount_headers'][1][0] != '2024-2025 135-Day Headcount':
        raise ValueError('South Carolina native income/headcount year mismatch')
    schools, excluded, seen = [], Counter(), set()
    for p in payload['profiles']:
        key, d = p['id'], p['directory']
        if school_id(key) != key or key in seen:
            raise ValueError('Duplicate South Carolina school identity')
        seen.add(key)
        types = set()
        for row in p['records']:
            if list(row) != payload['native_header'] + ['source_row'] or row['ReportCardYear'] != YEAR or school_id(row['SCHOOLID']) != key or row['SCHOOLTYPECD'] not in ['E', 'M'] or row['SCHOOLTYPECD'] in types:
                raise ValueError('South Carolina duplicate report type, identity/year/schema changed')
            types.add(row['SCHOOLTYPECD'])
        if d is None:
            excluded['Missing exact same-year CCD state-ID directory match'] += 1
            continue
        if (d['SCHOOL_YEAR'], d['ST'], d['ST_SCHID']) != ('2024-2025', 'SC', 'SC-' + key[:4] + '-' + key[4:]):
            raise ValueError('South Carolina directory crossed state, year or identity')
        if d['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8'] or not grade_school(d, p['membership_grades'], p['membership']):
            excluded['Outside verified operational grade-school scope'] += 1
            continue
        if len(p['records']) != 1:
            excluded['Separate E/M report cards require complete grade-band union audit'] += 1
            continue
        row = p['records'][0]
        n, low, pct, income_reason = income(p)
        outcomes = {}
        for subject, native in [('math', 'M'), ('reading', 'E')]:
            proficiency, tested, reason = outcome(row, native)
            outcomes[subject] = dict(proficiency=proficiency, tested=tested, valid_score_evidence=VALID_SCORE if tested is not None else None,
                source='native', source_row=row['source_row'], raw=row,
                raw_tested=dict(formula='sum(four independently visible actual score-level counts)',
                    eligible_total=row[native + '_NbrTOT'], not_tested=row[native + '_NbrNotTest']),
                exclusion='; '.join(filter(None, [income_reason, reason])) if pct is None or proficiency is None else None)
        schools.append(dict(id=key, name=d['SCH_NAME'], district_id=key[:4], district=d['LEA_NAME'], city=d['LCITY'],
            cohort='grade', enrollment=n, low_income=low, income=pct, income_source='income', income_row=p['income_row'],
            income_raw=dict(pip_record=p['income_record'], headcount_record=p['headcount_record'], academic_year='2024-25', day=135),
            directory_raw=d, membership_grades_raw=p['membership_grades'], outcomes=outcomes))
    assessment = 'South Carolina FAY SC READY + SC-Alt actual scored · Day135 PIP'
    scope = 'South Carolina operational grade schools with a single E/M report card, actual FAY score-level counts and individual Day135 PIP'
    return dict(dataset=DATASET, state=dict(id='SC', name='South Carolina'), year=YEAR, academic_year='2024–25',
        name='South Carolina actual scored 2024–25 · Day135 PIP', model_scope=scope, region='south-carolina',
        prepare_script='scripts/prepare_south_carolina.py', source_url=PORTAL, retrieved=payload['retrieved'], sources=payload['sources'], schools=schools,
        income_definition=dict(label='Individual Pupils in Poverty · three-year eligibility lookback', definition=ECON, url=MANUAL),
        cohorts=[dict(id='grade', level='ES', assessment=assessment, grades='3–8 at verified single-report-card grade schools',
            standard=STANDARD, source_url=MANUAL, source='native', label='Grade schools · FAY actual scored', outcome='SC READY Levels 3/4 + SC-Alt Meets/Exceeds',
            note='Actual scored FAY fraction · general + alternate · individual Day135 PIP')],
        coverage_note=ECON + ' ' + STANDARD,
        methodology=dict(summary='South Carolina uses actual FAY score-level counts, excluding separately reported nonparticipants, with individual Day135 PIP. SC READY and alternate thresholds are explicit; PIP eligibility has a three-year lookback.',
            details=[ECON, STANDARD,
                'Native numeric SIDN values are preserved and formatted to the authoritative seven-digit width, matching native Day135 string IDs and 2024–25 CCD SC-district(4)-school(3). Complete reported historical grade offers and reconciled grade enrollment exclude high schools. There is no name join or current-directory backfill. Map coordinates are unavailable.',
                'The official all-test-taker SC READY grade workbook describes a different regular-only population; the research workbook describes FAY general + alternate. They are not spliced together. The separate published report-card Poverty Index is not substituted for exact Day135 individual counts. Native percentages/counts and protected Not Tested values remain audit evidence.',
                'Separate full-state Math, ELA and Combined models use externally studentized residuals. Combined is the equally weighted Math/ELA mean. Filters do not refit; state thresholds are not a national scale, and results describe associations, not causal effectiveness or school quality.'],
            sources=[dict(label='Official 2025 research data', url=NATIVE), dict(label='2024–25 actual score-bin/FAY/alternate/PIP definitions', url=MANUAL),
                dict(label='Individual Day135 PIP counts and enrollment', url=INCOME), dict(label='Same-day enrolled grades', url=GRADES),
                dict(label='Historical CCD directory', url=payload['sources']['ccd_directory']['url'])]),
        source_audit=dict(native_school_profiles=len(seen), grade_school_profiles=len(schools), excluded=dict(excluded),
            income_unavailable=sum(s['income'] is None for s in schools), headcount_audit=payload['headcount_audit'],
            score_denominator='Sum of independently visible actual achievement-level counts; native eligible total not used',
            income_scope='Individual Day135 current-membership PIP with three-year benefits eligibility lookback', mapped=0))


def prepare(database=DEFAULT_DB):
    result = prepare_snapshot(normalize(json.loads(EXTRACT.read_text())), EXTRACT, OUTPUT, database)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract:
        extract()
    prepare(args.database)
