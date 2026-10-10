"""Canonical and static Palm Beach comparisons from pinned completed district audits."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path

import audit_palm_beach as roster_audit
import audit_palm_beach_models as model_audit
import prepare_florida as florida
from database import ROOT, DEFAULT_DB, connect, definition_id
from state_snapshot import prepare_snapshot

DATASET = 'fl-palm-beach-2025'
EXTRACT = ROOT / 'data/source/palm-beach.json'
OUTPUT = ROOT / 'data/palm-beach'
NUMERICAL_SHA = 'cd7ea4be8667f4632b2eb03f7793180387d765d741def824eb209ddd944497e8'
PROJECT_SOURCE = 'https://github.com/robot-assisted-projects/FRPL-RMA/blob/expansion/all-states/'
MODEL_SCOPE = (
    'Palm Beach County independent 2024–25 grade-school district models: exact '
    'operational CCD LEA 1201500 / native FL-50 attachments, complete reported '
    'pure lower offerings including grade 3–8, and explicit-zero native enrolled '
    'grades 9–12. Exact attached charters, alternatives, special-education and Career and Technical '
    'profiles are retained; native missing outcomes determine eligibility. '
    'Separate same-year native Florida School Grades Math, ELA and Combined '
    'point-only OLS models. High and mixed offerings are excluded.')


def load_inputs():
    roster = model_audit.load_roster()
    content = model_audit.OUTPUT.read_bytes()
    if hashlib.sha256(content).hexdigest() != NUMERICAL_SHA:
        raise ValueError('Palm Beach passed numerical audit fingerprint changed; re-audit the release')
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
        raise ValueError('Palm Beach numerical audit has unresolved release or population holds')
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
            name=profile['grades'][3], district_id=roster_audit.NATIVE_LEA, district='Palm Beach County',
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
    if len(schools) != 170:
        raise ValueError('Palm Beach release must retain all 170 exact pure directory profiles')
    source_audit = dict(
        operational_roster=roster['coverage'], cohorts=roster['cohorts'],
        excluded_operational_roster_records=excluded,
        nonoperational_directory=roster['nonoperational_directory'],
        outside_roster_profiles=roster['outside_roster_profiles'],
        native_assessments_without_operational_roster=roster['native_assessments_without_operational_roster'],
        income_without_fall_registry_links=roster['income_without_fall_registry_links'],
        full_directory_records=roster['directory_records'], directory_header=roster['directory_header'],
        planning_identity_reconciliation=roster['planning_identity_reconciliation'],
        planning_membership_evidence=roster['planning_membership_evidence'],
        planning_membership_exclusions=roster['planning_membership_exclusions'],
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
        roster_audit=dict(path='data/source/palm-beach-district-audit.json',
                          url=PROJECT_SOURCE + 'data/source/palm-beach-district-audit.json', sha256=model_audit.ROSTER_SHA),
        numerical_audit=dict(path='data/source/palm-beach-model-audit.json',
                             url=PROJECT_SOURCE + 'data/source/palm-beach-model-audit.json', sha256=NUMERICAL_SHA))
    coverage_note = (
        'Palm Beach County independent district comparison, 2024–25. Exact CCD LEA '
        '1201500 / FL-50 retains 170 matched pure lower profiles, including two '
        'nonapplicable primary-only schools. Of 168 offered-applicable profiles, '
        '165 have eligible native individual income and Math/ELA outcomes; three '
        'applicable profiles lack campus achievement. All 165 members retain their '
        'native flags: 141 noncharter and 24 charter, comprising 164 Regular schools '
        'and Career and Technical charter South Tech Preparatory Academy. All four '
        'missing-Fall mixed records and both provider-specific 50-7001 records remain '
        'in source coverage, never supplying invented campus outcomes. No eligible '
        'member has zero recorded income; observed zero and masked income retain '
        'their separate source reasons. Full-year/home-zoned achievement and February '
        'lunch eligibility describe different populations. No verified score counts: '
        'all model sampling intervals unavailable. No high/mixed models, audited '
        'admissions classifications, coordinates or boundaries; one year only.')
    details = [
        MODEL_SCOPE,
        'Every subject uses an independent district OLS fit and externally studentized residuals. Filters do not refit it, and statewide Florida residuals are never reused. Associations do not establish causal school effectiveness or overall quality.',
        'The discovery screen has 168 potential grade schools, matching the 168 native source-applicable profiles; independently verified source income/outcomes support 165 model members. Planning never selects model members. All 170 pure offered configurations have native source profiles. The original 58-row CCD membership proof retains four missing-Fall mixed schools and both primary-only schools; reported-zero CCD membership never creates native income or outcomes.',
        'All 170 matched pure lower profiles stay in the directory, including primary 50-1931 and 50-3100 and applicable 50-2791, 50-4100 and 50-0040 with unavailable campus achievement. Four unmatched operational configurations, all high/mixed offerings, all nonoperational records and the complete native roster remain retained in coverage without invented profiles.',
        'The offered-grade population requires complete reported PK–8-only flags, at least one offered grade 3–8, and explicit-zero Survey 2 enrollment in all grades 9–12. Protected positive counts never mean zero. All 168 applicable profiles have positive or protected tested-grade enrollment; raw offered/enrolled differences remain auditable.',
        'Career and Technical charter 50-3441, South Tech Preparatory Academy, remains eligible with offered grades 6–8, native Math 67 / ELA 70 and individual eligibility 350/528. The population retains native school-type labels rather than imposing a Regular-only filter; conventional influence flags never remove a member.',
        'Provider-specific 50-7001 records identify providers 302 and 309 at worksheet rows 2712 and 2713, with Math/ELA 67/81 and 38/56 respectively. There is no campus achievement row. The campus individual eligibility 9/89 cannot support either provider population; these mixed records remain outside the release and are never averaged or attributed to campus income.',
        'Seven native profiles have zero recorded individual eligibility with positive February enrollment. Pure 50-2791 lacks campus achievement and 50-3100 is primary-only; their recorded zero remains 0%, not missing. No eligible member has zero income. Mixed 50-3039 and 50-3091 retain masked enrollment and income, including masked code 4; actual Provision 2 participation is not established. Zero recorded eligibility does not establish that no low-income families attend.',
        florida.STANDARD,
        florida.ECON,
        'The outcome, Fall grade registry and February income describe different prescribed populations. Whole-percent achievement rounding and incomplete CEP income eligibility remain limitations. Published economic percentages, enrollment, percent tested, letter grades and the ten-student publication floor never supply valid-score denominators.',
        'Combined is the equally weighted mean of eligible Math and ELA proficiency, not proficiency in both. Counts and sampling variances are unavailable and no interval endpoints are published for any member of any district model. External studentization uses each deleted-school residual scale; it provides no enrollment adjustment or shrinkage.',
        'Independent full fits and all 495 leave-one-out fits were verified. Maximum leverage is 0.028054; deleting one member changes a fitted line by at most 0.933 proficiency points across observed income. South Tech remains included with its Career and Technical designation and descriptive ELA residual flag. Conventional influence flags are descriptive, never reasons to discard schools or assign quality labels.',
        'This is a single-year grade-school comparison. No audited admissions classifications, coordinates or boundaries are supplied. State assessment standards and economic eligibility do not create an interchangeable national scale.',
    ]
    return dict(
        schema_version=1, dataset=DATASET, year=2025, academic_year='2024–25',
        state=dict(id='FL', name='Florida'), name='Palm Beach County 2024–25 district comparison',
        region='palm-beach', region_name='Palm Beach County', statewide=False,
        comparison='Palm Beach County · {year} · {assessment} · {note}',
        prepare_script='scripts/prepare_palm_beach.py', source_url=florida.PORTAL,
        retrieved=roster_audit.load_florida()['retrieved'], model_scope=MODEL_SCOPE, release_status='ready',
        map_source='School coordinates and district boundaries are unavailable in the audited Palm Beach sources.',
        income_definition=dict(label='Individual reported FRPL/direct-certification eligibility', definition=florida.ECON,
                               url=florida.LUNCH_GUIDE),
        sources=sources, cohorts=cohorts(), schools=schools, selection=selection,
        source_audit=source_audit, coverage_note=coverage_note,
        methodology=dict(summary='Palm Beach County independent district grade-school models with same-year individual lunch eligibility.',
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
        raise ValueError('Palm Beach normalized extract differs from pinned source/model evidence, scope or selection policy')
    return payload['source_audit']


def extract(destination=EXTRACT):
    payload = build()
    Path(destination).write_text(json.dumps(payload, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return payload


def validate_canonical(payload, database, numerical, extract_path=EXTRACT):
    """Read every scoped canonical input/result and compare with the passed audits."""
    cohort = payload['cohorts'][0]
    assessment_id = definition_id(DATASET, 2025, cohort['assessment'], 'ES')
    income_id = DATASET + ':income'
    profiles = {s['id']: s for s in payload['schools']}
    number = lambda value: None if value is None else float(value)
    with closing(connect(database)) as db:
        dataset = db.execute('SELECT * FROM dataset WHERE id=?', (DATASET,)).fetchone()
        if dataset is None or not same(dict(dataset), dict(id=DATASET, state='FL', name=payload['name'],
                model_scope=payload['model_scope'], status='ready')):
            raise ValueError('Palm Beach canonical dataset release metadata changed')
        sources = dict(payload['sources'])
        sources['extract'] = dict(path=str(Path(extract_path).resolve().relative_to(ROOT)),
                                 url=payload['source_url'], sha256=hashlib.sha256(Path(extract_path).read_bytes()).hexdigest())
        expected_sources = {DATASET + ':' + key: dict(id=DATASET + ':' + key, dataset_id=DATASET,
            path=source['path'], url=source['url'], sha256=source['sha256'], imported_at=payload['retrieved'])
            for key, source in sources.items()}
        actual_sources = {r['id']: dict(r) for r in db.execute('SELECT * FROM source WHERE dataset_id=?', (DATASET,))}
        if not same(actual_sources, expected_sources):
            raise ValueError('Palm Beach canonical source provenance changed')
        definitions = [dict(r) for r in db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_definition = dict(id=assessment_id, state='FL', name=cohort['assessment'], year=2025,
            level='ES', grades=cohort['grades'], standard=cohort['standard'], source_url=cohort['source_url'])
        income = db.execute('SELECT * FROM economic_definition WHERE id=?', (income_id,)).fetchone()
        expected_income = dict(id=income_id, name=payload['income_definition']['label'],
            definition=payload['income_definition']['definition'], source_url=payload['income_definition']['url'])
        if not same(definitions, [expected_definition]) or income is None or not same(dict(income), expected_income):
            raise ValueError('Palm Beach canonical native assessment/income definition changed')
        school_rows = list(db.execute('SELECT * FROM school WHERE dataset_id=?', (DATASET,)))
        economic_rows = list(db.execute('SELECT * FROM economic_observation WHERE dataset_id=?', (DATASET,)))
        observation_rows = list(db.execute('SELECT * FROM assessment_observation WHERE dataset_id=?', (DATASET,)))
        if len(school_rows) != 170 or len(economic_rows) != 170 or len(observation_rows) != 340:
            raise ValueError('Palm Beach canonical profile/observation row counts changed')
        schools = {r['school_id']: dict(r) for r in school_rows}
        economic = {r['school_id']: dict(r) for r in economic_rows}
        observations = {(r['school_id'], r['subject']): dict(r) for r in observation_rows}
        if set(schools) != set(profiles) or set(economic) != set(profiles) or set(observations) != {(key, subject) for key in profiles for subject in ['math', 'reading']}:
            raise ValueError('Palm Beach canonical profile/observation membership changed')
        for order, profile in enumerate(payload['schools']):
            key = profile['id']
            school = dict(schools[key]); school['profile_json'] = json.loads(school['profile_json'])
            expected_school = dict(dataset_id=DATASET, school_id=key, name=profile['name'], district_id=profile['district_id'],
                district_name=profile['district'], city=profile['city'], county=profile['county'], profile_json=profile,
                source_id=DATASET + ':extract', source_order=order)
            econ = dict(economic[key]); econ['raw_json'] = json.loads(econ['raw_json'])
            expected_econ = dict(dataset_id=DATASET, school_id=key, year=2025, definition_id=income_id,
                name=profile['name'], enrollment=number(profile['enrollment']), low_income=number(profile['low_income']),
                percentage=profile['income'], source_label=payload['income_definition']['label'], raw_json=profile['income_raw'],
                source_id=DATASET + ':income', source_order=profile['income_row'])
            if not same(school, expected_school) or not same(econ, expected_econ):
                raise ValueError('Palm Beach canonical raw profile/same-year individual income changed')
            for subject in ['math', 'reading']:
                value = profile['outcomes'][subject]
                actual = dict(observations[(key, subject)])
                actual['raw_value'], actual['raw_tested'] = json.loads(actual['raw_value']), json.loads(actual['raw_tested'])
                expected = dict(dataset_id=DATASET, school_id=key, definition_id=assessment_id, subject=subject,
                    proficiency=number(value['proficiency']), tested=None,
                    status='reported' if value['proficiency'] is not None else 'suppressed_or_not_reported',
                    raw_value=value['raw'], raw_tested=None, source_id=DATASET + ':assessment', source_order=value['source_row'])
                if not same(actual, expected):
                    raise ValueError('Palm Beach canonical native outcome/raw exclusion/count evidence changed')
        model_rows = list(db.execute('SELECT * FROM model_run WHERE dataset_id=?', (DATASET,)))
        runs = {r['subject']: dict(r) for r in model_rows}
        if len(model_rows) != 3 or len(runs) != 3 or set(runs) != set(model_audit.SUBJECTS):
            raise ValueError('Palm Beach canonical models require exactly three ES subject fits')
        digest = hashlib.sha256(json.dumps([(key, actual_sources[key]['sha256']) for key in sorted(actual_sources)]).encode()).hexdigest()
        total = 0
        for model in numerical['models']:
            subject = model['subject']; run = runs[subject]
            summary = json.loads(run.pop('summary_json'))
            expected_run = dict(id=f'{assessment_id}:{subject}:ols-v1:{digest[:12]}', dataset_id=DATASET,
                definition_id=assessment_id, subject=subject, method_version='ols-studentized-v1', input_sha256=digest)
            expected_summary = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                assessed_schools=170, excluded_schools=5, **model['coefficients'])
            exact = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
            if (not same(run, expected_run) or not same({k: summary.get(k) for k in exact}, {k: expected_summary[k] for k in exact})
                    or not model_audit.numeric_equal(summary, expected_summary)):
                raise ValueError('Palm Beach canonical model metadata/coefficients differ from audited fits')
            saved = {r['school_id']: dict(r) for r in db.execute('SELECT * FROM model_result WHERE model_id=?', (run['id'],))}
            reference = {r['school_id']: r for r in model['results']}
            if set(saved) != set(reference):
                raise ValueError('Palm Beach canonical result membership changed')
            for key, result in reference.items():
                actual = saved[key]
                exact_result = dict(model_id=run['id'], dataset_id=DATASET, school_id=key, actual=float(result['actual']), low=None, high=None)
                expected_result = exact_result | dict(predicted=result['predicted'], studentized=result['studentized'])
                if (not same({k: actual.get(k) for k in exact_result}, exact_result)
                        or not model_audit.numeric_equal(actual, expected_result)):
                    raise ValueError('Palm Beach canonical point-only result differs from audited district fit')
            total += len(saved)
        if total != 495 or db.execute('SELECT count(*) FROM model_result WHERE dataset_id=?', (DATASET,)).fetchone()[0] != total:
            raise ValueError('Palm Beach canonical result count changed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Palm Beach canonical foreign-key integrity failed')
    return {'schools': len(profiles), 'observations': len(observations), 'models': len(runs), 'results': total}


def validate_exports(payload, output, numerical):
    output = Path(output)
    schools = json.loads((output / 'schools.json').read_text())
    history = json.loads((output / 'history.json').read_text())
    coverage = json.loads((output / 'coverage.json').read_text())
    descriptor = json.loads((output / 'catalog.json').read_text())
    exported = {s['id']: s for s in schools['schools']}
    records = {r['school_id']: r for r in history['records']}
    profiles = {s['id']: s for s in payload['schools']}
    if (len(schools['schools']) != 170 or len(history['records']) != 170
            or set(exported) != set(profiles) or set(records) != set(profiles)):
        raise ValueError('Palm Beach exported native source directory/history identities differ from selection')
    if set(schools['models']) != {'ES'} or set(schools['models']['ES']) != set(model_audit.SUBJECTS):
        raise ValueError('Palm Beach export requires only the three independently audited ES models')
    expected_keys = {(2025, 'ES', model_audit.ASSESSMENT, m['subject']) for m in numerical['models']}
    for summaries in [schools['history_models'], history['models']]:
        keyed = {(m['year'], m['level'], m['assessment'], m['subject']): m for m in summaries}
        if len(summaries) != 3 or len(keyed) != 3 or set(keyed) != expected_keys:
            raise ValueError('Palm Beach history must retain exactly three audited ES model populations')
        if any(not same(summary, schools['models']['ES'][key[3]]) for key, summary in keyed.items()):
            raise ValueError('Palm Beach historical model summaries differ from current district fits')
    for model in numerical['models']:
        subject = model['subject']
        actual_model = schools['models']['ES'][subject]
        expected_model = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                              assessed_schools=170, excluded_schools=5, **model['coefficients'])
        exact_model = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
        if (not same({k: actual_model.get(k) for k in exact_model}, {k: expected_model[k] for k in exact_model})
                or not model_audit.numeric_equal(actual_model, expected_model)):
            raise ValueError('Palm Beach exported district coefficients/coverage differ from numerical audit')
        reference = {r['school_id']: r for r in model['results']}
        eligible = {s['id'] for s in schools['schools'] if subject in s['metrics']}
        if eligible != set(reference):
            raise ValueError('Palm Beach exported subject membership differs from passed district audit')
        for key, result in reference.items():
            fields = ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'leverage']
            metric = exported[key]['metrics'][subject]
            expected_metric = {k: result[k] for k in fields} | dict(tested=None, cohort_n=165)
            exact = ['actual', 'tested', 'low', 'high', 'cohort_n']
            if (not same({k: metric.get(k) for k in exact}, {k: expected_metric[k] for k in exact})
                    or not model_audit.numeric_equal(metric, expected_metric)
                    or not same(metric, records[key]['subjects'][subject])):
                raise ValueError('Palm Beach per-school point-only metric differs from verified district fit')
    for key, school in exported.items():
        profile = profiles[key]
        record = records[key]
        expected_subjects = {m['subject'] for m in numerical['models'] if key in {r['school_id'] for r in m['results']}}
        if set(school['metrics']) != expected_subjects or set(record['subjects']) != expected_subjects:
            raise ValueError('Palm Beach profile/history subject set differs from exact audited eligibility')
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
            raise ValueError('Palm Beach profile/history/exclusion/geography evidence changed')
    expected_coverage = {'grade-schools': {'directory': 170, 'eligible': {s: 165 for s in model_audit.SUBJECTS}}}
    if not same(coverage, dict(year=2025, schools=170, cohorts=expected_coverage,
            source_audit=payload['source_audit'], exclusions=dict(Counter(
                reason for r in records.values() for reason in r['exclusions'].values())))):
        raise ValueError('Palm Beach exported coverage/source exclusions differ from approved selection')
    cohort = payload['cohorts'][0]
    expected_levels = {'ES': dict(year=2025, label=cohort['label'], assessment=cohort['assessment'],
                                  outcome=cohort['outcome'], math_label='Math', note=cohort['note'])}
    header = dict(year=payload['academic_year'], assessment_year=2025,
        income_label=payload['income_definition']['label'], program_options=['Unclassified'],
        levels=expected_levels, history_years=[2025], coverage_note=payload['coverage_note'],
        methodology=payload['methodology'])
    if not same({k: schools.get(k) for k in header}, header):
        raise ValueError('Palm Beach exported native assessment definition or methodology changed')
    expected_descriptor = dict(schema_version=1, state=payload['state'], prepare_script=payload['prepare_script'],
        regions=[dict(id='palm-beach', geography='palm-beach', name=payload['region_name'], dataset=DATASET,
            statewide=False, status='ready', levels=['ES'], boundaries=None, comparison=payload['comparison'],
            audit=str((output / 'coverage.json').relative_to(ROOT)),
            schools=str((output / 'schools.json').relative_to(ROOT)),
            model_scope=payload['model_scope'], map_source=payload['map_source'])])
    if not same(descriptor, expected_descriptor):
        raise ValueError('Palm Beach ready descriptor must retain distinct district and point-only scope')
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
    validate_canonical(payload, database, numerical, extract_path)
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
