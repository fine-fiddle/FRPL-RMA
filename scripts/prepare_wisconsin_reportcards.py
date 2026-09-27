"""Published Wisconsin school totals, kept separate from WISEdash grade-count models.

Rebuild offline from the committed extract; --extract additionally needs the official
2024-25 workbook and technical guide under data/raw. See docs/wisconsin-data.md.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path

import openpyxl
import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history
from prepare_wisconsin import EXTRACT as WISE_EXTRACT, ECON_DEFINITION, digest, number, source_entry

DATASET = 'wi-reportcards'
YEAR = 2025
SCHOOL_YEAR = '2024-25'
EXTRACT = ROOT / 'data/source/wisconsin-reportcards.json'
WORKBOOK = ROOT / 'data/raw/2024-25_school_reportcard_data.xlsx'
WORKBOOK_URL = ('https://dpi.wi.gov/sites/default/files/imce/accountability/xlsx/'
                '2024-25_school_reportcard_data.xlsx')
GUIDE = ROOT / 'data/raw/wi-report-card-technical-guide-2024-25.pdf'
GUIDE_URL = 'https://dpi.wi.gov/media/26129/download?inline'
BANDS = {
    'grade': ('ES', 'WSAS school totals · grades 3–8', 'Grade schools · school totals'),
    'high': ('HS', 'WSAS school totals · grades 9–11', 'High schools · school totals'),
    'mixed': ('HS', 'WSAS school totals · mixed grade spans', 'Mixed-grade schools · school totals'),
}
RATE_FIELDS = {'math': 'Percent Meeting Mathematics 2025', 'reading': 'Percent Meeting ELA 2025'}
PROFILE_FIELDS = [
    'School Year', 'DPI Agency Key', 'District Code', 'School Code', 'District Name',
    'School Name', 'Report Card Type', 'Agency Type', 'Lowest Grade Level',
    'Highest Grade Level', 'School Type', 'School Enrollment', 'City',
    'Charter school indicator', 'No Score Note', *RATE_FIELDS.values(),
]


def grade_number(value):
    if value in {'K3', 'K4', 'K5', 'PK', 'KG', 'K'}:
        return 0
    parsed = number(value)
    if parsed is None or parsed != int(parsed) or not 0 <= parsed <= 12:
        raise ValueError(f'Unknown grade: {value!r}')
    return int(parsed)


def band_for(row):
    low, high = (grade_number(row[f'{edge} Grade Level']) for edge in ['Lowest', 'Highest'])
    if low > high:
        raise ValueError('Inverted grade range')
    return 'grade' if high <= 8 else 'high' if low >= 9 else 'mixed'


def published_percentage(value):
    parsed = number(value)
    if parsed is not None and not 0 <= parsed <= 1:
        raise ValueError(f'Expected a published proportion in [0, 1]: {value!r}')
    return parsed * 100 if parsed is not None else None


def school_id(row):
    codes = [number(row[f'{kind} Code']) for kind in ['District', 'School']]
    if any(v is None or v != int(v) or not 0 < v <= 9999 for v in codes):
        raise ValueError('Invalid public school district/school code')
    return 'S' + ''.join(f'{int(v):04d}' for v in codes)


def extract():
    workbook = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    try:
        rows = iter(workbook['Data'].values)
        columns = next(rows)
        if len(set(columns)) != len(columns) or not set(PROFILE_FIELDS) <= set(columns):
            raise ValueError('Unexpected report-card workbook columns')
        schools, seen, skipped = [], set(), Counter()
        for source_row, values in enumerate(rows, 2):
            row = dict(zip(columns, values))
            if row['Report Card Type'] != 'Public - All Students':
                skipped[str(row['Report Card Type'])] += 1
                continue
            if row['School Year'] != SCHOOL_YEAR or row['Agency Type'] not in {'Public school', 'Non District Charter Schools'}:
                raise ValueError('Unexpected year or agency in public report card')
            key = school_id(row)
            if key in seen:
                raise ValueError(f'Duplicate public report card: {key}')
            seen.add(key)
            schools.append(dict(school_id=key, band=band_for(row), source_row=source_row,
                                raw={field: row[field] for field in PROFILE_FIELDS}))
            for field in RATE_FIELDS.values():
                published_percentage(row[field])
        payload = dict(
            year=YEAR, retrieved=date.today().isoformat(), schools=schools,
            sources={'wi-rc-workbook': source_entry(WORKBOOK, WORKBOOK_URL),
                     'wi-rc-guide': source_entry(GUIDE, GUIDE_URL)},
            excluded_source_rows=dict(skipped),
            workbook_notes=[list(row) for row in workbook['About the Data'].values],
            field_definitions=[list(row) for row in workbook['Field Description'].values
                               if row[0] in PROFILE_FIELDS])
        # Notes include a publication date stored as an Excel date.
        EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), default=str, allow_nan=False))
    finally:
        workbook.close()


def import_data(db, payload, wise):
    if payload['year'] != YEAR:
        raise ValueError('Unexpected report-card extract year')
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))
    db.execute('INSERT OR IGNORE INTO dataset VALUES (?,?,?,?,?)',
               (DATASET, 'WI', 'Wisconsin published school totals',
                'Separate WSAS grade-school, high-school and mixed-grade report-card cohorts', 'ready'))
    sources = dict(payload['sources'])
    sources['wi-rc-extract'] = dict(path=str(EXTRACT.relative_to(ROOT)), url=WORKBOOK_URL,
                                  sha256=digest(EXTRACT))
    sources['wi-rc-wise-extract'] = dict(path=str(WISE_EXTRACT.relative_to(ROOT)),
                                      url='https://dpi.wi.gov/wisedash/public/download-files',
                                      sha256=digest(WISE_EXTRACT))
    sources['wi-rc-income'] = wise['sources'][f'wi-enrollment-{SCHOOL_YEAR}']
    sources['wi-rc-directory'] = wise['directory_source']
    for ident, source in sources.items():
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
                   (ident, DATASET, source['path'], source['url'], source['sha256'], payload['retrieved']))
    econ_id = 'wi-rc-econ-2025'
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',
               (econ_id, 'Wisconsin Economically Disadvantaged 2024-25', ECON_DEFINITION,
                sources['wi-rc-income']['url']))
    for band, (level, assessment, _) in BANDS.items():
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
                   (definition_id(DATASET, YEAR, assessment, level), 'WI', assessment, YEAR,
                    level, {'grade': '3–8', 'high': '9–11', 'mixed': '3–11'}[band],
                    'Published single-year WSAS Meeting + Advanced percentages for FAY students; '
                    'Forward, PreACT Secure, ACT and DLM as applicable to the school grade span. '
                    'No tested counts in the workbook; point estimates only. Separate grade-span '
                    'populations; not the multi-year Achievement Score or overall accountability rating.',
                    WORKBOOK_URL))
    incomes = {r['school_id']: r for r in wise['enrollment'] if r['year'] == SCHOOL_YEAR}
    seen = set()
    for record in payload['schools']:
        row, key, order = record['raw'], record['school_id'], record['source_row']
        if (key in seen or key != school_id(row) or record['band'] != band_for(row)
                or row['School Year'] != SCHOOL_YEAR
                or row['Report Card Type'] != 'Public - All Students'
                or row['Agency Type'] not in {'Public school', 'Non District Charter Schools'}):
            raise ValueError(f'Invalid or duplicate extracted report card: {key}')
        seen.add(key)
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, key, row['School Name'], key[1:5], row['District Name'], row['City'],
                    wise['directory'].get(key, {}).get('county'), json.dumps(record), 'wi-rc-workbook', order))
        income = incomes.get(key)
        if income:
            db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (DATASET, key, YEAR, econ_id, income['name'], income['enrollment'],
                        income['econ'], income['percentage'], 'Econ Disadv', json.dumps(income),
                        'wi-rc-income', order))
        level, assessment, _ = BANDS[record['band']]
        for subject, field in RATE_FIELDS.items():
            pct = published_percentage(row[field])
            db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (DATASET, key, definition_id(DATASET, YEAR, assessment, level), subject,
                        pct, None, 'reported' if pct is not None else 'suppressed_or_not_reported',
                        str(row[field]) if row[field] is not None else None, None, 'wi-rc-workbook', order))


def prepare(database=DEFAULT_DB):
    payload, wise = json.loads(EXTRACT.read_text()), json.loads(WISE_EXTRACT.read_text())
    with connect(database) as db:
        import_data(db, payload, wise)
        assessments = pl.DataFrame([dict(r) for r in db.execute('''
            SELECT a.school_id, CAST(d.year AS TEXT) AS year, d.level, d.name AS assessment,
                   a.subject, a.proficiency, a.tested
            FROM assessment_observation a JOIN assessment_definition d ON a.definition_id=d.id
            WHERE a.dataset_id=?''', (DATASET,))], infer_schema_length=None)
        incomes = pl.DataFrame([dict(r) for r in db.execute('''
            SELECT school_id, CAST(year AS TEXT) AS year, name, enrollment, low_income, percentage
            FROM economic_observation WHERE dataset_id=?''', (DATASET,))], infer_schema_length=None)
        records, models = build_history(assessments, incomes,
                                       point_only_assessments=[v[1] for v in BANDS.values()])
        save_models(db, records, models, DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Foreign key check failed')
    by_id = {r['school_id']: r for r in records}
    schools_by_band = defaultdict(list)
    for entry in payload['schools']:
        key, row, band = entry['school_id'], entry['raw'], entry['band']
        annual = by_id[key]
        for subject, field in RATE_FIELDS.items():
            if published_percentage(row[field]) is None:
                annual['exclusions'][subject] = (
                    'DPI suppressed school-total proficiency' if row[field] == '*' else
                    'School has no WSAS-tested grades' if grade_number(row['Highest Grade Level']) < 3 else
                    'DPI did not publish school-total proficiency')
        # A precise reason for Combined helps explain why a school cannot be selected.
        if 'combined' not in annual['subjects']:
            reasons = [f'{"ELA" if s == "reading" else "Math"}: {annual["exclusions"][s]}'
                       for s in RATE_FIELDS if s in annual['exclusions']]
            annual['exclusions']['combined'] = '; '.join(reasons)
        hint = wise['directory'].get(key, {})
        schools_by_band[band].append(dict(
            id=key, name=row['School Name'], short=row['School Name'], level=BANDS[band][0],
            program='Unclassified', programs=['Unclassified'], district=row['District Name'],
            city=row['City'], county=hint.get('county'), income=annual['income'],
            enrollment=annual['enrollment'], latitude=hint.get('latitude'), longitude=hint.get('longitude'),
            metrics=annual['subjects'], exclusions=annual['exclusions'], history=[annual]))
    for folder_name, bands in [('reportcards', ['grade', 'high']), ('reportcards-mixed', ['mixed'])]:
        folder = ROOT / 'data/wisconsin' / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        schools = sorted([s for band in bands for s in schools_by_band[band]], key=lambda s: s['id'])
        names = {BANDS[band][1] for band in bands}
        cohort_models = [m for m in models if m['assessment'] in names]
        levels = {BANDS[b][0]: dict(year=YEAR, label=BANDS[b][2], outcome='Meeting + advanced',
                                   math_label='Math', assessment=BANDS[b][1],
                                   note=BANDS[b][1] + ' · published rates · sampling intervals unavailable')
                  for b in bands}
        output = dict(
            year='2024–25', assessment_year=YEAR, income_label='Economically disadvantaged',
            levels=levels, program_options=['Unclassified'], schools=schools,
            models={level: {s: next((m for m in cohort_models if m['level'] == level and m['subject'] == s), None)
                            for s in ['math', 'reading', 'combined']} for level in levels},
            history_years=[YEAR], history_models=cohort_models,
            coverage_note=(f'{len(schools)} public school report cards. Published 2024–25 WSAS '
                           'Meeting + Advanced rates include DLM and the tests applicable to each grade span. '
                           'Grade schools, high schools and mixed-grade schools have separate regressions. '
                           'Income is matched by DPI school ID to 2024–25 enrollment. Counts are not supplied; '
                           'sampling intervals are unavailable. This view contains one year only; choose '
                           'Tested-count history for the separate Forward/ACT series. Suppressed values '
                           'remain unavailable. Current directory coordinates may postdate results.'))
        (folder / 'schools.json').write_text(json.dumps(output, separators=(',', ':'), allow_nan=False))
        cohort_records = [r for r in records if r['assessment'] in names]
        (folder / 'history.json').write_text(json.dumps(dict(records=cohort_records, models=cohort_models,
            exclusions=dict(Counter(reason for r in cohort_records for reason in r['exclusions'].values()))),
            separators=(',', ':'), allow_nan=False))
    baseline = json.loads((ROOT / 'data/wisconsin/schools.json').read_text())
    old_ids = {s['id'] for s in baseline['schools'] if 'combined' in s['metrics']}
    new_ids = {s['id'] for schools in schools_by_band.values() for s in schools if 'combined' in s['metrics']}
    audit = dict(year=YEAR, original_combined=len(old_ids), published_combined=len(new_ids),
                 added_ids=sorted(new_ids - old_ids), original_only_ids=sorted(old_ids - new_ids),
                 models=[{k: m[k] for k in ['assessment', 'subject', 'n', 'excluded_schools']} for m in models])
    (ROOT / 'data/wisconsin/coverage-comparison.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({k: v if not isinstance(v, list) else len(v) for k, v in audit.items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract:
        extract()
    prepare(args.database)
