"""Canonical and static Clark County comparisons from pinned completed district audits."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import audit_clark_county as roster_audit
import audit_clark_county_models as model_audit
import copy
from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

DATASET = 'nv-clark-county-2025'
EXTRACT = ROOT / 'data/source/clark-county.json'
OUTPUT = ROOT / 'data/clark-county'
NUMERICAL_SHA = '44304bb83de3bb9656490bfcc933685fa5e29782460fa474d4a94fbd2e0332c5'
PROJECT_SOURCE = 'https://github.com/robot-assisted-projects/FRPL-RMA/blob/expansion/all-states/'
MODEL_SCOPE = (
    'Clark County independent 2024–25 native grade-school district models: exact '
    'operational CCD LEA 3200060 / native NV-02 attachments. Nevada reported-zero '
    'ungraded enrollment plus reconciled PK–8 membership, complete unadjusted lower '
    'offer flags and highest grade 01–08 define the native configuration. Retain '
    '289 native G38 source profiles, including three suppressed profiles, and all '
    '299 configurations in coverage. Exact attached charter/type/virtual evidence '
    'remains explicit; source missingness determines eligibility. Separate same-year '
    'SBAC Regular G38 Levels 3-4 Math, ELA and Combined point-only district OLS; '
    'high/mixed populations remain outside approval.')


def same(actual, expected):
    """Typed exact evidence equality; Python bool/int equality is insufficient."""
    return roster_audit.fingerprint(actual) == roster_audit.fingerprint(expected)


def load_inputs():
    roster = model_audit.load_roster()
    content = model_audit.OUTPUT.read_bytes()
    if hashlib.sha256(content).hexdigest() != NUMERICAL_SHA:
        raise ValueError('Clark County passed numerical audit fingerprint changed; re-audit the release')
    numerical = json.loads(content)
    model_audit.validate(numerical, model_audit.build(roster))
    if (numerical['hard_holds'] or numerical['approved_for_modeling'] is not False
            or roster['approved_for_modeling'] is not False
            or {(m['level'], m['subject']) for m in numerical['models']} != {('ES', s) for s in model_audit.SUBJECTS}
            or len(numerical['models']) != 3
            or any(m['status'] != 'numerically_verified_pending_integration'
                   or m['coefficients']['n'] < 30 or m['intervals']['available_for_entire_model']
                   for m in numerical['models'])):
        raise ValueError('Clark County numerical audit has unresolved release or population holds')
    return roster, numerical


def cohorts():
    # Copy the exact native Nevada definition; district scope is separate metadata.
    return copy.deepcopy(roster_audit.load_nevada()['cohorts'])


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
    native = roster_audit.load_nevada()
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
        if (not school['enrolled']['native_grade_school_contract']
                or school['enrolled']['ungraded_reported_count'] != 0
                or not school['enrolled']['lower_total_reconciled']
                or not school['native_g38_pair'] or school['income']['income_exclusion'] is not None):
            raise ValueError('Clark source profile lacks native zero-UG/reconciled-grade/income/G38 approval evidence')
        profile = school['state_snapshot_profile']
        schools.append(dict(
            id=school['school_id'], ncessch=school['school_id'], cohort='grade',
            name=profile['name'], district_id=roster_audit.LEA, district='Clark County',
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
    if len(schools) != 289:
        raise ValueError('Clark release must retain all 289 exact native G38 source profiles')
    source_audit = dict(
        operational_roster=roster['coverage'], cohorts=roster['cohorts'],
        excluded_operational_roster_records=excluded,
        excluded_native_configuration_records=numerical['models'][0]['coverage']['excluded_configuration_records'],
        outside_native_configuration_records=numerical['models'][0]['coverage']['outside_native_configuration_records'],
        nonoperational_directory=roster['nonoperational_directory'],
        outside_operational_roster_records=roster['outside_operational_roster_records'],
        historical_state_lunch_notes=roster['historical_state_lunch_notes'],
        raw_input_fingerprint=roster_audit.RAW_INPUT_SHA,
        retained_source_headers={k: dict(source_id=v['source_id'], header_source_row=v['header_source_row'],
            header=v['header'], selection=v['selection'], records=len(v['records'])) for k, v in raw.items()},
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
        roster_audit=dict(path='data/source/clark-county-district-audit.json',
                          url=PROJECT_SOURCE + 'data/source/clark-county-district-audit.json', sha256=model_audit.ROSTER_SHA),
        numerical_audit=dict(path='data/source/clark-county-model-audit.json',
                             url=PROJECT_SOURCE + 'data/source/clark-county-model-audit.json', sha256=NUMERICAL_SHA),
        state_extract=dict(path='data/source/ccd-state-snapshots.json',
                           url=PROJECT_SOURCE + 'data/source/ccd-state-snapshots.json', sha256=roster_audit.STATE_EXTRACT_SHA))
    coverage_note = (
        'Clark County independent district comparison, 2024–25. Exact CCD LEA 3200060 '
        '/ NV-02 has 379 operational schools, 299 native lower-grade configurations, '
        '298 offered-applicable and 289 native G38 profiles; 286 have eligible Math/ELA '
        'and matching individual-school Direct Certification income. Three suppressed '
        'profiles stay visible. All eligible points are regular schools: 283 noncharter '
        'and three attached charters. UG offerings require explicit reported-zero UG '
        'and reconciled PK–8 enrollment, not an assumption of strictly pure offerings. '
        'Primary, zero enrollment, missing/suppressed DC, absent G38 and high/mixed '
        'records remain in source coverage. Raw EDC score counts are unverified: all '
        'sampling intervals unavailable. No audited admissions labels, coordinates or '
        'boundaries; one year only.')
    details = [
        MODEL_SCOPE,
        'Every subject uses independent district OLS and externally studentized residuals, including all 858 explicit deleted-school checks. Filters never refit a model; statewide residuals are not reused. Associations do not establish causal school effectiveness or overall quality.',
        'The native directory has 289 source profiles including three with both subject rates suppressed: Blue Diamond, Reid Harry and Miley Achievement (special education). They remain visible with explicit exclusions. All 299 native lower configurations and 80 outside configurations retain complete scope/income/outcome reasons in coverage. Types, charters and EDC virtual flags never create fit-driven exclusions.',
        'All operational schools offer UG. Native lower-grade inclusion requires reported-zero UG, complete reconciled lower-grade enrollment, highest offered grade 01–08 and no high/adult offer. Missing or protected counts never mean zero. An offered grade is not proof of inclusion in the assessment total.',
        'SBAC Regular school All Students G38 Levels 3-4 uses EDC v3.1 documented SEA-native grades 3–8 totals. Exact published rates are used; individual-grade rates are never averaged. Source-level assessment population and valid-score denominator business rules are not independently verified.',
        native['income_definition']['definition'],
        'Income is individual-school reported nonnegative CCD Direct Certification divided by positive reported same-year school membership, including pre-K. Fall membership and the native tested population differ; benefits-based eligibility is distinct from household-income FRPL or universal free meals. Nevada lunch-category reporting caveats remain without inferred Clark-specific allocation failure.',
        'Combined is the equally weighted mean of eligible Math and ELA proficiency, not proficiency in both. Raw EDC tested/proficient/participation cells and enrollment never become valid-score counts. No sampling variance or interval endpoint is published for any member; studentization provides no enrollment adjustment or shrinkage.',
        'Independent numerical diagnostics found maximum leverage 0.028125 and maximum deleted-line shift 0.4921 proficiency points over observed incomes. Conventional influence flags are descriptive review signals, never quality labels or reasons to discard schools. Published-rate rounding, income proxy and native population limits persist.',
        'One-year grade-school comparison only. No high/mixed models, audited admissions classifications, school coordinates or boundaries. State thresholds and proxy definitions do not create an interchangeable national scale.',
    ]
    return dict(schema_version=1, dataset=DATASET, year=2025, academic_year='2024–25',
        state=dict(id='NV', name='Nevada'), name='Clark County 2024–25 district comparison',
        region='clark-county', region_name='Clark County', statewide=False,
        comparison='Clark County · {year} · {assessment} · {note}',
        prepare_script='scripts/prepare_clark_county.py', source_url=native['source_url'],
        retrieved=native['retrieved'], model_scope=MODEL_SCOPE, release_status='ready',
        map_source='School coordinates and district boundaries are unavailable in the audited Clark County source release.',
        income_definition=copy.deepcopy(native['income_definition']), sources=sources, cohorts=cohorts(),
        schools=schools, selection=selection, source_audit=source_audit, coverage_note=coverage_note,
        methodology=dict(summary='Clark County independent native grade-school district models with same-year individual-school Direct Certification.',
            details=details, sources=[dict(label='2025 Nevada native assessment source', url=roster_audit.nevada.SEA['NV']),
                dict(label='2025 Nevada EDC v3.1', url=roster['sources']['edc_2025']['url']),
                dict(label='2024–25 CCD individual Direct Certification', url=roster['sources']['ccd_lunch_2025']['url']),
                dict(label='2024–25 CCD membership and grade subtotals', url=roster['sources']['ccd_membership_2025']['url']),
                dict(label='2024–25 CCD exact school roster', url=roster['sources']['ccd_directory_2025']['url']),
                dict(label='EDC v3.1 grade-total provenance', url=roster['sources']['edc_technical_v3_1']['url'])]))


def build():
    return build_snapshot(*load_inputs())


def validate(payload, expected=None):
    expected = build() if expected is None else expected
    if not same(payload, expected):
        raise ValueError('Clark County normalized extract differs from pinned source/model evidence, scope or selection policy')
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
    if (len(schools['schools']) != 289 or len(history['records']) != 289
            or set(exported) != set(profiles) or set(records) != set(profiles)):
        raise ValueError('Clark County exported native source directory/history identities differ from selection')
    if set(schools['models']) != {'ES'} or set(schools['models']['ES']) != set(model_audit.SUBJECTS):
        raise ValueError('Clark County export requires only the three independently audited ES models')
    expected_keys = {(2025, 'ES', model_audit.ASSESSMENT, m['subject']) for m in numerical['models']}
    for summaries in [schools['history_models'], history['models']]:
        keyed = {(m['year'], m['level'], m['assessment'], m['subject']): m for m in summaries}
        if len(summaries) != 3 or len(keyed) != 3 or set(keyed) != expected_keys:
            raise ValueError('Clark County history must retain exactly three audited ES model populations')
        if any(not same(summary, schools['models']['ES'][key[3]]) for key, summary in keyed.items()):
            raise ValueError('Clark County historical model summaries differ from current district fits')
    for model in numerical['models']:
        subject = model['subject']
        actual_model = schools['models']['ES'][subject]
        expected_model = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                              assessed_schools=289, excluded_schools=3, **model['coefficients'])
        if not model_audit.numeric_equal(actual_model, expected_model):
            raise ValueError('Clark County exported district coefficients/coverage differ from numerical audit')
        reference = {r['school_id']: r for r in model['results']}
        eligible = {s['id'] for s in schools['schools'] if subject in s['metrics']}
        if eligible != set(reference):
            raise ValueError('Clark County exported subject membership differs from passed district audit')
        for key, result in reference.items():
            fields = ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'leverage']
            metric = exported[key]['metrics'][subject]
            expected_metric = {k: result[k] for k in fields} | dict(tested=None, cohort_n=286)
            exact = ['actual', 'tested', 'low', 'high', 'cohort_n']
            if (not same({k: metric.get(k) for k in exact}, {k: expected_metric[k] for k in exact})
                    or not model_audit.numeric_equal(metric, expected_metric)
                    or not same(metric, records[key]['subjects'][subject])):
                raise ValueError('Clark County per-school point-only metric differs from verified district fit')
    for key, school in exported.items():
        profile = profiles[key]
        record = records[key]
        expected_exclusions = {s: profile['outcomes'][s]['exclusion'] for s in ['math', 'reading']
                               if profile['outcomes'][s]['exclusion'] is not None}
        if expected_exclusions:
            expected_exclusions['combined'] = '; '.join(
                ('Math' if s == 'math' else 'ELA') + ': ' + expected_exclusions[s]
                for s in ['math', 'reading'] if s in expected_exclusions)
        profile_fields = dict(level='ES', name=profile['name'], short=profile['name'],
            district=profile['district'], income=profile['income'], enrollment=float(profile['enrollment']),
            city=profile['city'], county=profile['county'], latitude=None, longitude=None,
            program='Unclassified', programs=['Unclassified'], exclusions=expected_exclusions)
        record_fields = dict(level='ES', year=2025, income_year=2025,
            assessment=model_audit.ASSESSMENT, name=profile['name'], income=profile['income'],
            enrollment=float(profile['enrollment']), income_label=payload['income_definition']['label'],
            exclusions=expected_exclusions)
        if (not same({k: school.get(k) for k in profile_fields}, profile_fields)
                or not same({k: record.get(k) for k in record_fields}, record_fields)
                or not same(school['history'], [record])):
            raise ValueError('Clark County profile/history/exclusion/geography evidence changed')
    expected_coverage = {'grade': {'directory': 289, 'eligible': {s: 286 for s in model_audit.SUBJECTS}}}
    if not same(coverage, dict(year=2025, schools=289, cohorts=expected_coverage,
            source_audit=payload['source_audit'], exclusions=dict(Counter(
                reason for r in records.values() for reason in r['exclusions'].values())))):
        raise ValueError('Clark County exported coverage/source exclusions differ from approved selection')
    cohort = payload['cohorts'][0]
    expected_levels = {'ES': dict(year=2025, label=cohort['label'], assessment=cohort['assessment'],
                                  outcome=cohort['outcome'], math_label='Math', note=cohort['note'])}
    header = dict(year=payload['academic_year'], assessment_year=2025,
        income_label=payload['income_definition']['label'], program_options=['Unclassified'],
        levels=expected_levels, history_years=[2025], coverage_note=payload['coverage_note'],
        methodology=payload['methodology'])
    if not same({k: schools.get(k) for k in header}, header):
        raise ValueError('Clark County exported native assessment definition or methodology changed')
    expected_descriptor = dict(schema_version=1, state=payload['state'], prepare_script=payload['prepare_script'],
        regions=[dict(id='clark-county', geography='clark-county', name='Clark County', dataset=DATASET,
            statewide=False, status='ready', levels=['ES'], boundaries=None, comparison=payload['comparison'],
            audit=str((output / 'coverage.json').relative_to(ROOT)),
            schools=str((output / 'schools.json').relative_to(ROOT)),
            model_scope=payload['model_scope'], map_source=payload['map_source'])])
    if not same(descriptor, expected_descriptor):
        raise ValueError('Clark County ready descriptor must retain distinct district and point-only scope')
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
