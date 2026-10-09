"""Idaho 2024–25 ISAT/IDAA native school totals and individual eligibility."""
import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen

from audit_national_sources import DIRECTORY, read_ccd
from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

DATASET = 'id-isat-2025'
YEAR = 2025
EXTRACT = ROOT / 'data/source/idaho.json'
OUTPUT = ROOT / 'data/idaho'
PORTAL = 'https://www.idahoreportcard.org/datafiles'
API = 'https://www.idahoreportcard.org/api/DataExport/csv'
GLOSSARY = 'https://www.idahoreportcard.org/glossary'
RULES_2025 = 'https://www.sde.idaho.gov/wp-content/uploads/2025/09/2025-Accountability-Reporting-Business-Rules-Draft.pdf'
RULES_2026 = 'https://www.sde.idaho.gov/wp-content/uploads/2026/08/2026-Accountability-and-Reporting-Business-Rules.pdf'
QUERY = dict(measures=[89, 35, 36, 92], breakdowns=[1, 25, 46, 27, 77, 78, 76],
    fileFormat=0, isNormalized=True, includeAllLevels=True, organizationScope=1,
    organizationExternalId=None, yearIds=[25], districtExternalIds=None)
GROUPS = ['All Students', 'Students Economically Disadvantaged', 'Students Not Economically Disadvantaged']
LEVELS = ['Below Basic', 'Basic', 'Proficient', 'Advanced']
MEASURES = ['Total Enrollment', 'ELA Participation', 'Math Participation'] + [
    subject + suffix for subject in ['ELA', 'Math'] for suffix in [' Proficiency'] + [' Level ' + level for level in LEVELS]]
FIELDS = ['Measure Label', 'Student Group', 'School Year', 'Rate', 'Text Value',
    'Student Count', 'NSize', 'Suppression Type']
DIRECTORY_FIELDS = ['SCHOOL_YEAR', 'ST', 'ST_SCHID', 'ST_LEAID', 'NCESSCH',
    'SCH_NAME', 'LEA_NAME', 'LCITY', 'UPDATED_STATUS', 'GSLO', 'GSHI', 'IGOFFERED',
    'G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
ECON = ('Idaho 2024–25 native Pct Enrollment, Students Economically Disadvantaged: '
    'individual eligible students / same-year Total Enrollment (K–12, first Friday of May). '
    'Eligibility means ever identified in that reporting year as Free Lunch Eligible, Reduced Lunch Eligible, '
    'Direct Certified or Survey–Household Income through ISEE econDisStatus. It does not mean all CEP meals. '
    'The official glossary warns that undetermined eligibility at Provision 2/CEP schools may be coded '
    'Not Eligible, so undercount and survey coverage are unknown. Masked or blurred income remains unavailable; '
    'never reconstruct it from the complementary group or use prior-year income.')
STANDARD = ('2024–25 native ISAT/IDAA school All Students totals, Level 3 (Proficient) or Level 4 (Advanced), '
    'grades 3–8 at operational schools offering no grade 9–13, adult or ungraded classes in the same-year CCD directory. '
    'Includes Idaho alternate assessment and follows native school attribution/continuous-enrollment rules. '
    'The federal 95% denominator may exceed valid scores. Accept a subject only when all four native performance-level '
    'counts are independently published, unmasked, their sum equals every native proficiency/level NSize and the '
    'independently published participation Student Count (the official valid-scale-score numerator), and Levels 3+4 '
    'equal the published proficient count. Then use exact proficient / verified valid scores. The participation '
    'enrollment denominator is never used as a score denominator; never reconstruct a masked level.')


def source(path, url):
    return dict(path=str(path.relative_to(ROOT)), url=url,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def school_id(district, school):
    if not re.fullmatch(r'\d{3}', district) or not re.fullmatch(r'\d{4}', school):
        raise ValueError('Invalid authoritative Idaho school code')
    return district + '-' + school


def count(value):
    if value in ['', '*', '**', 'N/A']:
        return None
    value = float(value)
    if not math.isfinite(value) or value < 0 or value != int(value):
        raise ValueError('Invalid Idaho native count')
    return int(value)


def number(value):
    if value in ['', '*', '**', 'N/A']:
        return None
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError('Invalid Idaho native rate')
    return value


def visible(row):
    return row is not None and row['Suppression Type'] == 'None' and row['Text Value'] == ''


def indexed(profile):
    records = {}
    for row in profile['records']:
        if row['School Year'] != '2024-2025' or row['Student Group'] not in GROUPS:
            raise ValueError('Idaho extract crossed school year or student group')
        key = (row['Measure Label'].strip(), row['Student Group'])
        if key in records:
            raise ValueError('Duplicate Idaho native measure/group')
        records[key] = row
    return records


def grade_school(directory):
    if directory is None:
        return False
    if directory['SCHOOL_YEAR'] != '2024-2025' or directory['ST'] != 'ID':
        raise ValueError('Idaho directory crossed state/year')
    offers = ['G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
    return (directory['UPDATED_STATUS'] in ['1', '3', '4', '5', '8'] and
        directory['IGOFFERED'] == 'As reported' and directory['GSHI'] in ['PK', 'KG'] + [f'0{g}' for g in range(1, 9)] and
        all(directory[field] in ['Yes', 'No'] for field in offers) and
        all(directory[field] == 'No' for field in [f'G_{g}_OFFERED' for g in range(9, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']))


def income(records):
    total = records.get(('Total Enrollment', 'All Students'))
    eligible = records.get(('Pct Enrollment', 'Students Economically Disadvantaged'))
    n = count(total['Student Count']) if visible(total) else None
    if n is None or n <= 0 or not visible(eligible):
        return n, None, None, 'Individual economic eligibility count suppressed, blurred or unavailable'
    low, denominator = count(eligible['Student Count']), count(eligible['NSize'])
    if low is None or denominator is None:
        return n, None, None, 'Individual economic eligibility count suppressed, blurred or unavailable'
    if denominator != n or count(total['NSize']) != n or low > n:
        raise ValueError('Idaho economic eligibility and Spring Enrollment denominators disagree')
    rate = 100 * low / n
    published = number(eligible['Rate'])
    if published is None or abs(rate - published) > .500001:
        raise ValueError('Idaho native income rate does not match whole-percent rounding')
    return n, low, rate, None


def outcome(records, subject):
    label = 'Math' if subject == 'math' else 'ELA'
    native = records.get((label + ' Proficiency', 'All Students'))
    levels = [records.get((label + ' Level ' + level, 'All Students')) for level in LEVELS]
    participation = records.get((label + ' Participation', 'All Students'))
    raw = dict(proficiency=native, levels=levels, participation=participation)
    reason = 'Native proficient total or complete performance-level counts suppressed, blurred or unavailable'
    if not visible(native) or any(not visible(row) for row in levels):
        return None, None, raw, reason
    values = [count(row['Student Count']) for row in levels]
    denominators = [count(row['NSize']) for row in levels + [native]]
    proficient = count(native['Student Count'])
    if None in values or None in denominators or proficient is None:
        return None, None, raw, reason
    if len(set(denominators)) != 1:
        raise ValueError('Idaho native performance-level denominator mismatch')
    valid = sum(values)
    if valid != denominators[0]:
        return None, None, raw, 'Native 95% accountability denominator differs from complete valid-score total'
    if not visible(participation) or count(participation['Student Count']) is None:
        return None, None, raw, 'Independent valid-scale-score participation numerator suppressed or unavailable'
    if count(participation['Student Count']) != valid:
        return None, None, raw, 'Performance-level total differs from independently reported valid-scale-score count'
    if valid <= 0 or sum(values[2:]) != proficient:
        raise ValueError('Idaho proficient count disagrees with independently published Levels 3+4')
    rate = 100 * proficient / valid
    published = number(native['Rate'])
    if published is None or abs(rate - published) > .050001:
        raise ValueError('Idaho proficiency does not match native one-decimal rounding')
    return rate, valid, raw, None


def extract():
    directory = {row['ST_SCHID'].removeprefix('ID-'): row for row in read_ccd(DIRECTORY) if row['ST'] == 'ID'}
    profiles = {}
    with (ROOT / 'data/raw/id_reportcard_2025.csv').open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        required = set(FIELDS + ['Organization ID', 'Organization Name', 'Organization Type', 'District ID', 'District Name', 'Grades Served'])
        if not required <= set(reader.fieldnames):
            raise ValueError('Idaho report-card schema changed')
        for number_, row in enumerate(reader, 2):
            if row['School Year'] != '2024-2025':
                raise ValueError('Idaho report-card download contains another year')
            if row['Organization Type'] != 'School' or row['Student Group'] not in GROUPS:
                continue
            if row['Student Group'] == 'All Students' and row['Measure Label'].strip() not in MEASURES:
                continue
            if row['Student Group'] != 'All Students' and row['Measure Label'] != 'Pct Enrollment':
                continue
            key = school_id(row['District ID'], row['Organization ID'])
            if key not in profiles:
                ccd = directory.get(key)
                profiles[key] = dict(id=key, district_id=row['District ID'], school_id=row['Organization ID'],
                    display_metadata={field: row[field] for field in ['Organization Name', 'District Name', 'Grades Served', 'Enrollment', 'School Type', 'Latitude', 'Longitude']},
                    directory=None if ccd is None else {field: ccd[field] for field in DIRECTORY_FIELDS}, records=[])
            profiles[key]['records'].append(dict({field: row[field] for field in FIELDS}, source_row=number_))
    sources = dict(reportcard=source(ROOT / 'data/raw/id_reportcard_2025.csv', API),
        glossary=source(ROOT / 'data/raw/id_glossary.html', GLOSSARY),
        current_rules=source(ROOT / 'data/raw/id_rules_2026.pdf', RULES_2026),
        directory=source(ROOT / 'data/raw' / (DIRECTORY + '.zip'), 'https://nces.ed.gov/ccd/Data/zip/' + DIRECTORY + '.zip'))
    payload = dict(state='ID', year=YEAR, academic_year='2024-25', retrieved=str(date.today()),
        sources=sources, request=QUERY, profiles=list(profiles.values()),
        guide_2025=dict(url=RULES_2025, status='Indexed official draft; direct download returned HTTP 404 on audit date. Live glossary and count consistency independently verified.'))
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
    return payload


def normalize(payload):
    if (payload['state'], payload['year'], payload['academic_year']) != ('ID', YEAR, '2024-25') or payload['request'] != QUERY:
        raise ValueError('Wrong Idaho state/year or native query')
    schools, excluded, seen = [], Counter(), set()
    for profile in payload['profiles']:
        key = school_id(profile['district_id'], profile['school_id'])
        directory = profile['directory']
        if key != profile['id'] or key in seen or directory is not None and directory['ST_SCHID'] != 'ID-' + key:
            raise ValueError('Idaho authoritative directory identity mismatch')
        seen.add(key)
        records = indexed(profile)
        if not grade_school(directory):
            excluded['Outside operational same-year CCD grade-school scope'] += 1
            continue
        n, low, pct, income_reason = income(records)
        outcomes = {}
        for subject in ['math', 'reading']:
            rate, valid, raw, reason = outcome(records, subject)
            native = raw['proficiency']
            outcomes[subject] = dict(proficiency=rate, tested=valid, raw=raw,
                raw_tested=None if native is None else native['NSize'], source='reportcard',
                source_row=0 if native is None else native['source_row'],
                valid_score_evidence=STANDARD if valid is not None else None,
                exclusion='; '.join(filter(None, [income_reason, reason])) if rate is None or pct is None else None)
        native_income = records.get(('Pct Enrollment', 'Students Economically Disadvantaged'))
        schools.append(dict(id=key, name=directory['SCH_NAME'], district_id=profile['district_id'],
            district=directory['LEA_NAME'], city=directory['LCITY'], cohort='grade-schools',
            enrollment=n, low_income=low, income=pct, income_source='reportcard',
            income_row=0 if native_income is None else native_income['source_row'],
            income_raw={group: records.get(('Pct Enrollment', group)) for group in GROUPS[1:]},
            directory_raw=directory, display_metadata_raw=profile['display_metadata'], outcomes=outcomes))
    assessment = 'Idaho ISAT/IDAA · grades 3–8 · verified native score totals'
    scope = 'Idaho operational grade schools with same-year individual eligibility and complete native performance-level counts proving valid-score school totals'
    details = [ECON, STANDARD,
        'Same-year 2024–25 CCD directory IDs and grade offers define the grade-school population. The report-card directory presentation can change; its displayed grade span, enrollment and coordinates are not used to join, classify or supply historical counts. Every native school ID has an exact CCD district-school match.',
        'Counts must be independently published, even when the native overall proficiency is numeric. The full score-level sum must also equal the native participation Student Count, which the official guide defines as students with valid scale scores, excluding nonparticipants and forced incomplete scores. This check applies even below 95% participation; its enrollment denominator is not a tested count. Masked levels are never derived. Native All Students scope includes regular and alternate assessments; no tested-subgroup income ratio is used.',
        'Subject models use their full eligible statewide populations and externally studentized residuals. Combined is the equally weighted Math/ELA mean. UI filters do not refit. Verified valid counts support model sampling intervals; associations do not estimate causal effectiveness or overall school quality.',
        'One 2024–25 snapshot only. The 2026 guide announces a continuous-enrollment change, so another year must be audited separately. The 2025 guide is an indexed official draft whose live PDF link returns 404; the current downloaded guide confirms valid-score, privacy and longstanding eligibility definitions, and native count consistency is enforced independently. Historical campus coordinates are unavailable.']
    return dict(dataset=DATASET, state=dict(id='ID', name='Idaho'), year=YEAR, academic_year='2024–25',
        name='Idaho ISAT/IDAA 2024–25', model_scope=scope, region='idaho', prepare_script='scripts/prepare_idaho.py',
        source_url=PORTAL, retrieved=payload['retrieved'], sources=payload['sources'], schools=schools,
        income_definition=dict(label='Individual reported economic eligibility', definition=ECON, url=GLOSSARY),
        cohorts=[dict(id='grade-schools', level='ES', assessment=assessment, grades='3–8 at schools offering no high-school grades',
            standard=STANDARD, source_url=RULES_2025, source='reportcard', label='Grade schools · ISAT/IDAA',
            outcome='Level 3 or 4', note='Complete native valid-score totals')],
        coverage_note='Conservative complete-count coverage. ' + ECON + ' ' + STANDARD,
        methodology=dict(summary='Idaho models exact native ISAT/IDAA rates against same-year individual economic eligibility, requiring complete score levels to verify denominators.',
            details=details, sources=[dict(label='Official native report-card downloads', url=PORTAL),
                dict(label='Official eligibility and Spring Enrollment glossary', url=GLOSSARY),
                dict(label='2024–25 CCD directory and grade offers', url=payload['sources']['directory']['url']),
                dict(label='2025 official draft (indexed; current PDF unavailable)', url=RULES_2025),
                dict(label='Current reporting guide and explicit 2026 changes', url=RULES_2026)]),
        source_audit=dict(native_school_profiles=len(seen), exact_directory_matches=sum(p['directory'] is not None for p in payload['profiles']),
            grade_school_profiles=len(schools), excluded=dict(excluded), income_unavailable=sum(s['income'] is None for s in schools),
            native_display_high_grade_conflicts=[p['id'] for p in payload['profiles'] if p['directory'] is not None and
                (any(int(g) >= 9 for g in re.findall(r'\d+', p['display_metadata']['Grades Served'])) !=
                 any(p['directory'][f'G_{g}_OFFERED'] == 'Yes' for g in range(9, 14)))],
            outcome_exclusions={subject: dict(Counter(s['outcomes'][subject]['exclusion'] for s in schools if s['outcomes'][subject]['exclusion'])) for subject in ['math', 'reading']},
            valid_score_reconciliation=dict(grade_school_complete_subject_rows=sum(s['outcomes'][subject]['tested'] is not None for s in schools for subject in ['math', 'reading']),
                below_95_participation_subject_rows=sum(s['outcomes'][subject]['tested'] is not None and
                    number(s['outcomes'][subject]['raw']['participation']['Rate']) < 95 for s in schools for subject in ['math', 'reading'])),
            mapped=0))


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
    if args.download:
        for name, url in [('id_glossary.html', GLOSSARY), ('id_rules_2026.pdf', RULES_2026)]:
            (ROOT / 'data/raw' / name).write_bytes(urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read())
        request = Request(API, data=json.dumps(QUERY).encode(), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        (ROOT / 'data/raw/id_reportcard_2025.csv').write_bytes(urlopen(request, timeout=120).read())
    if args.download or args.extract:
        extract()
    prepare(args.database)
