"""Prepare site JSON from the canonical SQLite database. No network required."""
from pathlib import Path
import json
import numpy as np
import polars as pl
from database import DEFAULT_DB, connect, chicago_frames, save_models

ROOT = Path(__file__).resolve().parents[1]

def fit_model(x, y, variance):
    """OLS + externally studentized residuals and conditional sampling intervals.

    variance is a binomial approximation in percentage-point squared units.
    Intervals propagate it through (I-H); regression scale is held fixed.
    """
    x, y, variance = map(lambda v: np.asarray(v, dtype=float), (x, y, variance))
    X = np.column_stack([np.ones(len(x)), x])
    if len(x) < 4 or np.linalg.matrix_rank(X) != 2:
        raise ValueError('At least four schools and varying income percentages required')
    inv = np.linalg.inv(X.T @ X)
    beta = inv @ X.T @ y
    predicted = X @ beta
    residual = y - predicted
    h = np.einsum('ij,jk,ik->i', X, inv, X)
    sse = residual @ residual
    deleted_s2 = (sse - residual**2 / (1-h)) / (len(x)-3)
    denom = np.sqrt(np.maximum(deleted_s2, 1e-12) * (1-h))
    t = residual / denom
    H = X @ inv @ X.T
    sampling_variance = ((np.eye(len(x)) - H)**2) @ variance
    se = np.sqrt(np.maximum(sampling_variance, 0)) / denom
    return dict(intercept=float(beta[0]), slope=float(beta[1]), n=len(x),
                r2=float(1-sse/np.sum((y-y.mean())**2))), [
        dict(actual=float(y[i]), predicted=float(predicted[i]), residual=float(residual[i]),
             studentized=float(t[i]), low=float(t[i]-1.96*se[i]), high=float(t[i]+1.96*se[i]),
             leverage=float(h[i])) for i in range(len(x))]

def category(description):
    d = description.lower()
    if 'liberal arts' in d: return 'Classical'
    if 'entrance exam' in d: return 'Selective'
    if 'attendance boundary' in d: return 'Neighborhood'
    if 'independently' in d: return 'Charter'
    if 'specific subject area' in d: return 'Magnet'
    return 'Other'

def number(v):
    try:
        result = float(v)
        return result if np.isfinite(result) else None
    except (TypeError, ValueError): return None

def sampling_variance(pct, n):
    # Jeffreys smoothing avoids zero uncertainty at rounded 0% and 100%.
    p = (pct / 100 * n + .5) / (n+1)
    return 10000 * p * (1-p) / n

def build_history(assessments, incomes):
    """Fit all historical schools, without conditioning on the current directory."""
    if incomes.select(pl.struct(['school_id','year']).is_duplicated().any()).item():
        raise ValueError('Duplicate income school/year keys')
    keys = ['school_id','year','level','assessment','subject']
    if assessments.select(pl.struct(keys).is_duplicated().any()).item():
        raise ValueError('Duplicate historical assessment keys')
    income_lookup = {(r['school_id'], int(r['year'])): r for r in incomes.iter_rows(named=True)}
    records = {}
    for r in assessments.iter_rows(named=True):
        year = int(r['year'])
        key = (r['school_id'], year, r['level'], r['assessment'])
        demographic = income_lookup.get((r['school_id'], year), {})
        total, low = number(demographic.get('enrollment')), number(demographic.get('low_income'))
        income = number(demographic.get('percentage')) if 'percentage' in demographic else (100*low/total if total and total > 0 and low is not None and 0 <= low <= total else None)
        record = records.setdefault(key, dict(school_id=r['school_id'], year=year,
            level=r['level'], assessment=r['assessment'], name=demographic.get('name'),
            income=income, enrollment=total, income_year=year if demographic else None,
            income_label=demographic.get('income_label'), subjects={}, exclusions={}))
        pct, n = number(r['proficiency']), number(r['tested'])
        reason = ('Missing or suppressed proficiency' if pct is None else
                  'Invalid proficiency' if not 0 <= pct <= 100 else
                  'Missing or fewer than 10 tested' if n is None or n < 10 else
                  'Missing or invalid same-year income' if income is None else None)
        if reason:
            record['exclusions'][r['subject']] = reason
            continue
        record['subjects'][r['subject']] = dict(actual=pct, tested=int(n), variance=sampling_variance(pct, n))
    for record in records.values():
        subjects = record['subjects']
        if all(s in subjects for s in ['math', 'reading']):
            m, r = subjects['math'], subjects['reading']
            subjects['combined'] = dict(actual=(m['actual']+r['actual'])/2,
                tested=min(m['tested'],r['tested']),
                variance=(np.sqrt(m['variance'])+np.sqrt(r['variance']))**2/4)
        else:
            record['exclusions']['combined'] = 'Both eligible subject results required'
    models = []
    cohorts = sorted({(r['year'],r['level'],r['assessment']) for r in records.values()})
    for year, level, assessment in cohorts:
        cohort = [r for r in records.values() if (r['year'],r['level'],r['assessment']) == (year,level,assessment)]
        for subject in ['math', 'reading', 'combined']:
            eligible = [r for r in cohort if subject in r['subjects']]
            try:
                model, results = fit_model([r['income'] for r in eligible],
                    [r['subjects'][subject]['actual'] for r in eligible],
                    [r['subjects'][subject]['variance'] for r in eligible])
            except ValueError:
                for r in eligible:
                    del r['subjects'][subject]
                    r['exclusions'][subject] = 'Insufficient schools or income variation for regression'
                continue
            models.append(dict(year=year, level=level, assessment=assessment, subject=subject,
                               assessed_schools=len(cohort), excluded_schools=len(cohort)-len(eligible), **model))
            for record, result in zip(eligible, results):
                record['subjects'][subject].update(result, cohort_n=model['n'])
                del record['subjects'][subject]['variance']
    return sorted(records.values(), key=lambda r: (r['school_id'],r['year'],r['level'],r['assessment'])), models

def prepare(database=DEFAULT_DB):
    if not Path(database).exists():
        raise FileNotFoundError('Run scripts/build_database.py before preparing JSON')
    with connect(database) as db:
        profiles, history, incomes = chicago_frames(db)
    history_records, history_models = build_history(history, incomes)
    with connect(database) as db:
        save_models(db, history_records, history_models)
    current_income = {r['school_id']: r for r in incomes.iter_rows(named=True) if r['year'] == '2024'}
    schools = []
    for p in profiles.iter_rows(named=True):
        level = p['Primary_Category']
        if level not in ['ES','HS']: continue
        annual = current_income.get(p['School_ID'], {})
        total, low = number(annual.get('enrollment')), number(annual.get('low_income'))
        income = 100*low/total if total and low is not None and 0<=low<=total else None
        school = dict(id=p['School_ID'], name=p['Long_Name'], short=p['Short_Name'],
            level=level, program=category(p['Classification_Description'] or ''),
            classification=p['Classification_Description'], address=p['Address'],
            latitude=number(p['School_Latitude']), longitude=number(p['School_Longitude']),
            enrollment=total, income=income, profile=p['CPS_School_Profile'], metrics={},
            history=[r for r in history_records if r['school_id'] == p['School_ID'] and r['level'] == level])
        schools.append(school)
    # The snapshot and history share exactly the same annual regressions.
    models={}
    for level in ['ES','HS']:
        models[level]={}
        for subject in ['math','reading','combined']:
            models[level][subject]=next(m for m in history_models if m['year']==2024 and m['level']==level and m['subject']==subject)
        for school in (s for s in schools if s['level']==level):
            current = next((r for r in school['history'] if r['year']==2024), None)
            school['metrics'] = current['subjects'] if current else {}
    output=dict(year='2023–24', assessment_year=2024, income_label='Low-income enrollment (FRPL proxy)',
                schools=schools, models=models,
                history_years=sorted({r['year'] for r in history_records}), history_models=history_models)
    (ROOT/'data/schools.json').write_text(json.dumps(output, separators=(',',':'),allow_nan=False))
    (ROOT/'data/history.json').write_text(json.dumps(dict(records=history_records, models=history_models), separators=(',',':'), allow_nan=False))
    print(json.dumps({level:{s:m['n'] for s,m in subjects.items()} for level,subjects in models.items()},indent=2))

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    prepare(parser.parse_args().database)
