"""Audit independent LAUSD district fits offline; never import or publish models."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import numpy as np

import audit_los_angeles as roster_audit
from prepare_data import fit_model, sampling_variance

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/source/los-angeles-model-audit.json'
ROSTER = roster_audit.OUTPUT
ROSTER_SHA = '72633e06df2e9d84e23a3c204c241d4f97c9f0aef2fb454378f6298e0f7877d2'
MIN_SCHOOLS = 30
ABS_TOLERANCE = 2e-10
REL_TOLERANCE = 2e-10
VERIFY_TOLERANCE = 2e-9
SUBJECTS = ['math', 'reading', 'combined']
POLICY = {
    'roster': 'Exact operational 2024–25 CCD LEA 0622710 attachments only.',
    'school_types': 'Retain locally funded charters, alternatives and other exact roster types; no fit-driven exclusions.',
    'populations': 'Pure grade schools and pure high schools separately; mixed schools excluded.',
    'models': 'Separate 2024–25 Smarter Balanced district Math, ELA and Combined OLS models by pure level.',
    'minimum_usable_subject_schools': MIN_SCHOOLS,
    'studentization': 'Externally studentized residuals with the deleted-school residual scale.',
    'intervals': 'Conditional sampling intervals propagate every member through I−H with the regression scale held fixed; any missing member count omits modelwide intervals.',
    'combined': 'Equal mean of Math and ELA; variance is (sqrt(v_math)+sqrt(v_ELA))²/4. Minimum subject count is display-only.',
    'release': 'Independent numerical audit only; canonical import, browser integration and release review remain outstanding.',
}


def load_roster(path=ROSTER):
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != ROSTER_SHA:
        raise ValueError('LAUSD exact roster audit fingerprint changed; re-audit the population')
    document = json.loads(content)
    roster_audit.validate(document)
    return document


def selected_inputs(roster, level, subject):
    """Select from audited raw eligibility, never from statewide residuals."""
    if level not in ['ES', 'HS'] or subject not in SUBJECTS:
        raise ValueError('Unsupported district assessment population or subject')
    inputs = []
    pure = [r for r in roster['roster_links'] if r.get('scope') == level]
    for school in sorted(pure, key=lambda r: r['school_id']):
        values = school['assessments'][level]
        if not values[subject]['usable']:
            continue
        counts = {s: values[s]['valid_scores'] for s in ['math', 'reading']}
        variances = {s: sampling_variance(values[s]['proficiency'], counts[s])
                     if values[s]['usable'] and counts[s] is not None else None
                     for s in ['math', 'reading']}
        variance = ((math.sqrt(variances['math']) + math.sqrt(variances['reading'])) ** 2 / 4
                    if subject == 'combined' and all(v is not None for v in variances.values())
                    else None if subject == 'combined' else variances[subject])
        display_count = min(counts.values()) if subject == 'combined' and all(n is not None for n in counts.values()) else counts.get(subject)
        inputs.append({
            'school_id': school['school_id'], 'ncessch': school['ncessch'],
            'name': school['profile']['raw']['School Name'], 'level': level,
            'charter': school['charter'], 'ccd_school_type': school['ccd_school_type'],
            'income_pct': school['income']['percentage'], 'income_year': school['income']['year'],
            'outcome_pct': values[subject]['proficiency'], 'valid_scores_by_subject': counts,
            'display_valid_scores': display_count, 'sampling_variance': variance,
            'sources': {
                'ccd_source_row': school['ccd_source_row'],
                'frpm_source_id': 'ca-frpm-2025', 'frpm_source_row': school['income']['source_row'],
                'assessment_source_id': 'ca-sb-2025',
                'expected_grade_rows': {s: [r['source_row'] for r in values[s]['expected_grade_records']]
                                        for s in ['math', 'reading']},
                'expected_grades': {s: values[s]['expected_grades'] for s in ['math', 'reading']},
            },
        })
    coverage = {
        'pure_profiles': len(pure),
        'applicable_profiles': sum(r['assessments'][level][subject]['applicable'] for r in pure),
        'usable_schools': len(inputs),
        'excluded_profiles': len(pure) - len(inputs),
        'exclusions': dict(sorted(Counter(r['assessments'][level][subject]['exclusion']
                                         for r in pure if not r['assessments'][level][subject]['usable']).items())),
        'charter': dict(sorted(Counter(r['charter'] for r in inputs).items())),
        'school_types': dict(sorted(Counter(r['ccd_school_type'] for r in inputs).items())),
    }
    return inputs, coverage


def verify_independently(x, y, variance, model, results, intervals_available):
    """Explicit deleted fits and centered closed-form H, independent of fit_model."""
    n = len(x)
    centered = x - x.mean()
    spread = centered @ centered
    h = 1 / n + centered ** 2 / spread
    deleted = []
    full_design = np.column_stack([np.ones(n), centered])
    full_beta = np.linalg.lstsq(full_design, y, rcond=None)[0]
    full_predicted = full_design @ full_beta
    full_residual = y - full_predicted
    full_r2 = 1 - (full_residual @ full_residual) / ((y - y.mean()) @ (y - y.mean()))
    if model['n'] != n:
        raise ValueError('Returned district model count differs from the exact subject membership')
    errors = {
        'coefficient': max(abs(float(full_beta[0] - full_beta[1] * x.mean()) - model['intercept']),
                           abs(float(full_beta[1]) - model['slope'])),
        'predicted': max(abs(float(value) - row['predicted']) for value, row in zip(full_predicted, results)),
        'residual': max(abs(float(value) - row['residual']) for value, row in zip(full_residual, results)),
        'r2': abs(float(full_r2) - model['r2']),
        'studentized': 0., 'leverage': 0., 'interval_endpoint': 0. if intervals_available else None,
    }
    for i in range(n):
        keep = np.arange(n) != i
        mean_x = x[keep].mean()
        design = np.column_stack([np.ones(n - 1), x[keep] - mean_x])
        if np.linalg.matrix_rank(design) != 2:
            raise ValueError('An explicit deleted-school income design is rank deficient')
        beta = np.linalg.lstsq(design, y[keep], rcond=None)[0]
        residual = y[keep] - design @ beta
        deleted_sse = float(residual @ residual)
        if deleted_sse <= 0 or not math.isfinite(deleted_sse):
            raise ValueError('Explicit deleted-school residual scale is unavailable')
        predicted_held_out = float(beta[0] + beta[1] * (x[i] - mean_x))
        predictive_leverage = 1 / (n - 1) + (x[i] - mean_x) ** 2 / ((x[keep] - mean_x) @ (x[keep] - mean_x))
        scale = math.sqrt(deleted_sse / (n - 3))
        independent_t = (y[i] - predicted_held_out) / (scale * math.sqrt(1 + predictive_leverage))
        row = results[i]
        errors['studentized'] = max(errors['studentized'], abs(independent_t - row['studentized']))
        errors['leverage'] = max(errors['leverage'], abs(h[i] - row['leverage']))
        if intervals_available:
            hat_row = 1 / n + centered[i] * centered / spread
            residual_row = -hat_row
            residual_row[i] += 1
            propagated = float((residual_row ** 2) @ variance)
            se = math.sqrt(propagated) / (scale * math.sqrt(1 - h[i]))
            bounds = [independent_t - 1.96 * se, independent_t + 1.96 * se]
            errors['interval_endpoint'] = max(errors['interval_endpoint'],
                                              abs(bounds[0] - row['low']), abs(bounds[1] - row['high']))
        deleted.append({'intercept': float(beta[0] - beta[1] * mean_x),
                        'slope': float(beta[1]), 'sse': deleted_sse,
                        'held_out_prediction': predicted_held_out})
    if any(v is not None and v > VERIFY_TOLERANCE for v in errors.values()):
        raise ValueError('Independent deleted-fit/interval verification exceeded tolerance')
    return deleted, errors


def fit_audited_model(inputs, coverage, level, subject):
    if len(inputs) < MIN_SCHOOLS:
        raise ValueError('District subject model requires at least 30 usable schools')
    if len({r['school_id'] for r in inputs}) != len(inputs) or any(r['level'] != level or r['income_year'] != 2025 for r in inputs):
        raise ValueError('District model members require unique exact same-year pure population identities')
    x = np.array([r['income_pct'] for r in inputs], dtype=float)
    y = np.array([r['outcome_pct'] for r in inputs], dtype=float)
    required_subjects = ['math', 'reading'] if subject == 'combined' else [subject]
    verified_counts = [all(isinstance(r['valid_scores_by_subject'].get(s), int)
                           and not isinstance(r['valid_scores_by_subject'].get(s), bool)
                           and r['valid_scores_by_subject'][s] >= 11 for s in required_subjects)
                       for r in inputs]
    available_variance = [counted and r['sampling_variance'] is not None
                          for counted, r in zip(verified_counts, inputs)]
    intervals_available = all(available_variance)
    variance = np.array([r['sampling_variance'] if available else 0.
                         for available, r in zip(available_variance, inputs)], dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    rank = int(np.linalg.matrix_rank(design))
    if rank != 2:
        raise ValueError('District income design must have rank two')
    model, fitted = fit_model(x, y, variance)
    if not intervals_available:
        for result in fitted:
            result.update(low=None, high=None)
    deleted, errors = verify_independently(x, y, variance, model, fitted, intervals_available)
    residual = np.array([r['residual'] for r in fitted])
    sse = float(residual @ residual)
    s2 = sse / (len(x) - 2)
    results = []
    maximum_prediction_change = 0.
    for school, result, deletion in zip(inputs, fitted, deleted):
        h = result['leverage']
        cook = result['residual'] ** 2 * h / (2 * s2 * (1 - h) ** 2)
        endpoints = np.array([x.min(), x.max()])
        shift = (deletion['intercept'] - model['intercept']) + (deletion['slope'] - model['slope']) * endpoints
        change = float(np.max(np.abs(shift)))
        maximum_prediction_change = max(maximum_prediction_change, change)
        results.append({'school_id': school['school_id'], **result, 'cooks_distance': float(cook),
                        'deleted_intercept': deletion['intercept'], 'deleted_slope': deletion['slope'],
                        'deleted_sse': deletion['sse'], 'deleted_held_out_prediction': deletion['held_out_prediction'],
                        'maximum_prediction_change_on_observed_income_range': change})
    by_id = {r['school_id']: r for r in inputs}
    influence = []
    for result in sorted(results, key=lambda r: (-r['cooks_distance'], r['school_id']))[:10]:
        school = by_id[result['school_id']]
        influence.append({k: school[k] for k in ['school_id', 'name', 'charter', 'ccd_school_type', 'income_pct']} |
                         {k: result[k] for k in ['cooks_distance', 'leverage', 'studentized']})
    model_id = f'lausd-2025-{level}-{subject}'
    return {
        'model_id': model_id, 'status': 'numerically_verified_pending_integration', 'year': 2025,
        'academic_year': '2024-2025', 'population': 'Exact attached-LEA pure ' + ('grade schools' if level == 'ES' else 'high schools'),
        'level': level, 'subject': subject, 'assessment': roster_audit.california.ASSESSMENTS[level],
        'coverage': coverage, 'inputs': inputs,
        'population_sha256': roster_audit.fingerprint({'policy': POLICY, 'level': level, 'subject': subject,
                                                      'year': 2025, 'school_ids': [r['school_id'] for r in inputs]}),
        'coefficients': model, 'results': results,
        'intervals': {'available_for_entire_model': intervals_available,
                      'eligible_members_with_verified_subject_counts': sum(verified_counts),
                      'eligible_members': len(inputs), 'combined_count_is_display_only': subject == 'combined'},
        'diagnostics': {
            'income_design_rank': rank, 'income_design_condition_number': float(np.linalg.cond(design)),
            'centered_income_design_condition_number': float(np.linalg.cond(np.column_stack([np.ones(len(x)), x - x.mean()]))),
            'income': {'minimum': float(x.min()), 'maximum': float(x.max()), 'mean': float(x.mean()),
                       'standard_deviation_population': float(x.std()), 'distinct': len(set(x.tolist()))},
            'residual_sse': sse, 'residual_rmse': float(math.sqrt(s2)),
            'minimum_deleted_sse': min(r['sse'] for r in deleted),
            'maximum_leverage': max(r['leverage'] for r in results),
            'maximum_absolute_studentized_residual': max(abs(r['studentized']) for r in results),
            'maximum_cooks_distance': max(r['cooks_distance'] for r in results),
            'maximum_absolute_deleted_slope_change': max(abs(r['slope'] - model['slope']) for r in deleted),
            'maximum_prediction_change_on_observed_income_range': maximum_prediction_change,
            'top_ten_cooks_distance': influence,
            'interpretation': 'Descriptive influence review only; no school is excluded by leverage, residual or fit quality.',
        },
        'independent_verification': {'explicit_deleted_fits': len(inputs), 'tolerance_absolute': VERIFY_TOLERANCE,
                                     'maximum_absolute_errors': errors,
                                     'method': 'Centered-income full and leave-one-out least squares; independently centered closed-form hat rows propagate every sampling variance.'},
    }


def build(roster=None):
    if roster is None:
        roster = load_roster()
    else:
        roster_audit.validate(roster)
    models, holds = [], []
    for level in ['ES', 'HS']:
        for subject in SUBJECTS:
            inputs, coverage = selected_inputs(roster, level, subject)
            try:
                model = fit_audited_model(inputs, coverage, level, subject)
            except ValueError as error:
                model = {'model_id': f'lausd-2025-{level}-{subject}', 'status': 'numerical_hold',
                         'level': level, 'subject': subject, 'inputs': inputs, 'coverage': coverage,
                         'reason': str(error)}
                holds.append({'model_id': model['model_id'], 'reason': str(error)})
            models.append(model)
    return {'schema_version': 1, 'state': 'CA', 'year': 2025, 'nces_lea_id': roster_audit.LEA,
            'native_lea_id': roster_audit.NATIVE_LEA, 'status': 'numerical_audit_pending_integration',
            'approved_for_modeling': False,
            'policy': POLICY, 'sources': {
                'roster_audit': {'path': 'data/source/los-angeles-district-audit.json', 'sha256': ROSTER_SHA},
                'native_sources': roster['sources']},
            'replay_tolerance': {'absolute': ABS_TOLERANCE, 'relative': REL_TOLERANCE,
                                 'scope': 'Computed numerical metrics only. Source evidence, identity, configuration, membership and counts compare exactly.'},
            'models': models, 'hard_holds': holds}


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
    if {k: v for k, v in document.items() if k != 'models'} != {k: v for k, v in expected.items() if k != 'models'}:
        raise ValueError('District numerical audit metadata/source evidence changed')
    if len(document['models']) != len(expected['models']):
        raise ValueError('District numerical audit model set changed')
    for actual, model in zip(document['models'], expected['models']):
        for field in ['model_id', 'level', 'subject', 'status', 'coverage', 'inputs', 'population_sha256']:
            if field in model and actual.get(field) != model[field]:
                raise ValueError('District numerical audit source identities/counts/population changed')
        if 'results' in model:
            if [{k: r[k] for k in ['school_id', 'actual']} for r in actual.get('results', [])] != [{k: r[k] for k in ['school_id', 'actual']} for r in model['results']]:
                raise ValueError('District numerical result identities/native outcomes changed')
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
