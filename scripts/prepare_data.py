"""Prepare site JSON from source CSVs. No network or website build required."""
from pathlib import Path
import json
import numpy as np
import polars as pl

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

def prepare():
    profiles = pl.read_csv(ROOT/'data/source/cps-profile-sy2324.csv', infer_schema=False)
    assessments = pl.read_csv(ROOT/'data/source/assessments-2024.csv', infer_schema=False)
    history = pl.read_csv(ROOT/'data/source/assessments-history.csv', infer_schema=False)
    if assessments.select(pl.struct(['school_id','level','subject']).is_duplicated().any()).item():
        raise ValueError('Duplicate assessment keys')
    lookup = {(r['school_id'],r['level'],r['subject']):r for r in assessments.iter_rows(named=True)}
    historical = {}
    for r in history.iter_rows(named=True):
        pct, n = number(r['proficiency']), number(r['tested'])
        if pct is None or n is None or n < 10 or pct < 0 or pct > 100:
            continue
        record = historical.setdefault(r['school_id'], {}).setdefault(str(int(r['year'])), {
            'year': int(r['year']), 'assessment': r['assessment'], 'subjects': {}
        })
        record['subjects'][r['subject']] = {'actual': pct, 'tested': int(n)}
    for records in historical.values():
        for record in records.values():
            subjects = record['subjects']
            if 'math' in subjects and 'reading' in subjects:
                record['subjects']['combined'] = {
                    'actual': (subjects['math']['actual'] + subjects['reading']['actual']) / 2,
                    'tested': min(subjects['math']['tested'], subjects['reading']['tested'])
                }
    schools = []
    for p in profiles.iter_rows(named=True):
        level = p['Primary_Category']
        if level not in ['ES','HS']: continue
        total, low = number(p['Student_Count_Total']), number(p['Student_Count_Low_Income'])
        income = 100*low/total if total and low is not None and 0<=low<=total else None
        school = dict(id=p['School_ID'], name=p['Long_Name'], short=p['Short_Name'],
            level=level, program=category(p['Classification_Description'] or ''),
            classification=p['Classification_Description'], address=p['Address'],
            latitude=number(p['School_Latitude']), longitude=number(p['School_Longitude']),
            enrollment=total, income=income, profile=p['CPS_School_Profile'], metrics={},
            history=sorted(historical.get(p['School_ID'], {}).values(), key=lambda r: r['year']))
        for subject in ['math','reading']:
            a=lookup.get((school['id'],level,subject),{})
            pct,n=number(a.get('proficiency')),number(a.get('tested'))
            if pct is not None and n is not None and 0<=pct<=100 and n>=10 and income is not None:
                school['metrics'][subject]=dict(actual=pct,tested=int(n),variance=sampling_variance(pct,n))
        if all(s in school['metrics'] for s in ['math','reading']):
            m,r=school['metrics']['math'],school['metrics']['reading']
            school['metrics']['combined']=dict(actual=(m['actual']+r['actual'])/2,
                tested=min(m['tested'],r['tested']),
                variance=(np.sqrt(m['variance'])+np.sqrt(r['variance']))**2/4)
        schools.append(school)
    models={}
    for level in ['ES','HS']:
        models[level]={}
        for subject in ['math','reading','combined']:
            eligible=[s for s in schools if s['level']==level and subject in s['metrics']]
            model, results = fit_model([s['income'] for s in eligible],
                [s['metrics'][subject]['actual'] for s in eligible],
                [s['metrics'][subject]['variance'] for s in eligible])
            models[level][subject]=model
            for s,r in zip(eligible,results):
                s['metrics'][subject].update(r)
                del s['metrics'][subject]['variance']
    output=dict(year='2023–24', assessment_year=2024, income_label='Low-income enrollment (FRPL proxy)',
                schools=schools, models=models,
                history_years=sorted({r['year'] for records in historical.values() for r in records.values()}))
    (ROOT/'data/schools.json').write_text(json.dumps(output, separators=(',',':'),allow_nan=False))
    print(json.dumps({level:{s:m['n'] for s,m in subjects.items()} for level,subjects in models.items()},indent=2))

if __name__=='__main__': prepare()
