"""Canonical import and static export for audited single-year state adapters.

Adapters validate their native sources before calling this module. Each school
belongs to one explicitly defined assessment cohort; no source discovery is
accepted here and no missing count or economic value is manufactured.
"""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history


def bounded(value, maximum=None):
    if value is not None and (not isinstance(value, (int, float)) or
            not math.isfinite(value) or value < 0 or maximum is not None and value > maximum):
        raise ValueError('Invalid normalized state value')


def import_snapshot(db, payload, extract_path):
    release_status = payload.get('release_status', 'ready')
    if release_status not in ['ready', 'audit_pending']:
        raise ValueError('Invalid snapshot release status')
    dataset, year, state = payload['dataset'], payload['year'], payload['state']['id']
    cohorts = {c['id']: c for c in payload['cohorts']}
    if len(cohorts) != len(payload['cohorts']) or not cohorts:
        raise ValueError('Duplicate or missing assessment cohort')
    if len({c['level'] for c in cohorts.values()}) != len(cohorts):
        raise ValueError('Snapshot requires one cohort per school level')
    if len({c['assessment'] for c in cohorts.values()}) != len(cohorts):
        raise ValueError('Snapshot requires distinct cohort assessment labels')
    existing = db.execute('SELECT state FROM dataset WHERE id=?', (dataset,)).fetchone()
    if existing is not None and existing['state'] != state:
        raise ValueError('Dataset identity belongs to another state')
    # Delete only this adapter's rows, preserving every other release.
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (dataset,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?', (dataset + ':%',))
    db.execute('''INSERT INTO dataset VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
        name=excluded.name, model_scope=excluded.model_scope, status=excluded.status''',
        (dataset, state, payload['name'], payload['model_scope'], release_status))
    source_id = dataset + ':extract'
    db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
        (source_id, dataset, str(Path(extract_path).relative_to(ROOT)),
         payload['source_url'], hashlib.sha256(Path(extract_path).read_bytes()).hexdigest(), payload['retrieved']))
    for key, source in payload['sources'].items():
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
            (dataset + ':' + key, dataset, source['path'], source['url'], source['sha256'], payload['retrieved']))
    econ_id = dataset + ':income'
    income = payload['income_definition']
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',
        (econ_id, income['label'], income['definition'], income['url']))
    for cohort in cohorts.values():
        if cohort['level'] not in ['ES', 'HS']:
            raise ValueError('Invalid school level')
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
            (definition_id(dataset, year, cohort['assessment'], cohort['level']), state,
             cohort['assessment'], year, cohort['level'], cohort['grades'], cohort['standard'], cohort['source_url']))
    seen = set()
    for order, school in enumerate(payload['schools']):
        key = school['id']
        if not isinstance(key, str) or not key or key in seen or school['cohort'] not in cohorts:
            raise ValueError('Invalid or duplicate authoritative school identity')
        seen.add(key)
        bounded(school['income'], 100)
        bounded(school['enrollment'])
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
            (dataset, key, school['name'], school['district_id'], school['district'],
             school.get('city'), school.get('county'), json.dumps(school), source_id, order))
        # A rounded percentage never implies an exact low-income count.
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (dataset, key, year, econ_id, school['name'], school['enrollment'],
             school.get('low_income'), school['income'], income['label'], json.dumps(school['income_raw']),
             dataset + ':' + school['income_source'], school['income_row']))
        cohort = cohorts[school['cohort']]
        for subject in ['math', 'reading']:
            observation = school['outcomes'].get(subject, {})
            pct, tested = observation.get('proficiency'), observation.get('tested')
            bounded(pct, 100)
            bounded(tested)
            if tested is not None and (tested != int(tested) or not observation.get('valid_score_evidence')):
                raise ValueError('Counts require a verified valid-score denominator')
            db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (dataset, key, definition_id(dataset, year, cohort['assessment'], cohort['level']), subject,
                 pct, tested, 'reported' if pct is not None else 'suppressed_or_not_reported',
                 json.dumps(observation.get('raw')), json.dumps(observation.get('raw_tested')),
                 dataset + ':' + observation.get('source', cohort['source']), observation.get('source_row', 0)))


def prepare_snapshot(payload, extract_path, output, database=DEFAULT_DB):
    dataset, year = payload['dataset'], payload['year']
    with connect(database) as db:
        import_snapshot(db, payload, extract_path)
        assessments = pl.DataFrame([dict(r) for r in db.execute('''
            SELECT a.school_id, CAST(d.year AS TEXT) AS year, d.level, d.name AS assessment,
                   a.subject, a.proficiency, a.tested FROM assessment_observation a
            JOIN assessment_definition d ON a.definition_id=d.id WHERE a.dataset_id=?''', (dataset,))])
        incomes = pl.DataFrame([dict(r) for r in db.execute('''
            SELECT school_id, CAST(year AS TEXT) AS year, name, enrollment, low_income, percentage,
                   source_label AS income_label FROM economic_observation WHERE dataset_id=?''', (dataset,))])
        records, models = build_history(assessments, incomes,
            point_only_assessments=[c['assessment'] for c in payload['cohorts'] if c.get('allow_point_only')])
        save_models(db, records, models, dataset)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('State snapshot foreign key check failed')
    annual = {r['school_id']: r for r in records}
    cohorts = {c['id']: c for c in payload['cohorts']}
    schools = []
    for profile in payload['schools']:
        record = annual[profile['id']]
        for subject in ['math', 'reading']:
            if subject not in record['subjects'] and profile['outcomes'].get(subject, {}).get('exclusion'):
                record['exclusions'][subject] = profile['outcomes'][subject]['exclusion']
        if 'combined' not in record['subjects']:
            record['exclusions']['combined'] = '; '.join(
                f'{"ELA" if s == "reading" else "Math"}: {record["exclusions"][s]}'
                for s in ['math', 'reading'] if s in record['exclusions'])
        schools.append(dict(id=profile['id'], name=profile['name'], short=profile['name'],
            level=cohorts[profile['cohort']]['level'], program='Unclassified', programs=['Unclassified'],
            district=profile['district'], city=profile.get('city'), county=profile.get('county'),
            latitude=profile.get('latitude'), longitude=profile.get('longitude'),
            income=record['income'], enrollment=record['enrollment'], metrics=record['subjects'],
            exclusions=record['exclusions'], history=[record]))
    levels = {c['level']: dict(year=year, label=c['label'], assessment=c['assessment'],
        outcome=c['outcome'], math_label='Math', note=c['note']) for c in cohorts.values()}
    if len(levels) != len(cohorts):
        raise ValueError('Snapshot export requires one cohort per school level')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    result = dict(year=payload['academic_year'], assessment_year=year,
        income_label=payload['income_definition']['label'], program_options=['Unclassified'],
        levels=levels, schools=schools,
        models={level: {s: next((m for m in models if m['level']==level and m['subject']==s), None)
                       for s in ['math', 'reading', 'combined']} for level in levels},
        history_years=[year], history_models=models, coverage_note=payload['coverage_note'],
        methodology=payload['methodology'])
    (output/'schools.json').write_text(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n')
    (output/'history.json').write_text(json.dumps(dict(records=records, models=models),
        separators=(',', ':'), allow_nan=False)+'\n')
    path = str(output.relative_to(ROOT))
    region = dict(id=payload['region'], name='Statewide', dataset=dataset, status=payload.get('release_status', 'ready'),
        geography=payload['region'], levels=list(levels), schools=path+'/schools.json', boundaries=None,
        comparison=payload['state']['name']+' · {year} · {assessment} · {note}',
        model_scope=payload['model_scope'], map_source=payload.get('map_source',
            'School coordinates are unavailable in the audited source extract.'))
    (output/'catalog.json').write_text(json.dumps(dict(schema_version=1, state=payload['state'],
        prepare_script=payload['prepare_script'], regions=[region]), indent=2)+'\n')
    audit = dict(year=year, schools=len(schools), cohorts={c['id']: dict(
        directory=sum(p['cohort']==c['id'] for p in payload['schools']),
        eligible={m['subject']:m['n'] for m in models if m['assessment']==c['assessment']})
        for c in cohorts.values()}, exclusions=dict(Counter(
            reason for r in records for reason in r['exclusions'].values())),
        source_audit=payload.get('source_audit', {}))
    (output/'coverage.json').write_text(json.dumps(audit, indent=2)+'\n')
    return audit
