"""Replay Wake County's native point-only district fits without importing or publishing."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

import audit_wake as roster_audit
from prepare_data import fit_model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/source/wake-model-audit.json'
ROSTER = roster_audit.OUTPUT
ROSTER_SHA = '6416cc99800e45e1b1f405bf62e065e12faec35924155640732827ed90b7b3b2'
ROSTER_BYTES = 4369154
SOURCE_CODE = ROOT / 'scripts/audit_wake.py'
SOURCE_CODE_SHA = '1371ef8965e0c0468cdcc9f44d0e2c1c91f51ec68909725bb19fab19ad486190'
MIN_SCHOOLS = 30
ABS_TOLERANCE = 2e-10
REL_TOLERANCE = 2e-10
VERIFY_TOLERANCE = 2e-9
SUBJECTS = ['math', 'reading', 'combined']
ASSESSMENT = roster_audit.north_carolina.ASSESSMENT
STANDARD = 'Published native regular RG/GS/ALL grade-level proficient (GLP Level3 and above); grades3–8 including grade8 NC Math1 EOC; separate Wake grade-school population'
POLICY = {
    'roster': roster_audit.POLICY['roster'],
    'identity': roster_audit.POLICY['identity'],
    'populations': roster_audit.POLICY['population'],
    'native_eligibility': 'Independently recompute162 pure CCD grade-school configurations, two suppressed AprilEDS income exclusions,160 native source profiles and159Math/160ELA/159Combined from frozen original records. MillsParkMiddle Math>95 excludes only Math/Combined; preserve every source mask and all high/mixed/future/aggregate records. Source counts, enrollment and fit diagnostics never screen eligibility.',
    'income': roster_audit.POLICY['income'],
    'economic_denominator': roster_audit.POLICY['denominator'],
    'assessment': roster_audit.POLICY['assessment'],
    'native_definition_limits': roster_audit.POLICY['native_definition_limits'],
    'eds_definition_limits': roster_audit.POLICY['eds_definition_limits'],
    'federal_denominator': roster_audit.POLICY['federal_denominator'],
    'suppression': roster_audit.POLICY['suppression'],
    'models': 'Separate unweighted2024–25 Wake grade-school Math, ELA and Combined district OLS; no statewide residual reuse, enrollment weights, pooling or grade-percentage averaging. Combined requires both original published subject rates and has its own eligible population, fit and external studentization.',
    'minimum_usable_subject_schools': MIN_SCHOOLS,
    'studentization': 'Externally studentized residuals use deleted-school residual scale with N−3 degrees of freedom. Explicitly refit every eligible school omission, independently verifying the shared analytic formula.',
    'counts': roster_audit.POLICY['counts'],
    'intervals': 'Point estimates only: valid-score counts, sampling variances and all interval endpoints are null for the entire model. Native num_tested is raw unverified evidence and the ten-valid-scored minimum remains uncertified. An internal zero variance vector is a computational sentinel, never an uncertainty estimate.',
    'combined': roster_audit.POLICY['combined'],
    'release': 'Numerically verified audit only; source and modeling approvals remain false pending separate review and canonical/browser integration. No high, mixed, future or aggregate model is fitted or approved.',
}


def load_roster(path=ROSTER):
    if hashlib.sha256(SOURCE_CODE.read_bytes()).hexdigest() != SOURCE_CODE_SHA:
        raise ValueError('Frozen Wake source code/policy changed; fresh numerical audit required')
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != ROSTER_SHA or len(data) != ROSTER_BYTES:
        raise ValueError('Frozen complete Wake source artifact changed; fresh numerical audit required')
    document = json.loads(data)
    roster_audit.validate(document)
    return document


def require_frozen_roster(roster):
    if roster_audit.fingerprint(roster) != roster_audit.fingerprint(load_roster()):
        raise ValueError('In-memory Wake source evidence differs from the complete frozen artifact')


def frozen_population(roster):
    return dict(complete_directory_ncessch=sorted(e['raw']['NCESSCH'] for e in roster['raw_inputs']['directory']['records']),
        operational_roster_school_ids=sorted(r['school_id'] for r in roster['roster_links']),
        grade_school_configuration_ids=sorted(roster['cohorts']['ccd_grade_school_configurations']['school_ids']),
        native_source_profile_ids=sorted(roster['cohorts']['native_grade_school_source_profiles']['school_ids']),
        eligible_school_ids_by_subject={s: sorted(roster['cohorts']['native_grade_school_source_profiles']['subjects'][s]['eligible_school_ids']) for s in SUBJECTS},
        high_school_configuration_ids=sorted(roster['cohorts']['high_school_configurations']['school_ids']),
        mixed_configuration_ids=sorted(roster['cohorts']['mixed_configurations']['school_ids']),
        nonoperational_school_ids=sorted(r['school_id'] for r in roster['nonoperational_directory']),
        native_aggregate_codes=sorted({e['raw']['school_code'] for e in roster['outside_directory_records']['assessment']}))


def selected_inputs(roster, subject):
    """Select source eligibility from exact raw records before numerical work."""
    if subject not in SUBJECTS:
        raise ValueError('Only Math, ELA and Combined grade-school subjects are supported')
    require_frozen_roster(roster)
    raw = roster['raw_inputs']
    directory = {roster_audit.ccd_identity(e['raw']): e for e in raw['directory']['records']}
    incomes = {roster_audit.native_identity(e['raw'], income=True): e for e in raw['income']['records']}
    totals, grades, native = {}, {}, {}
    for entry in raw['membership']['records']:
        key = roster_audit.ccd_identity(entry['raw'])
        if entry['raw']['TOTAL_INDICATOR'] == 'Education Unit Total':
            totals[key] = entry
        else:
            grades.setdefault(key, {})[entry['raw']['GRADE']] = entry
    for entry in raw['assessment']['records']:
        row = entry['raw']; key = roster_audit.native_identity(row)
        if (row['subgroup'], row['type'], row['grade']) == ('ALL', 'RG', 'GS') and row['subject'] in {'MA', 'RD'}:
            native.setdefault(key, {})['math' if row['subject'] == 'MA' else 'reading'] = entry
    inputs, exclusions, configurations = [], [], []
    for link in sorted(roster['roster_links'], key=lambda r: r['school_id']):
        key = link['school_id']; profile = directory[key]['raw']
        grade_raw = {g: e['raw'] for g, e in grades.get(key, {}).items()}
        total = None if key not in totals else totals[key]['raw']
        configuration = roster_audit.grade_school_contract(profile, total, grade_raw)
        if not configuration:
            continue
        configurations.append(link)
        eds_entry = incomes.get(key); eds_raw = None if eds_entry is None else eds_entry['raw']
        income_pct = None if eds_raw is None else roster_audit.north_carolina.exact_percent(eds_raw['pct_eds'])
        april_enrollment = None if eds_raw is None else roster_audit.north_carolina.exact_enrollment(eds_raw['den'])
        outcomes = native.get(key, {})
        rates = {s: None if s not in outcomes else roster_audit.north_carolina.exact_percent(outcomes[s]['raw']['pct_glp']) for s in ['math', 'reading']}
        pair_compatible = (set(outcomes) == {'math', 'reading'} and
                           all(roster_audit.north_carolina.native_grade_school(e['raw']) for e in outcomes.values()))
        source_usable = (profile['UPDATED_STATUS'] in roster_audit.OPERATIONAL and pair_compatible and income_pct is not None
                         and april_enrollment is not None and any(profile['G_' + str(g) + '_OFFERED'] == 'Yes' for g in range(3, 9)))
        usable = source_usable and (all(v is not None for v in rates.values()) if subject == 'combined' else rates[subject] is not None)
        if usable is not link['subjects'][subject]['usable']:
            raise ValueError('Independent original-record eligibility differs from frozen Wake source audit')
        if not usable:
            exclusions.append(link)
            continue
        outcome_pct = (rates['math'] + rates['reading']) / 2 if subject == 'combined' else rates[subject]
        if income_pct != link['income']['percentage'] or outcome_pct != link['subjects'][subject]['native_rate']:
            raise ValueError('Independent original rates/income differ from frozen source values')
        inputs.append(dict(school_id=key, ncessch=profile['NCESSCH'], name=profile['SCH_NAME'], native_school_id=profile['ST_SCHID'],
            level='ES', charter=profile['CHARTER_TEXT'], ccd_school_type=profile['SCH_TYPE_TEXT'],
            income_pct=income_pct, income_year=2025, academic_year='2024-2025', april_enrollment=april_enrollment,
            outcome_pct=outcome_pct, outcome_by_subject=rates,
            valid_scores_by_subject={'math': None, 'reading': None}, display_valid_scores=None, sampling_variance=None,
            ten_valid_scored_floor_certified=False,
            sources=dict(directory=directory[key], directory_raw=profile, april_income=eds_entry,
                native_assessments=outcomes, membership_total=totals.get(key), membership_grades=[e for _, e in sorted(grades[key].items())],
                offered_evidence=link['offered'], enrolled_evidence=link['enrolled'], income_evidence=link['income'],
                subject_evidence=link['subjects'], april_minus_fall_enrollment=link['april_minus_fall_enrollment'])))
    expected_ids = sorted(roster['cohorts']['native_grade_school_source_profiles']['subjects'][subject]['eligible_school_ids'])
    if [r['school_id'] for r in inputs] != expected_ids:
        raise ValueError('Complete independent subject population differs from frozen source membership')
    coverage = dict(grade_school_configuration_profiles=len(configurations), native_source_profiles=160,
        native_applicable_profiles=sum(r['subjects'][subject]['applicable'] for r in configurations), usable_schools=len(inputs),
        excluded_configuration_profiles=len(exclusions),
        exclusions=dict(sorted(Counter(r['subjects'][subject]['exclusion'] for r in exclusions).items())),
        excluded_configuration_records=exclusions,
        outside_grade_school_configuration_records=[r for r in roster['roster_links'] if r not in configurations],
        nonoperational_directory=roster['nonoperational_directory'],
        charter=dict(sorted(Counter(r['charter'] for r in inputs).items())),
        school_types=dict(sorted(Counter(r['ccd_school_type'] for r in inputs).items())),
        eligible_members_with_verified_denominators=0, ten_valid_scored_floor_certified=False,
        model_sampling_intervals_available=False)
    return inputs, coverage


def verify_independently(x, y, model, results):
    """Centered full OLS, independent leverage and explicit held-out refits; no intervals."""
    n = len(x)
    if (n < MIN_SCHOOLS or x.shape != y.shape or x.ndim != 1
            or not np.isfinite(x).all() or not np.isfinite(y).all()):
        raise ValueError('Independent verification requires finite complete percentage vectors')
    def finite_number(value):
        return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)

    if (type(model.get('n')) is not int or model['n'] != n or len(results) != n
            or any(not finite_number(model.get(k)) for k in ['intercept', 'slope', 'r2'])
            or any(not finite_number(r.get(k)) for r in results
                   for k in ['actual', 'predicted', 'residual', 'leverage', 'studentized'])
            or any(not 0 <= r['leverage'] < 1 for r in results)):
        raise ValueError('Independent verification requires finite returned coefficients/results and exact model count')
    centered = x - x.mean()
    spread = centered @ centered
    h = 1 / n + centered ** 2 / spread
    design = np.column_stack([np.ones(n), centered])
    beta = np.linalg.lstsq(design, y, rcond=None)[0]
    predicted = design @ beta
    residual = y - predicted
    sse = float(residual @ residual)
    full_tolerance = 64 * np.finfo(float).eps * max(1., np.linalg.cond(design)) * max(np.linalg.norm(y), np.linalg.norm(predicted))
    if np.linalg.matrix_rank(design) != 2 or not math.isfinite(sse) or np.linalg.norm(residual) <= full_tolerance:
        raise ValueError('Independent full design/positive residual scale is unavailable')
    r2 = 1 - sse / ((y - y.mean()) @ (y - y.mean()))
    if [r['actual'] for r in results] != y.tolist():
        raise ValueError('Independent verification requires exact native actual proficiency')
    if any(r['low'] is not None or r['high'] is not None for r in results):
        raise ValueError('Point-only audit cannot expose numerical interval endpoints')
    errors = {
        'coefficient': max(abs(float(beta[0] - beta[1] * x.mean()) - model['intercept']),
                           abs(float(beta[1]) - model['slope'])),
        'predicted': max(abs(float(v) - r['predicted']) for v, r in zip(predicted, results)),
        'residual': max(abs(float(v) - r['residual']) for v, r in zip(residual, results)),
        'r2': abs(float(r2) - model['r2']), 'leverage': 0., 'studentized': 0.,
        'deleted_sse_identity': 0., 'held_out_prediction_identity': 0.,
        'interval_endpoint': None,
    }
    deleted = []
    for i in range(n):
        keep = np.arange(n) != i
        mean_x = x[keep].mean()
        deleted_centered = x[keep] - mean_x
        X = np.column_stack([np.ones(n - 1), deleted_centered])
        if np.linalg.matrix_rank(X) != 2:
            raise ValueError('Explicit deleted-school income design is rank deficient')
        b = np.linalg.lstsq(X, y[keep], rcond=None)[0]
        e = y[keep] - X @ b
        deleted_sse = float(e @ e)
        residual_tolerance = 64 * np.finfo(float).eps * max(1., np.linalg.cond(X)) * max(
            np.linalg.norm(y[keep]), np.linalg.norm(X @ b))
        if not math.isfinite(deleted_sse) or np.linalg.norm(e) <= residual_tolerance:
            raise ValueError('Explicit deleted-school residual scale is unavailable or numerically unresolved')
        held_out = float(b[0] + b[1] * (x[i] - mean_x))
        predictive_h = 1 / (n - 1) + (x[i] - mean_x) ** 2 / (deleted_centered @ deleted_centered)
        scale = math.sqrt(deleted_sse / (n - 3))
        external_t = (y[i] - held_out) / (scale * math.sqrt(1 + predictive_h))
        errors['studentized'] = max(errors['studentized'], abs(external_t - results[i]['studentized']))
        errors['leverage'] = max(errors['leverage'], abs(h[i] - results[i]['leverage']))
        errors['deleted_sse_identity'] = max(errors['deleted_sse_identity'],
                                             abs(deleted_sse - (sse - residual[i] ** 2 / (1 - h[i]))))
        errors['held_out_prediction_identity'] = max(errors['held_out_prediction_identity'],
                                                      abs(held_out - (predicted[i] - h[i] * residual[i] / (1 - h[i]))))
        deleted.append({'intercept': float(b[0] - b[1] * mean_x), 'slope': float(b[1]),
                        'sse': deleted_sse, 'held_out_prediction': held_out,
                        'held_out_prediction_leverage': float(predictive_h),
                        'residual_scale': scale, 'externally_studentized': float(external_t)})
    if any(v is not None and (not math.isfinite(v) or v > VERIFY_TOLERANCE) for v in errors.values()):
        raise ValueError('Independent full/deleted-fit verification exceeded tolerance')
    # JSON preserves Python float/int/bool types but not NumPy scalar classes.
    # Normalize computed errors before strict typed replay; native evidence is
    # never coerced and booleans remain invalid numerical substitutions.
    return deleted, {k: None if v is None else float(v) for k, v in errors.items()}




def fit_audited_model(inputs, coverage, subject):
    if subject not in SUBJECTS:
        raise ValueError('Only three proposed grade-school subjects may be audited')
    if not isinstance(inputs, list) or any(not isinstance(r, dict) for r in inputs):
        raise ValueError('District inputs require original frozen native records')
    if len(inputs) < MIN_SCHOOLS:
        raise ValueError('District subject model requires at least 30 usable schools')
    frozen_inputs, frozen_coverage = selected_inputs(load_roster(), subject)
    if ([r.get('school_id') for r in inputs] != [r['school_id'] for r in frozen_inputs]
            or roster_audit.fingerprint(inputs) != roster_audit.fingerprint(frozen_inputs)
            or roster_audit.fingerprint(coverage) != roster_audit.fingerprint(frozen_coverage)):
        raise ValueError('District fit requires exact frozen native inputs, complete eligible membership and coverage')
    if (len({r['school_id'] for r in inputs}) != len(inputs) or len({r['ncessch'] for r in inputs}) != len(inputs)
            or any(r['level'] != 'ES' or type(r['income_year']) is not int or r['income_year'] != 2025
                   or r['academic_year'] != '2024-2025' or not re.fullmatch(r'920\d{3}', r['school_id'])
                   or not re.fullmatch(roster_audit.LEA + r'\d{5}', r['ncessch'])
                   or roster_audit.ccd_identity(r['sources']['directory_raw'], directory=True) != r['school_id']
                   or r['sources']['directory_raw']['NCESSCH'] != r['ncessch']
                   or r['sources']['directory_raw']['UPDATED_STATUS'] not in roster_audit.OPERATIONAL
                   or roster_audit.native_identity(r['sources']['april_income']['raw'], income=True) != r['school_id']
                   or r['sources']['income_evidence']['exclusion'] is not None
                   or not r['sources']['enrolled_evidence']['native_grade_school_contract']
                   or r['ten_valid_scored_floor_certified'] is not False
                   for r in inputs)):
        raise ValueError('District members require exact same-year native pure grade-school identities and income')
    if any(r['sampling_variance'] is not None or r['display_valid_scores'] is not None
           or r['valid_scores_by_subject'] != {'math': None, 'reading': None} for r in inputs):
        raise ValueError('Point-only source contract prohibits fabricated counts or sampling variance')
    if subject == 'combined' and any(r['outcome_pct'] != (r['outcome_by_subject']['math'] + r['outcome_by_subject']['reading']) / 2 for r in inputs):
        raise ValueError('Combined must be the exact equally weighted subject mean')
    if any(isinstance(r[k], bool) or not isinstance(r[k], (int, float)) for r in inputs for k in ['income_pct', 'outcome_pct']):
        raise ValueError('District income and proficiency require numeric percentage values, never booleans')
    x = np.array([r['income_pct'] for r in inputs], dtype=float)
    y = np.array([r['outcome_pct'] for r in inputs], dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any((x < 0) | (x > 100) | (y < 0) | (y > 100)):
        raise ValueError('District income and proficiency must be finite percentages')
    design = np.column_stack([np.ones(len(x)), x])
    rank = int(np.linalg.matrix_rank(design))
    if rank != 2:
        raise ValueError('District income design must have rank two')
    # fit_model requires a variance vector. This zero vector is only its point-estimate
    # computational sentinel; no zero sampling variances or generated endpoints survive.
    model, fitted = fit_model(x, y, np.zeros(len(inputs), dtype=float))
    for row in fitted:
        row.update(low=None, high=None)
    deleted, errors = verify_independently(x, y, model, fitted)
    residual = np.array([r['residual'] for r in fitted])
    sse = float(residual @ residual)
    s2 = sse / (len(x) - 2)
    results = []
    thresholds = {'leverage_2p_over_n': 4 / len(x), 'cooks_4_over_n': 4 / len(x),
                  'absolute_external_t': 2.}
    for school, row, deletion in zip(inputs, fitted, deleted):
        h = row['leverage']
        cook = row['residual'] ** 2 * h / (2 * s2 * (1 - h) ** 2)
        endpoints = np.array([x.min(), x.max()])
        shift = (deletion['intercept'] - model['intercept']) + (deletion['slope'] - model['slope']) * endpoints
        results.append({
            'school_id': school['school_id'], **row, 'valid_scores': None, 'sampling_variance': None,
            'cooks_distance': float(cook), 'deleted_intercept': deletion['intercept'],
            'deleted_slope': deletion['slope'], 'deleted_sse': deletion['sse'],
            'deleted_residual_scale': deletion['residual_scale'],
            'deleted_held_out_prediction': deletion['held_out_prediction'],
            'deleted_held_out_prediction_leverage': deletion['held_out_prediction_leverage'],
            'maximum_prediction_change_on_observed_income_range': float(np.max(np.abs(shift))),
            'review_flags': {'leverage_above_2p_over_n': h > thresholds['leverage_2p_over_n'],
                             'cooks_above_4_over_n': cook > thresholds['cooks_4_over_n'],
                             'absolute_external_t_above_2': abs(row['studentized']) > 2},
        })
    by_id = {r['school_id']: r for r in inputs}
    influence = []
    for row in sorted(results, key=lambda r: (-r['cooks_distance'], r['school_id']))[:10]:
        school = by_id[row['school_id']]
        influence.append({k: school[k] for k in ['school_id', 'name', 'charter', 'ccd_school_type', 'income_pct']} |
                         {k: row[k] for k in ['cooks_distance', 'leverage', 'studentized']})
    return {
        'model_id': f'wake-2025-ES-{subject}', 'status': 'numerically_verified_pending_integration',
        'approved_for_source': False, 'approved_for_modeling': False, 'valid_score_floor_certified': False, 'year': 2025, 'academic_year': '2024-2025',
        'population': 'Exact Wake attached-LEA pure grade-school population; native April2025 individualEDS and published RG/GS/ALL grades3–8 Math/ELA GLP including grade8 Math1',
        'level': 'ES', 'subject': subject, 'assessment': ASSESSMENT,
        'assessment_standard': STANDARD,
        'coverage': coverage, 'inputs': inputs,
        'population_sha256': roster_audit.fingerprint({'policy': POLICY, 'source_audit_sha256': ROSTER_SHA,
                                                      'level': 'ES', 'subject': subject, 'year': 2025,
                                                      'school_ids': [r['school_id'] for r in inputs]}),
        'coefficients': model, 'results': results,
        'review_warnings': [
            'Valid-score denominators remain unverified; no count, sampling variance or interval is available.',
            'Conventional leverage, Cook distance and residual flags require descriptive review, never automatic exclusions.',
            'Native April individualEDS covers all enrolled school grades, broader than tested children; regular GS includes grade8 Math1 and published precision/suppression remain limits. Native num_tested and the ten-valid-scored floor remain unverified.',
        ],
        'intervals': {'available_for_entire_model': False, 'eligible_members': len(inputs),
                      'eligible_members_with_verified_denominators': 0,
                      'valid_score_counts': None, 'sampling_variances': None, 'ten_valid_scored_floor_certified': False,
                      'reason': 'Native NC num_tested valid-score scope and the ten-valid-scored minimum remain uncertified; published RG/GS/ALL GLP rates support this point-only numerical audit without certified counts or intervals.'},
        'diagnostics': {
            'income_design_rank': rank, 'income_design_condition_number': float(np.linalg.cond(design)),
            'centered_income_design_condition_number': float(np.linalg.cond(np.column_stack([np.ones(len(x)), x - x.mean()]))),
            'income': {'minimum': float(x.min()), 'maximum': float(x.max()), 'mean': float(x.mean()),
                       'standard_deviation_population': float(x.std()), 'distinct': len(set(x.tolist())),
                       'quantiles': {str(q): float(np.quantile(x, q)) for q in [.05, .25, .5, .75, .95]}},
            'residual_sse': sse, 'residual_standard_error': float(math.sqrt(s2)),
            'full_residual_degrees_of_freedom': len(x) - 2,
            'deleted_residual_degrees_of_freedom': len(x) - 3,
            'minimum_deleted_sse': min(r['sse'] for r in deleted),
            'minimum_deleted_residual_scale': min(r['residual_scale'] for r in deleted),
            'maximum_leverage': max(r['leverage'] for r in results),
            'maximum_absolute_studentized_residual': max(abs(r['studentized']) for r in results),
            'maximum_cooks_distance': max(r['cooks_distance'] for r in results),
            'maximum_absolute_deleted_slope_change': max(abs(r['slope'] - model['slope']) for r in deleted),
            'deleted_slope_range': {'minimum': min(r['slope'] for r in deleted), 'maximum': max(r['slope'] for r in deleted)},
            'maximum_prediction_change_on_observed_income_range': max(r['maximum_prediction_change_on_observed_income_range'] for r in results),
            'conventional_review_thresholds': thresholds,
            'conventional_review_flag_counts': {key: sum(r['review_flags'][key] for r in results) for key in results[0]['review_flags']},
            'top_ten_cooks_distance': influence,
            'interpretation': 'Descriptive influence flags only; no school is excluded by leverage, residual or fit quality. Published GLP precision, broader April individualEDS, grade8 Math1 and other grade/course mixtures, unverified native num_tested and uncertified ten-valid-scored minimum remain limitations.',
        },
        'independent_verification': {'full_income_design_rank': rank, 'full_residual_degrees_of_freedom': len(inputs) - 2,
                                     'explicit_deleted_fits': len(inputs), 'deleted_training_members': len(inputs) - 1,
                                     'deleted_residual_degrees_of_freedom': len(inputs) - 3, 'tolerance_absolute': VERIFY_TOLERANCE,
                                     'maximum_absolute_errors': errors,
                                     'method': 'Centered full OLS; centered closed-form leverage; every explicit leave-one-out fit uses N−3 scale and held-out variance factor 1+h_deleted. Interval verification is inapplicable because all verified valid-score denominators are unavailable; April economic enrollment, fall CCD grade membership and original num_tested remain raw provenance, never certified assessment denominators or a scored-count-floor certificate.'},
    }


def build(roster=None):
    roster = load_roster() if roster is None else roster
    require_frozen_roster(roster)
    models, holds = [], []
    for subject in SUBJECTS:
        inputs, coverage = selected_inputs(roster, subject)
        try:
            model = fit_audited_model(inputs, coverage, subject)
        except ValueError as error:
            model = dict(model_id=f'wake-2025-ES-{subject}', status='numerical_hold', approved_for_source=False,
                         approved_for_modeling=False, level='ES', subject=subject, inputs=inputs, coverage=coverage, reason=str(error))
            holds.append(dict(model_id=model['model_id'], reason=str(error)))
        models.append(model)
    population = frozen_population(roster)
    return dict(schema_version=1, state='NC', year=2025, academic_year='2024-2025', nces_lea_id=roster_audit.LEA,
        native_lea_id=roster_audit.NATIVE_LEA, scope='numerical_audit_only',
        status='numerical_hold' if holds else 'numerically_verified_pending_integration',
        approved_for_source=False, approved_for_modeling=False, policy=POLICY,
        count_definition_status=dict(status='unverified', raw_field='num_tested', valid_score_counts=None,
            sampling_variances=None, sampling_intervals_available=False, ten_valid_scored_floor_certified=False,
            reason='Completed-test source description does not independently certify exact valid-score num_tested denominators or the ten-valid-scored floor.'),
        sources=dict(roster_audit=dict(path='data/source/wake-district-audit.json', sha256=ROSTER_SHA, bytes=ROSTER_BYTES),
                     source_audit_code=dict(path='scripts/audit_wake.py', sha256=SOURCE_CODE_SHA),
                     state_extract=roster['state_extract'], native_sources=roster['sources']),
        frozen_population=population, frozen_population_sha256=roster_audit.fingerprint(dict(policy=POLICY, population=population)),
        source_coverage=roster['coverage'],
        retained_source_evidence=dict(raw_inputs=roster['raw_inputs'], state_extract=roster['state_extract'], source_policy=roster['policy'],
            source_scope=roster['scope'], source_status=roster['status'],
            source_approval=dict(approved_for_source=roster['approved_for_source'], approved_for_modeling=roster['approved_for_modeling']),
            source_definition_evidence=roster['source_definition_evidence'], planning_identity_reconciliation=roster['planning_identity_reconciliation'],
            historical_state_source_approval=roster['historical_state_source_approval']),
        retained_scope_exclusions=dict(source_cohorts=roster['cohorts'],
            outside_grade_school_configuration_records=[r for r in roster['roster_links'] if not r['enrolled']['native_grade_school_contract']],
            nonoperational_directory=roster['nonoperational_directory'], outside_directory_records=roster['outside_directory_records']),
        replay_tolerance=dict(absolute=ABS_TOLERANCE, relative=REL_TOLERANCE,
            scope='Computed finite floating-point metrics only, with strict numeric types. All source evidence, identity, raw/published outcomes, income, membership, counts, approvals and interval absence compare exactly.'),
        models=models, hard_holds=holds)


def numeric_equal(actual, expected):
    if type(expected) is float:
        return type(actual) is float and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=REL_TOLERANCE, abs_tol=ABS_TOLERANCE)
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(numeric_equal(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(numeric_equal(a, e) for a, e in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def validate(document, expected=None):
    expected = build() if expected is None else expected
    if not isinstance(document, dict) or roster_audit.fingerprint({k: v for k, v in document.items() if k != 'models'}) != roster_audit.fingerprint({k: v for k, v in expected.items() if k != 'models'}):
        raise ValueError('Wake numerical audit metadata/source evidence changed')
    if not isinstance(document.get('models'), list) or len(document['models']) != len(expected['models']):
        raise ValueError('Wake numerical audit model set changed')
    for actual, model in zip(document['models'], expected['models']):
        if not isinstance(actual, dict):
            raise ValueError('Wake model requires exact typed numerical/source fields')
        for field in ['model_id', 'level', 'subject', 'status', 'approved_for_source', 'approved_for_modeling',
                      'valid_score_floor_certified', 'year', 'academic_year', 'population', 'assessment', 'assessment_standard',
                      'review_warnings', 'coverage', 'inputs', 'population_sha256', 'intervals']:
            if field in model and roster_audit.fingerprint(actual.get(field)) != roster_audit.fingerprint(model[field]):
                raise ValueError('Wake numerical audit source identities, counts, approvals or population changed')
        if 'independent_verification' in model:
            metadata = lambda v: {k: value for k, value in v.items() if k != 'maximum_absolute_errors'}
            if roster_audit.fingerprint(metadata(actual.get('independent_verification', {}))) != roster_audit.fingerprint(metadata(model['independent_verification'])):
                raise ValueError('Wake independent verification metadata/tolerance changed')
        if 'results' in model:
            exact = ['school_id', 'actual', 'valid_scores', 'sampling_variance', 'low', 'high']
            if roster_audit.fingerprint([{k: r.get(k) for k in exact} for r in actual.get('results', [])]) != roster_audit.fingerprint([{k: r[k] for k in exact} for r in model['results']]):
                raise ValueError('Wake result identities/native outcomes/counts or interval absence changed')
        if not numeric_equal(actual, model):
            raise ValueError('Wake numerical metrics failed independent typed/finite replay tolerance')
    return {m['model_id']: m['coverage']['usable_schools'] for m in expected['models']}


def prepare(output=OUTPUT, check=False):
    expected = build()
    if check:
        validate(json.loads(Path(output).read_text()), expected)
    else:
        Path(output).write_text(json.dumps(expected, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return dict(models={m['model_id']: m['coverage']['usable_schools'] for m in expected['models']}, hard_holds=expected['hard_holds'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Recompute and validate saved audit without rewriting it')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.check), sort_keys=True))
