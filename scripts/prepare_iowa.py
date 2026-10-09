"""Iowa 2024–25 complete grade-school ISASP/DLM counts -> SQLite -> static JSON.

The default rebuild is offline. --extract reads downloaded official workbooks
listed in docs/iowa-data.md and preserves the raw cells in a compact extract.
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re

import openpyxl
import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET = 'ia-isasp-dlm'
YEAR = 2025
ASSESSMENT = 'ISASP + DLM grades 3–8 · grade schools'
EXTRACT = ROOT / 'data/source/iowa.json'
FOLDER = ROOT / 'data/iowa'
PORTAL = 'https://educate.iowa.gov/pk-12/data/education-statistics'
FILES = {
    'ia-assessment-2025': ('ia_assessment_2025.xlsx', 'https://educate.iowa.gov/media/11702/download?inline='),
    'ia-income-2025': ('ia_income_2025.xlsx', 'https://educate.iowa.gov/media/11022/download?inline='),
    'ia-grades-2025': ('ia_grades_2025.xlsx', 'https://educate.iowa.gov/media/10910/download?inline='),
    'ia-directory-2025': ('ia_directory_2025.xlsx', 'https://educate.iowa.gov/media/10250/download?inline='),
    'ia-cep-reporting': ('ia_cep_reporting.pdf', 'https://educate.iowa.gov/media/6358/download?inline='),
    'ia-sri-dictionary': ('ia_sri_dictionary.pdf', 'https://educate.iowa.gov/media/8703/download?inline='),
}
ECON_DEFINITION = (
    'Iowa 2024–25 SRI Fall K–12 students individually eligible for free or reduced-price '
    'lunch divided by same-year K–12 enrollment. Students eligible for both are counted '
    'once as free. CEP status does not confer individual eligibility: direct certification '
    'and household income information determine each student status. No CEP claiming '
    'multiplier is used. The source suppresses enrollment below 10 and FRL rates at or '
    'below 10% or at or above 90%. Pre-K is excluded from the income denominator. '
    'Incomplete household information can undercount eligibility; coverage is unknown.')
ASSESSMENT_DEFINITION = (
    'Iowa 2024–25 public school workbook, grades 3–8. Aggregate exact Proficient and Total '
    'Tested counts only when every grade has complete unsuppressed counts or published '
    'zero tested. The file includes ISASP and DLM alternate assessments and Partial '
    'Academic Year students, and excludes English learners in their first or second year '
    'enrolled in the US. Proficient / Total Tested; not a 95%-participation denominator. '
    'Grade schools have no enrolled grades 9–12 in the same-year fall snapshot.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code(value):
    if isinstance(value, (int, float)) and value == int(value):
        value = f'{int(value):04d}'
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}', value) or value == '0000':
        raise ValueError(f'Invalid Iowa district/building code: {value!r}')
    return value


def school_id(district, school):
    return code(district) + '-' + code(school)


def numeric(value):
    if value in (None, '', '***', 'small N', '≤ 10', '≥ 90'):
        return None
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Non-finite source number')
    return value


def count(value):
    value = numeric(value)
    if value is not None and (value < 0 or value != int(value)):
        raise ValueError('Invalid student count')
    return None if value is None else int(value)


def grade_school(grades):
    if len(grades) != 14 or any(count(v) is None for v in grades):
        raise ValueError('Incomplete same-year enrolled grades')
    return not any(grades[10:])  # PK, KG, grades 1–12.


def aggregate(raw):
    """Return complete score totals; never omit or reconstruct a masked grade."""
    if raw is None:
        return None, None, 'Assessment not reported'
    if len(raw) != 6 or any(len(g) != 4 for g in raw):
        raise ValueError('Expected grades 3–8, four raw fields per grade')
    proficient = tested = 0
    unavailable = False
    for cells in raw:
        if any(v in ('***', 'small N') for v in cells):
            unavailable = True
            continue
        nonprof, prof, total = [count(v) for v in cells[:3]]
        rate = numeric(cells[3])
        if None in (nonprof, prof, total):
            unavailable = True
            continue
        if nonprof + prof != total:
            raise ValueError('Grade performance counts do not sum to total tested')
        if total == 0:
            if prof != 0 or rate is not None:
                raise ValueError('Zero tested grade has a published rate')
        elif rate is None or not 0 <= rate <= 100 or abs(rate - 100 * prof / total) > .051:
            raise ValueError('Published grade rate does not reconcile to score counts')
        proficient += prof
        tested += total
    if unavailable:
        return None, None, 'At least one grade has suppressed assessment counts; incomplete aggregate'
    if tested == 0:
        return None, None, 'No tested grades 3–8'
    return 100 * proficient / tested, tested, None


def income_result(raw):
    if raw is None:
        return None, None, None, 'Same-year K–12 income not reported'
    if len(raw) != 5:
        raise ValueError('Unexpected income fields')
    enrollment, free, reduced, eligible = [count(v) for v in raw[:4]]
    rate = numeric(raw[4])
    if None in (free, reduced, eligible, rate):
        return enrollment, None, None, 'Iowa suppressed individual FRL eligibility'
    if enrollment is None or enrollment <= 0 or free + reduced != eligible or eligible > enrollment:
        raise ValueError('Invalid individual income counts')
    if not 0 <= rate <= 100 or abs(rate - 100 * eligible / enrollment) > .0051:
        raise ValueError('Published income rate does not reconcile to counts')
    return enrollment, eligible, 100 * eligible / enrollment, None


def worksheet(path, name=None):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return list((book[name] if name else book.worksheets[0]).values)
    finally:
        book.close()


def extract():
    sources = {key: dict(path='data/raw/' + filename, url=url,
        sha256=digest(ROOT / 'data/raw' / filename)) for key, (filename, url) in FILES.items()}
    read = lambda key, name=None: worksheet(ROOT / sources[key]['path'], name)
    grades = read('ia-grades-2025')
    incomes = read('ia-income-2025')
    if grades[4][8:23] != ('PK', 'KG', 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4',
            'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9', 'Grade 10', 'Grade 11', 'Grade 12', 'School Total'):
        raise ValueError('Unexpected enrolled-grade layout')
    if incomes[7][8:13] != ('K-12 Enrollment', 'Number Eligible for Free Lunch',
            'Number Eligible for Reduced Price Lunch', 'Number Eligible for Free or Reduced Price Lunch',
            'Percent Eligible for Free or Reduced Price Lunch'):
        raise ValueError('Unexpected individual FRL layout')
    schools, excluded_enrollment = {}, []
    for rownum, row in enumerate(grades[5:], 6):
        if not row[4]:
            continue
        if row[6] == '0000':
            excluded_enrollment.append(dict(source_row=rownum, raw=list(row[:23]), reason='District-level enrollment is not a school'))
            continue
        key = school_id(row[4], row[6])
        if key in schools:
            raise ValueError('Duplicate district/building ID')
        values = list(row[8:22])
        if sum(values) != count(row[22]):
            raise ValueError('Grade enrollment does not reconcile to school total')
        schools[key] = dict(school_id=key, district_id=code(row[4]), name=row[7], district=row[5],
            grades=values, grade_school=grade_school(values), grade_source_row=rownum,
            identity_raw=list(row[:8]), income_raw=None, income_source_row=0, cep=None, directory={})
    for rownum, row in enumerate(incomes[8:], 9):
        if not row[4]:
            continue
        if row[6] == '0000':
            continue
        key = school_id(row[4], row[6])
        if key not in schools or schools[key]['income_raw'] is not None:
            raise ValueError('Unmatched or duplicate income ID')
        if count(row[8]) != sum(schools[key]['grades'][1:]):
            raise ValueError('K–12 income enrollment disagrees with same-year grades')
        raw = list(row[8:13])
        income_result(raw)
        schools[key].update(income_raw=raw, income_source_row=rownum,
            income_identity_raw=list(row[:8]), cep=row[13])
    for row in read('ia-directory-2025')[6:]:
        if row[3] is None or row[5] is None or not str(row[3]).isdigit():
            continue
        key = school_id(row[3], row[5])
        if key in schools:
            if schools[key]['directory']:
                raise ValueError('Ambiguous directory ID')
            schools[key]['directory'] = dict(city=row[13], county=row[1], grades=row[21], level=row[20])
    observations = []
    for subject, sheet in [('math', 'Math'), ('reading', 'ELA')]:
        rows = read('ia-assessment-2025', sheet)
        if '2024-25' not in rows[0][0] or rows[6][7:11] != ('Grade 3 Not Proficient',
                'Grade 3 Proficient', 'Grade 3 Total Tested', 'Grade 3 % Proficient'):
            raise ValueError('Wrong assessment year or schema')
        for rownum, row in enumerate(rows[7:], 8):
            if not row[3]:
                continue
            key = school_id(row[3], row[4])
            if key not in schools:
                raise ValueError('Assessment lacks same-year public enrollment')
            raw = [list(row[7 + 5 * i:11 + 5 * i]) for i in range(6)]
            aggregate(raw)
            observations.append(dict(school_id=key, subject=subject, source_row=rownum,
                identity_raw=list(row[:7]), raw=raw))
    payload = dict(state='IA', year=YEAR, school_year='2024-25', retrieved=str(date.today()),
        sources=sources, schools=list(schools.values()), assessments=observations,
        excluded_enrollment=excluded_enrollment,
        income_guidance='CEP/SRI guide predates this year; current SRI dictionary download is 2026–27, rev. 8/14/26. Neither replaces the 2024–25 numeric snapshot.')
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))


def import_data(db, payload):
    if (payload['state'], payload['year'], payload['school_year']) != ('IA', YEAR, '2024-25'):
        raise ValueError('Wrong Iowa year/state')
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))
    db.execute('INSERT OR IGNORE INTO dataset VALUES (?,?,?,?,?)',
        (DATASET, 'IA', 'Iowa ISASP/DLM 2025', 'Complete public grade-school grades 3–8 score aggregates', 'ready'))
    for ident, source in dict(payload['sources'], **{'ia-extract': dict(path=str(EXTRACT.relative_to(ROOT)), url=PORTAL, sha256=digest(EXTRACT))}).items():
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
            (ident, DATASET, source['path'], source['url'], source['sha256'], payload['retrieved']))
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',
        ('ia-frl-2025', 'Iowa individual K–12 free/reduced-price lunch eligibility 2024–25', ECON_DEFINITION, FILES['ia-cep-reporting'][1]))
    ident = definition_id(DATASET, YEAR, ASSESSMENT, 'ES')
    db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
        (ident, 'IA', ASSESSMENT, YEAR, 'ES', '3–8', ASSESSMENT_DEFINITION, FILES['ia-assessment-2025'][1]))
    profiles = {}
    for order, profile in enumerate(payload['schools']):
        key = school_id(profile['district_id'], profile['school_id'].split('-')[-1])
        identity = profile['identity_raw']
        if (key in profiles or key != profile['school_id'] or key != school_id(identity[4], identity[6])
                or profile['name'] != identity[7] or profile['district'] != identity[5]
                or profile['grade_school'] != grade_school(profile['grades'])):
            raise ValueError('Duplicate identity or wrong grade scope')
        profiles[key] = profile
        if not profile['grade_school']:
            continue
        raw = profile['income_raw']
        enrollment, eligible, percentage, _ = income_result(raw)
        if raw is not None and enrollment != sum(profile['grades'][1:]):
            raise ValueError('Income is not same-year K–12 enrollment')
        if raw is not None and key != school_id(profile['income_identity_raw'][4], profile['income_identity_raw'][6]):
            raise ValueError('Income identity does not match public enrolled-school ID')
        hint = profile['directory']
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
            (DATASET, key, profile['name'], profile['district_id'], profile['district'],
             hint.get('city'), hint.get('county'), json.dumps(profile), 'ia-extract', order))
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (DATASET, key, YEAR, 'ia-frl-2025', profile['name'], enrollment, eligible,
             percentage, 'Individual FRL eligibility', json.dumps(profile), 'ia-income-2025', profile['income_source_row']))
    observations = {}
    for record in payload['assessments']:
        key = (record['school_id'], record['subject'])
        if (key in observations or key[0] not in profiles or key[1] not in ['math', 'reading']
                or key[0] != school_id(record['identity_raw'][3], record['identity_raw'][4])):
            raise ValueError('Duplicate or invalid assessment identity')
        aggregate(record['raw'])
        observations[key] = record
    for key, profile in profiles.items():
        if not profile['grade_school']:
            continue
        for subject in ['math', 'reading']:
            record = observations.get((key, subject), {})
            pct, tested, reason = aggregate(record.get('raw'))
            db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (DATASET, key, ident, subject, pct, tested, 'reported' if reason is None else
                 'suppressed_or_not_reported' if 'suppressed' in reason else 'not_reported',
                 json.dumps(record.get('raw')), str(tested) if tested is not None else None,
                 'ia-assessment-2025', record.get('source_row', 0)))


def prepare(database=DEFAULT_DB):
    payload = json.loads(EXTRACT.read_text())
    with connect(database) as db:
        import_data(db, payload)
        assessments = pl.DataFrame([dict(r) for r in db.execute('''SELECT a.school_id,
            CAST(d.year AS TEXT) AS year, d.level, d.name AS assessment, a.subject,
            a.proficiency, a.tested FROM assessment_observation a JOIN assessment_definition d
            ON a.definition_id=d.id WHERE a.dataset_id=?''', (DATASET,))])
        incomes = pl.DataFrame([dict(r) for r in db.execute('''SELECT school_id, CAST(year AS TEXT)
            AS year, name, enrollment, low_income, percentage, source_label AS income_label
            FROM economic_observation WHERE dataset_id=?''', (DATASET,))])
        records, models = build_history(assessments, incomes)
        save_models(db, records, models, DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Foreign key check failed')
    annuals = {r['school_id']: r for r in records}
    observations = {(r['school_id'], r['subject']): r for r in payload['assessments']}
    schools = []
    for profile in payload['schools']:
        if not profile['grade_school']:
            continue
        key = profile['school_id']
        annual = annuals[key]
        _, _, _, income_reason = income_result(profile['income_raw'])
        for subject in ['math', 'reading']:
            if subject not in annual['subjects']:
                _, _, assessment_reason = aggregate(observations.get((key, subject), {}).get('raw'))
                annual['exclusions'][subject] = '; '.join(filter(None, [income_reason, assessment_reason])) or annual['exclusions'].get(subject, 'Model unavailable')
        if 'combined' not in annual['subjects']:
            annual['exclusions']['combined'] = '; '.join(f'{"ELA" if s == "reading" else "Math"}: {annual["exclusions"][s]}' for s in ['math', 'reading'] if s in annual['exclusions'])
        hint = profile['directory']
        schools.append(dict(id=key, name=profile['name'], short=profile['name'], level='ES',
            program='Unclassified', programs=['Unclassified'], district=profile['district'],
            city=hint.get('city'), county=hint.get('county'), latitude=None, longitude=None,
            income=annual['income'], enrollment=annual['enrollment'], metrics=annual['subjects'],
            exclusions=annual['exclusions'], history=[annual]))
    methodology = dict(summary='Iowa grade-school models use complete grades 3–8 ISASP/DLM score counts and same-year individual K–12 lunch eligibility.',
        details=[ECON_DEFINITION, ASSESSMENT_DEFINITION,
            'Every grade in an aggregate must have unsuppressed counts or a published zero tested. Suppressed grades invalidate that subject for the school; they are never inferred or dropped. The final rate is computed from exact proficient / tested totals, not an average of rounded grade percentages.',
            'Combined is the equally weighted mean of math and ELA. Externally studentized residuals compare each school with a model fit to the complete eligible Iowa grade-school population. Verified score denominators support sampling intervals; enrollment is never a tested-count substitute.',
            'Schools with any enrolled grades 9–12 are excluded from this grade-school snapshot. Fall income enrollment excludes pre-K; fall grade scope includes pre-K. Income eligibility is a proxy, not direct income. Results describe associations, not causal school effectiveness.',
            'Only 2024–25 is available here. The published file combines ISASP and DLM and differs from accountability measures that exclude partial-year students. No school-coordinate crosswalk has been imported; these schools remain available in the list and charts.'],
        sources=[dict(label='Official Iowa source files', url=PORTAL),
                 dict(label='Public school ISASP/DLM score counts', url=FILES['ia-assessment-2025'][1]),
                 dict(label='Same-year individual FRL eligibility', url=FILES['ia-income-2025'][1]),
                 dict(label='Same-year fall enrolled grades', url=FILES['ia-grades-2025'][1]),
                 dict(label='Individual eligibility at CEP schools', url=FILES['ia-cep-reporting'][1])])
    output = dict(year='2024–25', assessment_year=YEAR, income_label='Individual K–12 free/reduced-price lunch eligibility',
        levels=dict(ES=dict(year=YEAR, label='Grade schools · ISASP + DLM', assessment=ASSESSMENT,
            outcome='Proficient or above', math_label='Math', note='Complete grades 3–8 score aggregates')),
        program_options=['Unclassified'], schools=schools, models=dict(ES={s: next((m for m in models if m['subject']==s), None) for s in ['math', 'reading', 'combined']}),
        history_years=[YEAR], history_models=models, methodology=methodology,
        coverage_note='Iowa 2024–25 grade schools only: no enrolled grades 9–12. Complete unsuppressed grade 3–8 ISASP/DLM score counts, including partial-year students; first/second-year US English learners excluded. Same-year individual K–12 FRL eligibility; extreme FRL rates suppressed. School coordinates unavailable. One year only.')
    FOLDER.mkdir(parents=True, exist_ok=True)
    (FOLDER / 'schools.json').write_text(json.dumps(output, separators=(',', ':'), allow_nan=False))
    (FOLDER / 'history.json').write_text(json.dumps(dict(records=records, models=models), separators=(',', ':'), allow_nan=False))
    (FOLDER / 'catalog.json').write_text(json.dumps(dict(schema_version=1, prepare_script='scripts/prepare_iowa.py', state=dict(id='IA', name='Iowa'), regions=[dict(id='iowa', name='Grade schools', dataset=DATASET, status='ready', geography='iowa', levels=['ES'], schools='data/iowa/schools.json', boundaries=None, comparison='Iowa · {year} · ISASP + DLM · {note}', model_scope='Public grade schools with complete grades 3–8 score aggregates and same-year individual FRL eligibility', map_source='School coordinates unavailable; no authoritative school-ID coordinate crosswalk imported')]), indent=2)+'\n')
    audit = dict(year=YEAR, public_enrollment_schools=len(payload['schools']), grade_schools=len(schools),
        excluded_district_level_enrollment=len(payload['excluded_enrollment']),
        excluded_high_or_mixed=sum(not p['grade_school'] for p in payload['schools']),
        eligible={m['subject']:m['n'] for m in models}, mapped=0,
        income_exclusions=dict(Counter(income_result(p['income_raw'])[3] for p in payload['schools'] if p['grade_school'] and income_result(p['income_raw'])[3])),
        assessment_exclusions={s:dict(Counter(aggregate(observations.get((p['school_id'],s),{}).get('raw'))[2] for p in payload['schools'] if p['grade_school'] and aggregate(observations.get((p['school_id'],s),{}).get('raw'))[2])) for s in ['math','reading']})
    (FOLDER / 'coverage.json').write_text(json.dumps(audit, indent=2)+'\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract:
        extract()
    prepare(args.database)
