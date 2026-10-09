"""Washington 2024–25 official OSPI tested-only SBAC and individual low-income eligibility."""
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET = 'wa-ospi-2025'
YEAR = 2025
RAW = ROOT/'data/raw/washington'
EXTRACT = ROOT/'data/source/washington.json'
OUTPUT = ROOT/'data/washington'
ASSESSMENT_PAGE = 'https://data.wa.gov/education/Report-Card-Assessment-Data-2024-25-School-Year/h5d9-vgwi'
ENROLLMENT_PAGE = 'https://data.wa.gov/education/Report-Card-Enrollment-2024-25-School-Year/2rwv-gs2e'
GUIDANCE = 'https://ospi.k12.wa.us/sites/default/files/2024-07/reporting_guidance_2024-25ada.pdf'
NOTES = 'https://data.wa.gov/api/views/h5d9-vgwi/files/f4862f81-7170-4645-bb71-49e195bdef72?download=true&filename=ReportCardDataNotes.xlsx'
ENROLLMENT_NOTES = 'https://data.wa.gov/api/views/2rwv-gs2e/files/53a7d0f1-3589-46b6-ad2a-e548e9dcb9c1?download=true&filename=ReportCardDataNotes.xlsx'
PRIVACY = 'https://data.wa.gov/api/views/h5d9-vgwi/files/018658f4-2d27-4ac0-bc32-4515c636af84?download=true&filename=protecting-student-privacy-public-reporting_adav3_92023.pdf'
GRADE_LABELS = {g: f'{g}{"st" if g == 1 else "nd" if g == 2 else "rd" if g == 3 else "th"} Grade' for g in range(1, 13)}
OTHER_GRADES = {'Pre-Kindergarten', 'Transition to Kindergarten', 'Kindergarten', 'Half-Day Kindergarten'}
ECON_DEFINITION = ('Same-year OSPI October primary-school enrollment, Pre-K through grade 12; '
    'CEDARS individual free/reduced-price meal eligibility or comparable-income status at any time '
    'during the school year. CNEEB applications, family income surveys and eligibility certification '
    'identify individuals; receiving universal CEP or Provision 2 meals does not make every student low-income.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def count(raw):
    if raw is None or raw == '':
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0 or value != int(value):
        raise ValueError('Washington count must be an exact nonnegative integer')
    return int(value)


def sid(row):
    key = row.get('schoolorganizationid')
    if not isinstance(key, str) or len(key) != 6 or not key.isdigit():
        raise ValueError('Washington requires the authoritative school organization ID')
    if row.get('schoolyear') != '2024-25' or row.get('organizationlevel') != 'School':
        raise ValueError('Washington requires same-year school records')
    return key


def income_values(row):
    total = count(row.get('all_students'))
    low, other = count(row.get('low_income')), count(row.get('non_low_income'))
    dat = row.get('dat', '')
    if dat not in ['', 'DAT Applied: N < 10', 'DAT Applied: > 95%', 'DAT Applied: Foster Care - N < 10']:
        raise ValueError('Unknown Washington enrollment privacy rule')
    if dat == 'DAT Applied: N < 10' or total is None or total == 0:
        return None, None, None
    if low is None or other is None:
        return total, None, None
    if low > total or other > total:
        raise ValueError('Washington low-income counts exceed enrollment')
    # DAT places zero in both protected complementary fields. Preserve those zeros
    # in provenance but never interpret them as zero eligibility or reconstruct them.
    if low+other != total:
        if dat != 'DAT Applied: > 95%' or low != 0 or other != 0:
            raise ValueError('Washington low-income complementary counts do not reconcile')
        return total, None, None
    return total, low, 100*low/total


def assessment_values(row):
    # The source also has expected-to-test and previously-passed fields. They are
    # not valid-score denominators and are intentionally never used here.
    if row.get('dat') != 'None':
        return None, None, 'OSPI disclosure avoidance applies to the assessment record'
    raw = row.get('percent_consistent_tested')
    if raw is None or raw == '':
        return None, None, 'Missing published tested-only proficiency'
    fraction = float(raw)
    if not math.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ValueError('Invalid Washington tested-only proficiency fraction')
    return 100*fraction, None, None


def level_for(entry):
    grades = {r['gradelevel'] for r in entry['grade_membership']}
    if not grades <= set(GRADE_LABELS.values()) | OTHER_GRADES:
        raise ValueError('Unknown Washington grade membership')
    if any(GRADE_LABELS[g] in grades for g in range(9, 13)):
        return 'HS'
    return 'ES' if any(GRADE_LABELS[g] in grades for g in range(3, 9)) else None


def extract(raw=RAW, destination=EXTRACT):
    raw = Path(raw)
    files = {
        'wa-assessment-2025': ('assessment.json', (raw/'assessment-url.txt').read_text()),
        'wa-enrollment-2025': ('enrollment.json', (raw/'enrollment-url.txt').read_text()),
        'wa-assessment-metadata-2025': ('assessment-metadata.json', 'https://data.wa.gov/api/views/h5d9-vgwi.json'),
        'wa-enrollment-metadata-2025': ('enrollment-metadata.json', 'https://data.wa.gov/api/views/2rwv-gs2e.json'),
        'wa-assessment-notes-2025': ('assessment-notes.xlsx', NOTES),
        'wa-enrollment-notes-2025': ('enrollment-notes.xlsx', ENROLLMENT_NOTES),
        'wa-privacy-2025': ('privacy.pdf', PRIVACY),
        'wa-cedars-guidance-2025': ('cedars-guidance.pdf', GUIDANCE),
    }
    metadata = json.loads((raw/'assessment-metadata.json').read_text())
    tested = next(c for c in metadata['columns'] if c['fieldName'] == 'percent_consistent_tested')
    if 'total count of students that received a score (levels 1 through 4) for that year' not in tested['description']:
        raise ValueError('OSPI tested-only proficiency definition changed')
    sources = {key: dict(path=str((raw/filename).relative_to(ROOT)) if (raw/filename).is_relative_to(ROOT) else str(raw/filename),
                        url=url, sha256=digest(raw/filename)) for key, (filename, url) in files.items()}
    enrollment = json.loads((raw/'enrollment.json').read_text())
    profile_rows, grades = {}, defaultdict(list)
    seen = set()
    for index, row in enumerate(enrollment, 1):
        key, grade = sid(row), row['gradelevel']
        if (key, grade) in seen:
            raise ValueError('Duplicate Washington enrollment school/grade')
        seen.add((key, grade))
        if grade == 'All Grades':
            income_values(row)
            profile_rows[key] = dict(school_id=key, source_row=index, raw=row)
        else:
            count(row.get('all_students'))
            grades[key].append({field: row.get(field) for field in ['gradelevel', 'all_students', 'dat']} | {'source_row': index})
    if set(grades)-set(profile_rows):
        raise ValueError('Washington grade membership lacks a school total')
    profiles = [dict(entry, grade_membership=grades[key]) for key, entry in sorted(profile_rows.items())]
    assessments = []
    for index, row in enumerate(json.loads((raw/'assessment.json').read_text()), 1):
        assessments.append(dict(school_id=sid(row), source_row=index, raw=row))
    payload = dict(schema_version=1, state='WA', year=YEAR, academic_year='2024-25',
                   retrieved=datetime.now(timezone.utc).isoformat(), sources=sources,
                   profiles=profiles, assessments=assessments)
    Path(destination).write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    return payload


def import_data(db, payload):
    if (payload['schema_version'], payload['state'], payload['year'], payload['academic_year']) != (1, 'WA', YEAR, '2024-25'):
        raise ValueError('Unexpected Washington source identity or school year')
    profiles = {}
    for entry in payload['profiles']:
        key, row = entry['school_id'], entry['raw']
        if key != sid(row) or key in profiles or row['gradelevel'] != 'All Grades':
            raise ValueError('Invalid or duplicate Washington school total')
        if len({r['gradelevel'] for r in entry['grade_membership']}) != len(entry['grade_membership']):
            raise ValueError('Duplicate Washington grade membership')
        level_for(entry)
        income_values(row)
        for grade in entry['grade_membership']:
            count(grade.get('all_students'))
        profiles[key] = entry
    observations, seen, ignored = [], set(), Counter()
    for entry in payload['assessments']:
        row, key = entry['raw'], entry['school_id']
        if (key != sid(row) or row['studentgroup'] != 'All Students' or row['studentgrouptype'] != 'All'
                or row['testadministration'] != 'SBAC' or row['test_administration_group'] != 'SBAC'
                or row['testsubject'] not in ['Math', 'ELA'] or row['gradelevel'] not in ['All Grades', '10']):
            raise ValueError('Washington assessment population changed')
        identity = (key, row['gradelevel'], row['testsubject'])
        if identity in seen:
            raise ValueError('Duplicate Washington school/grade/subject assessment')
        seen.add(identity)
        if key not in profiles:
            ignored['Assessment without same-year enrollment profile'] += 1
            continue
        level = level_for(profiles[key])
        if level is None or row['gradelevel'] != ('All Grades' if level == 'ES' else '10'):
            ignored['Schoolwide grades 3–8 or separate grade-10 population not applicable'] += 1
            continue
        pct, tested, exclusion = assessment_values(row)
        observations.append(dict(entry, year=YEAR, level=level, subject='math' if row['testsubject'] == 'Math' else 'reading',
            assessment='SBAC grades 3–8 tested only' if level == 'ES' else 'SBAC grade 10 tested only',
            proficiency=pct, tested=tested, exclusion=exclusion))
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?', (DATASET+':%',))
    db.execute('INSERT OR REPLACE INTO dataset VALUES (?,?,?,?,?)',
               (DATASET, 'WA', 'Washington OSPI 2024–25 SBAC', 'Separate statewide tested-only SBAC school populations', 'ready'))
    sources = dict(payload['sources'])
    sources['wa-extract-2025'] = dict(path=str(EXTRACT.relative_to(ROOT)), url=ASSESSMENT_PAGE, sha256=digest(EXTRACT))
    for ident, source in sources.items():
        if len(source['sha256']) != 64 or any(c not in '0123456789abcdef' for c in source['sha256']):
            raise ValueError('Invalid Washington source checksum')
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
                   (ident, DATASET, source['path'], source['url'], source['sha256'], payload['retrieved']))
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',
               ('wa-frpl-2025', 'OSPI individual low-income eligibility 2024–25', ECON_DEFINITION, GUIDANCE))
    for level, name in [('ES', 'SBAC grades 3–8 tested only'), ('HS', 'SBAC grade 10 tested only')]:
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
                   (definition_id(DATASET, YEAR, name, level), 'WA', name, YEAR, level,
                    '3–8' if level == 'ES' else '10',
                    'Published Percent Consistent Tested Only: current-year SBAC levels 3 and 4 / valid scores levels 1–4. '
                    'Untested and previously passed students excluded. Exact valid-score counts are unavailable; sampling intervals unavailable. '
                    + ('Native All Grades totals restricted to schools without enrolled grades 9–12; mixed-grade totals excluded.' if level == 'ES' else 'Separate grade-10 rows; All Grades totals excluded.'), ASSESSMENT_PAGE))
    for key, entry in profiles.items():
        row = entry['raw']
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, key, row['schoolname'], row['districtorganizationid'], row['districtname'], None, None,
                    json.dumps(dict(row, grade_membership=entry['grade_membership'])), 'wa-enrollment-2025', entry['source_row']))
        total, low, pct = income_values(row)
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, key, YEAR, 'wa-frpl-2025', row['schoolname'], total, low, pct,
                    'Pre-K–12 individual low-income eligibility', json.dumps(row), 'wa-enrollment-2025', entry['source_row']))
    for entry in observations:
        row = entry['raw']
        db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (DATASET, entry['school_id'], definition_id(DATASET, YEAR, entry['assessment'], entry['level']), entry['subject'],
                    entry['proficiency'], None, 'reported' if entry['proficiency'] is not None else 'suppressed_or_not_reported',
                    json.dumps(row), None, 'wa-assessment-2025', entry['source_row']))
    return profiles, observations, dict(ignored)


def prepare(database=DEFAULT_DB, output=OUTPUT):
    payload = json.loads(EXTRACT.read_text())
    with connect(database) as db:
        profiles, raw_observations, ignored = import_data(db, payload)
        observations = pl.DataFrame([{k: r[k] for k in ['school_id', 'year', 'level', 'assessment', 'subject', 'proficiency', 'tested']}
                                     for r in raw_observations], infer_schema_length=None)
        incomes = pl.DataFrame([dict(r) for r in db.execute(
            'SELECT school_id,year,name,enrollment,low_income,percentage FROM economic_observation WHERE dataset_id=?', (DATASET,))], infer_schema_length=None)
        records, models = build_history(observations, incomes,
            point_only_assessments=['SBAC grades 3–8 tested only', 'SBAC grade 10 tested only'])
        if not models:
            raise ValueError('Washington has no eligible models')
        save_models(db, records, models, DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Washington foreign key check failed')
    by_key = {(r['school_id'], r['level']): r for r in records}
    for raw in raw_observations:
        if raw['exclusion']:
            by_key[(raw['school_id'], raw['level'])]['exclusions'][raw['subject']] = raw['exclusion']
    schools = []
    for key, entry in profiles.items():
        level = level_for(entry)
        if level is None:
            continue
        row = entry['raw']
        total, _, income = income_values(row)
        annual = by_key.get((key, level))
        schools.append(dict(id=key, name=row['schoolname'], short=row['schoolname'], level=level,
            program='Unclassified', district=row['districtname'], city=None, county=row['county'],
            income=income, enrollment=total, latitude=None, longitude=None,
            metrics=annual['subjects'] if annual else {}, history=[annual] if annual else [],
            exclusions=annual['exclusions'] if annual else {s: 'No applicable published assessment population' for s in ['math', 'reading', 'combined']}))
    levels = {
        'ES': dict(year=YEAR, label='Grade schools · SBAC', assessment='SBAC grades 3–8 tested only', outcome='Consistent grade-level knowledge and above',
                   math_label='Math', note='SBAC grades 3–8 · native totals in schools without grades 9–12 · tested only'),
        'HS': dict(year=YEAR, label='High schools · SBAC', assessment='SBAC grade 10 tested only', outcome='Consistent grade-level knowledge and above',
                   math_label='Math', note='SBAC grade 10 · separate current-year tested-only results'),
    }
    details = [
        'Proficiency uses OSPI Percent Consistent Tested Only: current-year SBAC levels 3 and 4 divided by valid scores in levels 1–4. The expected-to-test outcome includes untested and previously passed students and is excluded. AIM alternate assessments and science are excluded.',
        'Grade schools use directly published All Grades SBAC totals only where same-year enrollment has no grade 9–12 rows, so all assessed grades are within 3–8. Mixed schools appear only in the high-school list and use separate grade-10 results. Their All Grades totals mix grades 3–8 and 10 and are excluded. Grade percentages are never averaged or weighted with enrollment.',
        'The native assessment table publishes no exact valid-score denominator. All tested counts and all sampling intervals remain unavailable. Expected-to-test, participation and enrollment counts never substitute for valid scores.',
        ECON_DEFINITION,
        'Any assessment DAT flag excludes the record, even if a numeric tested-only field remains. Enrollment privacy can replace protected complementary counts with zeros; only unsuppressed, reconciled Low-Income plus Non-Low Income counts are used. Suppressed eligibility is never treated as zero or reconstructed.',
        'Joins use the authoritative six-digit school organization ID and the 2024–25 school year. Whole-school income includes Pre-K, assessed-grade mix and participation are limitations. This release has one year, no admissions classifications and no map coordinates.',
    ]
    methodology = dict(summary='Washington 2024–25 current-year tested-only SBAC grades 3–8 and separate grade 10, with same-year individual low-income eligibility.',
        details=details, sources=[dict(label='OSPI 2024–25 assessment data and field definitions', url=ASSESSMENT_PAGE),
        dict(label='OSPI 2024–25 enrollment and individual low-income counts', url=ENROLLMENT_PAGE),
        dict(label='OSPI Report Card data notes', url=NOTES), dict(label='CEDARS 2024–25 eligibility guidance', url=GUIDANCE),
        dict(label='OSPI disclosure avoidance rules', url=PRIVACY)])
    result = dict(year='2024–25', assessment_year=YEAR, income_label='Low-income eligible', levels=levels,
        program_options=['Unclassified'], schools=sorted(schools, key=lambda s: s['id']),
        models={level: {s: next((m for m in models if m['level'] == level and m['subject'] == s), None)
                        for s in ['math', 'reading', 'combined']} for level in levels},
        history_years=[YEAR], history_models=models, coverage_note=' '.join(details), methodology=methodology)
    audit = dict(year=YEAR, directory_schools=len(schools), ignored_sources=ignored,
        eligible_models=[{k: m[k] for k in ['level', 'subject', 'n', 'excluded_schools']} for m in models],
        exclusions=dict(Counter(reason for r in records for reason in r['exclusions'].values())), map_coordinates=0,
        valid_score_counts='Unavailable in native source; every sampling interval omitted',
        joins='Authoritative school organization ID; same-year 2024–25 only')
    catalog = dict(schema_version=1, prepare_script='scripts/prepare_washington.py', state=dict(id='WA', name='Washington'), regions=[dict(
        id='washington', name='Statewide', dataset=DATASET, status='ready', geography='washington', levels=['ES', 'HS'],
        schools='data/washington/schools.json', boundaries=None, map_source='School coordinates are unavailable in the audited OSPI sources.',
        comparison='Comparison population: Washington statewide · {year} {note}. Separate tested-only SBAC cohorts; sampling intervals unavailable.',
        model_scope='SBAC grade-school native totals excluding mixed high-school grades, and separate grade-10 current-year tested-only results',
        audit='data/washington/audit.json')])
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    for filename, value in [('schools.json', result), ('history.json', dict(records=records, models=models)), ('audit.json', audit), ('catalog.json', catalog)]:
        (output/filename).write_text(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')
    print(json.dumps(audit, indent=2))
    return result, audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--raw', type=Path, default=RAW)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.extract:
        extract(args.raw)
    prepare(args.database, args.output)
