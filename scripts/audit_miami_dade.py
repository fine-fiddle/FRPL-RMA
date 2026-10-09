"""Replay Miami-Dade's exact 2024–25 source/grade-school cohorts; never fit models."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import zipfile

import prepare_florida as florida

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/source/miami-dade-district-audit.json'
DIRECTORY = ROOT / 'data/raw/ccd_sch_029_2425_w_1a_073025.zip'
PLANNING = ROOT / 'data/source/district-comparison-candidates.json'
LEA = '1200390'
NATIVE_LEA = 'FL-13'
NATIVE_DISTRICT = '13'
YEAR = '2024-2025'
OPERATIONAL = {'1', '3', '4', '5', '8'}
GRADES = ['PK', 'KG'] + [str(g) for g in range(1, 14)] + ['UG', 'AE']
ENROLLED_GRADES = GRADES[:14]
DIRECTORY_RECORDS_SHA = 'bb6c9571e6cf73aeac9174e3b76f2bfcd611c642c07f541911bc017b1b41dba2'
FLORIDA_PAYLOAD_SHA = 'f08640b8501e323cfc9298057500c4087e543bacdfda5fa4a6edb8a49778cfb8'
INCOME_HEADERS_SHA = '69ae27b3692c211ba0da156585105a87d5dcf47c9b6c4e160061b0f8abb88209'
SOURCES = {
    'ccd_school_directory': {
        'path': 'data/raw/ccd_sch_029_2425_w_1a_073025.zip',
        'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip',
        'sha256': '39326da788aa322353d20ceaf8ad4baed26272502cd05b066cf6c594988b21ab',
        'member': 'ccd_sch_029_2425_w_1a_073025.csv',
    },
    'florida_extract': {
        'path': 'data/source/florida.json', 'url': florida.PORTAL,
        'sha256': '523afad888444e875fc8d06486b20240896341d55b14d9484e8b935888f66daf',
    },
    'assessment': {
        'path': 'data/raw/fl_assessment_2025.xlsx',
        'url': 'https://cdn.fldoe.org/file/18534/SchoolGrades25.xlsx',
        'sha256': '52d3d3d7c2187eb9cbe22477bd088c0c13570f6f2b9f45f74a4b9f771be70a5b',
    },
    'income': {
        'path': 'data/raw/fl_income_2025.xlsx',
        'url': 'https://cdn.fldoe.org/file/7584/2425LunchStatusFS2-3.xlsx',
        'sha256': '48cd9428ea32decf723cc03c2ee7d25528ed8df3db36b20d97e948805344086d',
    },
    'grades': {
        'path': 'data/raw/fl_grades_2025.xlsx',
        'url': 'https://cdn.fldoe.org/file/7584/2425MembBySchoolByGrade.xlsx',
        'sha256': '930a81159fac3db4b38c6428aebc2e5000e9199ce88bb80ecc7431838ae3c93a',
    },
    'grade-guide': {
        'path': 'data/raw/fl_guide_2025.pdf',
        'url': 'https://cdn.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf',
        'sha256': '7dd60cd7c45d03f6324d16d9dcdeb244a5da79f5bccb25859badb32cc2932309',
    },
    'lunch-guide': {
        'path': 'data/raw/fl_lunch_definition_2025.pdf',
        'url': 'https://cdn.fldoe.org/core/fileparse.php/20744/urlt/2425-146025.pdf',
        'sha256': '1c8617d492e845e8bdf584c4780de6ac1cf7e7d35e7f2faaa96cec30cf322216',
    },
}
POLICY = {
    'baseline_roster': 'Exact operational CCD LEA 1200390 / native FL-13 schools in 2024–25; names never join.',
    'identity': 'Only the documented FL- prefix is removed from FL-13-ssss ST_SCHID to native 13-ssss. Retain NCESSCH and source rows.',
    'native_grade_school_contract': 'Florida Survey 2 requires explicit zero in every enrolled grade 9–12; protected or missing high-grade counts never mean zero.',
    'proposed_district_population': 'Intersection of exact operational roster, complete reported pure lower offered grades, at least one offered grade 3–8, and the native explicit-zero enrolled high-grade contract. Source/cohort proposal only.',
    'primary_only': 'Retain pure-lower profiles with no offered grade 3–8 separately as nonapplicable. Offered grades and enrolled grades are separate evidence.',
    'enrollment_differences': 'Report positive, protected, and explicit-zero enrolled grades against all offered flags. Planning enrollment/count reconciliation is not a model filter.',
    'charters_and_alternatives': 'Retain exact attached-LEA charter, alternative, special-education and other school-type flags; outcomes must pass native exclusions. No fit-driven selection.',
    'high_and_mixed': 'High/mixed assessment populations remain outside Florida approval. Native enrolled-grade schools with mixed CCD offerings are reported separately, never labeled pure.',
    'income': florida.ECON,
    'assessment': florida.STANDARD,
    'counts': 'No verified valid-score denominators in the native School Grades source. Every subject and entire future district model must omit sampling intervals; enrollment and percent tested are never substitute counts.',
    'approval': 'Source/cohort audit only; approved_for_modeling remains false. District population review, independent fits and numerical diagnostics, canonical import and browser validation remain required.',
}
PLANNING_RECONCILIATION = {
    'source': 'data/source/district-comparison-candidates.json',
    'operational_roster': 530, 'potential_pure_ES': 365, 'potential_pure_HS': 81,
    'pure_lower_without_offered_tested_grade': 5,
    'pure_offered_tested_with_enrolled_tested_zeros': 4,
    'explanation': 'Planning screens also require reconciled reported CCD membership. Here the 365 ES IDs equal the independently selected offered-tested/native-zero-high intersection; membership counts are not a modeling filter. The 81 HS planning IDs do not approve a high-school assessment population.',
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


def validate_florida(payload):
    if (payload.get('state'), payload.get('year'), payload.get('academic_year')) != ('FL', 2025, '2024-25'):
        raise ValueError('Wrong Florida state/year for Miami-Dade source audit')
    if fingerprint(payload) != FLORIDA_PAYLOAD_SHA:
        raise ValueError('Florida native record fingerprint changed; re-audit identities, scope and suppression')
    if payload['sources'] != {k: SOURCES[k] for k in florida.FILES}:
        raise ValueError('Florida source provenance changed')
    # Reuse the audited native outcome/income/identity contract, without importing or fitting.
    florida.normalize(payload)


def load_florida(path=florida.EXTRACT):
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != SOURCES['florida_extract']['sha256']:
        raise ValueError('Florida compact extract fingerprint changed; fresh source audit required')
    payload = json.loads(content)
    validate_florida(payload)
    return payload


def extract_income_headers():
    path = ROOT / SOURCES['income']['path']
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCES['income']['sha256']:
        raise ValueError('Florida income workbook fingerprint changed')
    book = florida.openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = [{'source_row': i, 'raw': list(r)} for i, r in enumerate(
            book['2425 FS3_Schl'].iter_rows(min_row=1, max_row=3, values_only=True), 1)]
    finally:
        book.close()
    headers = {'source_id': 'income', 'worksheet': '2425 FS3_Schl', 'rows': rows}
    if fingerprint(headers) != INCOME_HEADERS_SHA:
        raise ValueError('Florida Final Survey 3 income worksheet header changed')
    return headers


def directory_identity(raw):
    match = re.fullmatch(r'FL-(13-\d{4})', raw.get('ST_SCHID', ''))
    if (raw.get('ST') != 'FL' or raw.get('SCHOOL_YEAR') != YEAR
            or raw.get('LEAID') != LEA or raw.get('ST_LEAID') != NATIVE_LEA
            or not match or not re.fullmatch(LEA + r'\d{5}', raw.get('NCESSCH', ''))):
        raise ValueError('Miami-Dade requires exact same-year CCD school and LEA identities')
    return match.group(1)


def offered_evidence(raw):
    flags = {g: raw.get('G_' + g + '_OFFERED') for g in GRADES}
    complete = (raw.get('NOGRADES') == 'No' and raw.get('IGOFFERED') == 'As reported'
                and all(v in {'Yes', 'No'} for v in flags.values()))
    offered = [g for g, v in flags.items() if v == 'Yes']
    lower = any(g in offered for g in GRADES[:10])
    high = any(str(g) in offered for g in range(9, 13))
    extra = any(g in offered for g in ['13', 'UG', 'AE'])
    scope = ('uncertain' if not complete else 'other' if extra or not (lower or high)
             else 'mixed' if lower and high else 'ES' if lower else 'HS')
    return {'flags': flags, 'complete_reported_flags': complete, 'scope': scope,
            'offered': offered, 'offered_tested_grades': [str(g) for g in range(3, 9) if str(g) in offered],
            'low': raw.get('GSLO'), 'high': raw.get('GSHI'), 'level': raw.get('LEVEL'),
            'nogrades': raw.get('NOGRADES'), 'offered_flag_status': raw.get('IGOFFERED')}


def enrolled_evidence(profile, offered=None):
    raw = profile['grades']
    approved = florida.scope(raw)
    values = {}
    for grade, value in zip(ENROLLED_GRADES, raw[4:]):
        number = florida.count(value)
        status = ('explicit_zero' if number == 0 else 'positive' if number is not None
                  else 'protected_positive' if value == '*' else 'unavailable')
        values[grade] = {'raw': value, 'reported_count': number, 'status': status}
    evidence = [g for g, v in values.items() if v['status'] in {'positive', 'protected_positive'}]
    tested = [g for g in evidence if g in [str(n) for n in range(3, 9)]]
    result = {'source_id': 'grades', 'source_row': profile['grade_row'], 'grade_values': values,
              'native_grade_school_contract': approved, 'positive_or_protected_grades': evidence,
              'positive_or_protected_tested_grades': tested,
              'protected_grades': [g for g, v in values.items() if v['status'] == 'protected_positive'],
              'explicit_zero_tested_grades': all(values[str(g)]['status'] == 'explicit_zero' for g in range(3, 9)),
              'unavailable_grades': [g for g, v in values.items() if v['status'] == 'unavailable']}
    if offered is not None:
        result['offered_with_explicit_zero_enrollment'] = [g for g in offered['offered']
                                                          if g in values and values[g]['status'] == 'explicit_zero']
        result['positive_or_protected_without_offer'] = [g for g in evidence if g not in offered['offered']]
        result['exact_offered_vs_enrolled_evidence_set'] = (offered['complete_reported_flags']
                                                         and set(offered['offered']) == set(evidence))
    return result


def income_record(profile):
    raw = profile['income_raw']
    total, eligible, percentage, reason = florida.income(raw)
    return {'source_id': 'income', 'source_row': profile['income_row'], 'year': 2025,
            'raw': raw, 'survey_enrollment': total, 'individual_eligible': eligible,
            'percentage': percentage, 'exclusion': reason,
            'native_fields': None if raw is None else dict(zip(
                ['enrolled', 'free_D_F', 'reduced_3_E', 'provision2_4', 'CEP_direct_C_R'], raw[4:9]))}


def assessment_flags(entry):
    r = entry['raw']
    return {'source_id': 'assessment', 'source_row': entry['row'], 'school_id': entry['id'],
            'provider': r[3], 'role': 'campus' if r[3] in ('', None) else 'provider_specific_virtual',
            'collocated': r[47], 'collocated_school_number': r[48], 'charter': r[49],
            'title_i': r[50], 'alternative_or_ESE_center': r[51], 'school_type': r[52],
            'school_grade_2025': r[21], 'percent_tested': r[20],
            'published_economic_disadvantage': r[53]}


def subjects(profile, campus, proposed_reason):
    """Native outcomes and proposed district exclusions remain distinct; no score counts."""
    native_scope = florida.scope(profile['grades'])
    income = income_record(profile)
    raw = None if campus is None else campus['raw']
    values = {}
    for subject in ['math', 'reading']:
        rate, outcome_reason = florida.outcome(raw, subject)
        source_reason = ('Enrolled grades 9–12 or protected high-school grade membership'
                         if not native_scope else '; '.join(filter(None, [income['exclusion'], outcome_reason])) or None)
        native_usable = native_scope and source_reason is None
        district_reason = proposed_reason or source_reason
        values[subject] = {'source_id': 'assessment', 'source_row': 0 if campus is None else campus['row'],
                           'native_achievement_field': 9 if subject == 'math' else 6,
                           'native_achievement_raw': None if raw is None else raw[9 if subject == 'math' else 6],
                           'native_rate': rate, 'native_outcome_exclusion': outcome_reason,
                           'income_exclusion': income['exclusion'],
                           'native_grade_school_usable': native_usable, 'source_contract_exclusion': source_reason,
                           'district_applicable': proposed_reason is None,
                           'district_usable': proposed_reason is None and native_usable,
                           'district_exclusion': district_reason, 'valid_scores': None,
                           'sampling_interval_available': False}
    usable = all(v['native_grade_school_usable'] for v in values.values())
    district_usable = all(v['district_usable'] for v in values.values())
    reasons = '; '.join(s + ': ' + v['source_contract_exclusion'] for s, v in values.items()
                        if v['source_contract_exclusion'])
    values['combined'] = {'native_rate': (values['math']['native_rate'] + values['reading']['native_rate']) / 2 if usable else None,
                          'native_grade_school_usable': usable, 'source_contract_exclusion': reasons or None,
                          'district_applicable': proposed_reason is None, 'district_usable': district_usable,
                          'district_exclusion': proposed_reason or reasons or None,
                          'valid_scores': None, 'sampling_interval_available': False,
                          'definition': 'Equally weighted mean of eligible Math and ELA; not percent proficient in both.'}
    return values


def summarize(links, predicate, mode):
    members = [r for r in links if r['matched'] and predicate(r)]
    values = {'profiles': len(members), 'subjects': {},
              'school_ids': [r['school_id'] for r in members],
              'applicable_basis': ('Verified pure lower CCD offerings include grade 3–8 and native enrolled high grades are explicit zero.'
                                   if mode == 'district' else
                                   'Within native explicit-zero enrolled high-grade source contract; includes primary-only profiles and does not assert tested-grade applicability.')}
    for subject in ['math', 'reading', 'combined']:
        usable_key = 'district_usable' if mode == 'district' else 'native_grade_school_usable'
        reason_key = 'district_exclusion' if mode == 'district' else 'source_contract_exclusion'
        eligible = [r for r in members if r['subjects'][subject][usable_key]]
        values['subjects'][subject] = {
            'applicable': sum(r['subjects'][subject]['district_applicable'] for r in members) if mode == 'district' else len(members),
            'usable': len(eligible), 'eligible_school_ids': [r['school_id'] for r in eligible],
            'exclusions': dict(sorted(Counter(r['subjects'][subject][reason_key] for r in members
                                            if not r['subjects'][subject][usable_key]).items())),
            'verified_valid_score_counts': 0, 'model_sampling_intervals_available': False,
        }
    eligible = [r for r in members if r['subjects']['combined']['district_usable' if mode == 'district' else 'native_grade_school_usable']]
    incomes = [r['income']['percentage'] for r in eligible]
    values['combined_income'] = {'minimum': min(incomes) if incomes else None,
                                'maximum': max(incomes) if incomes else None, 'distinct': len(set(incomes)),
                                'mean': statistics.mean(incomes) if incomes else None,
                                'sample_standard_deviation': statistics.stdev(incomes) if len(incomes) > 1 else None}
    values['combined_ccd_charter'] = dict(sorted(Counter(r['ccd_flags']['charter'] for r in eligible).items()))
    values['combined_ccd_school_type'] = dict(sorted(Counter(r['ccd_flags']['school_type'] for r in eligible).items()))
    return values


def derive(document, payload):
    if (document.get('schema_version') != 1 or document.get('state') != 'FL'
            or document.get('year') != 2025 or document.get('academic_year') != YEAR
            or document.get('nces_lea_id') != LEA or document.get('native_lea_id') != NATIVE_LEA
            or document.get('status') != 'district_population_and_model_audit_pending'
            or document.get('approved_for_modeling') is not False
            or document.get('sources') != SOURCES or document.get('policy') != POLICY
            or document.get('planning') != PLANNING_RECONCILIATION):
        raise ValueError('Miami-Dade source-only audit contract/provenance changed')
    validate_florida(payload)
    if fingerprint(document.get('income_worksheet_headers')) != INCOME_HEADERS_SHA:
        raise ValueError('Retained Final Survey 3 income header fingerprint changed')
    records = document['directory_records']
    if fingerprint(records) != DIRECTORY_RECORDS_SHA:
        raise ValueError('Retained complete CCD roster fingerprint changed; fresh directory audit required')
    native_profiles = [p for p in payload['profiles'] if p['id'].startswith(NATIVE_DISTRICT + '-')]
    profiles = {p['id']: p for p in native_profiles}
    native_assessments = [a for a in payload['assessments'] if a['id'].startswith(NATIVE_DISTRICT + '-')]
    by_school = defaultdict(list)
    for entry in native_assessments:
        by_school[entry['id']].append(entry)
    native_income = [p for p in payload['unmatched_income'] if p['id'].startswith(NATIVE_DISTRICT + '-')]
    links, nonoperational, seen, nces_seen, row_seen = [], [], set(), set(), set()
    for entry in records:
        raw = entry['raw']
        key = directory_identity(raw)
        if key in seen or raw['NCESSCH'] in nces_seen or entry['source_row'] in row_seen or entry['source_row'] < 2:
            raise ValueError('Duplicate CCD school identity or invalid source row')
        seen.add(key); nces_seen.add(raw['NCESSCH']); row_seen.add(entry['source_row'])
        offered = offered_evidence(raw)
        link = {'school_id': key, 'ncessch': raw['NCESSCH'], 'ccd_source_row': entry['source_row'],
                'matched': key in profiles, 'offered': offered,
                'ccd_flags': {'operational': raw['UPDATED_STATUS'] in OPERATIONAL,
                              'status': raw['UPDATED_STATUS'], 'status_text': raw['UPDATED_STATUS_TEXT'],
                              'school_type_id': raw['SCH_TYPE'], 'school_type': raw['SCH_TYPE_TEXT'],
                              'charter': raw['CHARTER_TEXT'],
                              'virtual_status': None, 'virtual_status_note': 'This CCD directory has no virtual-status field.'},
                'native_assessment_flags': [assessment_flags(a) for a in by_school[key]],
                'native_assessment_rows': [a['row'] for a in by_school[key]]}
        if raw['UPDATED_STATUS'] not in OPERATIONAL:
            link['exclusion'] = 'CCD status is nonoperational for the same-year baseline'
            nonoperational.append(link)
            continue
        if key not in profiles:
            link['exclusion'] = 'No same-year Florida Fall Survey 2 school profile'
            links.append(link)
            continue
        profile = profiles[key]
        enrolled = enrolled_evidence(profile, offered)
        campus = next((a for a in by_school[key] if a['raw'][3] in ('', None)), None)
        proposed_reason = ('CCD offered configuration is not verified pure lower grades' if offered['scope'] != 'ES'
                           else 'No offered grade 3–8 in pure lower configuration' if not offered['offered_tested_grades']
                           else 'Enrolled grades 9–12 or protected high-school grade membership' if not enrolled['native_grade_school_contract']
                           else None)
        charter_agreement = None if campus is None else (
            {'YES': 'Yes', 'NO': 'No'}.get(campus['raw'][49]) == raw['CHARTER_TEXT'])
        link.update(profile=profile, enrolled=enrolled, income=income_record(profile),
                    subjects=subjects(profile, campus, proposed_reason),
                    proposed_population_exclusion=proposed_reason,
                    campus_charter_agreement=charter_agreement)
        links.append(link)
    matched = {r['school_id'] for r in links if r['matched']}
    outside = [{'school_id': p['id'], 'profile': p, 'enrolled': enrolled_evidence(p),
                'income': income_record(p), 'native_assessment_rows': [a['row'] for a in by_school[p['id']]],
                'native_assessment_flags': [assessment_flags(a) for a in by_school[p['id']]],
                'exclusion': 'Native Florida district code without exact operational CCD roster membership'}
               for p in native_profiles if p['id'] not in matched]
    pure = lambda r: r['offered']['scope'] == 'ES'
    native = lambda r: r['enrolled']['native_grade_school_contract']
    cohorts = {
        'native_enrolled_grade_school_contract': summarize(links, native, 'native'),
        'proposed_pure_lower_directory': summarize(links, pure, 'district'),
        'proposed_pure_offered_tested_grade': summarize(links, lambda r: pure(r) and r['subjects']['combined']['district_applicable'], 'district'),
        'pure_lower_enrolled_tested_evidence': summarize(links, lambda r: pure(r) and native(r) and bool(r['enrolled']['positive_or_protected_tested_grades']), 'district'),
        'pure_lower_primary_offers_only': summarize(links, lambda r: pure(r) and not r['offered']['offered_tested_grades'], 'district'),
        'native_grade_schools_with_mixed_offers': summarize(links, lambda r: native(r) and r['offered']['scope'] == 'mixed', 'native'),
    }
    differences = [r for r in links if r['matched'] and
                   (r['enrolled']['offered_with_explicit_zero_enrollment'] or r['enrolled']['positive_or_protected_without_offer'])]
    coverage = {
        'directory_records': len(records), 'operational_schools': len(links),
        'nonoperational_schools': len(nonoperational),
        'operational_statuses': dict(sorted(Counter(r['ccd_flags']['status_text'] for r in links).items())),
        'nonoperational_statuses': dict(sorted(Counter(r['ccd_flags']['status_text'] for r in nonoperational).items())),
        'operational_offered_scope': dict(sorted(Counter(r['offered']['scope'] for r in links).items())),
        'exact_fall_profile_matches': len(matched), 'operational_without_fall_profile': len(links) - len(matched),
        'native_district_profiles': len(native_profiles), 'outside_operational_roster_profiles': len(outside),
        'native_district_assessment_rows': len(native_assessments),
        'campus_assessment_rows': sum(a['raw'][3] in ('', None) for a in native_assessments),
        'provider_specific_virtual_assessment_rows': sum(a['raw'][3] not in ('', None) for a in native_assessments),
        'native_income_without_fall_registry': len(native_income),
        'matched_profiles_outside_native_grade_school_contract': sum(not native(r) for r in links if r['matched']),
        'profiles_with_offered_enrolled_differences': len(differences),
        'profiles_with_positive_or_protected_enrolled_grade_without_offer': sum(bool(r['enrolled']['positive_or_protected_without_offer']) for r in links if r['matched']),
        'profiles_with_protected_enrolled_grades': sum(bool(r['enrolled']['protected_grades']) for r in links if r['matched']),
        'protected_enrolled_grade_cells': sum(len(r['enrolled']['protected_grades']) for r in links if r['matched']),
        'offered_with_explicit_zero_enrolled_grade_cells': sum(len(r['enrolled']['offered_with_explicit_zero_enrollment']) for r in links if r['matched']),
        'exact_offered_vs_enrolled_evidence_sets': sum(r['enrolled']['exact_offered_vs_enrolled_evidence_set'] for r in links if r['matched']),
        'pure_offered_tested_with_explicit_zero_enrolled_tested': sum(pure(r) and bool(r['offered']['offered_tested_grades']) and r['enrolled']['explicit_zero_tested_grades'] for r in links if r['matched']),
        'pure_lower_income_exclusions': dict(sorted(Counter(r['income']['exclusion'] for r in links if r['matched'] and pure(r) and r['income']['exclusion']).items())),
        'campus_charter_disagreements': sum(r['campus_charter_agreement'] is False for r in links if r['matched']),
        'collocated_assessment_rows': sum(a['raw'][47] == 'Y' for a in native_assessments),
        'verified_valid_score_counts': 0, 'sampling_intervals_available': False,
    }
    return {'native_records': {'profiles': native_profiles, 'assessments': native_assessments,
                               'income_without_fall_registry': native_income, 'source_notes': payload['source_notes']},
            'roster_links': links, 'nonoperational_directory': nonoperational,
            'outside_roster_profiles': outside,
            'native_assessments_without_operational_roster': [a for a in native_assessments if a['id'] not in {r['school_id'] for r in links}],
            'offered_enrolled_difference_school_ids': [r['school_id'] for r in differences],
            'cohorts': cohorts, 'coverage': coverage}


def validate(document, payload=None):
    expected = derive(document, payload if payload is not None else load_florida())
    if any(document.get(key) != value for key, value in expected.items()):
        raise ValueError('Miami-Dade raw links, exclusions, missingness or cohort memberships failed replay')
    return expected['coverage']


def extract(directory=DIRECTORY, output=OUTPUT):
    directory, output = Path(directory), Path(output)
    if hashlib.sha256(directory.read_bytes()).hexdigest() != SOURCES['ccd_school_directory']['sha256']:
        raise ValueError('CCD archive fingerprint changed; fresh source audit required')
    payload = load_florida()
    with zipfile.ZipFile(directory) as archive:
        with archive.open(SOURCES['ccd_school_directory']['member']) as source:
            rows = csv.DictReader(io.TextIOWrapper(source, encoding='utf-8-sig'))
            records = [{'source_row': number, 'raw': row} for number, row in enumerate(rows, 2) if row['LEAID'] == LEA]
    document = {'schema_version': 1, 'state': 'FL', 'year': 2025, 'academic_year': YEAR,
                'nces_lea_id': LEA, 'native_lea_id': NATIVE_LEA,
                'status': 'district_population_and_model_audit_pending', 'approved_for_modeling': False,
                'sources': SOURCES, 'policy': POLICY, 'directory_records': records,
                'income_worksheet_headers': extract_income_headers(),
                'planning': PLANNING_RECONCILIATION}
    document.update(derive(document, payload))
    # Cross-check planning IDs only. No CCD membership fields select these source cohorts.
    agency = next(r for r in json.loads(PLANNING.read_text())['agencies'] if r['nces_lea_id'] == LEA)
    applicable = document['cohorts']['proposed_pure_offered_tested_grade']['school_ids']
    selected_nces = {r['ncessch'] for r in document['roster_links'] if r['school_id'] in applicable}
    if (selected_nces != set(agency['potential_school_ids']['ES'])
            or agency['school_directory_operational_count'] != 530
            or len(agency['potential_school_ids']['HS']) != 81):
        raise ValueError('Miami-Dade independent source population no longer reconciles to planning IDs')
    validate(document, payload)
    output.write_text(json.dumps(document, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return document['coverage']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--directory', type=Path, default=DIRECTORY)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = extract(args.directory, args.output) if args.extract else validate(json.loads(args.output.read_text()))
    print(json.dumps(result, sort_keys=True))
