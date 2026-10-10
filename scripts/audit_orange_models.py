"""Audit independent Orange County point-only district fits; never import or publish."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

import audit_orange as roster_audit
from prepare_data import fit_model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/source/orange-model-audit.json'
ROSTER = roster_audit.OUTPUT
ROSTER_SHA = '671c14166fd5110bd569b26b2997d8bc73264e0156393d757516324e57c726f3'
MIN_SCHOOLS = 30
ABS_TOLERANCE = 2e-10
REL_TOLERANCE = 2e-10
VERIFY_TOLERANCE = 2e-9
SUBJECTS = ['math', 'reading', 'combined']
ASSESSMENT = 'Florida School Grades FAST + FAA + Math EOC · grade schools'
POLICY = {
    'roster': 'Exact operational 2024–25 CCD LEA 1201440 / FL-48 attachments only; retain the full 282-record directory, 275 operational identities and 268 native profiles. Pure offered inventory 209 includes 207 tested configurations; 208 profiles match native sources.',
    'populations': 'Require complete reported pure PK–8 offerings, at least one offered grade 3–8, and explicit zero native Survey 2 enrollment in every grade 9–12. 206 matched profiles are offered-applicable; two matched PK-only profiles are nonapplicable. The unmatched 48-1961 offers 6–8 and remains a missing native profile, never a primary-only or inferred zero-income profile.',
    'native_eligibility': 'Independent subject eligibility uses same-year raw individual lunch income and native Florida achievement exclusions; 200 eligible schools per subject. Preserve all exclusions and native-usable mixed 48-0283 outside the pure cohort.',
    'source_exclusions': 'Retain seven missing-Fall schools, two primary profiles, collocated 48-0042/0065 shared 17 Math/20 ELA evidence and five other missing pure campus outcomes. The original 61-row CCD membership proof is discovery evidence only, never a fit or native eligibility filter.',
    'zero_income': 'Eligible charter 48-0056 and 48-0061 retain verified zero recorded individual lunch eligibility and positive February enrollment. Zero recorded eligibility is not evidence that no low-income families attend. Never trim these members by income or influence.',
    'school_types': 'Retain exact attached-LEA charter, alternative and special-education flags. Native exclusions leave 182 noncharter and 18 charter Regular schools eligible; no fit-driven exclusions.',
    'models': 'Separate 2024–25 native Florida full-year/home-zoned School Grades Math, ELA and Combined ES district OLS; never reuse statewide residuals.',
    'minimum_usable_subject_schools': MIN_SCHOOLS,
    'studentization': 'Externally studentized residuals use deleted-school residual scale with N−3 degrees of freedom.',
    'intervals': 'Point estimates only: native valid-score denominators are absent. Counts, sampling variances and all interval endpoints remain null, modelwide. An internal zero variance vector is a computational sentinel, never an uncertainty estimate.',
    'combined': 'Equally weighted mean of eligible Math and ELA proficiency; not percent proficient in both. No counts or sampling variance are inferred.',
    'release': 'Numerically verified audit only; source and modeling approval remain false pending independent review and separate canonical/browser integration.',
}


def load_roster(path=ROSTER):
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != ROSTER_SHA:
        raise ValueError('Orange County source audit fingerprint changed; re-audit the population')
    document = json.loads(content)
    roster_audit.validate(document)
    return document


def frozen_population(roster):
    links = roster['roster_links']
    return {
        'complete_directory_ncessch': sorted(r['raw']['NCESSCH'] for r in roster['directory_records']),
        'native_profile_school_ids': sorted(r['id'] for r in roster['native_records']['profiles']),
        'pure_lower_offered_tested_directory_school_ids': sorted(roster['cohorts']['exact_operational_pure_lower_directory']['offered_tested_school_ids']),
        'eligible_zero_individual_income_school_ids': sorted(r['school_id'] for r in links if r['matched'] and r['subjects']['combined']['district_usable'] and r['income']['percentage'] == 0),
        'collocated_assessment_school_ids': sorted(r['id'] for r in roster['native_records']['assessments'] if r['raw'][47] == 'Y'),
        'operational_roster_school_ids': sorted(r['school_id'] for r in links),
        'pure_lower_offered_directory_school_ids': sorted(r['school_id'] for r in links if r['offered']['scope'] == 'ES'),
        'pure_lower_directory_school_ids': sorted(r['school_id'] for r in links if r['matched'] and r['offered']['scope'] == 'ES'),
        'unmatched_operational_school_ids': sorted(r['school_id'] for r in links if not r['matched']),
        'unmatched_pure_lower_directory_school_ids': sorted(r['school_id'] for r in links if not r['matched'] and r['offered']['scope'] == 'ES'),
        'offered_applicable_school_ids': sorted(roster['cohorts']['proposed_pure_offered_tested_grade']['school_ids']),
        'primary_only_school_ids': sorted(roster['cohorts']['pure_lower_primary_offers_only']['school_ids']),
        'native_grade_schools_with_mixed_offers': sorted(roster['cohorts']['native_grade_schools_with_mixed_offers']['school_ids']),
        'income_only_school_ids': sorted(r['school_id'] for r in roster['income_without_fall_registry_links']),
        'outside_operational_native_school_ids': sorted(r['school_id'] for r in roster['outside_roster_profiles']),
        'planning_omitted_source_eligible_school_ids': list(roster['planning_identity_reconciliation']['source_proposed_not_in_planning_ES']),
        'provider_specific_assessment_rows': [{'school_id': r['id'], 'source_row': r['row'], 'provider': r['raw'][3]}
                                             for r in roster['native_records']['assessments'] if r['raw'][3] not in ('', None)],
        'eligible_school_ids_by_subject': {s: sorted(roster['cohorts']['proposed_pure_offered_tested_grade']['subjects'][s]['eligible_school_ids']) for s in SUBJECTS},
    }


def selected_inputs(roster, subject):
    """Select exact audited native eligibility without income- or fit-based filtering."""
    if subject not in SUBJECTS:
        raise ValueError('Unsupported district subject; high/mixed assessments are not approved')
    pure = sorted([r for r in roster['roster_links'] if r['matched'] and r['offered']['scope'] == 'ES'],
                  key=lambda r: r['school_id'])
    campus = {a['id']: a for a in roster['native_records']['assessments'] if a['raw'][3] in ('', None)}
    directory = {roster_audit.directory_identity(a['raw']): a['raw'] for a in roster['directory_records']}
    inputs, exclusions = [], []
    for school in pure:
        values = school['subjects']
        value = values[subject]
        if any(v['valid_scores'] is not None or v['sampling_variance'] is not None or v['sampling_interval_available'] for v in values.values()):
            raise ValueError('Florida point-only native contract cannot contain inferred score denominators, variances or intervals')
        if not value['district_usable']:
            exclusions.append({'school_id': school['school_id'], 'ncessch': school['ncessch'],
                               'name': school['profile']['grades'][3],
                               'offered_applicable': value['district_applicable'],
                               'district_exclusion': value['district_exclusion'],
                               'native_source_exclusion': value['source_contract_exclusion'],
                               'charter': school['ccd_flags']['charter'],
                               'ccd_school_type': school['ccd_flags']['school_type'],
                               'ccd_source_row': school['ccd_source_row'],
                               'grade_source_row': school['profile']['grade_row'],
                               'income_source_row': school['profile']['income_row'],
                               'assessment_source_rows': school['native_assessment_rows'],
                               'profile': school['profile'], 'income': school['income'],
                               'offered': school['offered'], 'enrolled': school['enrolled'],
                               'native_assessment_flags': school['native_assessment_flags'], 'subjects': values})
            continue
        a = campus[school['school_id']]
        outcome = value['native_rate']
        if subject == 'combined' and outcome != (values['math']['native_rate'] + values['reading']['native_rate']) / 2:
            raise ValueError('Combined must be the exact equally weighted subject mean')
        inputs.append({
            'school_id': school['school_id'], 'ncessch': school['ncessch'],
            'name': school['profile']['grades'][3], 'level': 'ES',
            'charter': school['ccd_flags']['charter'], 'ccd_school_type': school['ccd_flags']['school_type'],
            'ccd_flags': school['ccd_flags'], 'native_assessment_flags': school['native_assessment_flags'],
            'income_pct': school['income']['percentage'], 'income_year': school['income']['year'],
            'outcome_pct': outcome,
            'outcome_by_subject': {s: values[s]['native_rate'] for s in ['math', 'reading']},
            'valid_scores_by_subject': {'math': None, 'reading': None},
            'display_valid_scores': None, 'sampling_variance': None,
            'sources': {
                'ccd_source_id': 'ccd_school_directory', 'ccd_source_row': school['ccd_source_row'],
                'directory_raw': directory[school['school_id']],
                'native_school_id': school['school_id'], 'income_source_id': 'income',
                'income_source_row': school['income']['source_row'], 'income_raw': school['income']['raw'],
                'grade_source_id': 'grades', 'grade_source_row': school['profile']['grade_row'],
                'grade_raw': school['profile']['grades'], 'offered_evidence': school['offered'],
                'enrolled_evidence': school['enrolled'],
                'assessment_source_id': 'assessment', 'assessment_source_row': a['row'],
                'assessment_raw': a['raw'], 'achievement_field_by_subject': {'math': 9, 'reading': 6},
                'native_subjects': values,
            },
        })
    if [r['school_id'] for r in inputs] != sorted(roster['cohorts']['proposed_pure_offered_tested_grade']['subjects'][subject]['eligible_school_ids']):
        raise ValueError('Model subject membership differs from immutable source eligibility')
    coverage = {
        'pure_offered_directory_records': len(roster['cohorts']['exact_operational_pure_lower_directory']['school_ids']),
        'pure_directory_records_without_fall_profile': len(roster['cohorts']['exact_operational_pure_lower_directory']['without_fall_profile_school_ids']),
        'pure_directory_profiles': len(pure),
        'offered_applicable_profiles': sum(r['subjects'][subject]['district_applicable'] for r in pure),
        'usable_schools': len(inputs), 'excluded_directory_profiles': len(exclusions),
        'exclusions': dict(sorted(Counter(r['district_exclusion'] for r in exclusions).items())),
        'excluded_directory_records': exclusions,
        'native_mixed_profiles_outside_population': len(roster['cohorts']['native_grade_schools_with_mixed_offers']['school_ids']),
        'charter': dict(sorted(Counter(r['charter'] for r in inputs).items())),
        'school_types': dict(sorted(Counter(r['ccd_school_type'] for r in inputs).items())),
        'eligible_members_with_verified_denominators': 0,
    }
    return inputs, coverage


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
    if (len({r['school_id'] for r in inputs}) != len(inputs)
            or any(r['level'] != 'ES' or r['income_year'] != 2025
                   or not re.fullmatch(r'48-\d{4}', r['school_id'])
                   or not re.fullmatch(roster_audit.LEA + r'\d{5}', r['ncessch'])
                   or roster_audit.directory_identity(r['sources']['directory_raw']) != r['school_id']
                   or r['sources']['directory_raw']['NCESSCH'] != r['ncessch']
                   or r['sources']['directory_raw']['UPDATED_STATUS'] not in roster_audit.OPERATIONAL
                   or r['sources']['offered_evidence']['scope'] != 'ES'
                   or not r['sources']['offered_evidence']['offered_tested_grades']
                   or r['sources']['enrolled_evidence']['native_grade_school_contract'] is not True for r in inputs)):
        raise ValueError('District members require unique exact same-year pure grade-school identities')
    if any(r['sampling_variance'] is not None or r['display_valid_scores'] is not None
           or r['valid_scores_by_subject'] != {'math': None, 'reading': None} for r in inputs):
        raise ValueError('Point-only source contract prohibits fabricated counts or sampling variance')
    if subject == 'combined' and any(r['outcome_pct'] != (r['outcome_by_subject']['math'] + r['outcome_by_subject']['reading']) / 2 for r in inputs):
        raise ValueError('Combined must be the exact equally weighted subject mean')
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
        'model_id': f'orange-2025-ES-{subject}', 'status': 'numerically_verified_pending_integration',
        'approved_for_modeling': False, 'year': 2025, 'academic_year': '2024-2025',
        'population': 'Exact attached-LEA pure grade schools with native same-year eligible income and achievement',
        'level': 'ES', 'subject': subject, 'assessment': ASSESSMENT,
        'assessment_standard': roster_audit.florida.STANDARD,
        'coverage': coverage, 'inputs': inputs,
        'population_sha256': roster_audit.fingerprint({'policy': POLICY, 'source_audit_sha256': ROSTER_SHA,
                                                      'level': 'ES', 'subject': subject, 'year': 2025,
                                                      'school_ids': [r['school_id'] for r in inputs]}),
        'coefficients': model, 'results': results,
        'review_warnings': [
            'Native whole-percent rates have no verified valid-score denominators; no sampling variance or interval is available.',
            'Conventional leverage, Cook distance and residual flags require descriptive review, never automatic exclusions.',
            'The February individual lunch proxy and full-year/home-zoned achievement population differ; CEP identification coverage is unknown.',
        ],
        'intervals': {'available_for_entire_model': False, 'eligible_members': len(inputs),
                      'eligible_members_with_verified_denominators': 0,
                      'valid_score_counts': None, 'sampling_variances': None,
                      'reason': 'Native Florida School Grades rates have no verified valid-score denominators.'},
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
            'interpretation': 'Descriptive influence flags only; no school is excluded by leverage, residual or fit quality. Native whole-percent rounding, income proxy and population differences remain limitations.',
        },
        'independent_verification': {'explicit_deleted_fits': len(inputs), 'tolerance_absolute': VERIFY_TOLERANCE,
                                     'maximum_absolute_errors': errors,
                                     'method': 'Centered full OLS; centered closed-form leverage; every explicit leave-one-out fit uses N−3 scale and held-out variance factor 1+h_deleted. Interval verification is inapplicable because verified valid-score denominators are unavailable; enrollment and percent tested remain unused for uncertainty.'},
    }


def build(roster=None):
    roster = load_roster() if roster is None else roster
    roster_audit.validate(roster)
    models, holds = [], []
    for subject in SUBJECTS:
        inputs, coverage = selected_inputs(roster, subject)
        try:
            model = fit_audited_model(inputs, coverage, subject)
        except ValueError as error:
            model = {'model_id': f'orange-2025-ES-{subject}', 'status': 'numerical_hold',
                     'level': 'ES', 'subject': subject, 'inputs': inputs, 'coverage': coverage,
                     'reason': str(error)}
            holds.append({'model_id': model['model_id'], 'reason': str(error)})
        models.append(model)
    population = frozen_population(roster)
    return {
        'schema_version': 1, 'state': 'FL', 'year': 2025, 'nces_lea_id': roster_audit.LEA,
        'native_lea_id': roster_audit.NATIVE_LEA,
        'status': 'numerical_hold' if holds else 'numerically_verified_pending_integration',
        'approved_for_source': False, 'approved_for_modeling': False, 'policy': POLICY,
        'sources': {'roster_audit': {'path': 'data/source/orange-district-audit.json', 'sha256': ROSTER_SHA, 'bytes': 1748206},
                    'native_sources': roster['sources']},
        'frozen_population': population,
        'frozen_population_sha256': roster_audit.fingerprint({'policy': POLICY, 'population': population}),
        'source_coverage': roster['coverage'],
        'retained_source_evidence': {
            'directory_records': roster['directory_records'], 'directory_header': roster['directory_header'],
            'income_worksheet_headers': roster['income_worksheet_headers'],
            'native_records': roster['native_records'],
            'planning_identity_reconciliation': roster['planning_identity_reconciliation'],
            'planning_membership_evidence': roster['planning_membership_evidence'],
            'planning_membership_exclusions': roster['planning_membership_exclusions'],
        },
        'retained_scope_exclusions': {
            'outside_pure_lower_operational_records': [r for r in roster['roster_links'] if not r['matched'] or r['offered']['scope'] != 'ES'],
            'income_only_records': roster['income_without_fall_registry_links'],
            'provider_specific_assessment_records': [r for r in roster['native_records']['assessments'] if r['raw'][3] not in ('', None)],
            'nonoperational_records': roster['nonoperational_directory'],
            'outside_operational_native_profiles': roster['outside_roster_profiles'],
        },
        'replay_tolerance': {'absolute': ABS_TOLERANCE, 'relative': REL_TOLERANCE,
                             'scope': 'Computed numerical metrics only. Source evidence, identity, configuration, membership, counts and interval absence compare exactly.'},
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
                      'review_warnings', 'coverage', 'inputs', 'population_sha256', 'intervals']:
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
