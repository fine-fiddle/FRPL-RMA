"""Replay LAUSD's exact 2024–25 roster and usable cohorts; never fit a model."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import prepare_california as california

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/source/los-angeles-district-audit.json'
DIRECTORY = ROOT / 'data/raw/ccd_sch_029_2425_w_1a_073025.zip'
PLANNING = ROOT / 'data/source/district-comparison-candidates.json'
LEA = '0622710'
NATIVE_LEA = 'CA-1964733'
CDS_DISTRICT = '1964733'
YEAR = '2024-2025'
OPERATIONAL = {'1', '3', '4', '5', '8'}
GRADES = ['PK', 'KG'] + [str(g) for g in range(1, 14)] + ['UG', 'AE']
DIRECTORY_RECORDS_SHA = 'd3e445813775f9d0a2770f0d9721a8c2b6869e7df3e885f7c548f3d1618e2130'
CALIFORNIA_PAYLOAD_SHA = '1c382033b3143f849d322b5b9cdcb07a7196de268da9fe6e6bb69126bb55a3a2'
SOURCES = {
    'ccd_school_directory': {
        'path': 'data/raw/ccd_sch_029_2425_w_1a_073025.zip',
        'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip',
        'sha256': '39326da788aa322353d20ceaf8ad4baed26272502cd05b066cf6c594988b21ab',
        'member': 'ccd_sch_029_2425_w_1a_073025.csv',
    },
    'california_extract': {
        'path': 'data/source/california.json', 'url': california.RESEARCH_URL,
        'sha256': '5a66934a98646df3a7c09954753630634a6a9232a311accda724527124ec2e2d',
    },
    'ca-sb-2025': {
        'path': 'data/raw/california/sb_ca2025_1_csv_v1.zip',
        'url': california.ASSESSMENT_URL,
        'sha256': 'b1fea7cc714141ffe9c67ac91bad3eaa24282c49d37a18bd0f9ad6e2dc3b6e6b',
    },
    'ca-frpm-2025': {
        'path': 'data/raw/california/frpm2425.xlsx', 'url': california.INCOME_URL,
        'sha256': '86fb8bc64ce0e433468f4a4b9038115a82031fee56125f76bacd56037a654a40',
    },
    'ca-sb-layout-2025': {
        'path': 'data/raw/california/2025_SBAC_Research_File_Layout.xlsx',
        'url': california.LAYOUT_URL,
        'sha256': 'a1c6bfb0c88333413ad612b0aa47a7ad08a85c6d7cb1c27f7ff9facecbf6ab2e',
    },
}
POLICY = {
    'baseline': 'Operational schools attached to exact CCD LEA 0622710 in 2024–25.',
    'identity': 'Exact CA-1964733-sssssss CCD ST_SCHID to 1964733sssssss CDE CDS; names never join.',
    'charters': 'Include exact roster locally funded charters; exclude CDE reporting-prefix profiles outside the roster.',
    'alternatives': 'Retain alternative and special-education flags; a district model requires explicit population review.',
    'populations': 'Pure grade schools and pure high schools only in baseline counts; mixed schools are retained separately.',
    'income': california.ECON_DEFINITION,
    'assessment': 'Complete expected grades with exact valid-score counts; grade 13 never recovers missing or suppressed components.',
    'approval': 'Source/cohort audit only. Separate district fits, coverage, leverage and studentization checks remain required.',
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


def load_california(path=california.EXTRACT):
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != SOURCES['california_extract']['sha256']:
        raise ValueError('California extract fingerprint changed; perform a fresh source audit')
    payload = json.loads(content)
    validate_california(payload)
    return payload


def validate_california(payload):
    if fingerprint(payload) != CALIFORNIA_PAYLOAD_SHA:
        raise ValueError('California native records changed; re-audit count/suppression and scope')
    if payload['sources'] != {k: SOURCES[k] for k in ['ca-sb-2025', 'ca-frpm-2025', 'ca-sb-layout-2025']}:
        raise ValueError('California source provenance changed')


def directory_identity(raw):
    match = re.fullmatch(r'CA-(1964733)-(\d{7})', raw.get('ST_SCHID', ''))
    if (raw.get('ST') != 'CA' or raw.get('SCHOOL_YEAR') != YEAR
            or raw.get('LEAID') != LEA or raw.get('ST_LEAID') != NATIVE_LEA
            or not match or not re.fullmatch(LEA + r'\d{5}', raw.get('NCESSCH', ''))):
        raise ValueError('LAUSD roster must retain exact same-year CCD school/LEA identities')
    return ''.join(match.groups())


def directory_scope(raw):
    """Reported offered-grade configuration, independently of enrollment/outcomes."""
    if (raw.get('NOGRADES') != 'No' or raw.get('IGOFFERED') != 'As reported'
            or any(raw.get('G_' + g + '_OFFERED') not in {'Yes', 'No'} for g in GRADES)):
        return 'uncertain'
    if any(raw['G_' + g + '_OFFERED'] == 'Yes' for g in ['13', 'UG', 'AE']):
        return 'other'
    lower = any(raw['G_' + g + '_OFFERED'] == 'Yes' for g in ['PK', 'KG'] + [str(g) for g in range(1, 9)])
    high = any(raw['G_' + str(g) + '_OFFERED'] == 'Yes' for g in range(9, 13))
    return 'mixed' if lower and high else 'ES' if lower else 'HS' if high else 'other'


def profile_scope(profile):
    low, high = california.profile_span(profile)
    return 'ES' if high < 9 else 'HS' if low >= 9 else 'mixed'


def grade_agreement(raw, profile):
    scope = directory_scope(raw)
    offered = [0 if g in ['PK', 'KG'] else int(g)
               for g in ['PK', 'KG'] + [str(g) for g in range(1, 13)]
               if raw['G_' + g + '_OFFERED'] == 'Yes']
    if (scope != profile_scope(profile) or not offered
            or california.profile_span(profile) != (min(offered), max(offered))):
        raise ValueError('Native FRPM and CCD reported grade configurations disagree')
    return scope


def subject_record(observation, income):
    """Retain complete native expected-grade evidence, including suppressed cells."""
    if observation is None:
        return {'applicable': False, 'usable': False, 'proficiency': None, 'valid_scores': None,
                'exclusion': 'No applicable tested grade in native school configuration',
                'expected_grades': [], 'source_rows': [], 'expected_grade_records': []}
    reason = observation['exclusion']
    if income is None:
        reason = reason or 'Missing same-year K–12 FRPM eligibility'
    expected = observation['expected_grades']
    return {'applicable': True, 'usable': reason is None,
            'proficiency': observation['proficiency'], 'valid_scores': observation['tested'],
            'exclusion': reason, 'expected_grades': expected,
            'source_rows': [r['source_row'] for r in observation['raw']],
            'expected_grade_records': [
                {'source_id': 'ca-sb-2025', 'source_row': r['source_row'],
                 'raw': {k: r[k] for k in california.FIELDS}}
                for r in observation['raw'] if int(r['Grade']) in expected]}


def summarize(links, scope, level):
    members = [r for r in links if r.get('scope') == scope]
    result = {'profiles': len(members), 'applicable_profiles': 0, 'subjects': {}}
    for subject in ['math', 'reading', 'combined']:
        values = [r['assessments'][level][subject] for r in members]
        result['subjects'][subject] = {
            'applicable': sum(v['applicable'] for v in values),
            'usable': sum(v['usable'] for v in values),
            'exclusions': dict(sorted(Counter(v['exclusion'] for v in values if not v['usable']).items())),
        }
    result['applicable_profiles'] = result['subjects']['combined']['applicable']
    usable = [r for r in members if r['assessments'][level]['combined']['usable']]
    incomes = [r['income']['percentage'] for r in usable]
    result['combined_income'] = {'minimum': min(incomes) if incomes else None,
                                'maximum': max(incomes) if incomes else None,
                                'distinct': len(set(incomes))}
    result['combined_charter'] = dict(sorted(Counter(r['charter'] for r in usable).items()))
    result['combined_school_type'] = dict(sorted(Counter(r['ccd_school_type'] for r in usable).items()))
    return result


def derive(document, payload):
    if (document.get('schema_version') != 1 or document.get('state') != 'CA'
            or document.get('year') != 2025 or document.get('academic_year') != YEAR
            or document.get('nces_lea_id') != LEA or document.get('native_lea_id') != NATIVE_LEA
            or document.get('status') != 'district_model_audit_pending'
            or document.get('approved_for_modeling') is not False
            or document.get('sources') != SOURCES or document.get('policy') != POLICY):
        raise ValueError('LAUSD source-only audit contract/provenance changed')
    validate_california(payload)
    records = document['directory_records']
    if fingerprint(records) != DIRECTORY_RECORDS_SHA:
        raise ValueError('Retained CCD roster fingerprint changed; perform a fresh directory audit')
    profiles, observations, _ = california.normalized(payload)
    raw_profiles = {r['school_id']: r for r in payload['profiles']}
    observations = {(r['school_id'], r['level'], r['subject']): r for r in observations}
    types, assessment_refs = defaultdict(set), defaultdict(list)
    for values in payload['assessments']:
        raw = dict(zip(payload['assessment_fields'], values[1:]))
        key = california.cds(raw)
        if key.startswith(CDS_DISTRICT):
            types[key].add(raw['Type ID'])
            assessment_refs[key].append(values[0])
    links, excluded_directory, seen, seen_nces, seen_rows = [], [], set(), set(), set()
    for record in records:
        raw = record['raw']
        key = directory_identity(raw)
        if key in seen or raw['NCESSCH'] in seen_nces or record['source_row'] in seen_rows:
            raise ValueError('Duplicate CCD school identity or source row')
        seen.add(key); seen_nces.add(raw['NCESSCH']); seen_rows.add(record['source_row'])
        if raw['UPDATED_STATUS'] not in OPERATIONAL:
            excluded_directory.append({'school_id': key, 'ncessch': raw['NCESSCH'],
                                       'source_row': record['source_row'], 'status': raw['UPDATED_STATUS_TEXT']})
            continue
        link = {'school_id': key, 'ncessch': raw['NCESSCH'], 'ccd_source_row': record['source_row'],
                'matched': key in profiles, 'ccd_school_type': raw['SCH_TYPE_TEXT'],
                'assessment_type_ids': sorted(types[key])}
        if key not in profiles:
            link['exclusion'] = 'No supported same-year native FRPM school profile'
            links.append(link)
            continue
        profile = profiles[key]
        charter = profile['raw']['Charter School (Y/N)'].strip()
        if charter not in {'Yes', 'No'} or charter != raw['CHARTER_TEXT']:
            raise ValueError('Native FRPM and CCD charter flags disagree')
        scope = grade_agreement(raw, profile['raw'])
        enrollment, eligible, income = california.income_values(profile['raw'])
        link.update(scope=scope, charter=charter, profile=profile,
                    income={'source_id': 'ca-frpm-2025', 'source_row': profile['source_row'],
                            'year': 2025, 'enrollment': enrollment, 'eligible': eligible,
                            'percentage': income}, assessments={})
        for level in ['ES', 'HS']:
            values = {s: subject_record(observations.get((key, level, s)), income)
                      for s in ['math', 'reading']}
            math, ela = values['math'], values['reading']
            usable = math['usable'] and ela['usable']
            values['combined'] = {
                'applicable': math['applicable'] and ela['applicable'], 'usable': usable,
                'proficiency': (math['proficiency'] + ela['proficiency']) / 2 if usable else None,
                'exclusion': None if usable else 'Requires eligible Math and ELA: ' +
                '; '.join(s + ': ' + v['exclusion'] for s, v in [('math', math), ('reading', ela)] if not v['usable']),
            }
            link['assessments'][level] = values
        links.append(link)
    matched = {r['school_id'] for r in links if r['matched']}
    outside, unsupported = [], []
    for key, profile in raw_profiles.items():
        if not key.startswith(CDS_DISTRICT) or key in matched:
            continue
        item = {'school_id': key, 'profile': profile, 'assessment_type_ids': sorted(types[key]),
                'assessment_source_rows': assessment_refs[key]}
        if key in profiles:
            item['exclusion'] = 'Native reporting district prefix without exact operational CCD LEA roster membership'
            outside.append(item)
        else:
            item['exclusion'] = 'Unsupported or non-school native FRPM grade configuration'
            unsupported.append(item)
    cohorts = {'pure_grade_schools': summarize(links, 'ES', 'ES'),
               'pure_high_schools': summarize(links, 'HS', 'HS'),
               'mixed_grades_3_8': summarize(links, 'mixed', 'ES'),
               'mixed_grade_11': summarize(links, 'mixed', 'HS')}
    coverage = {'directory_records': len(records), 'operational_schools': len(links),
                'exact_supported_profile_matches': len(matched),
                'operational_without_supported_profile': len(links) - len(matched),
                'outside_roster_supported_prefix_profiles': len(outside),
                'unsupported_prefix_profiles': len(unsupported),
                'native_ccd_grade_bounds_and_scope_agreement': len(matched), 'native_ccd_charter_agreement': len(matched),
                'matched_scope': dict(sorted(Counter(r['scope'] for r in links if r['matched']).items())),
                'matched_charter': dict(sorted(Counter(r['charter'] for r in links if r['matched']).items()))}
    return {'roster_links': links, 'nonoperational_directory': excluded_directory,
            'outside_roster_profiles': outside, 'unsupported_native_profiles': unsupported,
            'cohorts': cohorts, 'coverage': coverage}


def validate(document, payload=None):
    expected = derive(document, payload if payload is not None else load_california())
    if any(document.get(key) != value for key, value in expected.items()):
        raise ValueError('Audit links, native count/suppression references or cohort coverage failed replay')
    if document.get('planning') != {
        'source': 'data/source/district-comparison-candidates.json',
        'potential_pure_ES': 572, 'potential_pure_HS': 147,
        'pure_ES_without_tested_grades': 17, 'pure_HS_without_grade_11': 3,
        'explanation': '17 K–2-or-lower schools lack grades 3–8; three grade-12-only schools lack grade 11. Planning counts are configuration screens, not model counts.',
    }:
        raise ValueError('Planning/applicability reconciliation changed')
    return expected['coverage']


def extract(directory=DIRECTORY, output=OUTPUT):
    directory, output = Path(directory), Path(output)
    if hashlib.sha256(directory.read_bytes()).hexdigest() != SOURCES['ccd_school_directory']['sha256']:
        raise ValueError('CCD archive changed; perform a fresh source audit')
    payload = load_california()
    with zipfile.ZipFile(directory) as archive:
        with archive.open(SOURCES['ccd_school_directory']['member']) as source:
            rows = csv.DictReader(io.TextIOWrapper(source, encoding='utf-8-sig'))
            records = [{'source_row': number, 'raw': row} for number, row in enumerate(rows, 2)
                       if row['LEAID'] == LEA]
    document = {'schema_version': 1, 'state': 'CA', 'year': 2025, 'academic_year': YEAR,
                'nces_lea_id': LEA, 'native_lea_id': NATIVE_LEA,
                'status': 'district_model_audit_pending', 'approved_for_modeling': False,
                'sources': SOURCES, 'policy': POLICY, 'directory_records': records,
                'planning': {
                    'source': 'data/source/district-comparison-candidates.json',
                    'potential_pure_ES': 572, 'potential_pure_HS': 147,
                    'pure_ES_without_tested_grades': 17, 'pure_HS_without_grade_11': 3,
                    'explanation': '17 K–2-or-lower schools lack grades 3–8; three grade-12-only schools lack grade 11. Planning counts are configuration screens, not model counts.',
                }}
    document.update(derive(document, payload))
    planning = json.loads(PLANNING.read_text())
    agency = next(r for r in planning['agencies'] if r['nces_lea_id'] == LEA)
    for level in ['ES', 'HS']:
        links = [r for r in document['roster_links'] if r.get('scope') == level
                 and (level == 'HS' or r['assessments'][level]['combined']['applicable'])]
        if {r['ncessch'] for r in links} != set(agency['potential_school_ids'][level]):
            raise ValueError('Exact pure cohort IDs no longer reconcile to CCD planning records')
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
