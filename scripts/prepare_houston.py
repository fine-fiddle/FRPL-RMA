"""Separate Houston published-rate canonical/static release from immutable passed audits."""
import argparse
from collections import Counter
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path

import audit_houston as roster_audit
import audit_houston_models as model_audit
from database import ROOT, DEFAULT_DB, connect, definition_id
from state_snapshot import prepare_snapshot

DATASET = 'tx-houston-2025'
EXTRACT = ROOT / 'data/source/houston.json'
OUTPUT = ROOT / 'data/houston'
NUMERICAL_SHA = '13850a2a618aff776feb35958e06dc6d183d3e7b5aa99c3b3ea01a2776c0ac95'
PROJECT_SOURCE = 'https://github.com/robot-assisted-projects/FRPL-RMA/blob/expansion/all-states/'
MODEL_SCOPE = (
    'Houston ISD independent 2024–25 published-rate grade-school district models: '
    'exact operational CCD LEA 4823640 / native TX-101912 / TAPR DISTRICT 101912 '
    'attachments. All 212 native enrolled positive grades 3–8/no-high-grade profiles '
    'remain visible; 210 schools enter each independently fitted Math, ELA and '
    'Combined model using native whole-percent All Students Meets or Above displays '
    'and exact same-year individual economic-status enrollment ratios. Two missing '
    'or masked subject profiles remain unmodeled. High, mixed, primary-only and '
    'missing-native records remain outside this distinct point-only population. '
    'Valid-score counts, sampling variances and intervals are unavailable modelwide; '
    'the ten-valid-scored floor remains uncertified under issue #16.')


def same(actual, expected):
    """Typed exact evidence equality; Python bool/int equality is insufficient."""
    return roster_audit.fingerprint(actual) == roster_audit.fingerprint(expected)


def load_inputs():
    roster = model_audit.load_roster()
    content = model_audit.OUTPUT.read_bytes()
    if hashlib.sha256(content).hexdigest() != NUMERICAL_SHA:
        raise ValueError('Houston passed numerical audit fingerprint changed; re-audit the release')
    numerical = json.loads(content)
    model_audit.validate(numerical, model_audit.build(roster))
    if (numerical['hard_holds'] or numerical['status'] != 'numerically_verified_pending_integration'
            or numerical['approved_for_source'] is not False or roster['approved_for_source'] is not False
            or numerical['approved_for_modeling'] is not False or roster['approved_for_modeling'] is not False
            or not same(numerical['count_definition_hold'], model_audit.COUNT_HOLD)
            or len(numerical['models']) != 3
            or {(m['level'], m['subject']) for m in numerical['models']} != {('ES', s) for s in model_audit.SUBJECTS}
            or any(m['status'] != 'numerically_verified_pending_integration'
                   or m['coefficients']['n'] != 210 or m['valid_score_floor_certified'] is not False
                   or m['intervals']['available_for_entire_model'] for m in numerical['models'])):
        raise ValueError('Houston published-rate audit has unresolved numerical/population holds or changed count policy')
    return roster, numerical


def cohorts():
    return [dict(id='grade', level='ES', assessment=model_audit.ASSESSMENT,
        label='Grade schools · enrolled grades 3–8 Including EOC',
        grades='Enrolled grades 3–8, including applicable Algebra I and English I–II EOC',
        standard=model_audit.STANDARD, source_url=roster_audit.SOURCES['assessment']['url'],
        source='assessment', allow_point_only=True,
        outcome='Meets Grade Level or Above · published whole percentages',
        note='Houston independent published-rate district models · sampling intervals unavailable · scored-count floor uncertified')]


def outcome(school, entry, subject):
    value = model_audit.published_rate_evidence(entry['raw'], subject)
    reason = school['income']['exclusion'] or value['exclusion']
    # Missing income must not erase a directly published native assessment value.
    return dict(proficiency=value['published_rate'], tested=None,
        valid_score_evidence=None, raw_tested=None, exclusion=reason,
        source='assessment', source_row=entry['source_row'],
        raw=dict(applicable=True, outcome_basis='native_published_whole_percent',
            published_rate_evidence=value, original_assessment_record=entry,
            unverified_reported_subject_evidence=school['subjects'][subject],
            native_school_id=school['native_school_id'],
            valid_score_count=None, sampling_variance=None, interval_availability=False,
            ten_valid_scored_floor_certified=False,
            count_note=model_audit.POLICY['counts']))


def build_snapshot(roster, numerical):
    raw = roster['raw_inputs']
    directory = {r['source_row']: r for r in raw['directory']['records']}
    students = {r['raw']['CAMPUS']: r for r in raw['stud']['records']}
    assessments = {r['raw']['CAMPUS']: r for r in raw['assessment']['records']}
    references = {r['raw']['CAMPUS']: r for r in raw['ref']['records']}
    schools, excluded = [], []
    for school in sorted(roster['roster_links'], key=lambda r: r['school_id']):
        if not (school['ccd_flags']['operational'] and school['native_present']
                and school['native_enrolled']['scope'] == 'grade-school'):
            excluded.append(copy.deepcopy(school))
            continue
        key = school['native_school_id']
        student, assessment, reference = students[key], assessments[key], references[key]
        income = school['income']
        schools.append(dict(id=school['school_id'], ncessch=school['school_id'], cohort='grade',
            name=school['name'], district_id=roster_audit.LEA, district=reference['raw']['DISTNAME'],
            city=None, county=reference['raw']['CNTYNAME'], enrollment=income['enrollment'],
            low_income=income['economic_disadvantage'], income=income['percentage'],
            income_source='stud', income_row=student['source_row'],
            income_raw=dict(original_student_record=student, reconciled_income_evidence=income,
                complete_native_grade_evidence=school['native_enrolled']),
            identity_raw=dict(ncessch=school['school_id'], native_school_id=key,
                ccd_native_school_id=school['ccd_native_school_id'],
                ccd_source_row=school['ccd_source_row'], ccd=directory[school['ccd_source_row']],
                native_source_rows=school['native_source_rows'], native_student=student,
                native_assessment=assessment, native_reference=reference,
                native_grade_evidence=school['native_enrolled'], ccd_offered=school['ccd_offered'],
                ccd_flags=school['ccd_flags'], supplemental_ccd_membership=school['ccd_membership'],
                native_peims_membership=school['native_peims_membership'],
                reference_high_grade_contradiction=school['native_reference_conflicts_with_positive_high_enrollment']),
            outcomes={s: outcome(school, assessment, s) for s in ['math', 'reading']}))
    if len(schools) != 212 or len(excluded) != 62:
        raise ValueError('Houston release must retain 212 exact native grade-school profiles and all 62 outside records')
    source_audit = dict(operational_roster=roster['coverage'], cohorts=roster['cohorts'],
        excluded_operational_roster_records=excluded,
        excluded_native_configuration_records=numerical['models'][0]['coverage']['excluded_configuration_records'],
        outside_native_configuration_records=numerical['models'][0]['coverage']['outside_native_configuration_records'],
        count_definition_hold=copy.deepcopy(model_audit.COUNT_HOLD),
        held_populations=dict(high='High-school assessment population not audited for district release',
            mixed='Mixed-grade assessment population not audited for district release',
            primary_only='No positive native enrolled grades 3–8',
            missing_native='No same-year native TAPR campus record'),
        native_assessment_definition=dict(state='TX', name=model_audit.ASSESSMENT, year=2025, level='ES',
            grades=cohorts()[0]['grades'], standard=model_audit.STANDARD,
            source_url=roster_audit.SOURCES['assessment']['url']),
        source_definition_policy=roster['policy'], published_rate_policy=model_audit.POLICY,
        native_source_definition_evidence=raw['definitions'],
        enrollment_reconciliation=roster['enrollment_reconciliation'],
        planning_identity_reconciliation=roster['planning_identity_reconciliation'],
        historical_state_consistency=roster['historical_state_consistency'],
        retained_raw_inputs=copy.deepcopy(raw), raw_input_fingerprint=roster_audit.RAW_INPUT_SHA,
        retained_source_headers={k: {field: copy.deepcopy(v[field]) for field in v if field != 'records'} |
            dict(records=len(v['records'])) for k, v in raw.items() if 'records' in v},
        release_basis=dict(exact_source_roster_replayed=True, numerical_audit_without_holds=True,
            minimum_subject_schools=30, historical_audits_approved_for_source=False,
            historical_audits_approved_for_modeling=False, all_models_point_only=True,
            verified_valid_score_denominators_available=False, ten_valid_scored_floor_certified=False,
            numerical_success_resolves_count_hold=False,
            note='Immutable source and numerical audit approvals remain false. This separate published-rate adapter validates normalized selection and every canonical/static fit; ready applies only to this explicit unknown-count contract, never the historical count-based gate.'))
    selection = dict(policy=model_audit.POLICY, frozen_source_population=numerical['frozen_population'],
        count_definition_hold=copy.deepcopy(model_audit.COUNT_HOLD),
        directory_school_ids=[r['id'] for r in schools],
        subject_models={m['model_id']: dict(level=m['level'], subject=m['subject'],
            school_ids=[r['school_id'] for r in m['inputs']], population_sha256=m['population_sha256'])
            for m in numerical['models']})
    selection['sha256'] = roster_audit.fingerprint(selection)
    sources = dict(roster['sources'])
    sources.update(roster_audit=dict(path='data/source/houston-district-audit.json',
            url=PROJECT_SOURCE + 'data/source/houston-district-audit.json', sha256=model_audit.ROSTER_SHA),
        numerical_audit=dict(path='data/source/houston-model-audit.json',
            url=PROJECT_SOURCE + 'data/source/houston-model-audit.json', sha256=NUMERICAL_SHA))
    coverage_note = (
        'Houston ISD independent district comparison, 2024–25: exact CCD LEA 4823640 / TX-101912. '
        'All 212 native positive grades 3–8/no-high-grade profiles are searchable; 210 enter each '
        'Math, ELA and Combined model. LAS AMERICAS has missing subject displays and SECONDARY DAEP '
        'has masked displays; neither is converted to zero or reconstructed from counts. '
        'The full source audit retains 274 operational CCD schools, 273 native campuses and all '
        '62 outside records. Outcomes are published whole-percent All Students enrolled-grades '
        '3–8 Including EOC Meets or Above, including STAAR, Spanish and Alternate 2. Income is '
        'exact October 25, 2024 individual economic-status enrollment ratio, broader than FRPL '
        'and broader than tested pupils. Verified valid-score counts, sampling variances and '
        'intervals are unavailable for every model; the ten-valid-scored floor remains uncertified '
        'under open issue #16. No audited admissions classifications, coordinates or boundaries; one year only.')
    details = [MODEL_SCOPE,
        'Separate equal-school-weight OLS and externally studentized residuals use the deleted-school residual scale with N−3 degrees of freedom. All 630 explicit deleted-school fits were verified. Filters never refit and statewide residuals are never reused. Associations do not establish causal school effectiveness or overall quality.',
        model_audit.POLICY['published_rate_eligibility'],
        model_audit.POLICY['outcome'],
        'Published whole-percent precision differs from the historical count-ratio audit at 202 Math and 203 ELA model members; no count-derived proficiency, grade-rate average or both-subject passing measure is substituted.',
        roster_audit.POLICY['income'], roster_audit.POLICY['income_limits'],
        roster_audit.POLICY['assessment'],
        model_audit.POLICY['combined'], model_audit.POLICY['counts'],
        'The full operational roster has 274 schools and 273 native campuses. Native enrolled grades classify 212 grade schools, ten primary-only, 42 high-only and nine mixed campuses; one CCD campus is absent from TAPR. T H Rogers has 31 native high-grade pupils despite its elementary reference label and remains mixed. Charter and alternative labels never select model membership.',
        'The separate TAPR PEIMS membership total is 176,039 versus enrollment 176,727, differing at 150 campuses. Native enrollment and ED plus non-ED reconcile for all 273 campuses. Membership, enrollment, participation and reported performance #Tests remain provenance, never substitutes for verified valid-score counts.',
        'The largest deleted-school line shift across observed economic disadvantage is 0.930174 proficiency points. Leverage, Cook distance and residual flags are descriptive and never remove a member. Whole-percent rounding, varying assessment/grade mixes, broader economic status and omitted prior attainment or admissions remain limitations; studentization provides no enrollment adjustment or shrinkage.',
        'Only the separately audited 2024–25 no-high-grade population is released. The immutable count-based source contract remains held: exact N/NAAR and M/medical exemption mapping is unresolved under issue #16; this point-only release does not certify ten valid scored tests. High and mixed assessment scopes, provider roles, admissions, coordinates, boundaries and cross-assessment relative ambition remain unaudited. State thresholds and income proxies do not create an interchangeable national scale.']
    return dict(schema_version=1, dataset=DATASET, year=2025, academic_year='2024–25',
        state=dict(id='TX', name='Texas'), name='Houston ISD 2024–25 published-rate district comparison',
        region='houston', region_name='Houston ISD', statewide=False,
        comparison='Houston ISD · {year} · {assessment} · {note}',
        prepare_script='scripts/prepare_houston.py', source_url=roster_audit.SOURCES['assessment']['url'],
        retrieved=roster_audit.load_texas()['retrieved'], model_scope=MODEL_SCOPE, release_status='ready',
        map_source='School coordinates and district boundaries are unavailable in the audited Houston ISD source release.',
        income_definition=dict(label='Individually classified economic disadvantage',
            definition=roster_audit.POLICY['income'] + ' ' + roster_audit.POLICY['income_limits'],
            url=roster_audit.SOURCES['income-guide']['url']),
        sources=sources, cohorts=cohorts(), schools=schools, selection=selection,
        source_audit=source_audit, coverage_note=coverage_note,
        methodology=dict(summary='Houston ISD independent published-rate grade-school district models with exact same-year individual economic status; verified counts and sampling intervals unavailable, scored-count floor uncertified.',
            details=details, sources=[dict(label=label, url=roster['sources'][key]['url']) for key, label in [
                ('assessment', 'TEA 2024–25 enrolled-grades 3–8 TAPR original subject displays'),
                ('dictionary', 'TEA native performance field dictionary'),
                ('stud', 'TEA native enrolled grade and individual economic-status counts'),
                ('ref', 'TEA native campus and district identities'),
                ('glossary', 'TAPR accountability subset and assessment definitions'),
                ('income-guide', 'Individual economic status reporting rules'),
                ('income-extension', 'Same-year income verification extension'),
                ('accountability-manual', '2025 Accountability Manual: performance/participation'),
                ('performance-listing', '2025 STAAR performance and participation listing'),
                ('directory', '2024–25 CCD exact district school roster'),
                ('membership', '2024–25 CCD supplemental membership and grade subtotals')]]))


def build():
    return build_snapshot(*load_inputs())


def validate(payload, expected=None):
    expected = build() if expected is None else expected
    if not same(payload, expected):
        raise ValueError('Houston normalized extract differs from pinned source/model evidence, published-rate scope or selection policy')
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
        if not same(datasets, [dict(id=DATASET, state='TX', name=payload['name'],
                model_scope=payload['model_scope'], status='ready')]):
            raise ValueError('Houston ISD canonical dataset release metadata changed')
        sources = dict(payload['sources'])
        sources['extract'] = dict(path=str(Path(extract_path).resolve().relative_to(ROOT)),
                                 url=payload['source_url'], sha256=hashlib.sha256(Path(extract_path).read_bytes()).hexdigest())
        expected_sources = {DATASET + ':' + key: dict(id=DATASET + ':' + key, dataset_id=DATASET,
            path=source['path'], url=source['url'], sha256=source['sha256'], imported_at=payload['retrieved'])
            for key, source in sources.items()}
        actual_sources = {r['id']: dict(r) for r in db.execute(
            'SELECT * FROM source WHERE dataset_id=? OR id LIKE ?', (DATASET, namespace))}
        if not same(actual_sources, expected_sources):
            raise ValueError('Houston ISD canonical source provenance changed')
        definitions = [dict(r) for r in db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_definition = dict(id=assessment_id, state='TX', name=cohort['assessment'], year=2025,
            level='ES', grades=cohort['grades'], standard=cohort['standard'], source_url=cohort['source_url'])
        income_rows = [dict(r) for r in db.execute('SELECT * FROM economic_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_income = dict(id=income_id, name=payload['income_definition']['label'],
            definition=payload['income_definition']['definition'], source_url=payload['income_definition']['url'])
        if not same(definitions, [expected_definition]) or not same(income_rows, [expected_income]):
            raise ValueError('Houston ISD canonical native assessment/income definition changed')
        # SQLite foreign keys verify each referenced identity but do not require
        # source/definition/model ownership to match the observation's dataset.
        # Include every namespace reference so a foreign owner cannot hide rows
        # from an otherwise correct dataset-only count. Houston keys use NCES IDs;
        # statewide Texas retains native CAMPUS IDs and an independent namespace.
        school_rows = list(db.execute('SELECT * FROM school WHERE dataset_id=? OR source_id LIKE ?',
                                      (DATASET, namespace)))
        economic_rows = list(db.execute('''SELECT * FROM economic_observation WHERE
            dataset_id=? OR definition_id LIKE ? OR source_id LIKE ?''', (DATASET, namespace, namespace)))
        observation_rows = list(db.execute('''SELECT * FROM assessment_observation WHERE
            dataset_id=? OR definition_id LIKE ? OR source_id LIKE ?''', (DATASET, namespace, namespace)))
        if len(school_rows) != 212 or len(economic_rows) != 212 or len(observation_rows) != 424:
            raise ValueError('Houston ISD canonical profile/observation row counts changed')
        schools = {r['school_id']: dict(r) for r in school_rows}
        economic = {r['school_id']: dict(r) for r in economic_rows}
        observations = {(r['school_id'], r['subject']): dict(r) for r in observation_rows}
        if set(schools) != set(profiles) or set(economic) != set(profiles) or set(observations) != {(key, subject) for key in profiles for subject in ['math', 'reading']}:
            raise ValueError('Houston ISD canonical profile/observation membership changed')
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
                raise ValueError('Houston ISD canonical raw profile/same-year individual income changed')
            for subject in ['math', 'reading']:
                value = profile['outcomes'][subject]
                actual = dict(observations[(key, subject)])
                actual['raw_value'], actual['raw_tested'] = json.loads(actual['raw_value']), json.loads(actual['raw_tested'])
                expected = dict(dataset_id=DATASET, school_id=key, definition_id=assessment_id, subject=subject,
                    proficiency=number(value['proficiency']), tested=None,
                    status='reported' if value['proficiency'] is not None else 'suppressed_or_not_reported',
                    raw_value=value['raw'], raw_tested=None, source_id=DATASET + ':' + value['source'], source_order=value['source_row'])
                if not same(actual, expected):
                    raise ValueError('Houston ISD canonical native outcome/raw exclusion/count evidence changed')
        model_rows = list(db.execute('''SELECT * FROM model_run WHERE
            dataset_id=? OR id LIKE ? OR definition_id LIKE ?''', (DATASET, namespace, namespace)))
        runs = {r['subject']: dict(r) for r in model_rows}
        if len(model_rows) != 3 or len(runs) != 3 or set(runs) != set(model_audit.SUBJECTS):
            raise ValueError('Houston ISD canonical models require exactly three ES subject fits')
        digest = hashlib.sha256(json.dumps([(key, actual_sources[key]['sha256']) for key in sorted(actual_sources)]).encode()).hexdigest()
        total = 0
        for model in numerical['models']:
            subject = model['subject']; run = runs[subject]
            summary = json.loads(run.pop('summary_json'))
            expected_run = dict(id=f'{assessment_id}:{subject}:ols-v1:{digest[:12]}', dataset_id=DATASET,
                definition_id=assessment_id, subject=subject, method_version='ols-studentized-v1', input_sha256=digest)
            expected_summary = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                assessed_schools=212, excluded_schools=2, **model['coefficients'])
            exact = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
            if (not same(run, expected_run) or not same({k: summary.get(k) for k in exact}, {k: expected_summary[k] for k in exact})
                    or not model_audit.numeric_equal(summary, expected_summary)):
                raise ValueError('Houston ISD canonical model metadata/coefficients differ from audited fits')
            saved = {r['school_id']: dict(r) for r in db.execute('SELECT * FROM model_result WHERE model_id=?', (run['id'],))}
            reference = {r['school_id']: r for r in model['results']}
            if set(saved) != set(reference):
                raise ValueError('Houston ISD canonical result membership changed')
            for key, result in reference.items():
                actual = saved[key]
                exact_result = dict(model_id=run['id'], dataset_id=DATASET, school_id=key, actual=float(result['actual']), low=None, high=None)
                expected_result = exact_result | dict(predicted=result['predicted'], studentized=result['studentized'])
                if (not same({k: actual.get(k) for k in exact_result}, exact_result)
                        or not model_audit.numeric_equal(actual, expected_result)):
                    raise ValueError('Houston ISD canonical point-only result differs from audited district fit')
            total += len(saved)
        if total != 630 or db.execute('SELECT count(*) FROM model_result WHERE dataset_id=? OR model_id LIKE ?',
                                      (DATASET, namespace)).fetchone()[0] != total:
            raise ValueError('Houston ISD canonical result count changed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Houston ISD canonical foreign-key integrity failed')
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
    if (len(schools['schools']) != 212 or len(history['records']) != 212
            or set(exported) != set(profiles) or set(records) != set(profiles)):
        raise ValueError('Houston ISD exported native source directory/history identities differ from selection')
    if set(schools['models']) != {'ES'} or set(schools['models']['ES']) != set(model_audit.SUBJECTS):
        raise ValueError('Houston ISD export requires only the three independently audited ES models')
    expected_keys = {(2025, 'ES', model_audit.ASSESSMENT, m['subject']) for m in numerical['models']}
    for summaries in [schools['history_models'], history['models']]:
        keyed = {(m['year'], m['level'], m['assessment'], m['subject']): m for m in summaries}
        if len(summaries) != 3 or len(keyed) != 3 or set(keyed) != expected_keys:
            raise ValueError('Houston ISD history must retain exactly three audited ES model populations')
        if any(not same(summary, schools['models']['ES'][key[3]]) for key, summary in keyed.items()):
            raise ValueError('Houston ISD historical model summaries differ from current district fits')
    for model in numerical['models']:
        subject = model['subject']
        actual_model = schools['models']['ES'][subject]
        expected_model = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                              assessed_schools=212, excluded_schools=2, **model['coefficients'])
        exact_model = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
        if (not same({k: actual_model.get(k) for k in exact_model}, {k: expected_model[k] for k in exact_model})
                or not model_audit.numeric_equal(actual_model, expected_model)):
            raise ValueError('Houston ISD exported district coefficients/coverage differ from numerical audit')
        reference = {r['school_id']: r for r in model['results']}
        eligible = {s['id'] for s in schools['schools'] if subject in s['metrics']}
        if eligible != set(reference):
            raise ValueError('Houston ISD exported subject membership differs from passed district audit')
        for key, result in reference.items():
            fields = ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'leverage']
            metric = exported[key]['metrics'][subject]
            expected_metric = {k: result[k] for k in fields} | dict(tested=None, cohort_n=210)
            exact = ['actual', 'tested', 'low', 'high', 'cohort_n']
            if (not same({k: metric.get(k) for k in exact}, {k: expected_metric[k] for k in exact})
                    or not model_audit.numeric_equal(metric, expected_metric)
                    or not same(metric, records[key]['subjects'][subject])):
                raise ValueError('Houston ISD per-school point-only metric differs from verified district fit')
    for key, school in exported.items():
        profile = profiles[key]
        record = records[key]
        expected_subjects = {m['subject'] for m in numerical['models'] if key in {r['school_id'] for r in m['results']}}
        if set(school['metrics']) != expected_subjects or set(record['subjects']) != expected_subjects:
            raise ValueError('Houston ISD profile/history subject set differs from exact audited eligibility')
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
            raise ValueError('Houston ISD profile/history/exclusion/geography evidence changed')
    expected_coverage = {'grade': {'directory': 212, 'eligible': {s: 210 for s in model_audit.SUBJECTS}}}
    if not same(coverage, dict(year=2025, schools=212, cohorts=expected_coverage,
            source_audit=payload['source_audit'], exclusions=dict(Counter(
                reason for r in records.values() for reason in r['exclusions'].values())))):
        raise ValueError('Houston ISD exported coverage/source exclusions differ from approved selection')
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
        raise ValueError('Houston ISD exported native assessment definition or methodology changed')
    expected_descriptor = dict(schema_version=1, state=payload['state'], prepare_script=payload['prepare_script'],
        regions=[dict(id='houston', geography='houston', name=payload['region_name'], dataset=DATASET,
            statewide=False, status='ready', levels=['ES'], boundaries=None, comparison=payload['comparison'],
            audit=str((output / 'coverage.json').relative_to(ROOT)),
            schools=str((output / 'schools.json').relative_to(ROOT)),
            model_scope=payload['model_scope'], map_source=payload['map_source'])])
    if not same(descriptor, expected_descriptor):
        raise ValueError('Houston ISD ready descriptor must retain distinct district and point-only scope')
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
