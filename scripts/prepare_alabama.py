"""Alabama 2024–25 native school totals and individual CCD direct certification."""
import argparse
from collections import Counter
import csv
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

DATASET = 'al-acap-dc-2025'
YEAR = 2025
EXTRACT = ROOT / 'data/source/alabama.json'
OUTPUT = ROOT / 'data/alabama'
PORTAL = 'https://reportcard.alsde.edu/SupportingData_Proficiency.aspx'
GLOSSARY = 'https://www.alabamaachieves.org/reports-data/school-data/glossary-of-terms/'
BUSINESS = 'https://www.alabamaachieves.org/reports-data/school-data/fed-rep-car-business-rules/'
NOTES = 'https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx'
NATIVE_FILTER = "[GradeName] = 'All Grades' And [GenderName] = 'All Gender' And [RaceName] = 'All Race' And [EthnicityName] = 'All Ethnicity' And [SubPopulationName] = 'All SubPopulation'"
CSV_FIELDS = ['System Code', 'School Code', 'Year', 'System', 'School', 'Subject', 'Grade',
    'Gender', 'Race', 'Ethnicity', 'Sub Population', 'Enrolled', 'Tested', 'Proficient',
    'Participation Rate', 'Proficient Rate', 'Level 1', 'Level 2', 'Level 3', 'Level 4',
    'Level 1 %', 'Level 2 %', 'Level 3 %', 'Level 4 %']
DIRECTORY_FIELDS = ['SCHOOL_YEAR', 'ST', 'NCESSCH', 'ST_SCHID', 'LEAID', 'SCH_NAME',
    'LEA_NAME', 'LCITY', 'UPDATED_STATUS', 'GSLO', 'GSHI', 'IGOFFERED',
    'G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
ECON = ('Reported school-level CCD 2024–25 Direct Certification Education Unit Total / positive reported '
    'same-year CCD Membership Education Unit Total, including pre-K where enrolled. Alabama explicitly '
    'includes students individually certified for both free and reduced meals, including Medicaid eligibility. '
    'This benefits-based proxy excludes application-only eligibility and does not count every CEP meal recipient. '
    'No CEP multiplier, uncertain Fall FRL fallback, tested-subgroup ratio or prior-year income is used. '
    'Alabama reports a roughly 6% decrease in directly certified students associated with Medicaid eligibility '
    'rollback in April 2025. Same academic year does not imply identical snapshot dates; membership is fall. '
    'Treat this definition and coverage separately from full FRPL and from other states.')
STANDARD = ('2024–25 native All Grades / All Gender / All Race / All Ethnicity / All SubPopulation '
    'Proficient Rate at operational grade schools with complete same-year grade offers and enrolled-grade '
    'counts proving no high-school grades. ACAP Summative and Alternate ELA/Math in grades 3–8, Levels 3 or 4 '
    'among the native valid-score proficiency population. This is the separately published unweighted '
    'participation/proficiency measure, not the weighted Academic Achievement Indicator, annual MIP targets '
    'or feeder-assigned accountability score. Native school totals are used without grade averaging. '
    'Published two-decimal rates only: native Tested is retained raw but not used as a proficiency denominator '
    'because it need not equal the response population, particularly for ELA exemptions. Sampling intervals '
    'are unavailable for all models. Suppressed *, ~, ranged and missing rates stay unavailable.')


def code(value, width):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,' + str(width) + '}', value):
        raise ValueError('Invalid authoritative Alabama code')
    return value.zfill(width)


def school_id(row):
    return code(row['System Code'], 3) + '-' + code(row['School Code'], 4)


def rate(value):
    if value in ['', '*', '~', 'N/A'] or re.search(r'[<>]', value) or re.fullmatch(r'\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?', value):
        return None
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 100:
        raise ValueError('Invalid Alabama native rate')
    return result


def validate_row(row):
    if (row['Year'], row['Grade'], row['Gender'], row['Race'], row['Ethnicity'], row['Sub Population']) != (
        '2025', 'All Grades', 'All Gender', 'All Race', 'All Ethnicity', 'All SubPopulation'):
        raise ValueError('Alabama native export crossed year or aggregate population')
    if row['Subject'] not in ['Math', 'ELA', 'Science']:
        raise ValueError('Unexpected Alabama assessment subject')


def income(profile):
    total, direct = profile['membership'], profile['direct_certification']
    n, low = reported_count(total), reported_count(direct)
    if n is None or n <= 0 or low is None:
        return n, None, None, 'Same-year individual CCD direct certification or membership unavailable'
    if low > n:
        return n, None, None, 'Individual-school direct certification exceeds membership'
    if direct['DATA_GROUP'] != 'Direct Certification' or direct['TOTAL_INDICATOR'] != 'Education Unit Total':
        raise ValueError('Alabama CCD income is outside the approved individual count category')
    for row in [total, direct]:
        if row['SCHOOL_YEAR'] != '2024-2025' or row['ST'] != 'AL' or row['NCESSCH'] != profile['directory']['NCESSCH'] or row['ST_SCHID'] != 'AL-' + profile['id']:
            raise ValueError('Alabama CCD economic join crossed identity, state or year')
    return n, low, 100 * low / n, None


def extract():
    directory = {r['ST_SCHID'].removeprefix('AL-'): r for r in read_ccd(DIRECTORY) if r['ST'] == 'AL'}
    lunch = {r['NCESSCH']: (i, r) for i, r in enumerate(read_ccd(LUNCH), 2)
             if r['ST'] == 'AL' and r['DATA_GROUP'] == 'Direct Certification'}
    membership = membership_cache()
    profiles = {}
    with (ROOT / 'data/raw/al_proficiency_2025.csv').open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames) != set(CSV_FIELDS):
            raise ValueError('Alabama native export schema changed or authoritative code columns absent')
        for number, row in enumerate(reader, 2):
            validate_row(row)
            if code(row['School Code'], 4) == '0000' or row['Subject'] == 'Science':
                continue
            key = school_id(row)
            if key not in profiles:
                d = directory.get(key)
                nces = None if d is None else d['NCESSCH']
                total = membership['totals'].get(nces)
                profiles[key] = dict(id=key, directory=None if d is None else {f: d[f] for f in DIRECTORY_FIELDS},
                    membership=None if total is None else dict(total, SCHOOL_YEAR='2024-2025', TOTAL_INDICATOR='Education Unit Total'),
                    membership_grades=membership['grades'].get(nces),
                    income_row=lunch.get(nces, (0, None))[0], direct_certification=lunch.get(nces, (0, None))[1], records=[])
            profiles[key]['records'].append(dict(row, source_row=number))
    sources = {key: source(ROOT / 'data/raw' / filename, url) for key, filename, url in [
        ('native', 'al_proficiency_2025.csv', PORTAL),
        ('glossary', 'al_glossary.html', GLOSSARY), ('business', 'al_business.html', BUSINESS),
        ('ccd_directory', DIRECTORY + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + DIRECTORY + '.zip'),
        ('ccd_membership', MEMBERSHIP + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + MEMBERSHIP + '.zip'),
        ('ccd_lunch', LUNCH + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + LUNCH + '.zip'),
        ('ccd_notes', 'SY_2024-25_CCD_Final_2a_Data_Notes.xlsx', NOTES),
        ('nces_definition', 'ccd-lunch-definition.html', 'https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data'),
        ('meal_codes', 'al_meal_status.txt', 'https://docs.google.com/document/d/1ZQOvtIocJhqNeyXM7uWNrYjTfGYYrjyb3Jk0ruh9xXk/edit'),
        ('native_math_workbook', 'al_math_2025.xlsx', 'https://www.alabamaachieves.org/wp-content/uploads/2025/08/RD_SP_2025813_2024-2025ParticipationandProficiencyMath_v1.xlsx'),
        ('native_ela_workbook', 'al_ela_2025.xlsx', 'https://www.alabamaachieves.org/wp-content/uploads/2025/08/RD_SP_2025813_2024-2025ParticipationandProficiencyELA_v1.xlsx')]}
    notes = json.loads((ROOT / 'data/raw/ccd-2025-lunch-state-notes.json').read_text())
    # The native ALL total includes only published grades 3–8 and 11, despite
    # ACAP also being administered in grade 2. Grade-school scope excludes 11.
    native_grades = {}
    for subject, filename, column in [('Math', 'al_math_2025.xlsx', 11), ('ELA', 'al_ela_2025.xlsx', 12)]:
        workbook = openpyxl.load_workbook(ROOT / 'data/raw' / filename, read_only=True, data_only=True)
        native_grades[subject] = [dict(grade=row[5], proficiency=row[column], sheet='State', source_row=i)
            for i, row in enumerate(workbook['State'].values, 1)
            if row[6:10] == ('All Gender', 'All Race', 'All Ethnicity', 'All SubPopulation')]
        workbook.close()
    payload = dict(state='AL', year=YEAR, academic_year='2024-25', retrieved=str(date.today()),
        sources=sources, native_filter=NATIVE_FILTER, profiles=list(profiles.values()),
        native_grade_rows=native_grades,
        state_lunch_notes=[r for r in notes if r['State or Jurisdiction'] == 'Alabama'])
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
    return payload


def normalize(payload):
    if (payload['state'], payload['year'], payload['academic_year'], payload['native_filter']) != ('AL', YEAR, '2024-25', NATIVE_FILTER):
        raise ValueError('Wrong Alabama state/year/native aggregate filter')
    for subject in ['Math', 'ELA']:
        if [r['grade'] for r in payload['native_grade_rows'][subject]] != ['ALL', '03', '04', '05', '06', '07', '08', '11']:
            raise ValueError('Alabama native reported grade scope changed')
    schools, excluded, seen = [], Counter(), set()
    for profile in payload['profiles']:
        key, d = profile['id'], profile['directory']
        records = {}
        for row in profile['records']:
            validate_row(row)
            if school_id(row) != key or row['Subject'] in records:
                raise ValueError('Alabama duplicate native subject or authoritative identity mismatch')
            records[row['Subject']] = row
        if key in seen:
            raise ValueError('Duplicate Alabama school profile')
        seen.add(key)
        if d is None:
            excluded['Missing exact same-year CCD state-ID directory match'] += 1
            continue
        if (d['SCHOOL_YEAR'], d['ST'], d['ST_SCHID']) != ('2024-2025', 'AL', 'AL-' + key):
            raise ValueError('Alabama directory join crossed state, year or identity')
        if d['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8'] or not grade_school(d, profile['membership_grades'], profile['membership']):
            excluded['Outside verified operational grade-school scope'] += 1
            continue
        n, low, pct, income_reason = income(profile)
        outcomes = {}
        for subject, label in [('math', 'Math'), ('reading', 'ELA')]:
            row = records.get(label)
            proficiency = None if row is None else rate(row['Proficient Rate'])
            reason = None if proficiency is not None else 'Native school proficiency rate suppressed, ranged or unavailable'
            outcomes[subject] = dict(proficiency=proficiency, tested=None,
                source='native', source_row=0 if row is None else row['source_row'], raw=row,
                raw_tested=None if row is None else row['Tested'],
                exclusion='; '.join(filter(None, [income_reason, reason])) if pct is None or proficiency is None else None)
        schools.append(dict(id=key, name=d['SCH_NAME'], district_id=key[:3], district=d['LEA_NAME'], city=d['LCITY'],
            cohort='grade', enrollment=n, low_income=low, income=pct, income_source='ccd_lunch', income_row=profile['income_row'],
            income_raw=dict(direct_certification=profile['direct_certification'], membership=profile['membership']),
            directory_raw=d, membership_grades_raw=profile['membership_grades'], outcomes=outcomes))
    assessment = 'Alabama ACAP Summative/Alternate grades 3–8 · CCD DC'
    scope = 'Alabama operational grade schools with native ACAP school totals and individual same-year CCD direct certification'
    return dict(dataset=DATASET, state=dict(id='AL', name='Alabama'), year=YEAR, academic_year='2024–25',
        name='Alabama ACAP 2024–25 · CCD direct certification', model_scope=scope, region='alabama',
        prepare_script='scripts/prepare_alabama.py', source_url=PORTAL, retrieved=payload['retrieved'],
        sources=payload['sources'], schools=schools,
        income_definition=dict(label='Individual direct certification (free and reduced)', definition=ECON, url=NOTES),
        cohorts=[dict(id='grade', level='ES', assessment=assessment, grades='3–8 at schools with no high-school enrollment/offers',
            standard=STANDARD, source_url=GLOSSARY, source='native', label='Grade schools · ACAP', outcome='Level 3 or 4',
            note='Native school totals · CCD direct certification · intervals unavailable', allow_point_only=True)],
        coverage_note=ECON + ' ' + STANDARD,
        methodology=dict(summary='Alabama models native ACAP proficiency against individual same-year direct certification, including free and reduced Medicaid eligibility. This is a benefits-based proxy with no sampling intervals.',
            details=[ECON, STANDARD,
                'Exact native three-digit system/four-digit school codes join the same-year CCD state school ID. Historical names, grade offers and complete reported/derived enrolled-grade totals establish grade-school scope. No name-based match or current directory backfill is used. Map coordinates are unavailable.',
                'The native Tested column is not imported as a score denominator. For example, the state ELA Tested total differs from the sum of native proficiency levels; the response population can exclude ELA exemptions. Counts remain raw audit evidence. Never derive a masked count or average grade percentages.',
                'Separate full-state Math, ELA and Combined models use externally studentized residuals. Combined is the equally weighted Math/ELA mean. UI filters do not refit, state proficiency standards are not a national scale, and associations do not measure causal effectiveness or overall school quality.'],
            sources=[dict(label='Native proficiency download', url=PORTAL), dict(label='Official valid-score proficiency glossary', url=GLOSSARY),
                dict(label='Assessment/weighted accountability distinctions', url=BUSINESS),
                dict(label='CCD 2024–25 state-specific income notes', url=NOTES),
                dict(label='Same-year CCD directory', url=payload['sources']['ccd_directory']['url']),
                dict(label='NCES individual lunch/DC definitions', url=payload['sources']['nces_definition']['url'])]),
        source_audit=dict(native_school_profiles=len(seen), grade_school_profiles=len(schools), excluded=dict(excluded),
            income_unavailable=sum(s['income'] is None for s in schools), state_lunch_notes=payload['state_lunch_notes'],
            native_published_grade_rows=payload['native_grade_rows'],
            approved_point_only=True, score_denominator='Native Tested retained raw; no verified matching proficiency denominator imported', mapped=0))


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
