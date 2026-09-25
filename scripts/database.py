"""Canonical SQLite imports. Raw sources remain immutable and independently auditable."""
import csv
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / 'data/build/schools.sqlite'
ISBE_URL = 'https://www.isbe.net/Documents/24-RC-Pub-Data-Set.xlsx'
RULES_URL = 'https://www.isbe.net/Documents/Public-Business-Rules-2024-Report-Card-Metrics.pdf'


def numeric(value):
    if isinstance(value, str):
        value = value.strip()
    if value in (None, '', '*', '‡', 'N/A', 'NA', '--'):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f'Non-finite source number: {value}')
    return result


def connect(path=DEFAULT_DB):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    return connection


def add_source(db, source_id, dataset, path, url):
    path = path.resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    source_path = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
               (source_id, dataset, source_path, url, digest,
                datetime.now(timezone.utc).isoformat()))
    return digest


def definition_id(dataset, year, assessment, level):
    return f'{dataset}:{year}:{assessment}:{level}'


def add_definition(db, dataset, year, assessment, level):
    ident = definition_id(dataset, year, assessment, level)
    db.execute('INSERT OR IGNORE INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
               (ident, 'IL', assessment, year, level,
                '3–8' if level == 'ES' else 'High-school tested grades under that year’s rules',
                f'Illinois {year} {assessment} percentage meeting or exceeding state standards. '
                'Specific assessment, grade coverage and cut scores apply; not a national proficiency scale.',
                RULES_URL if year == 2024 else 'https://www.isbe.net/Pages/Report-Card-Metrics.aspx'))
    return ident


def csv_rows(path):
    with path.open(newline='', encoding='utf-8-sig') as source:
        yield from csv.DictReader(source)


def import_chicago(db):
    dataset = 'cps'
    db.execute('INSERT INTO dataset VALUES (?,?,?,?,?)',
               (dataset, 'IL', 'Chicago Public Schools', 'CPS annual assessment cohorts', 'ready'))
    db.execute('INSERT INTO economic_definition VALUES (?,?,?,?)',
               ('cps-income', 'CPS annual low-income enrollment',
                'Annual 20th-day low-income count divided by enrollment. Source labels vary by year.',
                'https://www.cps.edu/about/district-data/demographics/'))
    inputs = [
        ('cps-profiles', 'cps-profile-sy2324.csv', 'https://data.cityofchicago.org/d/cu4u-b4d9'),
        ('cps-income', 'income-history.csv', 'https://www.cps.edu/about/district-data/demographics/'),
        ('cps-assessments', 'assessments-history.csv', 'https://www.cps.edu/about/district-data/metrics/assessment-reports/'),
    ]
    for ident, filename, url in inputs:
        add_source(db, ident, dataset, ROOT/'data/source'/filename, url)
    for i, p in enumerate(csv_rows(ROOT/'data/source/cps-profile-sy2324.csv')):
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (dataset, p['School_ID'], p['Long_Name'], 'CPS', 'Chicago Public Schools',
                    'Chicago', 'Cook', json.dumps(p), 'cps-profiles', i))
    for i, row in enumerate(csv_rows(ROOT/'data/source/income-history.csv')):
        sid = row['school_id']
        db.execute('INSERT OR IGNORE INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (dataset, sid, row['name'], 'CPS', 'Chicago Public Schools',
                    'Chicago', 'Cook', None, 'cps-income', i))
        total, low = numeric(row['enrollment']), numeric(row['low_income'])
        percentage = 100*low/total if total and low is not None else None
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (dataset, sid, int(row['year']), 'cps-income', row['name'], total, low,
                    percentage, row['income_label'], json.dumps(row), 'cps-income', i))
    for i, row in enumerate(csv_rows(ROOT/'data/source/assessments-history.csv')):
        sid = row['school_id']
        db.execute('INSERT OR IGNORE INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (dataset, sid, None, 'CPS', 'Chicago Public Schools', 'Chicago', 'Cook',
                    None, 'cps-assessments', i))
        ident = add_definition(db, dataset, int(row['year']), row['assessment'], row['level'])
        pct, tested = numeric(row['proficiency']), numeric(row['tested'])
        if tested is not None and tested != int(tested):
            raise ValueError('Non-integral tested count')
        db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (dataset, sid, ident, row['subject'], pct, tested,
                    'reported' if pct is not None else 'suppressed_or_not_reported',
                    row['proficiency'], row['tested'], 'cps-assessments', i))


def import_illinois(db, path):
    # Streaming extraction keeps the 53 MB workbook out of the website bundle.
    import openpyxl
    dataset = 'isbe-2024'
    db.execute('INSERT INTO dataset VALUES (?,?,?,?,?)',
               (dataset, 'IL', 'Illinois statewide 2024', 'Illinois statewide assessment cohorts',
                'awaiting_tested_counts'))
    add_source(db, dataset, dataset, path, ISBE_URL)
    db.execute('INSERT INTO economic_definition VALUES (?,?,?,?)',
               ('isbe-low-income-2024', 'Illinois Low Income',
                'Published 2024 Report Card percentage of enrolled students classified as low income. '
                'Uses the published percentage, retaining underlying counts separately.', RULES_URL))
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)

    def rows(sheet, required):
        iterator = workbook[sheet].values
        headers = next(iterator)
        missing = set(required) - set(headers)
        if missing:
            raise ValueError(f'{sheet}: missing columns {missing}')
        indices = {key: headers.index(key) for key in required}
        for line, row in enumerate(iterator, start=2):
            if row[1] == 'School':
                yield line, {key: row[index] for key, index in indices.items()}

    general = ['RCDTS', 'School Name', 'District', 'City', 'County', 'School Type', 'Grades Served',
               '# Student Enrollment', '# Student Enrollment - Low Income', '% Student Enrollment - Low Income']
    for line, row in rows('General', general):
        sid = row['RCDTS']
        if not isinstance(sid, str) or len(sid) != 15:
            raise ValueError(f'Invalid RCDTS on row {line}: {sid!r}')
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (dataset, sid, row['School Name'], sid[:11], row['District'], row['City'],
                    row['County'], json.dumps(row), dataset, line))
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (dataset, sid, 2024, 'isbe-low-income-2024', row['School Name'],
                    numeric(row['# Student Enrollment']), numeric(row['# Student Enrollment - Low Income']),
                    numeric(row['% Student Enrollment - Low Income']), 'Low Income', json.dumps(row), dataset, line))
    for assessment, level in [('IAR', 'ES'), ('SAT', 'HS')]:
        ident = add_definition(db, dataset, 2024, assessment, level)
        columns = {subject: f'{assessment} {label} Proficiency Rate - Total'
                   for subject, label in [('math', 'Math'), ('reading', 'ELA')]}
        for line, row in rows(assessment, ['RCDTS', *columns.values()]):
            for subject, column in columns.items():
                raw = row[column]
                value = numeric(raw)
                db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           (dataset, row['RCDTS'], ident, subject, value, None,
                            'reported' if value is not None else
                            'not_reported' if raw in (None, '') else 'suppressed_or_not_reported',
                            None if raw is None else str(raw), None, dataset, line))
    workbook.close()


def chicago_frames(db):
    """Adapter for the existing model. Preserve input order and raw strings exactly."""
    import polars as pl
    profiles = [json.loads(r[0]) for r in db.execute(
        "SELECT profile_json FROM school WHERE dataset_id='cps' AND profile_json IS NOT NULL ORDER BY source_order")]
    incomes = [json.loads(r[0]) for r in db.execute(
        "SELECT raw_json FROM economic_observation WHERE dataset_id='cps' ORDER BY source_order")]
    observations = [dict(r) for r in db.execute('''
        SELECT a.school_id, CAST(d.year AS TEXT) AS year, d.level, d.name AS assessment,
               a.subject, a.raw_value AS proficiency, a.raw_tested AS tested
        FROM assessment_observation a JOIN assessment_definition d ON d.id=a.definition_id
        WHERE a.dataset_id='cps' ORDER BY a.source_order''')]
    return tuple(pl.DataFrame(rows).with_columns(pl.all().replace('', None))
                 for rows in [profiles, observations, incomes])


def save_models(db, records, models):
    sources = list(db.execute("SELECT id,sha256 FROM source WHERE dataset_id='cps' ORDER BY id"))
    digest = hashlib.sha256(json.dumps([tuple(r) for r in sources]).encode()).hexdigest()
    db.execute("DELETE FROM model_run WHERE dataset_id='cps'")
    for model in models:
        definition = definition_id('cps', model['year'], model['assessment'], model['level'])
        ident = f'{definition}:{model["subject"]}:ols-v1:{digest[:12]}'
        db.execute('INSERT INTO model_run VALUES (?,?,?,?,?,?,?)',
                   (ident, 'cps', definition, model['subject'], 'ols-studentized-v1', digest, json.dumps(model)))
        for r in records:
            if (r['year'], r['assessment'], r['level']) != (model['year'], model['assessment'], model['level']):
                continue
            result = r['subjects'].get(model['subject'])
            if result:
                db.execute('INSERT INTO model_result VALUES (?,?,?,?,?,?,?,?)',
                           (ident, 'cps', r['school_id'], result['actual'], result['predicted'],
                            result['studentized'], result['low'], result['high']))
