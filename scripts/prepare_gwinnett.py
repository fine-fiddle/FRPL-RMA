"""Canonical and static Gwinnett County comparisons from pinned completed district audits."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path

import audit_gwinnett as roster_audit
import audit_gwinnett_models as model_audit
import copy
from database import ROOT, DEFAULT_DB, connect, definition_id
from state_snapshot import prepare_snapshot

DATASET = 'ga-gwinnett-2025'
EXTRACT = ROOT / 'data/source/gwinnett.json'
OUTPUT = ROOT / 'data/gwinnett'
NUMERICAL_SHA = '8589af1edb602efec119f90d796498342e74d6f74b90e3405aef5801649c4dee'
PROJECT_SOURCE = 'https://github.com/robot-assisted-projects/FRPL-RMA/blob/expansion/all-states/'
MODEL_SCOPE = (
    'Gwinnett County independent 2024–25 Georgia grade-school district models: exact '
    'operational CCD LEA 1302550 / native GA-667 attachments. Complete unadjusted '
    'pure lower offers with tested grades, highest grade 01–08 and reconciled PK–8 '
    'membership define all 111 native source profiles. Retain New Life charter and '
    'all original flags without label or fit-based exclusions. Individual Direct '
    'Certification is a same-year benefits/status proxy, not full FRPL. Separate '
    'Georgia Milestones EOG Regular G38 Levels 3-4 Math, ELA and Combined point-only '
    'district OLS; six mixed and 24 high configurations remain outside the models.')


def same(actual, expected):
    """Typed exact evidence equality; Python bool/int equality is insufficient."""
    return roster_audit.fingerprint(actual) == roster_audit.fingerprint(expected)


def load_inputs():
    roster = model_audit.load_roster()
    content = model_audit.OUTPUT.read_bytes()
    if hashlib.sha256(content).hexdigest() != NUMERICAL_SHA:
        raise ValueError('Gwinnett County passed numerical audit fingerprint changed; re-audit the release')
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
        raise ValueError('Gwinnett County numerical audit has unresolved release or population holds')
    return roster, numerical


def cohorts():
    # Only the population wording changes; native thresholds/year/grades/source
    # remain exact and the original cohort is separately retained as evidence.
    result = copy.deepcopy(roster_audit.load_georgia()['cohorts'])
    result[0]['standard'] = model_audit.STANDARD
    return result


def outcome(value, entry):
    return dict(proficiency=value['native_rate'] if value['usable'] else None,
        tested=None, valid_score_evidence=None, raw_tested=None,
        exclusion=value['exclusion'], source='edc_2025', source_row=entry['source_row'],
        raw=dict(applicable=value['applicable'], native_usable=value['usable'],
                 native_outcome_exclusion=value['outcome_exclusion'],
                 scope_exclusion=value['scope_exclusion'], income_exclusion=value['income_exclusion'],
                 native_rate=value['raw_rate'], assessment_raw=entry['raw'],
                 compact_source_row=entry['compact_source_row'],
                 raw_tested_unverified=value['raw_tested'], raw_proficient_unverified=value['raw_proficient'],
                 valid_score_count=None, sampling_variance=None, interval_availability=False,
                 count_note='EDC raw counts are unverified evidence, never valid-score denominators.'))


def build_snapshot(roster, numerical):
    native = roster_audit.load_georgia()
    schools, excluded = [], []
    raw = roster['raw_inputs']
    directory = {r['source_row']: r['raw'] for r in raw['directory']['records']}
    membership = {r['source_row']: r for r in raw['membership']['records']}
    lunch = {r['source_row']: r for r in raw['lunch']['records']}
    assessment = {r['source_row']: r for r in raw['assessment']['records']}
    for school in sorted(roster['roster_links'], key=lambda r: r['school_id']):
        if not school['source_profile_eligible']:
            excluded.append(copy.deepcopy(school))
            continue
        if (school['enrolled']['native_grade_school_contract'] is not True
                or school['offered']['strict_pure_offered_lower'] is not True
                or school['enrolled']['lower_total_reconciled'] is not True
                or not school['native_g38_pair'] or school['income']['income_exclusion'] is not None):
            raise ValueError('Gwinnett source profile lacks native pure-lower/reconciled-grade/income/G38 source evidence')
        profile = school['state_snapshot_profile']
        schools.append(dict(
            id=school['school_id'], ncessch=school['school_id'], cohort='grade',
            name=profile['name'], district_id=roster_audit.LEA, district='Gwinnett County',
            city=profile['city'], county=profile['county'],
            enrollment=school['income']['reported_membership'],
            low_income=school['income']['reported_direct_certification'], income=school['income']['percentage'],
            income_source='ccd_lunch_2025', income_row=school['income']['direct_source_row'],
            income_raw=dict(direct_certification=lunch[school['income']['direct_source_row']]['raw'],
                            membership=membership[school['income']['membership_source_row']]['raw']),
            identity_raw=dict(ncessch=school['school_id'], native_school_id=school['native_school_id'],
                ccd_source_row=school['ccd_source_row'], ccd=directory[school['ccd_source_row']],
                membership_source_row=school['income']['membership_source_row'],
                membership_grades=[membership[v['source_row']] for v in school['enrolled']['grade_values'].values()],
                offered_evidence=school['offered'], enrolled_evidence=school['enrolled'],
                ccd_flags=school['ccd_flags'], edc_metadata=school['edc_metadata'],
                native_assessment_source_rows=school['native_g38_source_rows']),
            outcomes={s: outcome(school['subjects'][s], assessment[school['subjects'][s]['source_row']])
                      for s in ['math', 'reading']}))
    if len(schools) != 111:
        raise ValueError('Gwinnett release must retain all 111 exact native G38 source profiles')
    source_audit = dict(
        operational_roster=roster['coverage'], cohorts=roster['cohorts'],
        excluded_operational_roster_records=excluded,
        excluded_native_configuration_records=numerical['models'][0]['coverage']['excluded_configuration_records'],
        outside_native_configuration_records=numerical['models'][0]['coverage']['outside_native_configuration_records'],
        nonoperational_directory=roster['nonoperational_directory'],
        outside_operational_roster_records=roster['outside_operational_roster_records'],
        historical_state_lunch_notes=roster['historical_state_lunch_notes'],
        native_assessment_cohorts=copy.deepcopy(native['cohorts']),
        assessment_scope_wording_note='Only the final standard wording changes from separate state model to separate district model; Georgia Levels 3-4 thresholds, 2025 regular assessment and all other cohort fields remain unchanged.',
        state_definition_evidence=roster['state_definition_evidence'],
        later_release_note_roster_gaps=roster['later_release_note_roster_gaps'],
        planning_identity_reconciliation=roster['planning_identity_reconciliation'],
        retained_raw_inputs=copy.deepcopy(raw),
        raw_input_fingerprint=roster_audit.RAW_INPUT_SHA,
        retained_source_headers={k: dict(source_id=v['source_id'], header_source_row=v['header_source_row'],
            header=v['header'], selection=v['selection'], records=len(v['records']))
            for k, v in raw.items() if k in {'directory', 'membership', 'lunch', 'assessment'}},
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
    sources.update(
        roster_audit=dict(path='data/source/gwinnett-district-audit.json',
                          url=PROJECT_SOURCE + 'data/source/gwinnett-district-audit.json', sha256=model_audit.ROSTER_SHA),
        numerical_audit=dict(path='data/source/gwinnett-model-audit.json',
                             url=PROJECT_SOURCE + 'data/source/gwinnett-model-audit.json', sha256=NUMERICAL_SHA),
        state_extract=dict(path='data/source/ccd-state-snapshots.json',
                           url=PROJECT_SOURCE + 'data/source/ccd-state-snapshots.json', sha256=roster_audit.STATE_EXTRACT_SHA))
    coverage_note = (
        'Gwinnett County independent district comparison, 2024–25. Exact CCD LEA '
        '1302550 / GA-667 has 141 operational schools: 111 pure lower, 24 high and '
        'six mixed configurations. All 111 pure lower profiles offer grades 3–8 and '
        'have eligible native Math/ELA and matching individual-school Direct '
        'Certification income. New Life Academy of Excellence charter remains '
        'included; 110 other members are noncharter. All original offerings, '
        'membership, lunch and grade-specific/native G38 rows remain in coverage. '
        'Raw EDC counts are unverified and sampling intervals are unavailable '
        'modelwide. Benefits eligibility/fall PK enrollment differs from tested '
        'G38 children; Georgia eligibility-era and later-release roster notes '
        'remain explicit. No high/mixed models, audited admissions classifications, '
        'coordinates or boundaries; one year only.')
    details = [
        MODEL_SCOPE,
        'Every subject uses independent district OLS and externally studentized residuals, including all 333 explicit deleted-school checks. Filters never refit a model and statewide residuals are not reused. Associations do not establish causal school effectiveness or overall quality.',
        'All 111 native grade-school profiles enter each subject model; 110 noncharter schools and New Life Academy of Excellence charter 130255003991 are retained with exact native flags. Observed Regular-school composition is not a Regular-only filter. The 24 high and six mixed configurations retain every source row and exclusion without becoming model members.',
        'Complete As reported lower-grade offers, highest grade 01–08, no high/adult offers and reconciled PK–8 membership establish native scope. No Gwinnett school offers Ungraded; the 141 Derived-zero Not Specified rows are distinct from UG. Missing and suppressed counts never mean zero.',
        'Georgia Milestones EOG Regular School/All Students/All Students G38 Levels 3-4 uses documented SEA-native aggregate provenance. Exact published rates are used and individual-grade rates are never averaged. Native assessment business rules and valid-score denominators remain unverified; EDC can derive achievement cells and supply tested-count proxies.',
        native['income_definition']['definition'],
        'The copied statewide no-school-allocation-warning wording describes the earlier audited note subset; the full Georgia notes retained here provide additional eligibility-era, PK and roster context. No absence of a warning establishes complete benefit coverage or full household-income eligibility.',
        'Georgia Final2a Data Notes row 129 CCD-0060 identifies Medicaid-income eligibility starting 2024 alongside SNAP/TANF and foster records. Membership metadata row 14 includes state-funded students and outside-program PK. These coverage/eligibility-era notes do not authorize full-FRPL inference, a CEP multiplier or prior-year backfill.',
        'Final2a Data Notes row 133 DGO-0033 names legacy 130255002906, absent from the entire pinned Final1a directory. Its note remains release-context provenance, without an added school, assigned current type or name-based identity. All 141 current records, original headers and source rows remain retained.',
        'Six mixed G38 pairs remain outside the pure-lower population, including numeric zero proficiency and Devereux protected tested counts. Published zero rates are distinct from suppression; neither the raw counts nor grade percentages supply a model denominator or aggregation weight. Planning 111 ES and 24 HS is discovery only.',
        'Combined is the equally weighted mean of eligible Math and ELA proficiency, not proficiency in both. No sampling count, variance or endpoint is published for any model member. Externally studentized residuals use each deleted-school residual scale and provide no enrollment adjustment or shrinkage.',
        'Independent centered full fits and all 333 deletions were verified. Maximum leverage is 0.052483 and largest deleted-line shift is 1.130 proficiency points across observed incomes. Conventional leverage/Cook/residual flags are descriptive, never school-quality labels or reasons to discard a member; Rosebud and New Life remain included.',
        'Single-year grade-school comparison only. No high/mixed models, audited admissions classifications, coordinates or boundaries. State proficiency thresholds and economic proxies do not create an interchangeable national scale.',
    ]
    return dict(schema_version=1, dataset=DATASET, year=2025, academic_year='2024–25',
        state=dict(id='GA', name='Georgia'), name='Gwinnett County 2024–25 district comparison',
        region='gwinnett', region_name='Gwinnett County', statewide=False,
        comparison='Gwinnett County · {year} · {assessment} · {note}',
        prepare_script='scripts/prepare_gwinnett.py', source_url=native['source_url'],
        retrieved=native['retrieved'], model_scope=MODEL_SCOPE, release_status='ready',
        map_source='School coordinates and district boundaries are unavailable in the audited Gwinnett County source release.',
        income_definition=copy.deepcopy(native['income_definition']), sources=sources, cohorts=cohorts(),
        schools=schools, selection=selection, source_audit=source_audit, coverage_note=coverage_note,
        methodology=dict(summary='Gwinnett County independent native grade-school district models with same-year individual-school Direct Certification.',
            details=details, sources=[dict(label='2025 Georgia native assessment source', url=roster_audit.georgia.SEA['GA']),
                dict(label='2025 Georgia EDC v3.1', url=roster['sources']['edc_2025']['url']),
                dict(label='2024–25 CCD individual Direct Certification', url=roster['sources']['ccd_lunch_2025']['url']),
                dict(label='2024–25 CCD membership and grade subtotals', url=roster['sources']['ccd_membership_2025']['url']),
                dict(label='2024–25 CCD exact school roster', url=roster['sources']['ccd_directory_2025']['url']),
                dict(label='2024–25 Georgia eligibility and membership metadata', url=roster['sources']['ccd_state_notes_2025']['url']),
                dict(label='EDC v3.1 grade-total provenance', url=roster['sources']['edc_technical_v3_1']['url'])]))


def build():
    return build_snapshot(*load_inputs())


def validate(payload, expected=None):
    expected = build() if expected is None else expected
    if not same(payload, expected):
        raise ValueError('Gwinnett County normalized extract differs from pinned source/model evidence, scope or selection policy')
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
        if dataset is None or not same(dict(dataset), dict(id=DATASET, state='GA', name=payload['name'],
                model_scope=payload['model_scope'], status='ready')):
            raise ValueError('Gwinnett County canonical dataset release metadata changed')
        sources = dict(payload['sources'])
        sources['extract'] = dict(path=str(Path(extract_path).resolve().relative_to(ROOT)),
                                 url=payload['source_url'], sha256=hashlib.sha256(Path(extract_path).read_bytes()).hexdigest())
        expected_sources = {DATASET + ':' + key: dict(id=DATASET + ':' + key, dataset_id=DATASET,
            path=source['path'], url=source['url'], sha256=source['sha256'], imported_at=payload['retrieved'])
            for key, source in sources.items()}
        actual_sources = {r['id']: dict(r) for r in db.execute('SELECT * FROM source WHERE dataset_id=?', (DATASET,))}
        if not same(actual_sources, expected_sources):
            raise ValueError('Gwinnett County canonical source provenance changed')
        definitions = [dict(r) for r in db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_definition = dict(id=assessment_id, state='GA', name=cohort['assessment'], year=2025,
            level='ES', grades=cohort['grades'], standard=cohort['standard'], source_url=cohort['source_url'])
        income = db.execute('SELECT * FROM economic_definition WHERE id=?', (income_id,)).fetchone()
        expected_income = dict(id=income_id, name=payload['income_definition']['label'],
            definition=payload['income_definition']['definition'], source_url=payload['income_definition']['url'])
        if not same(definitions, [expected_definition]) or income is None or not same(dict(income), expected_income):
            raise ValueError('Gwinnett County canonical native assessment/income definition changed')
        school_rows = list(db.execute('SELECT * FROM school WHERE dataset_id=?', (DATASET,)))
        economic_rows = list(db.execute('SELECT * FROM economic_observation WHERE dataset_id=?', (DATASET,)))
        observation_rows = list(db.execute('SELECT * FROM assessment_observation WHERE dataset_id=?', (DATASET,)))
        if len(school_rows) != 111 or len(economic_rows) != 111 or len(observation_rows) != 222:
            raise ValueError('Gwinnett County canonical profile/observation row counts changed')
        schools = {r['school_id']: dict(r) for r in school_rows}
        economic = {r['school_id']: dict(r) for r in economic_rows}
        observations = {(r['school_id'], r['subject']): dict(r) for r in observation_rows}
        if set(schools) != set(profiles) or set(economic) != set(profiles) or set(observations) != {(key, subject) for key in profiles for subject in ['math', 'reading']}:
            raise ValueError('Gwinnett County canonical profile/observation membership changed')
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
                source_id=DATASET + ':ccd_lunch_2025', source_order=profile['income_row'])
            if not same(school, expected_school) or not same(econ, expected_econ):
                raise ValueError('Gwinnett County canonical raw profile/same-year individual income changed')
            for subject in ['math', 'reading']:
                value = profile['outcomes'][subject]
                actual = dict(observations[(key, subject)])
                actual['raw_value'], actual['raw_tested'] = json.loads(actual['raw_value']), json.loads(actual['raw_tested'])
                expected = dict(dataset_id=DATASET, school_id=key, definition_id=assessment_id, subject=subject,
                    proficiency=number(value['proficiency']), tested=None,
                    status='reported' if value['proficiency'] is not None else 'suppressed_or_not_reported',
                    raw_value=value['raw'], raw_tested=None, source_id=DATASET + ':edc_2025', source_order=value['source_row'])
                if not same(actual, expected):
                    raise ValueError('Gwinnett County canonical native outcome/raw exclusion/count evidence changed')
        model_rows = list(db.execute('SELECT * FROM model_run WHERE dataset_id=?', (DATASET,)))
        runs = {r['subject']: dict(r) for r in model_rows}
        if len(model_rows) != 3 or len(runs) != 3 or set(runs) != set(model_audit.SUBJECTS):
            raise ValueError('Gwinnett County canonical models require exactly three ES subject fits')
        digest = hashlib.sha256(json.dumps([(key, actual_sources[key]['sha256']) for key in sorted(actual_sources)]).encode()).hexdigest()
        total = 0
        for model in numerical['models']:
            subject = model['subject']; run = runs[subject]
            summary = json.loads(run.pop('summary_json'))
            expected_run = dict(id=f'{assessment_id}:{subject}:ols-v1:{digest[:12]}', dataset_id=DATASET,
                definition_id=assessment_id, subject=subject, method_version='ols-studentized-v1', input_sha256=digest)
            expected_summary = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                assessed_schools=111, excluded_schools=0, **model['coefficients'])
            exact = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
            if (not same(run, expected_run) or not same({k: summary.get(k) for k in exact}, {k: expected_summary[k] for k in exact})
                    or not model_audit.numeric_equal(summary, expected_summary)):
                raise ValueError('Gwinnett County canonical model metadata/coefficients differ from audited fits')
            saved = {r['school_id']: dict(r) for r in db.execute('SELECT * FROM model_result WHERE model_id=?', (run['id'],))}
            reference = {r['school_id']: r for r in model['results']}
            if set(saved) != set(reference):
                raise ValueError('Gwinnett County canonical result membership changed')
            for key, result in reference.items():
                actual = saved[key]
                exact_result = dict(model_id=run['id'], dataset_id=DATASET, school_id=key, actual=float(result['actual']), low=None, high=None)
                expected_result = exact_result | dict(predicted=result['predicted'], studentized=result['studentized'])
                if (not same({k: actual.get(k) for k in exact_result}, exact_result)
                        or not model_audit.numeric_equal(actual, expected_result)):
                    raise ValueError('Gwinnett County canonical point-only result differs from audited district fit')
            total += len(saved)
        if total != 333 or db.execute('SELECT count(*) FROM model_result WHERE dataset_id=?', (DATASET,)).fetchone()[0] != total:
            raise ValueError('Gwinnett County canonical result count changed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Gwinnett County canonical foreign-key integrity failed')
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
    if (len(schools['schools']) != 111 or len(history['records']) != 111
            or set(exported) != set(profiles) or set(records) != set(profiles)):
        raise ValueError('Gwinnett County exported native source directory/history identities differ from selection')
    if set(schools['models']) != {'ES'} or set(schools['models']['ES']) != set(model_audit.SUBJECTS):
        raise ValueError('Gwinnett County export requires only the three independently audited ES models')
    expected_keys = {(2025, 'ES', model_audit.ASSESSMENT, m['subject']) for m in numerical['models']}
    for summaries in [schools['history_models'], history['models']]:
        keyed = {(m['year'], m['level'], m['assessment'], m['subject']): m for m in summaries}
        if len(summaries) != 3 or len(keyed) != 3 or set(keyed) != expected_keys:
            raise ValueError('Gwinnett County history must retain exactly three audited ES model populations')
        if any(not same(summary, schools['models']['ES'][key[3]]) for key, summary in keyed.items()):
            raise ValueError('Gwinnett County historical model summaries differ from current district fits')
    for model in numerical['models']:
        subject = model['subject']
        actual_model = schools['models']['ES'][subject]
        expected_model = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                              assessed_schools=111, excluded_schools=0, **model['coefficients'])
        exact_model = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
        if (not same({k: actual_model.get(k) for k in exact_model}, {k: expected_model[k] for k in exact_model})
                or not model_audit.numeric_equal(actual_model, expected_model)):
            raise ValueError('Gwinnett County exported district coefficients/coverage differ from numerical audit')
        reference = {r['school_id']: r for r in model['results']}
        eligible = {s['id'] for s in schools['schools'] if subject in s['metrics']}
        if eligible != set(reference):
            raise ValueError('Gwinnett County exported subject membership differs from passed district audit')
        for key, result in reference.items():
            fields = ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'leverage']
            metric = exported[key]['metrics'][subject]
            expected_metric = {k: result[k] for k in fields} | dict(tested=None, cohort_n=111)
            exact = ['actual', 'tested', 'low', 'high', 'cohort_n']
            if (not same({k: metric.get(k) for k in exact}, {k: expected_metric[k] for k in exact})
                    or not model_audit.numeric_equal(metric, expected_metric)
                    or not same(metric, records[key]['subjects'][subject])):
                raise ValueError('Gwinnett County per-school point-only metric differs from verified district fit')
    for key, school in exported.items():
        profile = profiles[key]
        record = records[key]
        expected_subjects = {m['subject'] for m in numerical['models'] if key in {r['school_id'] for r in m['results']}}
        if set(school['metrics']) != expected_subjects or set(record['subjects']) != expected_subjects:
            raise ValueError('Gwinnett County profile/history subject set differs from exact audited eligibility')
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
            raise ValueError('Gwinnett County profile/history/exclusion/geography evidence changed')
    expected_coverage = {'grade': {'directory': 111, 'eligible': {s: 111 for s in model_audit.SUBJECTS}}}
    if not same(coverage, dict(year=2025, schools=111, cohorts=expected_coverage,
            source_audit=payload['source_audit'], exclusions=dict(Counter(
                reason for r in records.values() for reason in r['exclusions'].values())))):
        raise ValueError('Gwinnett County exported coverage/source exclusions differ from approved selection')
    cohort = payload['cohorts'][0]
    expected_levels = {'ES': dict(year=2025, label=cohort['label'], assessment=cohort['assessment'],
                                  outcome=cohort['outcome'], math_label='Math', note=cohort['note'])}
    header = dict(year=payload['academic_year'], assessment_year=2025,
        income_label=payload['income_definition']['label'], program_options=['Unclassified'],
        levels=expected_levels, history_years=[2025], coverage_note=payload['coverage_note'],
        methodology=payload['methodology'])
    if not same({k: schools.get(k) for k in header}, header):
        raise ValueError('Gwinnett County exported native assessment definition or methodology changed')
    expected_descriptor = dict(schema_version=1, state=payload['state'], prepare_script=payload['prepare_script'],
        regions=[dict(id='gwinnett', geography='gwinnett', name=payload['region_name'], dataset=DATASET,
            statewide=False, status='ready', levels=['ES'], boundaries=None, comparison=payload['comparison'],
            audit=str((output / 'coverage.json').relative_to(ROOT)),
            schools=str((output / 'schools.json').relative_to(ROOT)),
            model_scope=payload['model_scope'], map_source=payload['map_source'])])
    if not same(descriptor, expected_descriptor):
        raise ValueError('Gwinnett County ready descriptor must retain distinct district and point-only scope')
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
