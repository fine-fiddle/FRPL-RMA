"""Mississippi 2024–25 complete regular MAAP grade counts and individual CCD DC."""
import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import re

import openpyxl

from audit_national_sources import DIRECTORY, LUNCH, MEMBERSHIP, read_ccd, membership_cache, source
from database import ROOT, DEFAULT_DB
from prepare_ccd_states import grade_school
from state_registry import reported_count
from state_snapshot import prepare_snapshot

DATASET = 'ms-maap-dc-2025'
YEAR = 2025
EXTRACT = ROOT / 'data/source/mississippi.json'
OUTPUT = ROOT / 'data/mississippi'
PORTAL = 'https://mdek12.org/specialeducation/spp-apr/'
NATIVE = 'https://mdek12.org/wp-content/uploads/sites/39/2026/02/School-MAAP-Proficiency.xlsx'
STATE_TOTALS = 'https://mdek12.org/wp-content/uploads/sites/39/2026/02/State-MAAP-Proficiency.xlsx'
PROTOCOL = 'https://mdek12.org/wp-content/uploads/sites/39/2026/02/C-Protocol-618-Assessment-REVISED.pdf'
INDICATOR = 'https://mdek12.org/wp-content/uploads/sites/39/2026/02/K-Protocol-Indicator-3-Assessment-REVISED.pdf'
APR = 'https://mdek12.org/wp-content/uploads/sites/39/2026/08/MS-01-SPP-PART-B-FFY-2024-25-3833-20260622085050.pdf'
GUIDE = 'https://msrc.mdek12.org/downloads/MSRCUserGuide.pdf'
DC_GUIDE = 'https://msachieves.mdek12.org/wp-content/uploads/2024/07/2024-25-Administrator-Calendar-Dates-to-Remember.pdf'
HEADER = ['YEAR', 'Subject', 'District ID', 'District', 'School ID', 'School', 'Student Group', 'Grade', 'Assessment Type', 'Number Proficient', 'Number Not Proficient']
DIRECTORY_FIELDS = ['SCHOOL_YEAR', 'ST', 'NCESSCH', 'ST_SCHID', 'LEAID', 'SCH_NAME',
    'LEA_NAME', 'LCITY', 'UPDATED_STATUS', 'GSLO', 'GSHI', 'IGOFFERED',
    'G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
ECON = ('Individually reported same-year CCD Direct Certification Education Unit Total divided by positive '
    'reported CCD Membership Education Unit Total, including pre-K where enrolled. This benefits-based '
    'eligibility proxy is narrower than application-based FRPL. Mississippi\'s 2024–25 administrator calendar '
    'requires regular direct certification matches for SNAP-eligible students; NCES identifies DC as '
    'individual eligibility, distinct from universal free-meal recipients and CEP claiming percentages. '
    'No FRPL fallback, CEP multiplier or prior-year income is used. Membership is fall enrollment; '
    'matching academic years does not establish identical collection dates. CCD notes one Mississippi '
    'school with absent LEA FRPL reporting; this does not authorize replacing individually reported DC.')
STANDARD = ('2024–25 native regular MAAP All-student proficient and not-proficient counts are summed '
    'across every required offered/enrolled grade 3–8 at operational grade schools. Every grade must '
    'have both independently visible integer counts; NR, ranges, missing grades and other protected '
    'cells make the entire subject unavailable. The 2025 assessment protocol excludes voided, incomplete '
    'and irregular scores before warehouse reporting. The Indicator 3 protocol defines proficiency '
    'among valid scores and includes full-academic-year and non-full-academic-year students. Native '
    'state grade 4/8 totals independently match the 2024–25 SPP/APR valid-score counts. No participation, '
    'enrollment or 95% denominator is substituted. Proficient means MAAP Level 4 or 5; Level 3 Passing '
    'is not proficient. Alternate MAAP-A, high-school EOCs and science are outside this response. '
    'The complete-count population supports propagated sampling intervals; it differs from report-card '
    'accountability/FAY rates and the first-time media release. This is a single 2025 snapshot.')
VALID_SCORE = PROTOCOL + ' pp.8–9,13; ' + INDICATOR + ' pp.1–2,5; ' + APR + ' pp.35–36'


def identity(row):
    district, school = row['District ID'], row['School ID']
    if not all(isinstance(v, str) and re.fullmatch(p, v) for p, v in [(r'\d{4}', district), (r'\d{3}', school)]):
        raise ValueError('Invalid native Mississippi district/school identity')
    return district + '-' + school, 'MS-' + district + '-' + district + school


def count(value):
    if value is None or value in ['', 'NR', '<10', '*', '---', 'N/A']:
        return None
    if isinstance(value, str) and (re.search(r'[<>]', value) or re.fullmatch(r'\d+\s*-\s*\d+', value)):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d+', value):
        raise ValueError('Mississippi native count schema changed')
    return int(value)


def income(profile):
    n, low = reported_count(profile['membership']), reported_count(profile['direct_certification'])
    if n is None or n <= 0 or low is None:
        return n, None, None, 'Same-year individual CCD direct certification or membership unavailable'
    if low > n:
        return n, None, None, 'Individual direct certification exceeds membership'
    direct = profile['direct_certification']
    if direct['DATA_GROUP'] != 'Direct Certification' or direct['TOTAL_INDICATOR'] != 'Education Unit Total':
        raise ValueError('Mississippi income is outside the approved individual category')
    state_id = 'MS-' + profile['id'][:4] + '-' + profile['id'].replace('-', '')
    for row in [profile['membership'], direct]:
        if row['SCHOOL_YEAR'] != '2024-2025' or row['ST'] != 'MS' or row['NCESSCH'] != profile['directory']['NCESSCH'] or row['ST_SCHID'] != state_id:
            raise ValueError('Mississippi economic join crossed identity, state or year')
    return n, low, 100 * low / n, None


def workbook_rows(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = iter(workbook.active.values)
    header = next(rows)
    for i, values in enumerate(rows, 2):
        if any(v is not None for v in values):
            yield i, dict(zip(header, values))
    workbook.close()


def extract():
    directory = {r['ST_SCHID']: r for r in read_ccd(DIRECTORY) if r['ST'] == 'MS'}
    lunch = {r['NCESSCH']: (i, r) for i, r in enumerate(read_ccd(LUNCH), 2)
        if r['ST'] == 'MS' and r['DATA_GROUP'] == 'Direct Certification'}
    membership = membership_cache()
    grouped = defaultdict(list)
    for number, row in workbook_rows(ROOT / 'data/raw/ms_school_proficiency_2025.xlsx'):
        if list(row) != HEADER or row['YEAR'] != '2024' or row['Assessment Type'] != 'Regular Assessment':
            raise ValueError('Mississippi source schema, academic start year or assessment changed')
        key, state_id = identity(row)
        if row['Student Group'] == 'All':
            grouped[key].append(dict(row, source_row=number))
    profiles = []
    for key, rows in grouped.items():
        d = directory.get(identity(rows[0])[1])
        nces = None if d is None else d['NCESSCH']
        total = membership['totals'].get(nces)
        profiles.append(dict(id=key, records=rows,
            directory=None if d is None else {f: d[f] for f in DIRECTORY_FIELDS},
            membership=None if total is None else dict(total, SCHOOL_YEAR='2024-2025', TOTAL_INDICATOR='Education Unit Total'),
            membership_grades=membership['grades'].get(nces),
            income_row=lunch.get(nces, (0, None))[0], direct_certification=lunch.get(nces, (0, None))[1]))
    sources = {key: source(ROOT / 'data/raw' / filename, url) for key, filename, url in [
        ('native', 'ms_school_proficiency_2025.xlsx', NATIVE), ('state_totals', 'ms_state_proficiency_2025.xlsx', STATE_TOTALS),
        ('portal', 'ms_sped.html', PORTAL), ('protocol', 'ms_idea_protocol_2025.pdf', PROTOCOL),
        ('indicator', 'ms_idea_indicator3_2025.pdf', INDICATOR), ('apr', 'ms_apr_2025.pdf', APR),
        ('guide', 'ms_reportcard_guide.pdf', GUIDE), ('dc_guide', 'ms_calendar_2025.pdf', DC_GUIDE),
        ('unused_reportcard', 'ms_reportcard_2025.xlsx', 'https://msrc.mdek12.org/downloads/2024-2025ReportCardData.xlsx'),
        ('unused_media', 'ms_maap_2025.xlsx', 'https://mdek12.org/wp-content/uploads/sites/33/2025/08/2025_maap_mediafile_ELA_MATH.xlsx'),
        ('ccd_directory', DIRECTORY + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + DIRECTORY + '.zip'),
        ('ccd_membership', MEMBERSHIP + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + MEMBERSHIP + '.zip'),
        ('ccd_lunch', LUNCH + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + LUNCH + '.zip'),
        ('ccd_notes', 'SY_2024-25_CCD_Final_2a_Data_Notes.xlsx', 'https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx'),
        ('nces_definition', 'ccd-lunch-definition.html', 'https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data')]}
    payload = dict(state='MS', year=YEAR, academic_year='2024-25', native_start_year='2024', retrieved=str(date.today()), sources=sources,
        profiles=profiles, state_totals=[dict(r, source_row=i) for i, r in workbook_rows(ROOT / 'data/raw/ms_state_proficiency_2025.xlsx')],
        apr_all_valid_counts=dict(ELA={'04': 30437, '08': 32025}, MATH={'04': 30404, '08': 32009}),
        state_lunch_notes=[r for r in json.loads((ROOT / 'data/raw/ccd-2025-lunch-state-notes.json').read_text()) if r['State or Jurisdiction'] == 'Mississippi'])
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
    return payload


def aggregate(profile, subject):
    d, grades = profile['directory'], profile['membership_grades']
    required = [str(g).zfill(2) for g in range(3, 9) if d[f'G_{g}_OFFERED'] == 'Yes' or int(grades.get(f'Grade {g}', {}).get('STUDENT_COUNT', '0')) > 0]
    rows = [r for r in profile['records'] if r['Subject'].strip() == subject]
    observed = [r['Grade'] for r in rows]
    # A high-school/EOC row at a grade school cannot silently become grade Math.
    if not required or sorted(observed) != required:
        return None, None, 'Incomplete or extra native grades for required grade-school response', rows, required
    values = [(count(r['Number Proficient']), count(r['Number Not Proficient'])) for r in rows]
    if any(p is None or q is None for p, q in values):
        return None, None, 'A required grade has suppressed, ranged or unavailable native achievement counts', rows, required
    proficient, valid = sum(p for p, q in values), sum(p + q for p, q in values)
    if valid <= 0:
        return None, None, 'Zero native valid-score count', rows, required
    return 100 * proficient / valid, valid, None, rows, required


def normalize(payload):
    if (payload['state'], payload['year'], payload['academic_year'], payload['native_start_year']) != ('MS', YEAR, '2024-25', '2024'):
        raise ValueError('Wrong Mississippi state/year/native start year')
    for subject, grades in payload['apr_all_valid_counts'].items():
        for grade, expected in grades.items():
            matches = [r for r in payload['state_totals'] if r['Subject'].strip() == subject and r['Grade'] == grade and r['Student Group'] == 'All' and r['Assessment Type'] == 'Regular Assessment' and r['YEAR'] == '2024']
            if len(matches) != 1 or count(matches[0]['Number Proficient']) + count(matches[0]['Number Not Proficient']) != expected:
                raise ValueError('Native state counts disagree with audited APR valid-score evidence')
    schools, excluded, seen = [], Counter(), set()
    for profile in payload['profiles']:
        key, d = profile['id'], profile['directory']
        if key in seen:
            raise ValueError('Duplicate Mississippi school profile')
        seen.add(key)
        row_seen = set()
        for r in profile['records']:
            token = (r['Subject'].strip(), r['Grade'])
            if identity(r)[0] != key or list(r) != HEADER + ['source_row'] or r['YEAR'] != '2024' or r['Student Group'] != 'All' or r['Assessment Type'] != 'Regular Assessment' or token in row_seen:
                raise ValueError('Mississippi duplicate grade, identity, year or native schema changed')
            if token[0] not in ['ELA', 'MATH', 'SCIENCE'] or token[1] not in [str(g).zfill(2) for g in range(3, 9)] + ['HS']:
                raise ValueError('Mississippi native grade/subject scope changed')
            row_seen.add(token)
        if d is None:
            excluded['Missing exact same-year CCD state-ID directory match'] += 1
            continue
        if (d['SCHOOL_YEAR'], d['ST'], d['ST_SCHID']) != ('2024-2025', 'MS', identity(profile['records'][0])[1]):
            raise ValueError('Mississippi directory join crossed state, year or identity')
        if d['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8'] or not grade_school(d, profile['membership_grades'], profile['membership']):
            excluded['Outside verified operational grade-school scope'] += 1
            continue
        n, low, pct, income_reason = income(profile)
        outcomes = {}
        for subject, native in [('math', 'MATH'), ('reading', 'ELA')]:
            proficiency, tested, reason, rows, required = aggregate(profile, native)
            outcomes[subject] = dict(proficiency=proficiency, tested=tested, valid_score_evidence=VALID_SCORE if tested is not None else None,
                source='native', source_row=rows[0]['source_row'] if rows else 0, raw=rows,
                raw_tested=dict(required_grades=required, formula='sum(Number Proficient + Number Not Proficient)'),
                exclusion='; '.join(filter(None, [income_reason, reason])) if pct is None or proficiency is None else None)
        schools.append(dict(id=key, name=d['SCH_NAME'], district_id=key[:4], district=d['LEA_NAME'], city=d['LCITY'],
            cohort='grade', enrollment=n, low_income=low, income=pct, income_source='ccd_lunch', income_row=profile['income_row'],
            income_raw=dict(direct_certification=profile['direct_certification'], membership=profile['membership']),
            directory_raw=d, membership_grades_raw=profile['membership_grades'], outcomes=outcomes))
    assessment = 'Mississippi regular MAAP complete grades 3–8 · CCD DC'
    scope = 'Mississippi operational grade schools with complete native regular MAAP grade counts and individual same-year CCD direct certification'
    return dict(dataset=DATASET, state=dict(id='MS', name='Mississippi'), year=YEAR, academic_year='2024–25',
        name='Mississippi MAAP 2024–25 · CCD direct certification', model_scope=scope, region='mississippi',
        prepare_script='scripts/prepare_mississippi.py', source_url=PORTAL, retrieved=payload['retrieved'], sources=payload['sources'], schools=schools,
        income_definition=dict(label='Individual direct certification', definition=ECON, url=DC_GUIDE),
        cohorts=[dict(id='grade', level='ES', assessment=assessment, grades='Complete offered/enrolled grades 3–8 at verified grade schools',
            standard=STANDARD, source_url=PROTOCOL, source='native', label='Grade schools · regular MAAP', outcome='MAAP Level 4 or 5',
            note='Complete native valid-score counts · individual CCD DC')],
        coverage_note=ECON + ' ' + STANDARD,
        methodology=dict(summary='Mississippi sums complete published regular MAAP proficient and not-proficient grade counts with individual same-year CCD direct certification. Missing or protected grades exclude the entire subject; valid counts support sampling intervals.',
            details=[ECON, STANDARD,
                'Exact native four-digit district and three-digit school IDs join 2024–25 CCD ST_SCHID=MS-district-districtschool. Historical grade offers and reconciled unadjusted enrolled grades exclude high-school, adult and ungraded programs. No name match or current directory backfill. Map coordinates are unavailable.',
                'The native YEAR field is academic start year 2024, explicitly labeled 2024–2025 on the official publication page and report selector. The report-card Math/English Proficiency fields describe a different accountability population, and its performance distributions differ from regular-only counts. The media file lacks school IDs and has different first-time totals. Neither source is blended into this response; their checksums remain audit evidence.',
                'Separate full-state Math, ELA and Combined models use externally studentized residuals. Combined is the equally weighted Math/ELA mean. Filters do not refit; state thresholds are not a national scale, and results describe associations, not causal effectiveness or school quality.'],
            sources=[dict(label='Official 2024–25 native assessment publication', url=PORTAL), dict(label='Native school grade counts', url=NATIVE),
                dict(label='Valid-score collection protocol', url=PROTOCOL), dict(label='Indicator proficiency definition', url=INDICATOR),
                dict(label='Independent same-year SPP/APR counts', url=APR), dict(label='2024–25 individual SNAP certification calendar', url=DC_GUIDE),
                dict(label='NCES individual DC definition', url=payload['sources']['nces_definition']['url'])]),
        source_audit=dict(native_school_profiles=len(seen), grade_school_profiles=len(schools), excluded=dict(excluded),
            income_unavailable=sum(s['income'] is None for s in schools), state_lunch_notes=payload['state_lunch_notes'],
            score_denominator='Complete regular-assessment proficient + not-proficient grade counts; invalid scores excluded by official protocol',
            apr_valid_count_check=payload['apr_all_valid_counts'], mapped=0))


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
