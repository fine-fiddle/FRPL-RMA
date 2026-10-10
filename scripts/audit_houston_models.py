"""Audit Houston's explicit published-display-rate-only fits; never import or publish."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

import audit_houston as roster_audit
from prepare_data import fit_model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/source/houston-model-audit.json'
ROSTER = roster_audit.OUTPUT
ROSTER_SHA = '5d8855dff069fed410ea3d3bd5981ced90849b2122c039c8494408c4136e2e4d'
ROSTER_BYTES = 5210877
MIN_SCHOOLS = 30
ABS_TOLERANCE = 2e-10
REL_TOLERANCE = 2e-10
VERIFY_TOLERANCE = 2e-9
SUBJECTS = ['math', 'reading', 'combined']
ASSESSMENT = 'STAAR enrolled grades 3–8 Including EOC · TAPR published Meets or Above percentages'
STANDARD = '2024–25 Texas All Students accountability subset; STAAR with/without accommodations, Spanish STAAR, Alternate 2 and applicable Algebra I/English I–II EOC; separate Houston no-high-grade population'
COUNT_HOLD = {
    'issue_number': 16,
    'url': 'https://github.com/robot-assisted-projects/FRPL-RMA/issues/16',
    'status': 'unresolved_exact_2025_N_M_performance_score_status_mapping',
    'ten_valid_scored_floor_certified': False,
    'numerical_success_resolves_hold': False,
    'reason': 'Native reported #Tests and source masking for 1–4 do not certify ten valid scored tests. The exact current-year N/NAAR and M/medical exemption mapping remains unresolved.',
}
POLICY = {
    'identity': roster_audit.POLICY['identity'],
    'population': roster_audit.POLICY['population'],
    'income': roster_audit.POLICY['income'],
    'income_limits': roster_audit.POLICY['income_limits'],
    'assessment': roster_audit.POLICY['assessment'],
    'published_rate_eligibility': 'Separate explicit unknown-valid-count numerical audit: exact operational same-year school identity, fully reconciled native enrolled positive grades 3–8 and zero grades 9–12, reconciled individual economic-status income, and the unmasked native whole-percent subject R cell. Do not select on reported #Tests, numerator/count ratios, source_usable, native_fields_usable, prospective count screens, charter/type labels or fit diagnostics. Combined requires both subject displays. This policy does not certify or satisfy the previous source audit ten-valid-scored contract.',
    'outcome': 'Use only the original published whole-percent CDA38AM0E225R / CDA38AR0E225R values. Do not reconstruct missing/masked displays from visible native counts and do not substitute the more precise count-derived source-audit proficiency. A published zero is valid; missing/masked is unavailable, never zero.',
    'combined': 'Exact equally weighted arithmetic mean of available published Math and ELA whole percentages, never count-weighted, an average of grade rates or the native percentage passing both.',
    'counts': 'All verified valid-score counts, sampling variances and interval endpoints remain null. Reported #Tests and #Meets-or-above remain complete unresolved raw provenance, are not passed to model fitting, and never establish the ten-valid-scored floor. Open issue #16 remains unresolved.',
    'models': 'Separate 2024–25 Houston ES Math, ELA and Combined district OLS; no statewide residual reuse or pooled national ranking.',
    'minimum_usable_subject_schools': MIN_SCHOOLS,
    'studentization': 'Externally studentized residuals use deleted-school residual scale with N−3 degrees of freedom. Every school is independently refitted after deletion.',
    'intervals': 'Point estimates only, unavailable modelwide. An internal all-zero variance vector is a computational sentinel for the existing fitter, never a zero-uncertainty estimate; all generated endpoints are discarded.',
    'release': 'Numerical audit only, pending separate integration review. Original source audit remains immutable with source/model approval false. This artifact source/model approval is also false. Numerical success does not release a comparison, resolve #16, approve a ten-valid-scored cohort, import SQLite or alter any served data. High/mixed, primary-only and native gaps remain outside these models.',
}


def load_roster(path=ROSTER):
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != ROSTER_SHA or len(content) != ROSTER_BYTES:
        raise ValueError('Houston source audit fingerprint changed; re-audit the population')
    document = json.loads(content)
    roster_audit.validate(document)
    return document


def published_rate_evidence(raw, subject):
    """Point-only availability depends solely on the subject's original display cell."""
    if subject not in ['math', 'reading']:
        raise ValueError('Published native rate requires Math or ELA')
    field = roster_audit.FIELDS[subject][2]
    raw_rate = raw[field]
    rate = roster_audit.number(raw_rate)
    if rate is not None and (not 0 <= rate <= 100 or rate != int(rate)):
        raise ValueError('Native TAPR published percentage must be a whole percentage from zero to 100')
    return {'field': field, 'raw_published_rate': raw_rate, 'published_rate': rate,
            'available': rate is not None,
            'exclusion': None if rate is not None else 'Native TAPR published subject percentage missing or masked; suppression preserved',
            'valid_scores': None, 'sampling_variance': None, 'sampling_interval_available': False}


def selected_inputs(roster, subject):
    """Derive explicit display-rate membership without any reported-count screen."""
    if subject not in SUBJECTS:
        raise ValueError('Unsupported district subject; high/mixed assessments are not approved')
    raw = roster['raw_inputs']
    directory = {r['raw']['NCESSCH']: r for r in raw['directory']['records']}
    students = {r['raw']['CAMPUS']: r for r in raw['stud']['records']}
    assessments = {r['raw']['CAMPUS']: r for r in raw['assessment']['records']}
    references = {r['raw']['CAMPUS']: r for r in raw['ref']['records']}
    configurations = sorted([r for r in roster['roster_links'] if r['native_present']
                             and roster_audit.grade_evidence(students[r['native_school_id']]['raw'])['scope'] == 'grade-school'
                             and directory[r['school_id']]['raw']['UPDATED_STATUS'] in roster_audit.OPERATIONAL],
                            key=lambda r: r['school_id'])
    inputs, exclusions = [], []
    for school in configurations:
        key = school['native_school_id']
        student, assessment, reference = students[key], assessments[key], references[key]
        income = roster_audit.income_evidence(student['raw'])
        grade = roster_audit.grade_evidence(student['raw'])
        displays = {s: published_rate_evidence(assessment['raw'], s) for s in ['math', 'reading']}
        required = ['math', 'reading'] if subject == 'combined' else [subject]
        reasons = [income['exclusion']] if income['exclusion'] else []
        reasons += [displays[s]['exclusion'] for s in required if not displays[s]['available']]
        if reasons:
            exclusions.append({'school_id': school['school_id'], 'native_school_id': key, 'name': school['name'],
                               'reason': '; '.join(dict.fromkeys(reasons)), 'income': income,
                               'native_grade': grade, 'published_subjects': displays,
                               'native_assessment': assessment, 'source_record': school})
            continue
        native_rates = {s: displays[s]['published_rate'] for s in ['math', 'reading']}
        outcome = (native_rates['math'] + native_rates['reading']) / 2 if subject == 'combined' else native_rates[subject]
        if income != school['income'] or grade != school['native_enrolled']:
            raise ValueError('Model income/configuration differ from reconciled same-year native evidence')
        inputs.append({
            'school_id': school['school_id'], 'native_school_id': key, 'ncessch': school['school_id'],
            'name': school['name'], 'level': 'ES', 'charter': school['ccd_flags']['charter'],
            'ccd_school_type': school['ccd_flags']['school_type'], 'ccd_flags': school['ccd_flags'],
            'income_pct': income['percentage'], 'income_year': 2025, 'outcome_pct': outcome,
            'outcome_by_subject': native_rates, 'outcome_basis': 'native_published_whole_percent',
            'valid_scores_by_subject': {'math': None, 'reading': None},
            'display_valid_scores': None, 'sampling_variance': None,
            'sources': {'ccd_source_id': 'directory', 'ccd_source_row': school['ccd_source_row'],
                        'directory_raw': directory[school['school_id']]['raw'],
                        'native_school_id': key, 'ccd_native_school_id': school['ccd_native_school_id'],
                        'native_source_rows': school['native_source_rows'], 'native_student': student,
                        'native_assessment': assessment, 'native_reference': reference,
                        'native_grade_evidence': grade, 'native_income_evidence': income,
                        'native_published_subjects': displays,
                        'unverified_reported_subject_evidence': school['subjects'],
                        'supplemental_ccd_membership': school['ccd_membership'],
                        'native_peims_membership': school['native_peims_membership'],
                        'reference_high_grade_contradiction': school['native_reference_conflicts_with_positive_high_enrollment']},
        })
    coverage = {
        'native_grade_school_configuration_profiles': len(configurations),
        'usable_schools': len(inputs), 'excluded_configuration_profiles': len(exclusions),
        'exclusions': dict(sorted(Counter(r['reason'] for r in exclusions).items())),
        'excluded_configuration_records': exclusions,
        'outside_native_configuration_records': [r for r in roster['roster_links'] if not (r['native_present'] and r['native_enrolled']['scope'] == 'grade-school')],
        'charter': dict(sorted(Counter(r['charter'] for r in inputs).items())),
        'school_types': dict(sorted(Counter(r['ccd_school_type'] for r in inputs).items())),
        'eligible_members_with_verified_denominators': 0,
        'ten_valid_scored_floor_certified': False,
        'published_rate_only_membership_matches_prior_prospective_count_screen':
            [r['school_id'] for r in inputs] == sorted(roster['cohorts']['prospective_grade_school']['subjects'][subject]['prospective_nces_school_ids']),
        'published_subject_rates_differing_from_count_ratios': {s: sum(
            r['outcome_by_subject'][s] != r['sources']['unverified_reported_subject_evidence'][s]['proficiency']
            for r in inputs) for s in ['math', 'reading']},
        'selection_basis': POLICY['published_rate_eligibility'],
    }
    return inputs, coverage


def frozen_population(roster):
    return {
        'complete_directory_ncessch': sorted(r['raw']['NCESSCH'] for r in roster['raw_inputs']['directory']['records']),
        'operational_roster_school_ids': sorted(r['school_id'] for r in roster['roster_links'] if r['ccd_flags']['operational']),
        'native_source_profile_ids': sorted(r['native_school_id'] for r in roster['roster_links'] if r['native_present']),
        'native_grade_school_configuration_ids': sorted(roster['cohorts']['prospective_grade_school']['native_school_ids']),
        'eligible_school_ids_by_subject': {s: [r['school_id'] for r in selected_inputs(roster, s)[0]] for s in SUBJECTS},
        'eligible_native_school_ids_by_subject': {s: [r['native_school_id'] for r in selected_inputs(roster, s)[0]] for s in SUBJECTS},
        'native_primary_only_ids': sorted(roster['cohorts']['primary_only']['native_school_ids']),
        'native_high_school_ids': sorted(roster['cohorts']['high_only']['native_school_ids']),
        'native_mixed_school_ids': sorted(roster['cohorts']['mixed_grade']['native_school_ids']),
        'missing_native_school_ids': sorted(r['school_id'] for r in roster['roster_links'] if not r['native_present']),
    }
def verify_independently(x, y, model, results):
    """Centered full OLS, independent leverage and explicit held-out refits; no intervals."""
    n = len(x)
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
    return deleted, errors


def fit_audited_model(inputs, coverage, subject):
    if subject not in SUBJECTS:
        raise ValueError('Only three proposed grade-school subjects may be audited')
    if len(inputs) < MIN_SCHOOLS:
        raise ValueError('District subject model requires at least 30 usable schools')
    # Enforce the source boundary even for direct calls. Fit diagnostics must
    # never become a route to changing income, published display values or membership.
    frozen_inputs, frozen_coverage = selected_inputs(load_roster(), subject)
    if ([r.get('school_id') for r in inputs] != [r['school_id'] for r in frozen_inputs]
            or roster_audit.fingerprint(inputs) != roster_audit.fingerprint(frozen_inputs)
            or roster_audit.fingerprint(coverage) != roster_audit.fingerprint(frozen_coverage)):
        raise ValueError('District fit requires exact frozen native inputs, complete eligible membership and coverage')
    if (len({r['school_id'] for r in inputs}) != len(inputs)
            or len({r['native_school_id'] for r in inputs}) != len(inputs)
            or any(r['level'] != 'ES' or type(r['income_year']) is not int or r['income_year'] != 2025
                   or not re.fullmatch(roster_audit.LEA + r'\d{5}', r['school_id'])
                   or not re.fullmatch(roster_audit.DISTRICT + r'\d{3}', r['native_school_id'])
                   or roster_audit.ccd_identity(r['sources']['directory_raw']) != (r['school_id'], r['native_school_id'])
                   or r['sources']['directory_raw']['UPDATED_STATUS'] not in roster_audit.OPERATIONAL
                   or roster_audit.native_identity(r['sources']['native_student']['raw']) != r['native_school_id']
                   or roster_audit.native_identity(r['sources']['native_assessment']['raw']) != r['native_school_id']
                   or roster_audit.grade_evidence(r['sources']['native_student']['raw'])['scope'] != 'grade-school'
                   or roster_audit.income_evidence(r['sources']['native_student']['raw'])['percentage'] is None
                   for r in inputs)):
        raise ValueError('District members require unique exact same-year native pure grade-school identities and reconciled enrollment')
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
        'model_id': f'houston-published-2025-ES-{subject}', 'status': 'numerically_verified_pending_integration',
        'approved_for_modeling': False, 'year': 2025, 'academic_year': '2024-2025',
        'population': 'Exact attached-LEA positive native enrolled grades 3–8 with no high grades; same-year individual economic status and published whole-percent All Students TAPR enrolled-grades 3–8 Including EOC Meets or Above rates',
        'level': 'ES', 'subject': subject, 'assessment': ASSESSMENT,
        'assessment_standard': STANDARD, 'outcome_basis': 'native_published_whole_percent',
        'valid_score_floor_certified': False, 'eligibility_policy': POLICY['published_rate_eligibility'],
        'coverage': coverage, 'inputs': inputs,
        'population_sha256': roster_audit.fingerprint({'policy': POLICY, 'source_audit_sha256': ROSTER_SHA,
                                                      'level': 'ES', 'subject': subject, 'year': 2025,
                                                      'school_ids': [r['school_id'] for r in inputs]}),
        'coefficients': model, 'results': results,
        'review_warnings': [
            'Valid-score denominators remain unverified; no count, sampling variance or interval is available.',
            'Conventional leverage, Cook distance and residual flags require descriptive review, never automatic exclusions.',
            'Native individual economic status is broader than FRPL; STAAR/Spanish/Alternate 2/EOC totals and whole-percent display rounding retain population and precision limitations. The ten-valid-scored floor remains uncertified under open issue #16.',
        ],
        'intervals': {'available_for_entire_model': False, 'eligible_members': len(inputs),
                      'eligible_members_with_verified_denominators': 0,
                      'valid_score_counts': None, 'sampling_variances': None,
                      'reason': 'Exact 2025 TAPR N/M performance score-status mapping is unresolved (#16). Published rates support only this explicit unknown-count audit; no ten-valid-scored certification or intervals.'},
        'diagnostics': {
            'income_design_rank': rank, 'income_design_condition_number': float(np.linalg.cond(design)),
            'centered_income_design_condition_number': float(np.linalg.cond(np.column_stack([np.ones(len(x)), x - x.mean()]))),
            'income': {'minimum': float(x.min()), 'maximum': float(x.max()), 'mean': float(x.mean()),
                       'standard_deviation_population': float(x.std()), 'distinct': len(set(x.tolist())),
                       'quantiles': {str(q): float(np.quantile(x, q)) for q in [.05, .25, .5, .75, .95]}},
            'residual_sse': sse, 'residual_standard_error': float(math.sqrt(s2)),
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
            'interpretation': 'Descriptive influence flags only; no school is excluded by leverage, residual or fit quality. Whole-percent published-rate rounding, broader native individual economic status, varying grade/course mixes and unresolved exact valid-score denominators/ten-valid-scored floor remain limitations.',
        },
        'independent_verification': {'explicit_deleted_fits': len(inputs), 'deleted_training_members': len(inputs) - 1,
                                     'deleted_residual_degrees_of_freedom': len(inputs) - 3, 'tolerance_absolute': VERIFY_TOLERANCE,
                                     'maximum_absolute_errors': errors,
                                     'method': 'Centered full OLS; centered closed-form leverage; every explicit leave-one-out fit uses N−3 scale and held-out variance factor 1+h_deleted. Interval verification is inapplicable because all verified valid-score denominators are unavailable; native enrollment, PEIMS membership and reported performance counts remain raw provenance, never assessment denominators or a ten-valid-scored certificate.'},
    }


def build(roster=None):
    roster = load_roster() if roster is None else roster
    roster_audit.validate(roster)
    if roster_audit.fingerprint(roster) != roster_audit.fingerprint(load_roster()):
        raise ValueError('In-memory Houston source audit differs from pinned complete source')
    models, holds = [], []
    for subject in SUBJECTS:
        inputs, coverage = selected_inputs(roster, subject)
        try:
            model = fit_audited_model(inputs, coverage, subject)
        except ValueError as error:
            model = {'model_id': f'houston-published-2025-ES-{subject}', 'status': 'numerical_hold',
                     'approved_for_modeling': False, 'level': 'ES', 'subject': subject, 'inputs': inputs, 'coverage': coverage,
                     'reason': str(error)}
            holds.append({'model_id': model['model_id'], 'reason': str(error)})
        models.append(model)
    population = frozen_population(roster)
    return {
        'schema_version': 1, 'state': 'TX', 'year': 2025, 'academic_year': '2024-2025', 'nces_lea_id': roster_audit.LEA,
        'native_lea_id': roster_audit.NATIVE_LEA, 'native_district_id': roster_audit.DISTRICT,
        'scope': 'published_rate_only_numerical_audit',
        'status': 'numerical_hold' if holds else 'numerically_verified_pending_integration',
        'approved_for_source': False, 'approved_for_modeling': False, 'policy': POLICY,
        'count_definition_hold': COUNT_HOLD,
        'sources': {'roster_audit': {'path': 'data/source/houston-district-audit.json', 'sha256': ROSTER_SHA, 'bytes': ROSTER_BYTES},
                    'native_sources': roster['sources']},
        'frozen_population': population,
        'frozen_population_sha256': roster_audit.fingerprint({'policy': POLICY, 'population': population}),
        'source_coverage': roster['coverage'],
        'retained_source_evidence': {
            'raw_inputs': roster['raw_inputs'], 'state_extract': roster['state_extract'],
            'source_policy': roster['policy'], 'source_approval': {'approved_for_source': roster['approved_for_source'], 'approved_for_modeling': roster['approved_for_modeling']},
            'enrollment_reconciliation': roster['enrollment_reconciliation'],
            'planning_identity_reconciliation': roster['planning_identity_reconciliation'],
            'historical_state_consistency': roster['historical_state_consistency'],
        },
        'retained_scope_exclusions': {
            'source_cohorts': roster['cohorts'],
            'outside_grade_school_population': roster['outside_grade_school_population'],
            'outside_native_configuration_records': [r for r in roster['roster_links'] if not (r['native_present'] and r['native_enrolled']['scope'] == 'grade-school')],
        },
        'replay_tolerance': {'absolute': ABS_TOLERANCE, 'relative': REL_TOLERANCE,
                             'scope': 'Computed numerical metrics only. Original source evidence, identity, configuration, displayed outcomes, income, membership, count hold and interval absence compare exactly.'},
        'models': models, 'hard_holds': holds,
    }


def numeric_equal(actual, expected):
    if isinstance(expected, float):
        return isinstance(actual, (float, int)) and not isinstance(actual, bool) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=REL_TOLERANCE, abs_tol=ABS_TOLERANCE)
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(numeric_equal(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(numeric_equal(a, e) for a, e in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def validate(document, expected=None):
    expected = build() if expected is None else expected
    if roster_audit.fingerprint({k: v for k, v in document.items() if k != 'models'}) != roster_audit.fingerprint({k: v for k, v in expected.items() if k != 'models'}):
        raise ValueError('District numerical audit metadata/source evidence changed')
    if len(document['models']) != len(expected['models']):
        raise ValueError('District numerical audit model set changed')
    for actual, model in zip(document['models'], expected['models']):
        for field in ['model_id', 'level', 'subject', 'status', 'approved_for_modeling', 'year',
                      'academic_year', 'population', 'assessment', 'assessment_standard',
                      'review_warnings', 'coverage', 'inputs', 'population_sha256', 'intervals',
                      'outcome_basis', 'valid_score_floor_certified', 'eligibility_policy']:
            if field in model and roster_audit.fingerprint(actual.get(field)) != roster_audit.fingerprint(model[field]):
                raise ValueError('District numerical audit source identities/counts/population changed')
        if 'independent_verification' in model:
            metadata = lambda value: {k: v for k, v in value.items() if k != 'maximum_absolute_errors'}
            if roster_audit.fingerprint(metadata(actual.get('independent_verification', {}))) != roster_audit.fingerprint(metadata(model['independent_verification'])):
                raise ValueError('District independent verification metadata/tolerance changed')
        if 'results' in model:
            exact = ['school_id', 'actual', 'valid_scores', 'sampling_variance', 'low', 'high']
            if roster_audit.fingerprint([{k: r.get(k) for k in exact} for r in actual.get('results', [])]) != roster_audit.fingerprint([{k: r[k] for k in exact} for r in model['results']]):
                raise ValueError('District numerical result identities/native outcomes/counts or interval absence changed')
        if not numeric_equal(actual, model):
            raise ValueError('District numerical results failed independent replay tolerance')
    return {m['model_id']: m['coverage']['usable_schools'] for m in expected['models']}


def prepare(output=OUTPUT, check=False):
    expected = build()
    if check:
        validate(json.loads(Path(output).read_text()), expected)
    else:
        Path(output).write_text(json.dumps(expected, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return {'models': {m['model_id']: m['coverage']['usable_schools'] for m in expected['models']},
            'hard_holds': expected['hard_holds']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Replay saved audit without rewriting it')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.check), sort_keys=True))
