"""Import documented 2017 school-level PARCC/SAT aggregates, with same-year income."""
import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from database import ROOT, add_source, add_definition, numeric

OUTPUT = ROOT/'data/source/illinois-history-2017.json'
FILES = ['rc17.zip', 'rc17_assessment.zip', 'RC17_layout.xlsx']


def archive_rows(filename, member, expected_fields):
    with zipfile.ZipFile(ROOT/'data/raw'/filename) as archive:
        with io.TextIOWrapper(archive.open(member), encoding='cp1252', newline='') as stream:
            result = {}
            for row in csv.reader(stream, delimiter=';'):
                row = [v.strip() for v in row]
                if len(row) != expected_fields or not re.fullmatch(r'[0-9A-Z]{15}', row[0]):
                    raise ValueError(f'Unexpected archive record: {filename} {row[0]}')
                if row[0] in result or row[0].endswith('0000'):
                    raise ValueError(f'Duplicate or non-school ID: {row[0]}')
                result[row[0]] = row
            return result


def extract():
    import openpyxl
    workbook = openpyxl.load_workbook(ROOT/'data/raw/RC17_layout.xlsx', read_only=True, data_only=True)
    layouts = {s: {r[0]: r for r in workbook[s].values if isinstance(r[0], int)} for s in ['RC17','Assessment']}
    fields = {'RCDTS': (1, 'SCHOOL ID (R-C-D-T-S)'), 'School Name': (4, 'SCHOOL NAME'),
              'District': (5, 'DISTRICT NAME'), 'City': (6, 'CITY'), 'County': (7, 'COUNTY'),
              'School Type': (12, 'SCHOOL TYPE NAME'), 'Grades Served': (13, 'GRADES IN SCHOOL'),
              '# Student Enrollment': (21, 'SCHOOL TOTAL ENROLLMENT'),
              '% Student Enrollment - Low Income': (54, 'LOW-INCOME SCHOOL %')}
    for index, label in fields.values():
        if layouts['RC17'][index][5].strip() != label:
            raise ValueError(f'Demographic layout changed: {index}')
    assessment_fields = {'PARCC': {'reading': 271, 'math': 275}, 'SAT': {'reading': 279, 'math': 283}}
    level_fields = {'PARCC': {'reading': list(range(439,444)), 'math': list(range(459,464))},
                    'SAT': {'reading': list(range(495,499)), 'math': list(range(511,515))}}
    for test, subjects in assessment_fields.items():
        for subject, index in subjects.items():
            label = 'ELA' if subject == 'reading' else 'MATH'
            r = layouts['Assessment'][index]
            if (r[1], r[2], r[5].strip()) != (test, f'2017-{label}', f'2017 SCHOOL PERCENT OF PROFICIENCY IN {label}'):
                raise ValueError(f'Assessment layout changed: {index}')
            for level_index in level_fields[test][subject]:
                level = layouts['Assessment'][level_index]
                if level[1] != test or level[2] != 'ALL' or not level[5].startswith(f'2017 {label} SCHOOL'):
                    raise ValueError(f'Performance-level layout changed: {level_index}')
    workbook.close()
    profiles = archive_rows('rc17.zip', 'rc17.txt', 1472)
    assessments = archive_rows('rc17_assessment.zip', 'rc17_assessment.txt', 8315)
    if profiles.keys() != assessments.keys():
        raise ValueError('2017 demographic/assessment school IDs differ')
    observations = []
    for sid, row in sorted(profiles.items()):
        p = {name: row[index-1] for name, (index, _) in fields.items()}
        rates = {test: {subject: assessments[sid][index-1] for subject, index in subjects.items()}
                 for test, subjects in assessment_fields.items()}
        levels = {test: {subject: [assessments[sid][i-1] for i in indices] for subject, indices in subjects.items()}
                  for test, subjects in level_fields.items()}
        for test, subjects in rates.items():
            for subject, raw in subjects.items():
                if numeric(raw) is None:
                    continue
                parts = [numeric(v) for v in levels[test][subject]]
                if any(v is None for v in parts) or abs(sum(parts)-100) > .251 or abs(sum(parts[-2:])-numeric(raw)) > .151:
                    raise ValueError(f'Proficiency does not reconcile to performance levels: {sid} {test} {subject}')
        observations.append(dict(profile=p, proficiency=rates, levels=levels))
    payload = dict(year=2017, observations=observations, fields=fields, assessment_fields=assessment_fields, level_fields=level_fields,
                   sources=[dict(url='https://www.isbe.net/Documents/'+f,
                                 sha256=hashlib.sha256((ROOT/'data/raw'/f).read_bytes()).hexdigest()) for f in FILES])
    OUTPUT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))


def import_history(db):
    dataset, source = 'isbe-2024', 'isbe-history-2017'
    payload = json.loads(OUTPUT.read_text())
    if db.execute('SELECT 1 FROM source WHERE id=?', (source,)).fetchone():
        db.execute('UPDATE source SET sha256=? WHERE id=?', (hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), source))
    else:
        add_source(db, source, dataset, OUTPUT, 'https://www.isbe.net/ilreportcarddata')
    economic = 'isbe-low-income-2017'
    db.execute('INSERT OR IGNORE INTO economic_definition VALUES (?,?,?,?)',
               (economic, 'Illinois Low Income 2017', 'Published 2017 Report Card low-income percentage.', 'https://www.isbe.net/ilreportcarddata'))
    definitions = {test: add_definition(db, dataset, 2017, test, level) for test, level in [('PARCC','ES'),('SAT','HS')]}
    for definition in definitions.values():
        db.execute('DELETE FROM assessment_observation WHERE definition_id=?', (definition,))
    for order, row in enumerate(payload['observations']):
        p = row['profile']; sid = p['RCDTS']
        db.execute('INSERT OR IGNORE INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (dataset, sid, p['School Name'], sid[:11], p['District'], p['City'], p['County'], json.dumps(p), source, order))
        db.execute('INSERT OR REPLACE INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (dataset, sid, 2017, economic, p['School Name'], numeric(p['# Student Enrollment'].replace(',', '')),
                    None, numeric(p['% Student Enrollment - Low Income']), 'Low Income', json.dumps(p), source, order))
        for test, subjects in row['proficiency'].items():
            for subject, raw in subjects.items():
                rate = numeric(raw)
                if rate is not None and not 0 <= rate <= 100:
                    raise ValueError(f'Invalid proficiency: {sid} {test} {subject}')
                # Nonparticipating tests have empty fields; keep only observed cohorts.
                if not any(v for v in subjects.values()):
                    continue
                db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           (dataset, sid, definitions[test], subject, rate, None,
                            'reported' if rate is not None else 'suppressed_or_not_reported', raw, None, source, order))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    if parser.parse_args().extract:
        extract()
