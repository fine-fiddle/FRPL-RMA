"""Preserve published SAT levels and same-year income; never infer tested counts."""
import argparse
import hashlib
import json
from pathlib import Path
from database import ROOT, add_source, add_definition, numeric

OUTPUT = ROOT/'data/source/illinois-sat-history.json'
SOURCES = {
    2018: ('18-RC-Pub-Data-Set.xlsx', 'Report-Card-Public-Data-Set.xlsx'),
    2019: ('19-RC-Pub-Data-Set.xlsx', '2019-Report-Card-Public-Data-Set.xlsx'),
    2021: ('21-RC-Pub-Data-Set.xlsx', '2021-RC-Pub-Data-Set.xlsx'),
    2022: ('22-RC-Pub-Data-Set.xlsx', '2022-Report-Card-Public-Data-Set.xlsx'),
    2023: ('23-RC-Pub-Data-Set.xlsx', '23-RC-Pub-Data-Set.xlsx'),
}
FIELDS = ['RCDTS', 'School Name', 'District', 'City', 'County', 'School Type',
          'Grades Served', '# Student Enrollment', '% Student Enrollment - Low Income']


def extract():
    import openpyxl
    years = []
    for year, (filename, remote) in SOURCES.items():
        path = ROOT/'data/raw'/filename
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows = workbook['General'].values
        headers = next(rows)
        aliases = {'# Student Enrollment': 'Student Enrollment - Total',
                   '% Student Enrollment - Low Income': 'Student Enrollment - Low Income %'} if year == 2018 else {}
        indices = [headers.index(aliases.get(f, f)) for f in FIELDS]
        profiles = {r[0]: dict(zip(FIELDS, [r[i] for i in indices])) for r in rows
                    if r[headers.index('Type')] == 'School'}
        rows = workbook['SAT'].values
        headers = next(rows)
        indices = {s: [headers.index(f'SAT {label} Total Students Level {n} %') for n in (3, 4)]
                   for s, label in [('math', 'Math'), ('reading', 'Reading')]}
        observations = []
        for row in rows:
            if row[headers.index('Type')] != 'School':
                continue
            levels = {s: [row[i] for i in ii] for s, ii in indices.items()}
            # Retain high-school suppression as well as reported mixed-grade results.
            if str(profiles[row[0]]['School Type']).casefold() == 'high school' or any(
                    all(numeric(v) is not None for v in values) for values in levels.values()):
                observations.append(dict(profile=profiles[row[0]], levels=levels))
        workbook.close()
        years.append(dict(year=year, observations=observations,
                          url='https://www.isbe.net/Documents/'+remote,
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    OUTPUT.write_text(json.dumps(years, separators=(',', ':'), allow_nan=False))


def import_history(db):
    dataset = 'isbe-2024'
    source = 'isbe-sat-history'
    if db.execute('SELECT 1 FROM source WHERE id=?', (source,)).fetchone():
        db.execute('UPDATE source SET sha256=? WHERE id=?',
                   (hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), source))
    else:
        add_source(db, source, dataset, OUTPUT, 'https://www.isbe.net/ilreportcarddata')
    for payload in json.loads(OUTPUT.read_text()):
        year = payload['year']
        definition = add_definition(db, dataset, year, 'SAT', 'HS')
        db.execute('DELETE FROM assessment_observation WHERE definition_id=?', (definition,))
        economic = f'isbe-low-income-{year}'
        db.execute('INSERT OR IGNORE INTO economic_definition VALUES (?,?,?,?)',
                   (economic, f'Illinois Low Income {year}', f'Published {year} Report Card low-income percentage.', payload['url']))
        for order, row in enumerate(payload['observations']):
            p = row['profile']
            sid = p['RCDTS']
            db.execute('INSERT OR IGNORE INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (dataset, sid, p['School Name'], sid[:11], p['District'], p['City'], p['County'], json.dumps(p), source, order))
            db.execute('INSERT OR REPLACE INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (dataset, sid, year, economic, p['School Name'], numeric(p['# Student Enrollment']),
                        None, numeric(p['% Student Enrollment - Low Income']), 'Low Income', json.dumps(p), source, order))
            for subject, levels in row['levels'].items():
                values = [numeric(v) for v in levels]
                rate = sum(values) if all(v is not None and 0 <= v <= 100 for v in values) else None
                if rate is not None and rate > 100:
                    raise ValueError(f'Invalid SAT levels: {year} {sid} {subject}')
                db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           (dataset, sid, definition, subject, rate, None,
                            'reported' if rate is not None else 'suppressed_or_not_reported',
                            json.dumps(levels), None, source, order))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    if parser.parse_args().extract:
        extract()
