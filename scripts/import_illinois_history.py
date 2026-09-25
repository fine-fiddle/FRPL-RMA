"""Extract and import 2023 IAR history with same-year ISBE income and EDC counts."""
import argparse
import hashlib
import json
from pathlib import Path
import polars as pl
from database import ROOT, DEFAULT_DB, connect, add_source, add_definition, numeric

OUTPUT = ROOT/'data/source/illinois-history-2023.json'
WORKBOOK_URL = 'https://www.isbe.net/Documents/23-RC-Pub-Data-Set.xlsx'
COUNTS_URL = 'https://eddatacenter.org/api/data/3.1?state=IL&year=2023'


def extract(workbook_path, counts_path):
    import openpyxl
    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    fields = ['RCDTS', 'School Name', 'District', 'City', 'County', 'School Type', 'Grades Served',
              '# Student Enrollment', '% Student Enrollment - Low Income']
    profiles = []
    iterator = workbook['General'].values
    headers = next(iterator)
    for row in iterator:
        if row[headers.index('Type')] == 'School':
            profiles.append({f: row[headers.index(f)] for f in fields})
    grade_rates = {}
    for sheet in ['IAR', 'IAR (2)']:
        iterator = workbook[sheet].values
        headers = next(iterator)
        columns = {}
        for grade in range(3, 9):
            for subject, label in [('math', 'Mathematics'), ('ela', 'ELA')]:
                names = [f'% All students IAR {label} Level {level} - Grade {grade}' for level in [4, 5]]
                if all(n in headers for n in names):
                    columns[(f'G0{grade}', subject)] = [headers.index(n) for n in names]
        for row in iterator:
            if row[headers.index('Type')] != 'School':
                continue
            for (grade, subject), indices in columns.items():
                grade_rates[(row[0], grade, subject)] = [row[i] for i in indices]
    workbook.close()
    counts = pl.read_csv(counts_path, infer_schema=False).filter(
        (pl.col('DataLevel') == 'School') & (pl.col('StudentGroup') == 'All Students') &
        (pl.col('StudentSubGroup') == 'All Students') & (pl.col('AssmtName') == 'IAR') &
        (pl.col('AssmtType') == 'Regular') & (pl.col('SchYear') == '2022-23') &
        pl.col('Subject').is_in(['math', 'ela']))
    observations = []
    for row in counts.iter_rows(named=True):
        key = (row['StateAssignedSchID'], row['GradeLevel'], row['Subject'])
        observations.append(dict(school_id=key[0], grade=key[1], subject=key[2],
            tested=row['StudentSubGroup_TotalTested'], edc_proficiency=row['ProficientOrAbove_percent'],
            levels=grade_rates.get(key)))
    payload = dict(year=2023, profiles=profiles, grades=sorted(observations, key=lambda r:(r['school_id'],r['subject'],r['grade'])),
        sources=[dict(url=url, sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
                 for path, url in [(workbook_path, WORKBOOK_URL), (counts_path, COUNTS_URL)]])
    OUTPUT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))


def import_history(db):
    from prepare_illinois import validate_counts
    payload = json.loads(OUTPUT.read_text())
    dataset, source = 'isbe-2024', 'isbe-edc-history-2023'
    db.execute('DELETE FROM economic_observation WHERE dataset_id=? AND year=2023', (dataset,))
    definition = add_definition(db, dataset, 2023, 'IAR', 'ES')
    db.execute('DELETE FROM assessment_observation WHERE dataset_id=? AND definition_id=?', (dataset, definition))
    if not db.execute('SELECT 1 FROM source WHERE id=?', (source,)).fetchone():
        add_source(db, source, dataset, OUTPUT, WORKBOOK_URL)
    else:
        db.execute('UPDATE source SET sha256=? WHERE id=?', (hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), source))
    db.execute('INSERT OR IGNORE INTO economic_definition VALUES (?,?,?,?)',
        ('isbe-low-income-2023', 'Illinois Low Income 2023', 'Published 2023 Report Card low-income percentage.', 'https://www.isbe.net/ilreportcarddata'))
    groups = {}
    for row in payload['grades']:
        groups.setdefault((row['school_id'], row['subject']), []).append(row)
    for order, profile in enumerate(payload['profiles']):
        sid = profile['RCDTS']
        db.execute('INSERT OR IGNORE INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
            (dataset, sid, profile['School Name'], sid[:11], profile['District'], profile['City'], profile['County'], json.dumps(profile), source, order))
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (dataset, sid, 2023, 'isbe-low-income-2023', profile['School Name'], numeric(profile['# Student Enrollment']),
             None, numeric(profile['% Student Enrollment - Low Income']), 'Low Income', json.dumps(profile), source, order))
        for subject in ['math', 'ela']:
            site_subject = 'reading' if subject == 'ela' else subject
            db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (dataset, sid, definition, site_subject, None, None, 'suppressed_or_not_reported', None, None, source, order))
            rows = groups.get((sid, subject), [])
            valid = []
            for row in rows:
                try:
                    levels = [numeric(v) for v in row['levels']]
                    rate = sum(levels)
                    if not 0 <= rate <= 100 or abs(rate-100*float(row['edc_proficiency'])) > .16:
                        break
                    valid.append(dict(GradeLevel=row['grade'], StudentSubGroup_TotalTested=row['tested'], ProficientOrAbove_percent=str(rate/100)))
                except (TypeError, ValueError):
                    break
            else:
                try:
                    total = sum(int(r['StudentSubGroup_TotalTested']) for r in valid)
                    rate = 100*sum(int(r['StudentSubGroup_TotalTested'])*float(r['ProficientOrAbove_percent']) for r in valid)/total
                    n = validate_counts(valid, rate, profile['Grades Served'])
                except (ValueError, TypeError, ZeroDivisionError):
                    n = None
                if n is not None:
                    db.execute('UPDATE assessment_observation SET proficiency=?,tested=?,status=?,raw_value=?,raw_tested=? WHERE dataset_id=? AND school_id=? AND definition_id=? AND subject=?',
                        (rate, n, 'reported', str(rate), str(n), dataset, sid, definition, site_subject))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path)
    parser.add_argument('--counts', type=Path)
    args = parser.parse_args()
    if args.workbook and args.counts:
        extract(args.workbook, args.counts)
    with connect(DEFAULT_DB) as db:
        import_history(db)
