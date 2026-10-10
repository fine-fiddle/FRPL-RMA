"""Canonical and static Fairfax County comparisons from pinned completed district audits."""
import argparse
from collections import Counter
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path

import audit_fairfax as roster_audit
import audit_fairfax_models as model_audit
from database import ROOT, DEFAULT_DB, connect, definition_id
from state_snapshot import prepare_snapshot

DATASET = 'va-fairfax-2025'
EXTRACT = ROOT / 'data/source/fairfax.json'
OUTPUT = ROOT / 'data/fairfax'
NUMERICAL_SHA = 'd95fe3f778d0daca09a877f70f87ca746fb8fa049532923e8341990ea007fda3'
PROJECT_SOURCE = 'https://github.com/robot-assisted-projects/FRPL-RMA/blob/expansion/all-states/'
MODEL_SCOPE = (
    'Fairfax County independent 2024–25 Virginia grade-school district models: exact '
    'operational CCD LEA 5101260 / native VA-029 attachments. All 162 native enrolled '
    'grade-school profiles remain visible; 152 schools with fully reconciled '
    'same-year individual economic status enter each native All Students Math, ELA '
    'and Combined schoolwide SOL/VAAP Passed model. Ten incomplete native grade-count '
    'income profiles retain their raw published outcomes and source exclusions. '
    'High, mixed, primary-only, unclassified and missing-native schools remain '
    'outside this point-only district release.')


def same(actual, expected):
    """Typed exact evidence equality; Python bool/int equality is insufficient."""
    return roster_audit.fingerprint(actual) == roster_audit.fingerprint(expected)


def load_inputs():
    roster = model_audit.load_roster()
    content = model_audit.OUTPUT.read_bytes()
    if hashlib.sha256(content).hexdigest() != NUMERICAL_SHA:
        raise ValueError('Fairfax County passed numerical audit fingerprint changed; re-audit the release')
    numerical = json.loads(content)
    model_audit.validate(numerical, model_audit.build(roster))
    if (numerical['hard_holds'] or roster['hard_holds'] or roster['release_holds']['grade']
            or numerical['approved_for_source'] is not False or roster['approved_for_source'] is not False
            or numerical['approved_for_modeling'] is not False or roster['approved_for_modeling'] is not False
            or len(numerical['models']) != 3
            or {(m['level'], m['subject']) for m in numerical['models']} != {('ES', s) for s in model_audit.SUBJECTS}
            or any(m['status'] != 'numerically_verified_pending_integration'
                   or m['coefficients']['n'] != 152 or m['intervals']['available_for_entire_model']
                   for m in numerical['models'])):
        raise ValueError('Fairfax County numerical audit has unresolved grade-school release or population holds')
    return roster, numerical


def cohorts():
    native = roster_audit.virginia
    return [dict(id='grade', level='ES', assessment=native.BANDS['grade'][1],
        label=native.BANDS['grade'][2],
        grades='Schoolwide grade-level and/or end-of-course tests applicable to the grade span',
        standard=model_audit.STANDARD, source_url=native.PROFILE_PAGE,
        source='virginia_extract_2025', allow_point_only=True,
        outcome='Passed · proficient or advanced',
        note='Fairfax grade-school SOL/VAAP totals · published rates · sampling intervals unavailable')]


def outcome(value, entry, subject):
    # Missing income does not erase a directly published native assessment rate.
    return dict(proficiency=value['native_rate'], tested=None,
        valid_score_evidence=None, raw_tested=None, exclusion=value['exclusion'],
        source=entry['source'], source_row=entry['source_row'],
        raw=dict(applicable=value['applicable'], native_usable=value['usable'],
            native_outcome=value, assessment_raw=entry['raw']['assessments'][subject],
            native_rate=value['raw_rate'], native_school_id=entry['school_id'],
            valid_score_count=None, sampling_variance=None, interval_availability=False,
            count_note='Native enrollment and portal Record Count are never valid-score denominators.'))


def build_snapshot(roster, numerical):
    native = roster_audit.load_virginia()
    raw = roster['raw_inputs']
    directory = {r['source_row']: r for r in raw['directory']['records']}
    profiles = {r['school_id']: r for r in raw['native_profiles']['records']}
    schools, excluded = [], []
    for school in sorted(roster['roster_links'], key=lambda r: r['school_id']):
        if not (school['operational'] and school['native_profile_present']
                and school['native_grade']['native_band'] == 'grade'):
            excluded.append(copy.deepcopy(school))
            continue
        entry = profiles[school['school_id']]
        profile = entry['raw']
        income = school['income']
        schools.append(dict(id=school['school_id'], ncessch=school['ncessch'], cohort='grade',
            name=profile['name'], district_id=roster_audit.LEA, district=profile['district'],
            city=None, county=None, enrollment=income['reported_all_students'],
            low_income=income['verified_ed_count'], income=income['percentage'],
            income_source=entry['source'], income_row=entry['source_row'],
            income_raw=dict(enrollment_subgroups=profile['enrollment_subgroups'],
                grade_table=profile['grade_table'], reconciled_income_evidence=income),
            identity_raw=dict(ncessch=school['ncessch'], native_school_id=school['native_school_id'],
                ccd_source_row=school['directory_source_row'], ccd=directory[school['directory_source_row']],
                native_source_row=entry['source_row'], native_profile=entry,
                native_grade_evidence=school['native_grade'], offered_evidence=school['offered'],
                ccd_flags=school['ccd_flags'], supplemental_ccd_membership=school['ccd_membership'],
                supplemental_ccd_lunch_source_rows=school['supplemental_ccd_lunch_source_rows'],
                membership_difference_native_minus_ccd=school['membership_difference_native_minus_ccd']),
            outcomes={s: outcome(school['subjects'][s], entry, s) for s in ['math', 'reading']}))
    if len(schools) != 162 or len(excluded) != 61:
        raise ValueError('Fairfax release must retain all 162 exact native grade-school profiles and 61 outside-roster records')
    source_audit = dict(operational_roster=roster['coverage'], cohorts=roster['cohorts'],
        excluded_operational_roster_records=excluded,
        excluded_native_configuration_records=numerical['models'][0]['coverage']['excluded_configuration_records'],
        outside_native_configuration_records=numerical['models'][0]['coverage']['outside_native_configuration_records'],
        missing_native_profiles=roster['missing_native_profiles'],
        held_populations={k: v for k, v in roster['release_holds'].items() if k != 'grade'},
        native_assessment_definition=dict(state='VA', name=roster_audit.virginia.BANDS['grade'][1],
            year=2025, level='ES', grades=cohorts()[0]['grades'],
            standard='Native All Students subject-area Passed percentages, including proficient and advanced levels, for SOL plus VAAP. '
                '2023 mathematics and 2024 English standards first assessed spring 2025. Exact valid-score denominators '
                'not supplied in the profile; sampling intervals unavailable. Separate ordinary and mixed grade spans.',
            source_url=roster_audit.virginia.PROFILE_PAGE),
        assessment_scope_wording_note='Native grade-school assessment name, year, grades, thresholds and source remain unchanged; the namespaced district standard identifies the separately fitted Fairfax population.',
        state_definition_evidence=roster['state_definition_evidence'],
        planning_identity_reconciliation=roster['planning_identity_reconciliation'],
        retained_raw_inputs=copy.deepcopy(raw), raw_input_fingerprint=roster_audit.RAW_INPUT_SHA,
        retained_source_headers={k: dict(source_id=v['source_id'], header_source_row=v['header_source_row'],
            header=v['header'], records=len(v['records'])) for k, v in raw.items() if k in {'directory', 'membership', 'lunch'}},
        release_basis=dict(exact_source_roster_replayed=True, numerical_audit_without_holds=True,
            minimum_subject_schools=30, historical_audits_approved_for_source=False,
            historical_audits_approved_for_modeling=False, all_models_point_only=True,
            note='Immutable source and numerical audit approvals remain false. This separate adapter validates normalized source selection and every canonical/static district fit before release.'))
    selection = dict(policy=model_audit.POLICY, frozen_source_population=numerical['frozen_population'],
        directory_school_ids=[r['id'] for r in schools],
        subject_models={m['model_id']: dict(level=m['level'], subject=m['subject'],
            school_ids=[r['school_id'] for r in m['inputs']], population_sha256=m['population_sha256'])
            for m in numerical['models']})
    selection['sha256'] = roster_audit.fingerprint(selection)
    sources = dict(roster['sources'])
    sources.update(roster_audit=dict(path='data/source/fairfax-district-audit.json',
            url=PROJECT_SOURCE + 'data/source/fairfax-district-audit.json', sha256=model_audit.ROSTER_SHA),
        numerical_audit=dict(path='data/source/fairfax-model-audit.json',
            url=PROJECT_SOURCE + 'data/source/fairfax-model-audit.json', sha256=NUMERICAL_SHA))
    coverage_note = (
        'Fairfax County independent district comparison, 2024–25: exact CCD LEA 5101260 / VA-029. '
        'All 162 native grade-school profiles are searchable; 152 enter each Math, ELA and Combined '
        'model. Ten profiles have missing or suppressed same-year grade counts and retain published '
        'assessment rates with unavailable income and residuals. The full source audit retains 223 '
        'operational schools, 195 native profiles, 28 native gaps and all 61 schools outside this '
        'grade-school population. Native individual economic status is broader than FRPL; direct '
        'rounded All Students schoolwide Passed rates include SOL and VAAP. Verified valid-score '
        'counts and sampling intervals are unavailable modelwide. High and mixed models remain '
        'below the 30-school floor; primary-only and positive unsupported grades remain unclassified. '
        'No audited admissions classifications, coordinates or boundaries; one year only.')
    details = [MODEL_SCOPE,
        'Every subject uses independent district OLS and externally studentized residuals, including all 456 explicit deleted-school checks. Filters never refit a model and statewide residuals are not reused. Associations do not establish causal school effectiveness or overall quality.',
        'Native division/school identities match exact CCD VA-029 attachments. All 162 same-year native enrolled grade-school profiles remain visible; 152 are eligible per subject. Complete offered-grade agreement is a diagnostic, never an additional population filter. No school is removed by residuals, leverage, category label or fit quality.',
        'Schoolwide All Students Passed is directly published for Mathematics and English Reading, including SOL and VAAP. Native grade/course percentages and Advanced plus Proficient category sums are never substituted. Rounded category sums differ from direct Passed for 39 Math and 37 ELA eligible schools; one further eligible Math category pair is incomplete.',
        roster_audit.virginia.ECON_DEFINITION,
        'Use only fully reconciled same-year native All Students, ED, non-ED and every grade count. Retain displayed percentages, raw categories and original grade evidence. Ten grade-school profiles have missing or suppressed grade counts; missingness never means zero. CCD lunch and membership remain supplemental provenance, never substitute income or outcome denominators.',
        'Across all 195 native district profiles, 128 displayed ED percentages use a stale denominator and 163 native enrollment totals differ from corresponding CCD totals. These sources are not interchangeable. Fall September 30 whole-school economic status and spring tested grade/course populations differ.',
        'High 23 and mixed one eligible profiles remain below the 30-school floor. Three primary-only profiles and Lake Braddock with positive Post Graduate membership remain unclassified. The native Post Graduate label is retained and is not Ungraded. Four PK-only centers and 24 CCD records reporting no offered grades have no native profile; missing records never imply zero pupils or inferred ungraded membership.',
        'Combined is the equally weighted mean of eligible Math and ELA pass percentages, not proficiency in both. Counts, sampling variances and interval endpoints remain unavailable for every member. Enrollment, portal Record Count and participation are never valid-score proxies. Studentization uses the deleted-school residual scale and provides no enrollment adjustment or shrinkage.',
        'Independent centered full fits and all 456 deletions were verified. Maximum leverage is 0.026304 and the largest deleted-line shift is 0.447468 proficiency points across observed incomes. Conventional leverage, Cook and residual flags are descriptive, never reasons to discard a member or school-quality labels.',
        'One year only: 2023 mathematics and 2024 English SOL standards were first assessed in spring 2025, so older displayed profile years remain outside the models. No audited admissions classifications, coordinates or boundaries. State proficiency thresholds and economic proxies do not create an interchangeable national scale.']
    return dict(schema_version=1, dataset=DATASET, year=2025, academic_year='2024–25',
        state=dict(id='VA', name='Virginia'), name='Fairfax County 2024–25 district comparison',
        region='fairfax', region_name='Fairfax County', statewide=False,
        comparison='Fairfax County · {year} · {assessment} · {note}',
        prepare_script='scripts/prepare_fairfax.py', source_url=roster_audit.virginia.PROFILE_PAGE,
        retrieved=native['retrieved'], model_scope=MODEL_SCOPE, release_status='ready',
        map_source='School coordinates and district boundaries are unavailable in the audited Fairfax County source release.',
        income_definition=dict(label='Individually classified economic disadvantage',
            definition=roster_audit.virginia.ECON_DEFINITION, url=roster_audit.virginia.GLOSSARY),
        sources=sources, cohorts=cohorts(), schools=schools, selection=selection,
        source_audit=source_audit, coverage_note=coverage_note,
        methodology=dict(summary='Fairfax County independent native grade-school district models with same-year individual economic status and schoolwide SOL/VAAP Passed rates.',
            details=details, sources=[dict(label='VDOE School Quality native school profiles', url=roster_audit.virginia.PROFILE_PAGE),
                dict(label='Native export definitions and subject-area tables', url=roster_audit.virginia.DOWNLOAD_PAGE),
                dict(label='School Quality economic and assessment definitions', url=roster_audit.virginia.GLOSSARY),
                dict(label='Spring 2025 new English and mathematics standards', url=roster_audit.virginia.STANDARDS),
                dict(label='2024–25 CCD exact district school roster', url=roster['sources']['ccd_directory_2025']['url']),
                dict(label='2024–25 CCD supplemental membership and grade subtotals', url=roster['sources']['ccd_membership_2025']['url']),
                dict(label='2024–25 CCD supplemental lunch and economic status', url=roster['sources']['ccd_lunch_2025']['url'])]))


def build():
    return build_snapshot(*load_inputs())

def validate(payload, expected=None):
    expected = build() if expected is None else expected
    if not same(payload, expected):
        raise ValueError('Fairfax County normalized extract differs from pinned source/model evidence, scope or selection policy')
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
    namespace = DATASET + ':%'
    with closing(connect(database)) as db:
        datasets = [dict(r) for r in db.execute('SELECT * FROM dataset WHERE id=? OR id LIKE ?', (DATASET, namespace))]
        if not same(datasets, [dict(id=DATASET, state='VA', name=payload['name'],
                model_scope=payload['model_scope'], status='ready')]):
            raise ValueError('Fairfax County canonical dataset release metadata changed')
        sources = dict(payload['sources'])
        sources['extract'] = dict(path=str(Path(extract_path).resolve().relative_to(ROOT)),
                                 url=payload['source_url'], sha256=hashlib.sha256(Path(extract_path).read_bytes()).hexdigest())
        expected_sources = {DATASET + ':' + key: dict(id=DATASET + ':' + key, dataset_id=DATASET,
            path=source['path'], url=source['url'], sha256=source['sha256'], imported_at=payload['retrieved'])
            for key, source in sources.items()}
        actual_sources = {r['id']: dict(r) for r in db.execute(
            'SELECT * FROM source WHERE dataset_id=? OR id LIKE ?', (DATASET, namespace))}
        if not same(actual_sources, expected_sources):
            raise ValueError('Fairfax County canonical source provenance changed')
        definitions = [dict(r) for r in db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_definition = dict(id=assessment_id, state='VA', name=cohort['assessment'], year=2025,
            level='ES', grades=cohort['grades'], standard=cohort['standard'], source_url=cohort['source_url'])
        income_rows = [dict(r) for r in db.execute('SELECT * FROM economic_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_income = dict(id=income_id, name=payload['income_definition']['label'],
            definition=payload['income_definition']['definition'], source_url=payload['income_definition']['url'])
        if not same(definitions, [expected_definition]) or not same(income_rows, [expected_income]):
            raise ValueError('Fairfax County canonical native assessment/income definition changed')
        # SQLite foreign keys verify each referenced identity but do not require
        # source/definition/model ownership to match the observation's dataset.
        # Include every namespace reference so a foreign owner cannot hide rows
        # from an otherwise correct dataset-only count. Native school IDs remain
        # shared with Virginia's independent statewide release.
        school_rows = list(db.execute('SELECT * FROM school WHERE dataset_id=? OR source_id LIKE ?',
                                      (DATASET, namespace)))
        economic_rows = list(db.execute('''SELECT * FROM economic_observation WHERE
            dataset_id=? OR definition_id LIKE ? OR source_id LIKE ?''', (DATASET, namespace, namespace)))
        observation_rows = list(db.execute('''SELECT * FROM assessment_observation WHERE
            dataset_id=? OR definition_id LIKE ? OR source_id LIKE ?''', (DATASET, namespace, namespace)))
        if len(school_rows) != 162 or len(economic_rows) != 162 or len(observation_rows) != 324:
            raise ValueError('Fairfax County canonical profile/observation row counts changed')
        schools = {r['school_id']: dict(r) for r in school_rows}
        economic = {r['school_id']: dict(r) for r in economic_rows}
        observations = {(r['school_id'], r['subject']): dict(r) for r in observation_rows}
        if set(schools) != set(profiles) or set(economic) != set(profiles) or set(observations) != {(key, subject) for key in profiles for subject in ['math', 'reading']}:
            raise ValueError('Fairfax County canonical profile/observation membership changed')
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
                source_id=DATASET + ':' + profile['income_source'], source_order=profile['income_row'])
            if not same(school, expected_school) or not same(econ, expected_econ):
                raise ValueError('Fairfax County canonical raw profile/same-year individual income changed')
            for subject in ['math', 'reading']:
                value = profile['outcomes'][subject]
                actual = dict(observations[(key, subject)])
                actual['raw_value'], actual['raw_tested'] = json.loads(actual['raw_value']), json.loads(actual['raw_tested'])
                expected = dict(dataset_id=DATASET, school_id=key, definition_id=assessment_id, subject=subject,
                    proficiency=number(value['proficiency']), tested=None,
                    status='reported' if value['proficiency'] is not None else 'suppressed_or_not_reported',
                    raw_value=value['raw'], raw_tested=None, source_id=DATASET + ':' + value['source'], source_order=value['source_row'])
                if not same(actual, expected):
                    raise ValueError('Fairfax County canonical native outcome/raw exclusion/count evidence changed')
        model_rows = list(db.execute('''SELECT * FROM model_run WHERE
            dataset_id=? OR id LIKE ? OR definition_id LIKE ?''', (DATASET, namespace, namespace)))
        runs = {r['subject']: dict(r) for r in model_rows}
        if len(model_rows) != 3 or len(runs) != 3 or set(runs) != set(model_audit.SUBJECTS):
            raise ValueError('Fairfax County canonical models require exactly three ES subject fits')
        digest = hashlib.sha256(json.dumps([(key, actual_sources[key]['sha256']) for key in sorted(actual_sources)]).encode()).hexdigest()
        total = 0
        for model in numerical['models']:
            subject = model['subject']; run = runs[subject]
            summary = json.loads(run.pop('summary_json'))
            expected_run = dict(id=f'{assessment_id}:{subject}:ols-v1:{digest[:12]}', dataset_id=DATASET,
                definition_id=assessment_id, subject=subject, method_version='ols-studentized-v1', input_sha256=digest)
            expected_summary = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                assessed_schools=162, excluded_schools=10, **model['coefficients'])
            exact = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
            if (not same(run, expected_run) or not same({k: summary.get(k) for k in exact}, {k: expected_summary[k] for k in exact})
                    or not model_audit.numeric_equal(summary, expected_summary)):
                raise ValueError('Fairfax County canonical model metadata/coefficients differ from audited fits')
            saved = {r['school_id']: dict(r) for r in db.execute('SELECT * FROM model_result WHERE model_id=?', (run['id'],))}
            reference = {r['school_id']: r for r in model['results']}
            if set(saved) != set(reference):
                raise ValueError('Fairfax County canonical result membership changed')
            for key, result in reference.items():
                actual = saved[key]
                exact_result = dict(model_id=run['id'], dataset_id=DATASET, school_id=key, actual=float(result['actual']), low=None, high=None)
                expected_result = exact_result | dict(predicted=result['predicted'], studentized=result['studentized'])
                if (not same({k: actual.get(k) for k in exact_result}, exact_result)
                        or not model_audit.numeric_equal(actual, expected_result)):
                    raise ValueError('Fairfax County canonical point-only result differs from audited district fit')
            total += len(saved)
        if total != 456 or db.execute('SELECT count(*) FROM model_result WHERE dataset_id=? OR model_id LIKE ?',
                                      (DATASET, namespace)).fetchone()[0] != total:
            raise ValueError('Fairfax County canonical result count changed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Fairfax County canonical foreign-key integrity failed')
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
    if (len(schools['schools']) != 162 or len(history['records']) != 162
            or set(exported) != set(profiles) or set(records) != set(profiles)):
        raise ValueError('Fairfax County exported native source directory/history identities differ from selection')
    if set(schools['models']) != {'ES'} or set(schools['models']['ES']) != set(model_audit.SUBJECTS):
        raise ValueError('Fairfax County export requires only the three independently audited ES models')
    expected_keys = {(2025, 'ES', model_audit.ASSESSMENT, m['subject']) for m in numerical['models']}
    for summaries in [schools['history_models'], history['models']]:
        keyed = {(m['year'], m['level'], m['assessment'], m['subject']): m for m in summaries}
        if len(summaries) != 3 or len(keyed) != 3 or set(keyed) != expected_keys:
            raise ValueError('Fairfax County history must retain exactly three audited ES model populations')
        if any(not same(summary, schools['models']['ES'][key[3]]) for key, summary in keyed.items()):
            raise ValueError('Fairfax County historical model summaries differ from current district fits')
    for model in numerical['models']:
        subject = model['subject']
        actual_model = schools['models']['ES'][subject]
        expected_model = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                              assessed_schools=162, excluded_schools=10, **model['coefficients'])
        exact_model = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
        if (not same({k: actual_model.get(k) for k in exact_model}, {k: expected_model[k] for k in exact_model})
                or not model_audit.numeric_equal(actual_model, expected_model)):
            raise ValueError('Fairfax County exported district coefficients/coverage differ from numerical audit')
        reference = {r['school_id']: r for r in model['results']}
        eligible = {s['id'] for s in schools['schools'] if subject in s['metrics']}
        if eligible != set(reference):
            raise ValueError('Fairfax County exported subject membership differs from passed district audit')
        for key, result in reference.items():
            fields = ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'leverage']
            metric = exported[key]['metrics'][subject]
            expected_metric = {k: result[k] for k in fields} | dict(tested=None, cohort_n=152)
            exact = ['actual', 'tested', 'low', 'high', 'cohort_n']
            if (not same({k: metric.get(k) for k in exact}, {k: expected_metric[k] for k in exact})
                    or not model_audit.numeric_equal(metric, expected_metric)
                    or not same(metric, records[key]['subjects'][subject])):
                raise ValueError('Fairfax County per-school point-only metric differs from verified district fit')
    for key, school in exported.items():
        profile = profiles[key]
        record = records[key]
        expected_subjects = {m['subject'] for m in numerical['models'] if key in {r['school_id'] for r in m['results']}}
        if set(school['metrics']) != expected_subjects or set(record['subjects']) != expected_subjects:
            raise ValueError('Fairfax County profile/history subject set differs from exact audited eligibility')
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
        if (set(school) != set(profile_fields) | {'id', 'metrics', 'history'}
                or set(record) != set(record_fields) | {'school_id', 'subjects'}
                or not same({k: school.get(k) for k in profile_fields}, profile_fields)
                or not same({k: record.get(k) for k in record_fields}, record_fields)
                or not same(school['history'], [record])):
            raise ValueError('Fairfax County profile/history/exclusion/geography evidence changed')
    expected_coverage = {'grade': {'directory': 162, 'eligible': {s: 152 for s in model_audit.SUBJECTS}}}
    if not same(coverage, dict(year=2025, schools=162, cohorts=expected_coverage,
            source_audit=payload['source_audit'], exclusions=dict(Counter(
                reason for r in records.values() for reason in r['exclusions'].values())))):
        raise ValueError('Fairfax County exported coverage/source exclusions differ from approved selection')
    cohort = payload['cohorts'][0]
    expected_levels = {'ES': dict(year=2025, label=cohort['label'], assessment=cohort['assessment'],
                                  outcome=cohort['outcome'], math_label='Math', note=cohort['note'])}
    header = dict(year=payload['academic_year'], assessment_year=2025,
        income_label=payload['income_definition']['label'], program_options=['Unclassified'],
        levels=expected_levels, history_years=[2025], coverage_note=payload['coverage_note'],
        methodology=payload['methodology'])
    if (set(schools) != set(header) | {'schools', 'models', 'history_models'}
            or set(history) != {'records', 'models'}
            or not same({k: schools.get(k) for k in header}, header)):
        raise ValueError('Fairfax County exported native assessment definition or methodology changed')
    expected_descriptor = dict(schema_version=1, state=payload['state'], prepare_script=payload['prepare_script'],
        regions=[dict(id='fairfax', geography='fairfax', name=payload['region_name'], dataset=DATASET,
            statewide=False, status='ready', levels=['ES'], boundaries=None, comparison=payload['comparison'],
            audit=str((output / 'coverage.json').relative_to(ROOT)),
            schools=str((output / 'schools.json').relative_to(ROOT)),
            model_scope=payload['model_scope'], map_source=payload['map_source'])])
    if not same(descriptor, expected_descriptor):
        raise ValueError('Fairfax County ready descriptor must retain distinct district and point-only scope')
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
