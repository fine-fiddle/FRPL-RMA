"""Canonical and static LAUSD district comparisons from pinned completed audits."""
import argparse
import hashlib
import json
from pathlib import Path

import audit_los_angeles as roster_audit
import audit_los_angeles_models as model_audit
import prepare_california as california
from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

DATASET = 'ca-lausd-2025'
EXTRACT = ROOT / 'data/source/los-angeles.json'
OUTPUT = ROOT / 'data/los-angeles'
NUMERICAL_SHA = '0e2b1911ac5306f9e5591a904db35c05c6ff1960065f52f20919de11c993f48d'
PROJECT_SOURCE = 'https://github.com/robot-assisted-projects/FRPL-RMA/blob/expansion/all-states/'
STANDARD = ('2024–25 CAASPP Smarter Balanced Standard Met or Exceeded (Levels 3+4); '
            'all students, valid scores only. California alternate assessments are excluded. '
            'Exact proficient and valid-score counts are summed across complete tested grades.')
VALID_SCORE_EVIDENCE = (
    '2025 CAASPP research-file layout: Overall Total is the scored performance-level '
    'denominator and equals Total Students Tested with Scores. Count Standard Met and '
    'Above is the proficient numerator. Every expected grade requires unsuppressed '
    'exact counts and a reconciled published rate; totals never recover protected grades. '
    + california.LAYOUT_URL)
MODEL_SCOPE = (
    'Los Angeles Unified district models: exact operational 2024–25 CCD LEA 0622710 '
    'attachments, including locally funded charters and alternatives; pure grade '
    'schools and pure high schools separately; mixed schools excluded. Separate '
    'same-year Smarter Balanced grades 3–8 and grade 11 Math, ELA and Combined models.')


def load_inputs():
    roster = model_audit.load_roster()
    content = model_audit.OUTPUT.read_bytes()
    if hashlib.sha256(content).hexdigest() != NUMERICAL_SHA:
        raise ValueError('LAUSD passed numerical audit fingerprint changed; re-audit the release')
    numerical = json.loads(content)
    model_audit.validate(numerical, model_audit.build(roster))
    if numerical['hard_holds'] or any(m['status'] != 'numerically_verified_pending_integration'
                                      or m['coefficients']['n'] < 30 for m in numerical['models']):
        raise ValueError('LAUSD numerical audit has unresolved release holds')
    return roster, numerical


def cohorts():
    return [dict(id='grade' if level == 'ES' else 'high', level=level,
                 assessment=california.ASSESSMENTS[level], grades='3–8' if level == 'ES' else '11',
                 standard=STANDARD, source='ca-sb-2025', source_url=california.LAYOUT_URL,
                 label='Grade schools · Smarter Balanced' if level == 'ES' else 'High schools · Smarter Balanced',
                 outcome='Standard met or exceeded',
                 note=california.ASSESSMENTS[level] + ' · valid scores · California alternate assessments excluded')
            for level in ['ES', 'HS']]


def outcome(value):
    return dict(proficiency=value['proficiency'] if value['usable'] else None,
                tested=value['valid_scores'] if value['usable'] else None,
                valid_score_evidence=VALID_SCORE_EVIDENCE if value['usable'] else None,
                exclusion=value['exclusion'], source='ca-sb-2025',
                source_row=value['expected_grade_records'][0]['source_row'] if value['expected_grade_records'] else 0,
                raw=dict(applicable=value['applicable'], expected_grades=value['expected_grades'],
                         exclusion=value['exclusion'], all_assessment_source_rows=value['source_rows'],
                         expected_grade_records=value['expected_grade_records']),
                raw_tested=[r['raw']['Overall Total'] for r in value['expected_grade_records']])


def build_snapshot(roster, numerical):
    schools, excluded = [], []
    directory = {r['source_row']: r['raw'] for r in roster['directory_records']}
    for school in sorted(roster['roster_links'], key=lambda r: r['school_id']):
        if school.get('scope') not in ['ES', 'HS']:
            excluded.append(dict(id=school['school_id'], ncessch=school['ncessch'],
                ccd_source_row=school['ccd_source_row'],
                reason='Mixed native grade configuration' if school['matched'] else school['exclusion'],
                profile_source_row=school['profile']['source_row'] if school['matched'] else None,
                scope=school.get('scope'),
                audit_source='roster_audit'))
            continue
        profile = school['profile']['raw']
        level = school['scope']
        schools.append(dict(id=school['school_id'], ncessch=school['ncessch'],
            cohort='grade' if level == 'ES' else 'high', name=profile['School Name'],
            district_id=roster_audit.NATIVE_LEA, district='Los Angeles Unified',
            county=profile['County Name'], city=None,
            enrollment=school['income']['enrollment'], low_income=school['income']['eligible'],
            income=school['income']['percentage'], income_raw=profile,
            income_source='ca-frpm-2025', income_row=school['income']['source_row'],
            identity_raw=dict(ccd_source_row=school['ccd_source_row'], ccd=directory[school['ccd_source_row']],
                              profile_source_row=school['profile']['source_row'],
                              native_grade_scope=level, charter=school['charter'],
                              assessment_type_ids=school['assessment_type_ids']),
            outcomes={s: outcome(school['assessments'][level][s]) for s in ['math', 'reading']}))
    source_audit = dict(
        operational_roster=roster['coverage'],
        cohorts=roster['cohorts'],
        excluded_roster_records=excluded,
        outside_roster_prefix_profiles=[dict(id=r['school_id'], profile_source_row=r['profile']['source_row'],
                                             assessment_type_ids=r['assessment_type_ids'], reason=r['exclusion'])
                                       for r in roster['outside_roster_profiles']],
        nonoperational_directory=roster['nonoperational_directory'],
        unsupported_native_profiles=[dict(id=r['school_id'], profile_source_row=r['profile']['source_row'],
                                          reason=r['exclusion']) for r in roster['unsupported_native_profiles']],
        release_basis=dict(exact_source_roster_replayed=True, numerical_audit_without_holds=True,
                           minimum_subject_schools=30, historical_audits_approved_for_modeling=False,
                           note='Historical source and numerical audits remain approved_for_modeling:false; this separate adapter verifies source, model and export integration before release.'))
    selection = dict(policy=model_audit.POLICY,
        directory_school_ids=[r['id'] for r in schools],
        subject_models={m['model_id']: dict(level=m['level'], subject=m['subject'],
            school_ids=[r['school_id'] for r in m['inputs']], population_sha256=m['population_sha256'])
            for m in numerical['models']})
    selection['sha256'] = roster_audit.fingerprint(selection)
    sources = dict(roster['sources'])
    sources.update(roster_audit=dict(path='data/source/los-angeles-district-audit.json',
                                    url=PROJECT_SOURCE + 'data/source/los-angeles-district-audit.json',
                                    sha256=model_audit.ROSTER_SHA),
                   numerical_audit=dict(path='data/source/los-angeles-model-audit.json',
                                        url=PROJECT_SOURCE + 'data/source/los-angeles-model-audit.json',
                                        sha256=NUMERICAL_SHA))
    coverage_note = (
        'Los Angeles Unified independent district comparison, 2024–25. The directory '
        'contains 589 pure grade-school and 147 pure high-school profiles attached to '
        'exact CCD LEA 0622710, including locally funded charters and alternatives. '
        'Seventeen primary-only and three grade-12-only profiles have no applicable '
        'assessment; missing and suppressed outcomes remain unavailable. Mixed schools '
        'and outside-roster reporting associations are excluded. Math/ELA/Combined '
        'models contain 561/561/561 grade schools and 137/137/136 high schools. '
        'High-school FRPM is clustered around 91%, and alternatives comprise 51 of '
        '136 Combined members; leverage and differing school populations limit interpretation. '
        'Statewide California predictions and district predictions use separate populations. '
        'One year only; no audited admissions classifications or school coordinates.')
    details = [
        MODEL_SCOPE,
        'Each subject uses an independent district fit. Filters do not refit it, and statewide residuals are never reused. Results describe associations within this district population, not causal school effectiveness.',
        'The whole pure directory is retained, including 17 primary-only and three grade-12-only profiles with no applicable assessed grade. Missing or suppressed values are never zero. Mixed schools, one unmatched operational preschool record and 218 outside-roster charter reporting profiles are excluded from the district directory but retained in source coverage.',
        VALID_SCORE_EVIDENCE,
        'Every expected native grade in the school span is required. Grades 3–8 and grade 11 remain separate. Combined is the equal mean of Math and ELA, not proficiency in both. California alternate assessments are excluded.',
        california.ECON_DEFINITION,
        'Externally studentized residuals use deleted-school variance. Conditional intervals propagate every model member’s verified valid-score sampling variance with regression scale held fixed; one eligible member without counts removes all intervals for that model. Combined uses the covariance upper bound from both subject variances; the minimum subject count is display-only. Studentization provides no enrollment adjustment or shrinkage.',
        'High-school income means are 91.34–91.40%, standard deviations 8.76–8.78 points, and the range is 56.60–100%. Lower-income members have greater leverage; deleting one member can shift predictions by up to 3.50 proficiency points within the observed income range. All source-eligible alternatives and locally funded charters remain in the chosen population.',
        'This is a single-year comparison. There are no audited admissions classifications, coordinates or boundaries. State proficiency standards and FRPM eligibility do not create an interchangeable national scale.',
    ]
    return dict(schema_version=1, dataset=DATASET, year=2025, academic_year='2024–25',
        state=dict(id='CA', name='California'), name='Los Angeles Unified 2024–25 district comparison',
        region='los-angeles', region_name='Los Angeles Unified', statewide=False,
        comparison='Los Angeles Unified · {year} · {assessment} · {note}',
        prepare_script='scripts/prepare_los_angeles.py', source_url=california.RESEARCH_URL,
        retrieved='2026-10-09', model_scope=MODEL_SCOPE, release_status='ready',
        map_source='School coordinates and district boundaries are unavailable in the audited LAUSD sources.',
        income_definition=dict(label='K–12 FRPM eligibility', definition=california.ECON_DEFINITION,
                               url=california.INCOME_INFO_URL),
        sources=sources, cohorts=cohorts(), schools=schools, selection=selection,
        source_audit=source_audit, coverage_note=coverage_note,
        methodology=dict(summary='Los Angeles Unified independent district models with same-year FRPM eligibility.',
            details=details, sources=[dict(label='Official 2025 CAASPP research files', url=california.RESEARCH_URL),
                dict(label='Official 2025 CAASPP field definitions', url=california.LAYOUT_URL),
                dict(label='Official 2024–25 CDE FRPM workbook', url=california.INCOME_URL),
                dict(label='Official 2024–25 CCD exact school roster', url=roster_audit.SOURCES['ccd_school_directory']['url'])]))


def validate(payload, expected=None):
    expected = build_snapshot(*load_inputs()) if expected is None else expected
    if payload != expected:
        raise ValueError('LAUSD normalized extract differs from pinned source/model evidence, scope or selection policy')
    return payload['source_audit']


def extract(destination=EXTRACT):
    payload = build_snapshot(*load_inputs())
    Path(destination).write_text(json.dumps(payload, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return payload


def validate_exports(payload, output, numerical):
    output = Path(output)
    schools = json.loads((output / 'schools.json').read_text())
    history = json.loads((output / 'history.json').read_text())
    exported = {s['id']: s for s in schools['schools']}
    records = {r['school_id']: r for r in history['records']}
    profiles = {s['id']: s for s in payload['schools']}
    if (len(exported) != len(profiles) or len(schools['schools']) != len(profiles)
            or len(history['records']) != len(profiles)
            or set(exported) != set(profiles) or set(records) != set(profiles)):
        raise ValueError('LAUSD exported pure directory identities differ from source selection')
    expected_keys = {(2025, m['level'], california.ASSESSMENTS[m['level']], m['subject'])
                     for m in numerical['models']}
    for summaries in [schools['history_models'], history['models']]:
        keyed = {(m['year'], m['level'], m['assessment'], m['subject']): m for m in summaries}
        if len(summaries) != 6 or len(keyed) != 6 or set(keyed) != expected_keys:
            raise ValueError('LAUSD history must retain exactly the six independently audited model populations')
        for key, summary in keyed.items():
            if summary != schools['models'][key[1]][key[3]]:
                raise ValueError('LAUSD historical model summaries differ from current district fits')
    for model in numerical['models']:
        level, subject = model['level'], model['subject']
        actual_model = schools['models'][level][subject]
        if actual_model is None or not model_audit.numeric_equal(
                {k: actual_model[k] for k in model['coefficients']}, model['coefficients']):
            raise ValueError('LAUSD exported district coefficients differ from passed numerical audit')
        if (actual_model['year'], actual_model['level'], actual_model['assessment'], actual_model['subject']) != (
                2025, level, california.ASSESSMENTS[level], subject):
            raise ValueError('LAUSD exported assessment population metadata changed')
        expected_metrics = {r['school_id']: r for r in model['results']}
        expected_inputs = {r['school_id']: r for r in model['inputs']}
        eligible = {s['id'] for s in schools['schools'] if s['level'] == level and subject in s['metrics']}
        if eligible != set(expected_metrics):
            raise ValueError('LAUSD exported subject membership differs from passed district audit')
        for key, reference in expected_metrics.items():
            metric = exported[key]['metrics'][subject]
            fields = ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'leverage']
            if (not model_audit.numeric_equal({k: metric[k] for k in fields}, {k: reference[k] for k in fields})
                    or metric['tested'] != expected_inputs[key]['display_valid_scores']
                    or metric['cohort_n'] != model['coefficients']['n']
                    or metric != records[key]['subjects'][subject]):
                raise ValueError('LAUSD per-school district metric differs from independently verified fit')
    for key, school in exported.items():
        profile = profiles[key]
        expected_level = 'ES' if profile['cohort'] == 'grade' else 'HS'
        if (school['level'] != expected_level or school['income'] != profile['income']
                or records[key]['income_year'] != 2025 or school['history'] != [records[key]]
                or school['latitude'] is not None or school['longitude'] is not None):
            raise ValueError('LAUSD profile/history/coordinate evidence changed')
        for subject in ['math', 'reading']:
            if profile['outcomes'][subject]['exclusion'] is not None:
                if subject in school['metrics'] or school['exclusions'].get(subject) != profile['outcomes'][subject]['exclusion']:
                    raise ValueError('LAUSD missing/suppressed/applicability exclusion was not preserved')
    return {m['model_id']: m['coefficients']['n'] for m in numerical['models']}


def prepare(database=DEFAULT_DB, output=OUTPUT, extract_path=EXTRACT):
    roster, numerical = load_inputs()
    payload = json.loads(Path(extract_path).read_text())
    validate(payload, build_snapshot(roster, numerical))
    coverage = prepare_snapshot(payload, extract_path, output, database)
    descriptor_path = Path(output) / 'catalog.json'
    descriptor = json.loads(descriptor_path.read_text())
    descriptor['regions'][0].update(name=payload['region_name'], statewide=False,
        comparison=payload['comparison'], audit=str((Path(output) / 'coverage.json').relative_to(ROOT)))
    descriptor_path.write_text(json.dumps(descriptor, indent=2) + '\n')
    validate_exports(payload, output, numerical)
    return coverage


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract:
        extract()
    result = prepare(args.database)
    print(json.dumps({k: result[k] for k in ['year', 'schools', 'cohorts']}, sort_keys=True))
