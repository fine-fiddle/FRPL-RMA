"""Oklahoma 2024–25 complete regular OSTP valid counts and individual CCD DC."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import json
from pathlib import Path
import re

from audit_national_sources import DIRECTORY, LUNCH, MEMBERSHIP, read_ccd, membership_cache, source
from database import ROOT, DEFAULT_DB
from prepare_ccd_states import grade_school
from state_registry import reported_count
from state_snapshot import prepare_snapshot

DATASET = 'ok-ostp-dc-2025'
YEAR = 2025
EXTRACT = ROOT / 'data/source/oklahoma.json'
OUTPUT = ROOT / 'data/oklahoma'
PORTAL = 'https://oklahoma.gov/education/services/assessments/state-testing-resources.html'
NATIVE = 'https://oklahoma.gov/content/dam/ok/en/osde/documents/services/assessments/state-testing-resources/2025-state-testing-resources/2425OKOSTPMediaRedacted.csv'
TECHNICAL = 'https://oklahoma.gov/content/dam/ok/en/osde/documents/services/assessments/state-testing-resources/24-25%20OK%20Tech%20Report%20to%20Appendix%20L.pdf'
BUSINESS = 'https://oklahoma.gov/content/dam/ok/en/osde/documents/services/assessments/state-testing-resources/24-25%20OK_TechReport_Part-II_AppM-V.pdf'
NUTRITION = 'https://oklahoma.gov/education/services/child-nutrition/documents.html'
DC_GUIDE = 'https://oklahoma.gov/content/dam/ok/en/osde/documents/services/child-nutrition/child-nutrition-documents/school-meal-program-various-documents-forms/2026%20School%20Training%20Manual.pdf'
DIRECTORY_FIELDS = ['SCHOOL_YEAR', 'ST', 'NCESSCH', 'ST_SCHID', 'LEAID', 'SCH_NAME',
    'LEA_NAME', 'LCITY', 'UPDATED_STATUS', 'GSLO', 'GSHI', 'IGOFFERED',
    'G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
FIELDS = ['Grade', 'CountyName', 'OrganizationId', 'Group', 'Administration'] + [s + ' - ' + f
    for s in ['ELA', 'Mathematics'] for f in ['Total N', 'Valid N', 'Below Basic No.', 'Below Basic %',
        'Basic No.', 'Basic %', 'Proficient No.', 'Proficient %', 'Advanced No.', 'Advanced %']]
ECON = ('Individually reported same-year CCD Direct Certification Education Unit Total divided by positive '
    'reported CCD Membership Education Unit Total, including pre-K where enrolled. This benefits-based '
    'eligibility proxy is narrower than application-based FRPL. NCES defines DC as individual categorical '
    'eligibility, distinct from universal free-meal recipients or CEP claiming percentages. Oklahoma publishes '
    'a separate 2025 CEP ISP/proxy-ISP notification and a low-income meal report; neither is substituted '
    'for this individual DC count. The state nutrition manual distinguishes individual WAVE certification '
    'codes, including Medicaid, from applications and universal meals; its July 2025 version is corroborating '
    'documentation, not a claim that the program mix was identical at the fall 2024 collection. No CEP '
    'multiplier, FRPL fallback or prior-year income is used. Matching academic years does not establish '
    'identical collection dates: CCD membership is fall enrollment.')
STANDARD = ('2024–25 regular OSTP grades 3–8 use Proficient plus Advanced student counts divided by '
    'native Valid N, summed across every required offered/enrolled grade at operational grade schools. '
    'Appendix V of the official same-year technical report defines valid participants as attempted, valid '
    'scores and explicitly excludes Did Not Attempt, exemption, invalidation and alternate-assessment '
    'records from tested aggregates. Total N includes such records and is never a substitute. Every required '
    'grade must publish its own valid N and both proficient counts; protected counts, absent grades and '
    'zero valid totals make the entire subject unavailable. Suppressed lower-level counts are not '
    'reconstructed. School totals are calculated from exact visible counts, not rounded percentages. '
    'OAAP alternate tests, science and high-school assessments are outside this response. In May 2025 '
    'CEQA rescinded the 2024 ELA/Math cut scores and restored the 2023 cuts for spring 2025 while retaining '
    'the 2024 descriptors. This is an explicit standards reset and a single 2025 snapshot, not connected '
    '2024 history. Valid counts support propagated sampling intervals. This response differs from '
    'report-card FAY achievement points and targets.')
VALID_SCORE = BUSINESS + ' Appendix V pp.14–18,22 (PDF pp.742–746,750)'


def identity(key):
    if not isinstance(key, str) or not re.fullmatch(r'\d{2}[A-Z]\d{3}\d{3}', key):
        raise ValueError('Invalid native Oklahoma nine-character school identity')
    district = key[:2] + '-' + key[2:6]
    return district, 'OK-' + district + '-' + district + '-' + key[6:]


def count(value):
    if value in [None, '', '***', 'N/A', '*', '---'] or isinstance(value, str) and (re.search(r'[<>]', value) or re.fullmatch(r'\d+\s*-\s*\d+', value)):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d+', value):
        raise ValueError('Invalid Oklahoma native count schema')
    return int(value)


def income(profile):
    n, low = reported_count(profile['membership']), reported_count(profile['direct_certification'])
    if n is None or n <= 0 or low is None:
        return n, None, None, 'Same-year individual CCD DC or membership unavailable'
    if low > n:
        return n, None, None, 'Individual direct certification exceeds membership'
    direct = profile['direct_certification']
    if direct['DATA_GROUP'] != 'Direct Certification' or direct['TOTAL_INDICATOR'] != 'Education Unit Total':
        raise ValueError('Oklahoma income is outside the individual category')
    for row in [direct, profile['membership']]:
        if (row['SCHOOL_YEAR'], row['ST'], row['ST_SCHID'], row['NCESSCH']) != ('2024-2025', 'OK', identity(profile['id'])[1], profile['directory']['NCESSCH']):
            raise ValueError('Oklahoma economic join crossed identity, state or year')
    return n, low, 100 * low / n, None


def extract():
    directory = {r['ST_SCHID']: r for r in read_ccd(DIRECTORY) if r['ST'] == 'OK'}
    lunch = {r['NCESSCH']: (i, r) for i, r in enumerate(read_ccd(LUNCH), 2)
        if r['ST'] == 'OK' and r['DATA_GROUP'] == 'Direct Certification'}
    membership = membership_cache()
    grouped = defaultdict(list)
    with (ROOT / 'data/raw/ok_ostp_2025.csv').open(encoding='utf-8-sig', newline='') as file:
        for i, row in enumerate(csv.DictReader(file), 2):
            if row['Administration'] != '2425' or row['Grade'] not in [str(g).zfill(2) for g in range(3, 9)]:
                raise ValueError('Oklahoma native administration/grade changed')
            if len(row['OrganizationId']) == 9:
                identity(row['OrganizationId'])
                grouped[row['OrganizationId']].append(dict({f: row[f] for f in FIELDS}, source_row=i))
    profiles = []
    for key, records in grouped.items():
        d = directory.get(identity(key)[1])
        nces = None if d is None else d['NCESSCH']
        total = membership['totals'].get(nces)
        profiles.append(dict(id=key, records=records,
            directory=None if d is None else {f: d[f] for f in DIRECTORY_FIELDS},
            membership=None if total is None else dict(total, SCHOOL_YEAR='2024-2025', TOTAL_INDICATOR='Education Unit Total'),
            membership_grades=membership['grades'].get(nces), income_row=lunch.get(nces, (0, None))[0],
            direct_certification=lunch.get(nces, (0, None))[1]))
    sources = {key: source(ROOT / 'data/raw' / filename, url) for key, filename, url in [
        ('native', 'ok_ostp_2025.csv', NATIVE), ('portal', 'ok_assessment_resources_2025.html', PORTAL),
        ('technical', 'ok_technical_2025.pdf', TECHNICAL), ('business', 'ok_technical_part2_2025.pdf', BUSINESS),
        ('nutrition', 'ok_child_nutrition_documents.html', NUTRITION), ('dc_guide', 'ok_nutrition_2026.pdf', DC_GUIDE),
        ('unused_low_income', 'ok_income_2025.xlsx', 'https://oklahoma.gov/content/dam/ok/en/osde/documents/services/child-nutrition/documents/2025_Low%20Income%20Report.xlsx'),
        ('unused_cep', 'ok_cep_2025.xlsx', 'https://oklahoma.gov/content/dam/ok/en/osde/documents/services/child-nutrition/child-nutrition-documents/community-eligibility-provision/Community%20Eligibility%20Proxy%20for%20Districts%20and%20Sites%202025%20v2.xlsx'),
        ('unused_reportcard', 'ok_performance_2025.csv', 'https://oklaschools.com/download-data/'),
        ('ccd_directory', DIRECTORY + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + DIRECTORY + '.zip'),
        ('ccd_membership', MEMBERSHIP + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + MEMBERSHIP + '.zip'),
        ('ccd_lunch', LUNCH + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + LUNCH + '.zip'),
        ('ccd_notes', 'SY_2024-25_CCD_Final_2a_Data_Notes.xlsx', 'https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx'),
        ('nces_definition', 'ccd-lunch-definition.html', 'https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data')]}
    payload = dict(state='OK', year=YEAR, academic_year='2024-25', administration='2425', retrieved=str(date.today()),
        sources=sources, profiles=profiles,
        state_lunch_notes=[r for r in json.loads((ROOT / 'data/raw/ccd-2025-lunch-state-notes.json').read_text()) if r['State or Jurisdiction'] == 'Oklahoma'])
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
    return payload


def aggregate(profile, subject):
    d, grades, rows = profile['directory'], profile['membership_grades'], profile['records']
    required = [str(g).zfill(2) for g in range(3, 9) if d[f'G_{g}_OFFERED'] == 'Yes' or int(grades.get(f'Grade {g}', {}).get('STUDENT_COUNT', '0')) > 0]
    if not required or sorted(r['Grade'] for r in rows) != required:
        return None, None, 'Incomplete or extra native grades for required grade-school response', required
    values = [(count(r[subject + ' - Valid N']), count(r[subject + ' - Proficient No.']), count(r[subject + ' - Advanced No.'])) for r in rows]
    if any(v is None for tup in values for v in tup):
        return None, None, 'A required grade has protected or unavailable native valid/proficient counts', required
    for row, (n, p, a) in zip(rows, values):
        if p + a > n:
            raise ValueError('Oklahoma proficient counts exceed valid scores')
        lower = [count(row[subject + ' - ' + f]) for f in ['Below Basic No.', 'Basic No.']]
        if all(v is not None for v in lower) and sum(lower) + p + a != n:
            raise ValueError('Oklahoma visible performance distribution does not match valid scores')
    valid, proficient = sum(n for n, p, a in values), sum(p + a for n, p, a in values)
    if valid <= 0:
        return None, None, 'Zero native valid-score count', required
    return 100 * proficient / valid, valid, None, required


def normalize(payload):
    if (payload['state'], payload['year'], payload['academic_year'], payload['administration']) != ('OK', YEAR, '2024-25', '2425'):
        raise ValueError('Wrong Oklahoma state/year/administration')
    schools, excluded, seen = [], Counter(), set()
    for profile in payload['profiles']:
        key, d = profile['id'], profile['directory']
        district, state_id = identity(key)
        if key in seen:
            raise ValueError('Duplicate Oklahoma school profile')
        seen.add(key)
        row_seen = set()
        for r in profile['records']:
            if list(r) != FIELDS + ['source_row'] or r['OrganizationId'] != key or r['Administration'] != '2425' or r['Grade'] not in [str(g).zfill(2) for g in range(3, 9)] or r['Grade'] in row_seen:
                raise ValueError('Oklahoma duplicate grade, native identity/year/schema changed')
            row_seen.add(r['Grade'])
        if d is None:
            excluded['Missing exact same-year CCD state-ID directory match'] += 1
            continue
        if (d['SCHOOL_YEAR'], d['ST'], d['ST_SCHID']) != ('2024-2025', 'OK', state_id):
            raise ValueError('Oklahoma directory join crossed state, year or identity')
        if d['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8'] or not grade_school(d, profile['membership_grades'], profile['membership']):
            excluded['Outside verified operational grade-school scope'] += 1
            continue
        n, low, pct, income_reason = income(profile)
        outcomes = {}
        for subject, native in [('math', 'Mathematics'), ('reading', 'ELA')]:
            proficiency, tested, reason, required = aggregate(profile, native)
            outcomes[subject] = dict(proficiency=proficiency, tested=tested, valid_score_evidence=VALID_SCORE if tested is not None else None,
                source='native', source_row=profile['records'][0]['source_row'], raw=profile['records'],
                raw_tested=dict(required_grades=required, formula='sum(native subject Valid N)'),
                exclusion='; '.join(filter(None, [income_reason, reason])) if pct is None or proficiency is None else None)
        schools.append(dict(id=key, name=d['SCH_NAME'], district_id=district, district=d['LEA_NAME'], city=d['LCITY'],
            cohort='grade', enrollment=n, low_income=low, income=pct, income_source='ccd_lunch', income_row=profile['income_row'],
            income_raw=dict(direct_certification=profile['direct_certification'], membership=profile['membership']),
            directory_raw=d, membership_grades_raw=profile['membership_grades'], outcomes=outcomes))
    assessment = 'Oklahoma regular OSTP complete grades 3–8 · 2025 reset · CCD DC'
    scope = 'Oklahoma operational grade schools with complete visible regular OSTP valid/proficient counts and individual same-year CCD DC'
    return dict(dataset=DATASET, state=dict(id='OK', name='Oklahoma'), year=YEAR, academic_year='2024–25',
        name='Oklahoma OSTP 2024–25 · CCD direct certification', model_scope=scope, region='oklahoma',
        prepare_script='scripts/prepare_oklahoma.py', source_url=PORTAL, retrieved=payload['retrieved'], sources=payload['sources'], schools=schools,
        income_definition=dict(label='Individual direct certification', definition=ECON, url=payload['sources']['nces_definition']['url']),
        cohorts=[dict(id='grade', level='ES', assessment=assessment, grades='Complete offered/enrolled grades 3–8 at verified grade schools',
            standard=STANDARD, source_url=BUSINESS, source='native', label='Grade schools · regular OSTP', outcome='Proficient or Advanced',
            note='2025 standards reset · complete valid-score counts · individual CCD DC')],
        coverage_note=ECON + ' ' + STANDARD,
        methodology=dict(summary='Oklahoma sums complete visible regular OSTP valid and proficient grade counts with individual same-year CCD direct certification. The 2025 cut-score reset is explicit; unavailable grades exclude the entire subject.',
            details=[ECON, STANDARD,
                'Native county (2), district (4) and school (3) characters deterministically join 2024–25 CCD ST_SCHID=OK-county-district-county-district-school. Historical grade offers and reconciled unadjusted grade enrollment exclude high-school, adult and ungraded programs. No name match or current directory backfill. Map coordinates are unavailable.',
                'Appendix V preserves other-placement exclusion rules and independently masks small totals and performance-level cells. Visible Proficient and Advanced counts may be summed while protected lower-level cells remain untouched; protected required proficient cells never become a response. The broader report-card contextual download is retained as audit evidence and does not fill protected counts.',
                'Separate full-state Math, ELA and Combined models use externally studentized residuals. Combined is the equally weighted Math/ELA mean. Filters do not refit; state thresholds are not a national scale, and results describe associations, not causal effectiveness or school quality.'],
            sources=[dict(label='Official 2024–25 assessment downloads', url=PORTAL), dict(label='Native redacted grade counts', url=NATIVE),
                dict(label='Same-year valid-score and redaction business rules', url=BUSINESS), dict(label='2025 cut-score reset', url=TECHNICAL),
                dict(label='NCES individual DC definition', url=payload['sources']['nces_definition']['url']), dict(label='State meal/CEP reports', url=NUTRITION)]),
        source_audit=dict(native_school_profiles=len(seen), grade_school_profiles=len(schools), excluded=dict(excluded),
            income_unavailable=sum(s['income'] is None for s in schools), state_lunch_notes=payload['state_lunch_notes'],
            score_denominator='Complete native Valid N; only Valid Participant status Z, not Total N', standards_change='2025 restored 2023 cuts; 2024 descriptors retained', mapped=0))


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
