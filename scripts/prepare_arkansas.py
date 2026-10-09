"""Arkansas 2024–25 post-correction ATLAS school totals and individual CCD DC."""
import argparse
from collections import Counter
from datetime import date
import json
import math
from pathlib import Path
import re

import openpyxl

from audit_national_sources import DIRECTORY, LUNCH, MEMBERSHIP, read_ccd, membership_cache, source
from database import ROOT, DEFAULT_DB
from prepare_ccd_states import grade_school
from state_registry import reported_count
from state_snapshot import prepare_snapshot

DATASET = 'ar-atlas-dc-2025'
YEAR = 2025
EXTRACT = ROOT / 'data/source/arkansas.json'
OUTPUT = ROOT / 'data/arkansas'
PORTAL = 'https://dese.ade.arkansas.gov/Offices/public-school-accountability/assessment-test-scores/2025'
NATIVE = 'https://dese-admin.ade.arkansas.gov/Files/ATLAS_Summary_Post-Corrections_Scores_No-Grade_Spring_2025_PSA.xlsx'
GRADES = 'https://dese-admin.ade.arkansas.gov/Files/ATLAS_Summary_Post-Corrections_Scores_Spring_2025_PSA.xlsx'
BUSINESS = 'https://docs.google.com/document/d/1Qhf9liDMCPG34QAGGk4MQt5FrRwKhNNYMx5hLUGd2Dc/edit?usp=sharing'
DC_GUIDE = 'https://dese.ade.arkansas.gov/Files/Direct_Certification_7.5.22_COMM.pdf'
NOTES = 'https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx'
SUBJECTS = ['ELA', 'Reading', 'Math', 'Algebra', 'Geometry', 'Math Combined', 'Science', 'Biology', 'Science Combined']
DIRECTORY_FIELDS = ['SCHOOL_YEAR', 'ST', 'NCESSCH', 'ST_SCHID', 'LEAID', 'SCH_NAME',
    'LEA_NAME', 'LCITY', 'UPDATED_STATUS', 'GSLO', 'GSHI', 'IGOFFERED',
    'G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
HEADER = ['District LEA', 'District Name', 'School LEA', 'School Name'] + [s + ' ' + field
    for s in SUBJECTS for field in ['N Tested', '% Level 1', '% Level 2', '% Level 3', '% Level 4', '% Level 3 & 4']]
ECON = ('Individually reported same-year CCD Direct Certification Education Unit Total divided by positive '
    'reported CCD Membership Education Unit Total, including pre-K where enrolled. This benefits-based '
    'eligibility proxy is narrower than application-based FRPL. Arkansas direct certification guidance '
    'requires verified individual matches or documented household extension; high/low probability matches '
    'alone do not establish eligibility. It does not count every universal-free-meal recipient or use a CEP '
    'multiplier. The MySchoolInfo 2025 Direct Certification (Final) field is zero for 1,060 numeric school entries (15 unavailable) '
    'despite positive individual counts in CCD, and is not used. Native FRPL reporting at special '
    'provision schools has not been established as individual eligibility, so there is no FRPL fallback. '
    'Same academic year does not establish identical collection dates: CCD membership is fall.')
STANDARD = ('2024–25 post-correction ATLAS native Schools / No-Grade ELA and Math Level 3 & 4 rates '
    'at operational grade schools with complete same-year CCD offers and enrollment proving no high-school '
    'grades. ELA includes Reading and Writing and is distinct from the Reading component. Math is the '
    'grade-level Math assessment, distinct from Algebra, Geometry and Math Combined; advanced students '
    'taking only an EOC Math assessment are outside this response. At these grade schools tested grades '
    'are 3–8. Native schoolwide rates among tested score-level students are used without grade averaging '
    'or federal 95% accountability adjustment; DLM is separately published and is not included. Rates are '
    'published to one decimal. N Tested remains raw audit evidence; verified valid-score denominators '
    'are not imported and all sampling intervals are unavailable. Suppression, ranges and missingness '
    'remain unavailable. This is a single 2025 snapshot, not a continuation of ACT Aspire history.')


def school_id(row):
    district, school = row['District LEA'], row['School LEA']
    if not all(isinstance(v, str) and re.fullmatch(r'\d{7}', v) for v in [district, school]) or district[-2:] != '00' or district[:4] != school[:4]:
        raise ValueError('Invalid native authoritative Arkansas district/school LEA')
    return school


def rate(value):
    if value is None or value in ['', 'N<10', 'RV', 'N/A', '---', '*']:
        return None
    if not isinstance(value, str):
        raise ValueError('Arkansas workbook percent schema changed')
    if re.search(r'[<>]', value) or re.fullmatch(r'\d+(?:\.\d+)?%?\s*-\s*\d+(?:\.\d+)?%?', value):
        return None
    if not value.endswith('%'):
        raise ValueError('Arkansas native percentage unit missing')
    result = float(value[:-1])
    if not math.isfinite(result) or not 0 <= result <= 100:
        raise ValueError('Invalid Arkansas native rate')
    return result


def income(profile):
    n, low = reported_count(profile['membership']), reported_count(profile['direct_certification'])
    if n is None or n <= 0 or low is None:
        return n, None, None, 'Same-year individual CCD direct certification or membership unavailable'
    if low > n:
        return n, None, None, 'Individual direct certification exceeds membership'
    direct = profile['direct_certification']
    if direct['DATA_GROUP'] != 'Direct Certification' or direct['TOTAL_INDICATOR'] != 'Education Unit Total':
        raise ValueError('Arkansas income is outside the approved individual count category')
    state_id = 'AR-' + profile['record']['District LEA'] + '-' + profile['id']
    for row in [profile['membership'], direct]:
        if row['SCHOOL_YEAR'] != '2024-2025' or row['ST'] != 'AR' or row['NCESSCH'] != profile['directory']['NCESSCH'] or row['ST_SCHID'] != state_id:
            raise ValueError('Arkansas economic join crossed identity, state or year')
    return n, low, 100 * low / n, None


def workbook_rows(path, sheet):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = iter(workbook[sheet].values)
    header = next(rows)
    header = header[:next((i for i, v in enumerate(header) if v is None), len(header))]
    for i, values in enumerate(rows, 2):
        if any(v is not None for v in values):
            yield i, dict(zip(header, values))
    workbook.close()


def extract():
    directory = {r['ST_SCHID']: r for r in read_ccd(DIRECTORY) if r['ST'] == 'AR'}
    lunch = {r['NCESSCH']: (i, r) for i, r in enumerate(read_ccd(LUNCH), 2)
        if r['ST'] == 'AR' and r['DATA_GROUP'] == 'Direct Certification'}
    membership = membership_cache()
    profiles = []
    for number, record in workbook_rows(ROOT / 'data/raw/ar_atlas_all_2025.xlsx', 'Schools'):
        if list(record) != HEADER:
            raise ValueError('Arkansas native schoolwide workbook schema changed')
        key = school_id(record)
        d = directory.get('AR-' + record['District LEA'] + '-' + key)
        nces = None if d is None else d['NCESSCH']
        total = membership['totals'].get(nces)
        profiles.append(dict(id=key, record=record, source_row=number,
            directory=None if d is None else {f: d[f] for f in DIRECTORY_FIELDS},
            membership=None if total is None else dict(total, SCHOOL_YEAR='2024-2025', TOTAL_INDICATOR='Education Unit Total'),
            membership_grades=membership['grades'].get(nces),
            income_row=lunch.get(nces, (0, None))[0], direct_certification=lunch.get(nces, (0, None))[1]))
    sources = {key: source(ROOT / 'data/raw' / filename, url) for key, filename, url in [
        ('native', 'ar_atlas_all_2025.xlsx', NATIVE), ('native_grades', 'ar_atlas_grades_2025.xlsx', GRADES),
        ('assessment_page', 'ar_assessment_2025.html', PORTAL), ('business', 'ar_business_2025.txt', BUSINESS),
        ('dc_guide', 'ar_direct_certification.pdf', DC_GUIDE),
        ('unused_native_income', 'ar_native_income_export_2025.xlsx', 'https://myschoolinfo.arkansas.gov/Plus/Schools'),
        ('ccd_directory', DIRECTORY + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + DIRECTORY + '.zip'),
        ('ccd_membership', MEMBERSHIP + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + MEMBERSHIP + '.zip'),
        ('ccd_lunch', LUNCH + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + LUNCH + '.zip'),
        ('ccd_notes', 'SY_2024-25_CCD_Final_2a_Data_Notes.xlsx', NOTES),
        ('nces_definition', 'ccd-lunch-definition.html', 'https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data')]}
    unused = openpyxl.load_workbook(ROOT / 'data/raw/ar_native_income_export_2025.xlsx', read_only=True, data_only=True)
    rows = list(unused.active.values)
    if rows[2][7] != 'Direct Certification (Final)' or any(r[7] not in [0, 'N/A'] for r in rows[3:]):
        raise ValueError('Arkansas unused native DC anomaly changed; re-audit income')
    unused.close()
    payload = dict(state='AR', year=YEAR, academic_year='2024-25', retrieved=str(date.today()), sources=sources,
        native_sheet='Schools', native_release='Post-Corrections / No-Grade / Spring 2025', profiles=profiles,
        unused_native_dc=dict(year=2025, field='Direct Certification (Final)', school_rows=len(rows)-3, numeric_zero=sum(r[7] == 0 for r in rows[3:]), unavailable=sum(r[7] == 'N/A' for r in rows[3:]), nonzero=0),
        state_grade_rows=[dict(r, source_row=i) for i, r in workbook_rows(ROOT / 'data/raw/ar_atlas_grades_2025.xlsx', 'State')],
        state_lunch_notes=[r for r in json.loads((ROOT / 'data/raw/ccd-2025-lunch-state-notes.json').read_text()) if r['State or Jurisdiction'] == 'Arkansas'])
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
    return payload


def normalize(payload):
    if (payload['state'], payload['year'], payload['academic_year'], payload['native_sheet'], payload['native_release']) != (
        'AR', YEAR, '2024-25', 'Schools', 'Post-Corrections / No-Grade / Spring 2025'):
        raise ValueError('Wrong Arkansas state/year/native release')
    if [r['Grade'] for r in payload['state_grade_rows']] != [str(g).zfill(2) for g in range(3, 13)]:
        raise ValueError('Arkansas native grade schema changed')
    schools, excluded, seen = [], Counter(), set()
    for profile in payload['profiles']:
        key, d, row = profile['id'], profile['directory'], profile['record']
        if school_id(row) != key or key in seen or list(row) != HEADER:
            raise ValueError('Duplicate Arkansas school or incorrect native identity/schema')
        seen.add(key)
        if d is None:
            excluded['Missing exact same-year CCD state-ID directory match'] += 1
            continue
        if (d['SCHOOL_YEAR'], d['ST'], d['ST_SCHID']) != ('2024-2025', 'AR', 'AR-' + row['District LEA'] + '-' + key):
            raise ValueError('Arkansas directory join crossed state, year or identity')
        if d['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8'] or not grade_school(d, profile['membership_grades'], profile['membership']):
            excluded['Outside verified operational grade-school scope'] += 1
            continue
        n, low, pct, income_reason = income(profile)
        outcomes = {}
        for subject, native in [('math', 'Math'), ('reading', 'ELA')]:
            proficiency = rate(row[native + ' % Level 3 & 4'])
            reason = None if proficiency is not None else 'Native schoolwide ATLAS rate suppressed, ranged or unavailable'
            outcomes[subject] = dict(proficiency=proficiency, tested=None, source='native', source_row=profile['source_row'],
                raw=row, raw_tested=row[native + ' N Tested'],
                exclusion='; '.join(filter(None, [income_reason, reason])) if pct is None or proficiency is None else None)
        schools.append(dict(id=key, name=d['SCH_NAME'], district_id=row['District LEA'], district=d['LEA_NAME'], city=d['LCITY'],
            cohort='grade', enrollment=n, low_income=low, income=pct, income_source='ccd_lunch', income_row=profile['income_row'],
            income_raw=dict(direct_certification=profile['direct_certification'], membership=profile['membership']),
            directory_raw=d, membership_grades_raw=profile['membership_grades'], outcomes=outcomes))
    assessment = 'Arkansas ATLAS grades 3–8 · post-correction · CCD DC'
    scope = 'Arkansas operational grade schools with native post-correction ATLAS totals and individual same-year CCD direct certification'
    return dict(dataset=DATASET, state=dict(id='AR', name='Arkansas'), year=YEAR, academic_year='2024–25',
        name='Arkansas ATLAS 2024–25 · CCD direct certification', model_scope=scope, region='arkansas',
        prepare_script='scripts/prepare_arkansas.py', source_url=PORTAL, retrieved=payload['retrieved'], sources=payload['sources'], schools=schools,
        income_definition=dict(label='Individual direct certification', definition=ECON, url=DC_GUIDE),
        cohorts=[dict(id='grade', level='ES', assessment=assessment, grades='3–8 at schools with no high-school enrollment/offers',
            standard=STANDARD, source_url=BUSINESS, source='native', label='Grade schools · ATLAS', outcome='Level 3 or 4',
            note='Post-correction native school totals · individual CCD DC · intervals unavailable', allow_point_only=True)],
        coverage_note=ECON + ' ' + STANDARD,
        methodology=dict(summary='Arkansas uses post-correction native ATLAS Math and ELA school totals with individual same-year CCD direct certification. Income is a narrower benefits-based proxy, and sampling intervals are unavailable.',
            details=[ECON, STANDARD,
                'Exact native seven-digit district/school LEAs join CCD ST_SCHID=AR-district-school in 2024–25. Historical grade offers and complete unadjusted reported/derived enrolled-grade totals exclude high-school grades and adult/ungraded programs. No name match or current directory backfill. Map coordinates are unavailable.',
                'The public report generator uses an earlier two-decimal response release; it is retained only to audit the zero native DC anomaly. The adapter uses the explicitly labeled post-correction assessment workbook and does not splice response versions. Never infer protected counts from rates or complementary levels.',
                'Separate full-state Math, ELA and Combined models use externally studentized residuals. Combined is the equally weighted Math/ELA mean. Filters do not refit; state thresholds are not a national scale, and results describe associations, not causal effectiveness or school quality.'],
            sources=[dict(label='Official 2025 assessment downloads', url=PORTAL), dict(label='Native post-correction school totals', url=NATIVE),
                dict(label='2025 report-card business rules', url=BUSINESS), dict(label='Individual direct certification and special provision guidance', url=DC_GUIDE),
                dict(label='Same-year CCD directory', url=payload['sources']['ccd_directory']['url']),
                dict(label='NCES individual DC definition', url=payload['sources']['nces_definition']['url'])]),
        source_audit=dict(native_school_profiles=len(seen), grade_school_profiles=len(schools), excluded=dict(excluded),
            income_unavailable=sum(s['income'] is None for s in schools), unused_native_dc=payload['unused_native_dc'],
            state_lunch_notes=payload['state_lunch_notes'], approved_point_only=True,
            score_denominator='Native N Tested retained raw; no independently verified valid-score count imported', mapped=0))


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
