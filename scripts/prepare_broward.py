"""Canonical and static Broward comparisons from pinned completed district audits."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import audit_broward as roster_audit
import audit_broward_models as model_audit
import prepare_florida as florida
from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

DATASET = 'fl-broward-2025'
EXTRACT = ROOT / 'data/source/broward.json'
OUTPUT = ROOT / 'data/broward'
NUMERICAL_SHA = '882067b31bae9fa2f524ff458b55479b8953f52f819a6a87eedb70242b54233d'
PROJECT_SOURCE = 'https://github.com/robot-assisted-projects/FRPL-RMA/blob/expansion/all-states/'
MODEL_SCOPE = (
    'Broward County independent 2024–25 grade-school district models: exact '
    'operational CCD LEA 1200180 / native FL-06 attachments, complete reported '
    'pure lower offerings including grade 3–8, and explicit-zero native enrolled '
    'grades 9–12. Exact attached charters, alternatives and special-education '
    'profiles are retained; native missing outcomes determine eligibility. '
    'Separate same-year native Florida School Grades Math, ELA and Combined '
    'point-only OLS models. High and mixed offerings are excluded.')


def load_inputs():
    roster = model_audit.load_roster()
    content = model_audit.OUTPUT.read_bytes()
    if hashlib.sha256(content).hexdigest() != NUMERICAL_SHA:
        raise ValueError('Broward passed numerical audit fingerprint changed; re-audit the release')
    numerical = json.loads(content)
    model_audit.validate(numerical, model_audit.build(roster))
    if (numerical['hard_holds'] or numerical['approved_for_source'] is not False
            or roster['approved_for_source'] is not False or numerical['approved_for_modeling'] is not False
            or roster['approved_for_modeling'] is not False
            or {(m['level'], m['subject']) for m in numerical['models']} != {('ES', s) for s in model_audit.SUBJECTS}
            or len(numerical['models']) != 3
            or any(m['status'] != 'numerically_verified_pending_integration'
                   or m['coefficients']['n'] < 30 or m['intervals']['available_for_entire_model']
                   for m in numerical['models'])):
        raise ValueError('Broward numerical audit has unresolved release or population holds')
    return roster, numerical


def cohorts():
    # Exact native assessment/grades/standard/source definition; the district
    # population policy is separate and definitions are namespaced on import.
    return florida.normalize(roster_audit.load_florida())['cohorts']


def outcome(value, school, campus):
    return dict(
        proficiency=value['native_rate'] if value['district_usable'] else None,
        tested=None, valid_score_evidence=None, raw_tested=None,
        exclusion=value['district_exclusion'], source='assessment', source_row=value['source_row'],
        raw=dict(applicable=value['district_applicable'],
                 native_grade_school_usable=value['native_grade_school_usable'],
                 native_outcome_exclusion=value['native_outcome_exclusion'],
                 source_contract_exclusion=value['source_contract_exclusion'],
                 district_exclusion=value['district_exclusion'],
                 native_achievement=value['native_achievement_raw'],
                 native_achievement_field=value['native_achievement_field'],
                 assessment_raw=None if campus is None else campus['raw'],
                 offered_tested_grades=school['offered']['offered_tested_grades'],
                 enrolled_tested_evidence=school['enrolled']['positive_or_protected_tested_grades'],
                 valid_score_count=None, sampling_variance=None,
                 interval_availability=False,
                 count_note='Native whole-percent achievement has no verified valid-score denominator.'))


def build_snapshot(roster, numerical):
    schools, excluded = [], []
    directory = {r['source_row']: r['raw'] for r in roster['directory_records']}
    campus = {a['id']: a for a in roster['native_records']['assessments'] if a['raw'][3] in ('', None)}
    for school in sorted(roster['roster_links'], key=lambda r: r['school_id']):
        if not school['matched'] or school['offered']['scope'] != 'ES':
            excluded.append(dict(
                id=school['school_id'], ncessch=school['ncessch'], ccd_source_row=school['ccd_source_row'],
                offered_scope=school['offered']['scope'],
                reason=school['exclusion'] if not school['matched'] else
                    'High or mixed offered configuration outside the approved pure grade-school district population',
                native_grade_school_contract=school['enrolled']['native_grade_school_contract'] if school['matched'] else None,
                native_assessment_source_rows=school['native_assessment_rows'],
                ccd_flags=school['ccd_flags'], native_record=school, audit_source='roster_audit'))
            continue
        if not school['enrolled']['native_grade_school_contract']:
            raise ValueError('Pure directory profiles must retain explicit-zero native high-grade enrollment')
        profile = school['profile']
        schools.append(dict(
            id=school['school_id'], ncessch=school['ncessch'], cohort='grade-schools',
            name=profile['grades'][3], district_id=roster_audit.NATIVE_LEA, district='Broward County',
            city=None, county=None,
            enrollment=school['income']['survey_enrollment'], low_income=school['income']['individual_eligible'],
            income=school['income']['percentage'], income_raw=school['income']['raw'],
            income_source='income', income_row=school['income']['source_row'],
            identity_raw=dict(ccd_source_row=school['ccd_source_row'], ccd=directory[school['ccd_source_row']],
                              grade_source_row=profile['grade_row'], grade_raw=profile['grades'],
                              offered_evidence=school['offered'], enrolled_evidence=school['enrolled'],
                              ccd_flags=school['ccd_flags'], native_assessment_flags=school['native_assessment_flags'],
                              native_assessment_source_rows=school['native_assessment_rows']),
            outcomes={s: outcome(school['subjects'][s], school, campus.get(school['school_id']))
                      for s in ['math', 'reading']}))
    if len(schools) != 249:
        raise ValueError('Broward release must retain all 249 exact pure directory profiles')
    source_audit = dict(
        operational_roster=roster['coverage'], cohorts=roster['cohorts'],
        excluded_operational_roster_records=excluded,
        nonoperational_directory=roster['nonoperational_directory'],
        outside_roster_profiles=roster['outside_roster_profiles'],
        native_assessments_without_operational_roster=roster['native_assessments_without_operational_roster'],
        income_without_fall_registry_links=roster['income_without_fall_registry_links'],
        full_directory_records=roster['directory_records'], directory_header=roster['directory_header'],
        native_records=roster['native_records'],
        provider_specific_virtual_rows=[a for a in roster['native_records']['assessments'] if a['raw'][3] not in ('', None)],
        income_worksheet_headers=roster['income_worksheet_headers'],
        release_basis=dict(exact_source_roster_replayed=True, numerical_audit_without_holds=True,
                           minimum_subject_schools=30, historical_audits_approved_for_modeling=False,
                           all_models_point_only=True,
                           note='Historical source and numerical audits retain false approval flags. This separate adapter validates normalized selection and every exported district model/metric before release.'))
    selection = dict(policy=model_audit.POLICY, frozen_source_population=numerical['frozen_population'],
        directory_school_ids=[r['id'] for r in schools],
        subject_models={m['model_id']: dict(level=m['level'], subject=m['subject'],
            school_ids=[r['school_id'] for r in m['inputs']], population_sha256=m['population_sha256'])
            for m in numerical['models']})
    selection['sha256'] = roster_audit.fingerprint(selection)
    sources = dict(roster['sources'])
    sources.update(
        roster_audit=dict(path='data/source/broward-district-audit.json',
                          url=PROJECT_SOURCE + 'data/source/broward-district-audit.json', sha256=model_audit.ROSTER_SHA),
        numerical_audit=dict(path='data/source/broward-model-audit.json',
                             url=PROJECT_SOURCE + 'data/source/broward-model-audit.json', sha256=NUMERICAL_SHA))
    coverage_note = (
        'Broward County independent district comparison, 2024–25. Exact CCD LEA '
        '1200180 / FL-06 pure lower directory contains 249 Regular profiles, including attached '
        'charters. Exact alternative/special-education flags remain in full source coverage. Of 243 schools offering '
        'grades 3–8, 241 have matching native income and Math/ELA outcomes. Six primary-only '
        'profiles are nonapplicable and two offered-applicable profiles lack achievement. '
        'All 241 eligible schools are regular schools: 176 noncharter and 65 charter. '
        'Three native enrolled-grade schools with mixed CCD offerings remain outside this pure '
        'district cohort; all three have usable native outcomes. Full-year/home-zoned achievement '
        'and February lunch eligibility describe different populations. No verified score '
        'counts: all model sampling intervals unavailable. No high/mixed models, audited '
        'admissions classifications, coordinates or boundaries; one year only.')
    details = [
        MODEL_SCOPE,
        'Every subject uses an independent district OLS fit and externally studentized residuals. Filters do not refit it, and statewide Florida residuals are never reused. Associations do not establish causal school effectiveness or overall quality.',
        'All 249 pure lower profiles stay in the directory, including six primary-only nonapplicable schools and two schools with unavailable campus achievement. One has only provider-specific virtual achievement; the other has explicit-zero Fall enrolled grades 3–8. Source scope and missingness determine eligibility, never performance selection. High/mixed offered configurations, unmatched operational records and outside-roster profiles remain in source coverage.',
        'The offered-grade population requires complete reported PK–8-only flags, at least one offered grade 3–8, and explicit-zero Survey 2 enrollment in all grades 9–12. Protected positive counts are never zero. One school offers tested grades while reporting explicit Fall zeros in all grades 3–8; it remains offered-applicable with missing outcomes.',
        florida.STANDARD,
        florida.ECON,
        'The outcome, Fall grade registry and February income describe different prescribed populations. Whole-percent achievement rounding and incomplete CEP income eligibility remain limitations. Published economic percentages, enrollment, percent tested, letter grades and the ten-student publication floor never supply valid-score denominators.',
        'Combined is the equally weighted mean of eligible Math and ELA proficiency, not proficiency in both. Counts and sampling variances are unavailable and no interval endpoints are published for any member of any district model. External studentization uses each deleted-school residual scale; it provides no enrollment adjustment or shrinkage.',
        'Independent full fits and every leave-one-out fit were verified. Maximum leverage is 0.029597; deleting one member changes the fitted line by at most 1.019 proficiency points across observed income. Conventional influence flags are descriptive, never reasons to discard schools or assign quality labels.',
        'This is a single-year grade-school comparison. No audited admissions classifications, coordinates or boundaries are supplied. State assessment standards and economic eligibility do not create an interchangeable national scale.',
    ]
    return dict(
        schema_version=1, dataset=DATASET, year=2025, academic_year='2024–25',
        state=dict(id='FL', name='Florida'), name='Broward County 2024–25 district comparison',
        region='broward', region_name='Broward County', statewide=False,
        comparison='Broward County · {year} · {assessment} · {note}',
        prepare_script='scripts/prepare_broward.py', source_url=florida.PORTAL,
        retrieved=roster_audit.load_florida()['retrieved'], model_scope=MODEL_SCOPE, release_status='ready',
        map_source='School coordinates and district boundaries are unavailable in the audited Broward sources.',
        income_definition=dict(label='Individual reported FRPL/direct-certification eligibility', definition=florida.ECON,
                               url=florida.LUNCH_GUIDE),
        sources=sources, cohorts=cohorts(), schools=schools, selection=selection,
        source_audit=source_audit, coverage_note=coverage_note,
        methodology=dict(summary='Broward County independent district grade-school models with same-year individual lunch eligibility.',
            details=details, sources=[dict(label='2025 native Florida School Grades', url=florida.FILES['assessment'][1]),
                dict(label='2024–25 individual Lunch Status counts', url=florida.FILES['income'][1]),
                dict(label='2024–25 native enrolled grades', url=florida.FILES['grades'][1]),
                dict(label='2024–25 Florida achievement inclusion rules', url=florida.GRADE_GUIDE),
                dict(label='2024–25 Lunch Status definitions', url=florida.LUNCH_GUIDE),
                dict(label='2024–25 CCD exact school roster', url=roster_audit.SOURCES['ccd_school_directory']['url'])]))


def build():
    return build_snapshot(*load_inputs())


def same(actual, expected):
    return roster_audit.fingerprint(actual) == roster_audit.fingerprint(expected)


def validate(payload, expected=None):
    expected = build() if expected is None else expected
    if not same(payload, expected):
        raise ValueError('Broward normalized extract differs from pinned source/model evidence, scope or selection policy')
    return payload['source_audit']


def extract(destination=EXTRACT):
    payload = build()
    Path(destination).write_text(json.dumps(payload, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return payload


def validate_exports(payload, output, numerical):
    output = Path(output)
    schools = json.loads((output / 'schools.json').read_text())
    history = json.loads((output / 'history.json').read_text())
    coverage = json.loads((output / 'coverage.json').read_text())
    descriptor = json.loads((output / 'catalog.json').read_text())
    exported = {s['id']: s for s in schools['schools']}
    records = {r['school_id']: r for r in history['records']}
    profiles = {s['id']: s for s in payload['schools']}
    if (len(schools['schools']) != 249 or len(history['records']) != 249
            or set(exported) != set(profiles) or set(records) != set(profiles)):
        raise ValueError('Broward exported native source directory/history identities differ from selection')
    if set(schools['models']) != {'ES'} or set(schools['models']['ES']) != set(model_audit.SUBJECTS):
        raise ValueError('Broward export requires only the three independently audited ES models')
    expected_keys = {(2025, 'ES', model_audit.ASSESSMENT, m['subject']) for m in numerical['models']}
    for summaries in [schools['history_models'], history['models']]:
        keyed = {(m['year'], m['level'], m['assessment'], m['subject']): m for m in summaries}
        if len(summaries) != 3 or len(keyed) != 3 or set(keyed) != expected_keys:
            raise ValueError('Broward history must retain exactly three audited ES model populations')
        if any(not same(summary, schools['models']['ES'][key[3]]) for key, summary in keyed.items()):
            raise ValueError('Broward historical model summaries differ from current district fits')
    for model in numerical['models']:
        subject = model['subject']
        actual_model = schools['models']['ES'][subject]
        expected_model = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                              assessed_schools=249, excluded_schools=8, **model['coefficients'])
        exact_model = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
        if (not same({k: actual_model.get(k) for k in exact_model}, {k: expected_model[k] for k in exact_model})
                or not model_audit.numeric_equal(actual_model, expected_model)):
            raise ValueError('Broward exported district coefficients/coverage differ from numerical audit')
        reference = {r['school_id']: r for r in model['results']}
        eligible = {s['id'] for s in schools['schools'] if subject in s['metrics']}
        if eligible != set(reference):
            raise ValueError('Broward exported subject membership differs from passed district audit')
        for key, result in reference.items():
            fields = ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'leverage']
            metric = exported[key]['metrics'][subject]
            expected_metric = {k: result[k] for k in fields} | dict(tested=None, cohort_n=241)
            exact = ['actual', 'tested', 'low', 'high', 'cohort_n']
            if (not same({k: metric.get(k) for k in exact}, {k: expected_metric[k] for k in exact})
                    or not model_audit.numeric_equal(metric, expected_metric)
                    or not same(metric, records[key]['subjects'][subject])):
                raise ValueError('Broward per-school point-only metric differs from verified district fit')
    for key, school in exported.items():
        profile = profiles[key]
        record = records[key]
        expected_subjects = {m['subject'] for m in numerical['models'] if key in {r['school_id'] for r in m['results']}}
        if set(school['metrics']) != expected_subjects or set(record['subjects']) != expected_subjects:
            raise ValueError('Broward profile/history subject set differs from exact audited eligibility')
        expected_exclusions = {s: profile['outcomes'][s]['exclusion'] for s in ['math', 'reading']
                               if profile['outcomes'][s]['exclusion'] is not None}
        if expected_exclusions:
            expected_exclusions['combined'] = '; '.join(
                ('Math' if s == 'math' else 'ELA') + ': ' + expected_exclusions[s]
                for s in ['math', 'reading'] if s in expected_exclusions)
        profile_fields = dict(level='ES', name=profile['name'], short=profile['name'],
            district=profile['district'], income=profile['income'], enrollment=None if profile['enrollment'] is None else float(profile['enrollment']),
            city=profile['city'], county=profile['county'], latitude=None, longitude=None,
            program='Unclassified', programs=['Unclassified'], exclusions=expected_exclusions)
        record_fields = dict(level='ES', year=2025, income_year=2025,
            assessment=model_audit.ASSESSMENT, name=profile['name'], income=profile['income'],
            enrollment=None if profile['enrollment'] is None else float(profile['enrollment']), income_label=payload['income_definition']['label'],
            exclusions=expected_exclusions)
        if (not same({k: school.get(k) for k in profile_fields}, profile_fields)
                or not same({k: record.get(k) for k in record_fields}, record_fields)
                or not same(school['history'], [record])):
            raise ValueError('Broward profile/history/exclusion/geography evidence changed')
    expected_coverage = {'grade-schools': {'directory': 249, 'eligible': {s: 241 for s in model_audit.SUBJECTS}}}
    if not same(coverage, dict(year=2025, schools=249, cohorts=expected_coverage,
            source_audit=payload['source_audit'], exclusions=dict(Counter(
                reason for r in records.values() for reason in r['exclusions'].values())))):
        raise ValueError('Broward exported coverage/source exclusions differ from approved selection')
    cohort = payload['cohorts'][0]
    expected_levels = {'ES': dict(year=2025, label=cohort['label'], assessment=cohort['assessment'],
                                  outcome=cohort['outcome'], math_label='Math', note=cohort['note'])}
    header = dict(year=payload['academic_year'], assessment_year=2025,
        income_label=payload['income_definition']['label'], program_options=['Unclassified'],
        levels=expected_levels, history_years=[2025], coverage_note=payload['coverage_note'],
        methodology=payload['methodology'])
    if not same({k: schools.get(k) for k in header}, header):
        raise ValueError('Broward exported native assessment definition or methodology changed')
    expected_descriptor = dict(schema_version=1, state=payload['state'], prepare_script=payload['prepare_script'],
        regions=[dict(id='broward', geography='broward', name=payload['region_name'], dataset=DATASET,
            statewide=False, status='ready', levels=['ES'], boundaries=None, comparison=payload['comparison'],
            audit=str((output / 'coverage.json').relative_to(ROOT)),
            schools=str((output / 'schools.json').relative_to(ROOT)),
            model_scope=payload['model_scope'], map_source=payload['map_source'])])
    if not same(descriptor, expected_descriptor):
        raise ValueError('Broward ready descriptor must retain distinct district and point-only scope')
    return {m['model_id']: m['coefficients']['n'] for m in numerical['models']}


def prepare(database=DEFAULT_DB, output=OUTPUT, extract_path=EXTRACT):
    output, extract_path = Path(output).resolve(), Path(extract_path).resolve()
    # The shared helper emits repository-relative provenance/catalog links.
    # Reject unsupported destinations before opening any database transaction.
    output.relative_to(ROOT)
    extract_path.relative_to(ROOT)
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
    parser.add_argument('--extract-only', action='store_true', help='Rebuild normalized evidence without database import or exports')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.extract or args.extract_only:
        extract()
    if args.extract_only:
        print(json.dumps({'dataset': DATASET, 'normalized_extract': str(EXTRACT)}, sort_keys=True))
    else:
        result = prepare(args.database, args.output)
        print(json.dumps({k: result[k] for k in ['year', 'schools', 'cohorts']}, sort_keys=True))
