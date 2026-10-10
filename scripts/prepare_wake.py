"""Canonical and static Wake County published-rate comparisons from frozen audits."""
import argparse
from collections import Counter
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path

import audit_wake as roster_audit
import audit_wake_models as model_audit
from database import ROOT, DEFAULT_DB, connect, definition_id
from state_snapshot import prepare_snapshot

DATASET = 'nc-wake-2025'
EXTRACT = ROOT / 'data/source/wake.json'
OUTPUT = ROOT / 'data/wake'
NUMERICAL_SHA = '75739a380c4b5818ac78bb3de12ddacbc5129a62a800c20b0d19540f1c750be3'
NUMERICAL_CODE_SHA = '5cb09e5aba40dc20fd648565680a0cadc7b86033e1a88fb800bd3eb48142c343'
PROJECT_SOURCE = 'https://github.com/robot-assisted-projects/FRPL-RMA/blob/expansion/all-states/'
EXPECTED_N = {'math': 159, 'reading': 160, 'combined': 159}
MODEL_SCOPE = (
    'Wake County independent 2024–25 North Carolina grade-school district models: exact '
    'operational CCD LEA 3704720 / native NC-920 / PSU 920 identities. All 162 audited '
    'grade-school configurations remain visible, including two suppressed April individual '
    'EDS income profiles. Native regular RG/GS/ALL published GLP Level3+ rates support '
    '159 Math, 160 ELA and 159 Combined fits. Grade 8 mathematics includes NC Math 1 EOC. '
    'Valid-score count scope and the ten-valid-scored floor remain uncertified; sampling '
    'intervals are unavailable for every model. High, mixed, future and district aggregate '
    'records remain outside this separate published-rate district release.')
COUNT_NOTE = (
    'Valid-score count scope and the ten-valid-scored floor remain uncertified. '
    'Native num_tested, April enrollment, fall membership and federal 95%-rule counts '
    'are never substituted as valid-score denominators. Sampling intervals are unavailable.')


def same(actual, expected):
    """Typed exact evidence equality; Python bool/int equality is insufficient."""
    return roster_audit.fingerprint(actual) == roster_audit.fingerprint(expected)


def require_frozen_inputs(roster, numerical):
    """Direct normalization also requires both complete immutable evidence sets."""
    model_audit.require_frozen_roster(roster)
    if hashlib.sha256((ROOT / 'scripts/audit_wake_models.py').read_bytes()).hexdigest() != NUMERICAL_CODE_SHA:
        raise ValueError('Wake County frozen numerical code/policy fingerprint changed')
    content = model_audit.OUTPUT.read_bytes()
    if hashlib.sha256(content).hexdigest() != NUMERICAL_SHA or not same(numerical, json.loads(content)):
        raise ValueError('Wake County complete numerical evidence fingerprint changed')


def load_inputs():
    roster = model_audit.load_roster()
    code = ROOT / 'scripts/audit_wake_models.py'
    if hashlib.sha256(code.read_bytes()).hexdigest() != NUMERICAL_CODE_SHA:
        raise ValueError('Wake County frozen numerical code/policy fingerprint changed; re-audit the release')
    content = model_audit.OUTPUT.read_bytes()
    if hashlib.sha256(content).hexdigest() != NUMERICAL_SHA:
        raise ValueError('Wake County passed numerical audit fingerprint changed; re-audit the release')
    numerical = json.loads(content)
    model_audit.validate(numerical, model_audit.build(roster))
    if (numerical['hard_holds']
            or numerical['approved_for_source'] is not False or roster['approved_for_source'] is not False
            or numerical['approved_for_modeling'] is not False or roster['approved_for_modeling'] is not False
            or len(numerical['models']) != 3
            or {(m['level'], m['subject']) for m in numerical['models']} != {('ES', s) for s in model_audit.SUBJECTS}
            or len(numerical['frozen_population']['grade_school_configuration_ids']) != 162
            or len(numerical['frozen_population']['native_source_profile_ids']) != 160
            or any(m['status'] != 'numerically_verified_pending_integration'
                   or m['coefficients']['n'] != EXPECTED_N[m['subject']]
                   or m['intervals']['available_for_entire_model']
                   or m['coverage']['ten_valid_scored_floor_certified'] is not False
                   for m in numerical['models'])):
        raise ValueError('Wake County numerical audit has unresolved grade-school release or population holds')
    return roster, numerical


def cohorts():
    return [dict(id='grade', level='ES', assessment=model_audit.ASSESSMENT,
        label='Grade schools · NC EOG/Math 1', grades='3–8', standard=model_audit.STANDARD,
        source_url=roster_audit.north_carolina.PERFORMANCE_URL, source='dpi_performance',
        allow_point_only=True, outcome='Grade-level proficient',
        note='Native regular RG/GS/ALL grades 3–8 · grade 8 Math 1 included · April individual EDS · '
             'valid-score count scope and ten-valid-scored floor uncertified · sampling intervals unavailable')]


def outcome(value, entry):
    # Preserve a directly published rate even when matching income is suppressed.
    return dict(proficiency=value['native_rate'], tested=None, valid_score_evidence=None,
        raw_tested=None, exclusion=value['exclusion'], source=value['source'],
        source_row=entry['source_row'], raw=dict(applicable=value['applicable'],
            native_usable=value['usable'], native_outcome=copy.deepcopy(value),
            assessment_raw=copy.deepcopy(entry['raw']), native_rate=value['raw_rate'],
            native_school_id=entry['raw']['school_code'],
            valid_score_count=None, sampling_variance=None, interval_availability=False,
            ten_valid_scored_floor_certified=False, count_note=COUNT_NOTE))


def build_snapshot(roster, numerical):
    """Retain the complete audited configuration cohort, before source masks."""
    require_frozen_inputs(roster, numerical)
    raw = roster['raw_inputs']
    directory = {roster_audit.ccd_identity(r['raw']): r for r in raw['directory']['records']}
    income_rows = {roster_audit.native_identity(r['raw'], income=True): r for r in raw['income']['records']}
    native = {}
    for entry in raw['assessment']['records']:
        r = entry['raw']
        if (r['subgroup'], r['type'], r['grade']) == ('ALL', 'RG', 'GS') and r['subject'] in {'MA', 'RD'}:
            key = roster_audit.native_identity(r)
            subject = 'math' if r['subject'] == 'MA' else 'reading'
            if subject in native.setdefault(key, {}):
                raise ValueError('Duplicate exact Wake native regular GS subject')
            native[key][subject] = entry
    configurations = set(numerical['frozen_population']['grade_school_configuration_ids'])
    schools, excluded = [], []
    for school in sorted(roster['roster_links'], key=lambda r: r['school_id']):
        key = school['school_id']
        if key not in configurations:
            excluded.append(copy.deepcopy(school)); continue
        profile = directory[key]['raw']; income = school['income']; eds = income_rows[key]
        schools.append(dict(id=key, ncessch=school['ncessch'], cohort='grade',
            name=profile['SCH_NAME'], district_id=roster_audit.LEA, district=profile['LEA_NAME'],
            city=profile['LCITY'] or None, county=None, enrollment=income['april_enrollment'], low_income=None,
            income=income['percentage'], income_source=income['source'], income_row=eds['source_row'],
            income_raw=dict(april_income=copy.deepcopy(eds), individual_eds_evidence=copy.deepcopy(income)),
            identity_raw=dict(ncessch=school['ncessch'], native_school_id=school['native_school_id'],
                ccd=copy.deepcopy(directory[key]), offered_evidence=copy.deepcopy(school['offered']),
                enrolled_evidence=copy.deepcopy(school['enrolled']), ccd_flags=copy.deepcopy(school['ccd_flags']),
                april_minus_fall_enrollment=school['april_minus_fall_enrollment']),
            outcomes={s: outcome(school['subjects'][s], native[key][s]) for s in ['math', 'reading']}))
    if len(schools) != 162 or len(excluded) != 36:
        raise ValueError('Wake release requires 162 grade-school configurations and 36 outside operational records')
    source_audit = dict(operational_roster=copy.deepcopy(roster['coverage']), cohorts=copy.deepcopy(roster['cohorts']),
        excluded_operational_roster_records=excluded, nonoperational_directory=copy.deepcopy(roster['nonoperational_directory']),
        outside_directory_records=copy.deepcopy(roster['outside_directory_records']),
        subject_coverage={m['subject']: copy.deepcopy(m['coverage']) for m in numerical['models']},
        native_assessment_definition=dict(state='NC', name=model_audit.ASSESSMENT, year=2025,
            level='ES', grades='3–8', standard=model_audit.STANDARD,
            source_url=roster_audit.north_carolina.PERFORMANCE_URL),
        source_definition_evidence=copy.deepcopy(roster['source_definition_evidence']),
        planning_identity_reconciliation=copy.deepcopy(roster['planning_identity_reconciliation']),
        retained_raw_inputs=copy.deepcopy(raw), raw_input_fingerprint=roster_audit.RAW_INPUT_SHA,
        retained_source_headers={k: dict(source_id=v['source_id'], header_source_row=v['header_source_row'],
            header=v['header'], records=len(v['records'])) for k, v in raw.items()
            if k in {'directory', 'membership', 'lea_directory', 'lea_membership', 'assessment', 'income'}},
        historical_state_extract=copy.deepcopy(roster['state_extract']),
        count_definition_status=copy.deepcopy(numerical['count_definition_status']),
        release_basis=dict(exact_source_roster_replayed=True, numerical_audit_without_holds=True,
            minimum_subject_schools=30, historical_audits_approved_for_source=False,
            historical_audits_approved_for_modeling=False, all_models_point_only=True,
            normalized_source_approved=True, district_modeling_approved=True,
            note='Historical source and numerical audit approvals remain false. This separate published-rate adapter validates normalized source selection and every canonical/static fit before release. Valid-score count scope and the ten-valid-scored floor remain uncertified; no high, mixed, future or aggregate population is approved.'))
    selection = dict(policy=copy.deepcopy(model_audit.POLICY), frozen_source_population=copy.deepcopy(numerical['frozen_population']),
        directory_school_ids=[r['id'] for r in schools],
        subject_models={m['model_id']: dict(level=m['level'], subject=m['subject'],
            school_ids=[r['school_id'] for r in m['inputs']], population_sha256=m['population_sha256']) for m in numerical['models']})
    selection['sha256'] = roster_audit.fingerprint(selection)
    sources = copy.deepcopy(roster['sources'])
    sources.update(roster_audit=dict(path='data/source/wake-district-audit.json',
            url=PROJECT_SOURCE + 'data/source/wake-district-audit.json', sha256=model_audit.ROSTER_SHA),
        numerical_audit=dict(path='data/source/wake-model-audit.json',
            url=PROJECT_SOURCE + 'data/source/wake-model-audit.json', sha256=NUMERICAL_SHA))
    coverage_note = (
        'Wake County independent district comparison, 2024–25: exact CCD LEA 3704720 / NC-920 / PSU 920. '
        'All 162 audited grade-school configurations are searchable; 160 have usable April individual EDS income. '
        'Models include 159 Math, 160 ELA and 159 Combined schools. Apex Friendship and White Oak retain suppressed '
        'income; Mills Park retains ELA but has a masked Math rate. White Oak Math is also masked. '
        'The full audit preserves 198 operational schools, 33 high and 3 mixed configurations, 4 future records '
        'and district aggregates. Native regular RG/GS/ALL GLP 3+ includes grade 8 Math 1 EOC; April EDS covers '
        'the broader enrolled population and is not fall membership or the tested-income subgroup. '
        'Valid-score count scope and the ten-valid-scored floor are uncertified; sampling intervals '
        'unavailable modelwide. No audited admissions classifications, provider roles, coordinates or boundaries; one year only.')
    details = [MODEL_SCOPE,
        'Each subject uses independent unweighted district OLS and externally studentized residuals, including all 478 explicit deleted-school checks. Combined is the equally weighted mean of original Math and ELA percentages with its own 159-school fit and studentization, not proficiency in both. Filters never refit models. Associations do not establish causal effectiveness or overall school quality.',
        'Exact native RG/GS/ALL rows preserve published GLP Level3 and above. Grade 8 mathematics includes NC Math 1 EOC. Standalone high-school EOC rows, alternate X1 rows, ALL test-type totals, subgroup totals and district aggregates are excluded. Native codebook EXT1 versus actual X1 and grade 9–12 versus grade 9–13 notes remain retained source limitations. Completed 2024–25 tests include 2024 summer school.',
        roster_audit.north_carolina.INCOME_DEFINITION,
        'April individual EDS is a percentage of all currently enrolled pupils, broader than tested grades. No low-income count is inferred from the rounded percentage. April enrollment totals 164495 reconcile to the district aggregate; fall CCD LEA 163325 differs from summed school membership 163176 by 149. 192 school April denominators differ from fall counts. These sources and populations are not interchangeable.',
        'Preserve 162 complete CCD grade configurations and 160 usable-income profiles. Apex Friendship 920314 and White Oak 920614 have April EDS<5; Mills Park 920502 and White Oak Math>95 remain missing. Missing or ranged values never mean zero or endpoints. All3 eligible Alternative schools remain; category, residuals, leverage and fit diagnostics never remove a member.',
        COUNT_NOTE + ' All valid-score counts, sampling variances and interval endpoints are null for every model member. Studentization uses the deleted-school residual scale with N−3 degrees of freedom and provides no enrollment adjustment or shrinkage. Federal 95%-rule school-grade calculations are distinct from these published completed-test totals.',
        'Only audited grade schools are released. 33 high configurations include 4 grade 13 early colleges; 3 mixed configurations include 2 grades 6–13 leadership schools with native GS rows, which do not approve a mixed model. 4 future directory records remain outside. Complete original headers, masks, definitions, checksums and source rows remain available in source evidence.',
        'Independent full fits and all 478 omissions have finite positive residual scales. Largest deleted-line shifts over observed incomes are 1.152430 Math, 0.874748 ELA and 1.019816 Combined proficiency points. Influence flags are descriptive and never exclusions or school-quality labels.',
        'One year only. No audited admissions classifications, provider roles, coordinates or boundaries. The CCD Alternative label remains provenance; visible programs are Unclassified. State thresholds and economic definitions do not create a common national ranking.']
    return dict(schema_version=1, dataset=DATASET, year=2025, academic_year='2024–25',
        state=dict(id='NC', name='North Carolina'), name='Wake County 2024–25 district comparison',
        region='wake', region_name='Wake County', statewide=False,
        comparison='Wake County · {year} · {assessment} · {note}', prepare_script='scripts/prepare_wake.py',
        source_url=roster_audit.north_carolina.PERFORMANCE_URL, retrieved='2026-10-09',
        model_scope=MODEL_SCOPE, release_status='ready', approved_for_source=True, approved_for_modeling=True,
        map_source='School coordinates and district boundaries are unavailable in the audited Wake County source release.',
        income_definition=dict(label='Economically disadvantaged', definition=roster_audit.north_carolina.INCOME_DEFINITION,
            url=roster_audit.north_carolina.DEFINITION_URL), sources=sources, cohorts=cohorts(),
        schools=schools, selection=selection, source_audit=source_audit, coverage_note=coverage_note,
        methodology=dict(summary='Wake County independent grade-school district models with same-year April individual EDS and native regular GLP 3+ rates; valid-score count scope and ten-valid-scored floor uncertified, sampling intervals unavailable.',
            details=details, sources=[dict(label=label, url=sources[key]['url']) for key, label in [
                ('dpi_performance', 'DPI native completed-test disaggregated totals and descriptions'),
                ('dpi_income', 'DPI April 2025 individual EDS workbook'),
                ('dpi_income_definition', 'DPI EDS collection scope'),
                ('dpi_eds_web_definition', 'DPI individual EDS eligibility definitions'),
                ('dpi_technical', 'DPI 2024–25 school-grade technical guide'),
                ('ccd_directory', 'CCD exact district school directory'),
                ('ccd_membership', 'CCD complete school membership and grade subtotals'),
                ('ccd_lea_membership', 'CCD fall agency membership')]]))

def build():
    return build_snapshot(*load_inputs())

def validate(payload, expected=None):
    expected = build() if expected is None else expected
    if not same(payload, expected):
        raise ValueError('Wake County normalized extract differs from pinned source/model evidence, scope or selection policy')
    return payload['source_audit']


def extract(destination=EXTRACT):
    payload = build()
    Path(destination).write_text(json.dumps(payload, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return payload


def validate_canonical(payload, database, numerical, extract_path=EXTRACT):
    """Read every scoped canonical input/result and compare with the passed audits."""
    validate(payload, build_snapshot(model_audit.load_roster(), numerical))
    cohort = payload['cohorts'][0]
    assessment_id = definition_id(DATASET, 2025, cohort['assessment'], 'ES')
    income_id = DATASET + ':income'
    profiles = {s['id']: s for s in payload['schools']}
    number = lambda value: None if value is None else float(value)
    namespace = DATASET + ':%'
    with closing(connect(database)) as db:
        datasets = [dict(r) for r in db.execute('SELECT * FROM dataset WHERE id=? OR id LIKE ?', (DATASET, namespace))]
        if not same(datasets, [dict(id=DATASET, state='NC', name=payload['name'],
                model_scope=payload['model_scope'], status='ready')]):
            raise ValueError('Wake County canonical dataset release metadata changed')
        sources = dict(payload['sources'])
        sources['extract'] = dict(path=str(Path(extract_path).resolve().relative_to(ROOT)),
                                 url=payload['source_url'], sha256=hashlib.sha256(Path(extract_path).read_bytes()).hexdigest())
        expected_sources = {DATASET + ':' + key: dict(id=DATASET + ':' + key, dataset_id=DATASET,
            path=source['path'], url=source['url'], sha256=source['sha256'], imported_at=payload['retrieved'])
            for key, source in sources.items()}
        actual_sources = {r['id']: dict(r) for r in db.execute(
            'SELECT * FROM source WHERE dataset_id=? OR id LIKE ?', (DATASET, namespace))}
        if not same(actual_sources, expected_sources):
            raise ValueError('Wake County canonical source provenance changed')
        definitions = [dict(r) for r in db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_definition = dict(id=assessment_id, state='NC', name=cohort['assessment'], year=2025,
            level='ES', grades=cohort['grades'], standard=cohort['standard'], source_url=cohort['source_url'])
        income_rows = [dict(r) for r in db.execute('SELECT * FROM economic_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_income = dict(id=income_id, name=payload['income_definition']['label'],
            definition=payload['income_definition']['definition'], source_url=payload['income_definition']['url'])
        if not same(definitions, [expected_definition]) or not same(income_rows, [expected_income]):
            raise ValueError('Wake County canonical native assessment/income definition changed')
        # SQLite foreign keys verify each referenced identity but do not require
        # source/definition/model ownership to match the observation's dataset.
        # Include every namespace reference so a foreign owner cannot hide rows
        # from an otherwise correct dataset-only count. Native school IDs remain
        # shared with North Carolina's independent statewide release.
        school_rows = list(db.execute('SELECT * FROM school WHERE dataset_id=? OR source_id LIKE ?',
                                      (DATASET, namespace)))
        economic_rows = list(db.execute('''SELECT * FROM economic_observation WHERE
            dataset_id=? OR definition_id LIKE ? OR source_id LIKE ?''', (DATASET, namespace, namespace)))
        observation_rows = list(db.execute('''SELECT * FROM assessment_observation WHERE
            dataset_id=? OR definition_id LIKE ? OR source_id LIKE ?''', (DATASET, namespace, namespace)))
        if len(school_rows) != 162 or len(economic_rows) != 162 or len(observation_rows) != 324:
            raise ValueError('Wake County canonical profile/observation row counts changed')
        schools = {r['school_id']: dict(r) for r in school_rows}
        economic = {r['school_id']: dict(r) for r in economic_rows}
        observations = {(r['school_id'], r['subject']): dict(r) for r in observation_rows}
        if set(schools) != set(profiles) or set(economic) != set(profiles) or set(observations) != {(key, subject) for key in profiles for subject in ['math', 'reading']}:
            raise ValueError('Wake County canonical profile/observation membership changed')
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
                raise ValueError('Wake County canonical raw profile/same-year individual income changed')
            for subject in ['math', 'reading']:
                value = profile['outcomes'][subject]
                actual = dict(observations[(key, subject)])
                actual['raw_value'], actual['raw_tested'] = json.loads(actual['raw_value']), json.loads(actual['raw_tested'])
                expected = dict(dataset_id=DATASET, school_id=key, definition_id=assessment_id, subject=subject,
                    proficiency=number(value['proficiency']), tested=None,
                    status='reported' if value['proficiency'] is not None else 'suppressed_or_not_reported',
                    raw_value=value['raw'], raw_tested=None, source_id=DATASET + ':' + value['source'], source_order=value['source_row'])
                if not same(actual, expected):
                    raise ValueError('Wake County canonical native outcome/raw exclusion/count evidence changed')
        model_rows = list(db.execute('''SELECT * FROM model_run WHERE
            dataset_id=? OR id LIKE ? OR definition_id LIKE ?''', (DATASET, namespace, namespace)))
        runs = {r['subject']: dict(r) for r in model_rows}
        if len(model_rows) != 3 or len(runs) != 3 or set(runs) != set(model_audit.SUBJECTS):
            raise ValueError('Wake County canonical models require exactly three ES subject fits')
        digest = hashlib.sha256(json.dumps([(key, actual_sources[key]['sha256']) for key in sorted(actual_sources)]).encode()).hexdigest()
        total = 0
        for model in numerical['models']:
            subject = model['subject']; run = runs[subject]
            summary = json.loads(run.pop('summary_json'))
            expected_run = dict(id=f'{assessment_id}:{subject}:ols-v1:{digest[:12]}', dataset_id=DATASET,
                definition_id=assessment_id, subject=subject, method_version='ols-studentized-v1', input_sha256=digest)
            expected_summary = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                assessed_schools=162, excluded_schools=162 - model['coefficients']['n'], **model['coefficients'])
            exact = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
            if (not same(run, expected_run) or not same({k: summary.get(k) for k in exact}, {k: expected_summary[k] for k in exact})
                    or not model_audit.numeric_equal(summary, expected_summary)):
                raise ValueError('Wake County canonical model metadata/coefficients differ from audited fits')
            saved = {r['school_id']: dict(r) for r in db.execute('SELECT * FROM model_result WHERE model_id=?', (run['id'],))}
            reference = {r['school_id']: r for r in model['results']}
            if set(saved) != set(reference):
                raise ValueError('Wake County canonical result membership changed')
            for key, result in reference.items():
                actual = saved[key]
                exact_result = dict(model_id=run['id'], dataset_id=DATASET, school_id=key, actual=float(result['actual']), low=None, high=None)
                expected_result = exact_result | dict(predicted=result['predicted'], studentized=result['studentized'])
                if (not same({k: actual.get(k) for k in exact_result}, exact_result)
                        or not model_audit.numeric_equal(actual, expected_result)):
                    raise ValueError('Wake County canonical point-only result differs from audited district fit')
            total += len(saved)
        if total != 478 or db.execute('SELECT count(*) FROM model_result WHERE dataset_id=? OR model_id LIKE ?',
                                      (DATASET, namespace)).fetchone()[0] != total:
            raise ValueError('Wake County canonical result count changed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Wake County canonical foreign-key integrity failed')
    return {'schools': len(profiles), 'observations': len(observations), 'models': len(runs), 'results': total}


def validate_exports(payload, output, numerical):
    validate(payload, build_snapshot(model_audit.load_roster(), numerical))
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
        raise ValueError('Wake County exported native source directory/history identities differ from selection')
    if set(schools['models']) != {'ES'} or set(schools['models']['ES']) != set(model_audit.SUBJECTS):
        raise ValueError('Wake County export requires only the three independently audited ES models')
    expected_keys = {(2025, 'ES', model_audit.ASSESSMENT, m['subject']) for m in numerical['models']}
    for summaries in [schools['history_models'], history['models']]:
        keyed = {(m['year'], m['level'], m['assessment'], m['subject']): m for m in summaries}
        if len(summaries) != 3 or len(keyed) != 3 or set(keyed) != expected_keys:
            raise ValueError('Wake County history must retain exactly three audited ES model populations')
        if any(not same(summary, schools['models']['ES'][key[3]]) for key, summary in keyed.items()):
            raise ValueError('Wake County historical model summaries differ from current district fits')
    for model in numerical['models']:
        subject = model['subject']
        actual_model = schools['models']['ES'][subject]
        expected_model = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                              assessed_schools=162, excluded_schools=162 - model['coefficients']['n'], **model['coefficients'])
        exact_model = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
        if (not same({k: actual_model.get(k) for k in exact_model}, {k: expected_model[k] for k in exact_model})
                or not model_audit.numeric_equal(actual_model, expected_model)):
            raise ValueError('Wake County exported district coefficients/coverage differ from numerical audit')
        reference = {r['school_id']: r for r in model['results']}
        eligible = {s['id'] for s in schools['schools'] if subject in s['metrics']}
        if eligible != set(reference):
            raise ValueError('Wake County exported subject membership differs from passed district audit')
        for key, result in reference.items():
            fields = ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'leverage']
            metric = exported[key]['metrics'][subject]
            expected_metric = {k: result[k] for k in fields} | dict(tested=None, cohort_n=model['coefficients']['n'])
            exact = ['actual', 'tested', 'low', 'high', 'cohort_n']
            if (not same({k: metric.get(k) for k in exact}, {k: expected_metric[k] for k in exact})
                    or not model_audit.numeric_equal(metric, expected_metric)
                    or not same(metric, records[key]['subjects'][subject])):
                raise ValueError('Wake County per-school point-only metric differs from verified district fit')
    for key, school in exported.items():
        profile = profiles[key]
        record = records[key]
        expected_subjects = {m['subject'] for m in numerical['models'] if key in {r['school_id'] for r in m['results']}}
        if set(school['metrics']) != expected_subjects or set(record['subjects']) != expected_subjects:
            raise ValueError('Wake County profile/history subject set differs from exact audited eligibility')
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
            raise ValueError('Wake County profile/history/exclusion/geography evidence changed')
    expected_coverage = {'grade': {'directory': 162, 'eligible': {m['subject']: m['coefficients']['n'] for m in numerical['models']}}}
    if not same(coverage, dict(year=2025, schools=162, cohorts=expected_coverage,
            source_audit=payload['source_audit'], exclusions=dict(Counter(
                reason for r in records.values() for reason in r['exclusions'].values())))):
        raise ValueError('Wake County exported coverage/source exclusions differ from approved selection')
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
        raise ValueError('Wake County exported native assessment definition or methodology changed')
    expected_descriptor = dict(schema_version=1, state=payload['state'], prepare_script=payload['prepare_script'],
        regions=[dict(id='wake', geography='wake', name=payload['region_name'], dataset=DATASET,
            statewide=False, status='ready', levels=['ES'], boundaries=None, comparison=payload['comparison'],
            audit=str((output / 'coverage.json').relative_to(ROOT)),
            schools=str((output / 'schools.json').relative_to(ROOT)),
            model_scope=payload['model_scope'], map_source=payload['map_source'])])
    if not same(descriptor, expected_descriptor):
        raise ValueError('Wake County ready descriptor must retain distinct district and point-only scope')
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
