"""Audited Massachusetts 2025 native MCAS totals and October low-income enrollment.

Rebuild offline from the committed extract. --extract reads the official files
listed in docs/massachusetts-data.md; no implicit network requests are made.
"""
import argparse
from collections import Counter
from datetime import date
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import polars as pl

from database import ROOT, DEFAULT_DB, connect, definition_id, save_models
from prepare_data import build_history

DATASET = 'ma-mcas'
YEAR = 2025
EXTRACT = ROOT / 'data/source/massachusetts.json'
PORTAL = 'https://educationtocareer.data.mass.gov'
ASSESSMENT_URL = PORTAL + '/resource/i9w6-niyt.json?%24where=sy%3D%272025%27+AND+org_type+in%28%27Public+School%27%2C%27Charter+School%27%29+AND+stu_grp%3D%27All+Students%27+AND+subject_code+in%28%27ELA%27%2C%27MATH%27%29&%24limit=50000&%24order=org_code%2Ctest_grade%2Csubject_code'
ENROLLMENT_URL = PORTAL + '/resource/t8td-gens.json?%24where=sy%3D%272025%27+AND+org_type%3D%27School%27&%24limit=50000&%24order=org_code'
NCES = 'https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2324/MapServer/0'
FILES = {
    'ma-assessment-2025': ('ma-mcas-2025.json', ASSESSMENT_URL),
    'ma-income-2025': ('ma-enrollment-2025.json', ENROLLMENT_URL),
    'ma-assessment-metadata': ('ma-mcas-metadata.json', PORTAL + '/api/views/i9w6-niyt.json'),
    'ma-income-metadata': ('ma-enrollment-metadata.json', PORTAL + '/api/views/t8td-gens.json'),
    'ma-assessment-definition': ('ma-assessment-definition.html', 'https://profiles.doe.mass.edu/help/data.aspx?section=assess'),
    'ma-income-definition': ('ma-enrollment-definition.html', 'https://profiles.doe.mass.edu/help/data.aspx?section=students'),
    'ma-technical-2025': ('ma-mcas-technical-2025.pdf', 'https://www.doe.mass.edu/mcas/tech/2025-technical-report.pdf'),
    'ma-ccd-crosswalk-2025': ('ccd_sch_033_2425_l_1a_073025.zip', 'https://nces.ed.gov/ccd/Data/zip/ccd_sch_033_2425_l_1a_073025.zip'),
    'ma-locations-2024': ('ma-nces-locations-2024.json', NCES + '/query?where=STATE%3D%27MA%27&outFields=NCESSCH%2CNAME%2CCITY%2CNMCNTY%2CLAT%2CLON%2CSCHOOLYEAR&f=json&returnGeometry=false&resultRecordCount=5000'),
}
GRADES = ['pk_cnt', 'k_cnt'] + [f'g{i}_cnt' for i in range(1, 13)] + ['sp_cnt']
RESULT_FIELDS = ['m_plus_e_pct', 'm_plus_e_cnt', 'e_cnt', 'm_cnt', 'pm_cnt', 'nm_cnt', 'stu_cnt', 'stu_part_pct']
BANDS = {
    'grade': ('ES', 'MCAS grades 3–8 · grade schools', 'Grade schools · MCAS', 'ALL (03-08)'),
    'high': ('HS', 'MCAS grade 10 · high schools', 'High schools · MCAS', '10'),
    'mixed': ('HS', 'MCAS grades 3–8 · mixed-grade schools', 'Mixed-grade schools · MCAS grades 3–8', 'ALL (03-08)'),
}
ECON_DEFINITION = (
    'Massachusetts published Low Income percentage of October 1, 2024 enrollment for '
    'school year 2024–25, from SIMS. Since 2022, classification includes SNAP, TAFDC, '
    'DCF foster care and expanded MassHealth/Medicaid benefits up to 185% of the federal '
    'poverty level, district-reported homeless students, and supplemental low-income '
    'students confirmed through the documented DESE application process. This is not '
    'the narrower 2015–21 Economically Disadvantaged definition or a universal-meal '
    'participation count. Use the published percentage, preserving low-income and '
    'enrollment counts; enrollment includes pre-K and students beyond grade 12.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def school_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{8}', value) or value == '00000000':
        raise ValueError(f'Invalid Massachusetts organization code: {value!r}')
    return value


def count(value):
    if value is None or value in ('', '*', '**', '***', 'NA'):
        return None
    if not re.fullmatch(r'\d+', str(value)):
        raise ValueError(f'Invalid student count: {value!r}')
    return int(value)


def proportion(value):
    if value is None or value in ('', '*', '**', '***', 'NA'):
        return None
    result = float(value)
    if not 0 <= result <= 1:
        raise ValueError(f'Invalid published proportion: {value!r}')
    return result


def band_for(raw):
    total = count(raw.get('total_cnt'))
    if total is None:
        raise ValueError('Missing same-year enrollment total')
    if total == 0:
        # A zero-total school has no modeled grade population. Missing grade cells
        # remain raw missing cells; they are not converted into grade observations.
        return 'no-enrollment'
    grades = [count(raw.get(field)) for field in GRADES]
    if any(v is None for v in grades) or sum(grades) != total:
        raise ValueError('Incomplete or inconsistent same-year grade enrollment')
    low, high = any(grades[:10]), any(grades[10:])
    return 'mixed' if low and high else 'high' if high else 'grade'


def result(raw):
    """Keep native published totals; never infer suppressed rates from their counts."""
    pct = proportion(raw.get('m_plus_e_pct'))
    if pct is None:
        return None, None
    values = [count(raw.get(field)) for field in RESULT_FIELDS[1:7]]
    if any(v is None for v in values):
        raise ValueError('Published MCAS percentage lacks achievement-level counts')
    proficient, exceeding, meeting, partial, not_meeting, tested = values
    if tested < 10 or exceeding + meeting != proficient or sum(values[1:5]) != tested:
        raise ValueError('MCAS achievement-level counts do not reconcile')
    # Profiles percentages are rounded to whole percentage points. Preserve that
    # reported outcome rather than replacing it with a more precise inferred rate.
    if abs(proficient / tested - pct) > .005000001:
        raise ValueError('Published MCAS rate differs from valid-score counts')
    proportion(raw.get('stu_part_pct'))  # Separate metadata, never the denominator.
    return pct * 100, tested


def income(raw):
    total, low, pct = count(raw.get('total_cnt')), count(raw.get('li_cnt')), proportion(raw.get('li_pct'))
    if low is not None and (total is None or low > total):
        raise ValueError('Low-income count exceeds enrollment')
    if pct is not None and total:
        if low is None or abs(low / total - pct) > .000500001:
            raise ValueError('Published low-income percentage differs from enrollment counts')
    return total, low, pct * 100 if pct is not None and total else None


def extract():
    sources = {key: dict(path='data/raw/' + filename, url=url,
                        sha256=digest(ROOT / 'data/raw' / filename))
               for key, (filename, url) in FILES.items()}
    enrollment = json.loads((ROOT / sources['ma-income-2025']['path']).read_text())
    assessment = json.loads((ROOT / sources['ma-assessment-2025']['path']).read_text())
    if len(enrollment) != 1817 or len(assessment) != 11848:
        raise ValueError('2025 source counts differ from independently queried API counts')
    crosswalk = {}
    with zipfile.ZipFile(ROOT / sources['ma-ccd-crosswalk-2025']['path']) as archive:
        member = 'ccd_sch_033_2425_l_1a_073025.csv'
        for row in csv.DictReader(io.TextIOWrapper(archive.open(member), encoding='utf-8-sig')):
            if row['ST'] != 'MA':
                continue
            match = re.fullmatch(r'MA-\d{4}-(\d{8})', row['ST_SCHID'])
            if not match or row['SCHOOL_YEAR'] != '2024-2025' or not re.fullmatch(r'25\d{10}', row['NCESSCH']):
                raise ValueError('Invalid official CCD Massachusetts crosswalk')
            key = school_id(match[1])
            hint = dict(nces_id=row['NCESSCH'], state_id_raw=row['ST_SCHID'])
            if key in crosswalk and crosswalk[key] != hint:
                raise ValueError('Ambiguous CCD school crosswalk')
            crosswalk[key] = hint
    locations = json.loads((ROOT / sources['ma-locations-2024']['path']).read_text())
    if locations.get('error') or locations.get('exceededTransferLimit'):
        raise ValueError('Incomplete official NCES coordinate query')
    points = {}
    for feature in locations['features']:
        row = feature['attributes']
        if row['SCHOOLYEAR'] != '2023-2024' or row['NCESSCH'] in points:
            raise ValueError('Wrong-year or duplicate NCES location')
        lat, lon = row['LAT'], row['LON']
        if lat is not None and lon is not None and 41 <= lat <= 43 and -74 <= lon <= -69:
            points[row['NCESSCH']] = dict(latitude=lat, longitude=lon, city=row['CITY'], county=row['NMCNTY'])
    schools, seen = [], set()
    fields = ['sy', 'dist_code', 'dist_name', 'org_code', 'org_name', 'org_type',
              'total_cnt', 'li_cnt', 'li_pct', *GRADES]
    for order, raw in enumerate(enrollment):
        key = school_id(raw['org_code'])
        if raw['sy'] != str(YEAR) or raw['org_type'] != 'School' or key in seen:
            raise ValueError('Wrong-year or duplicate enrollment identity')
        seen.add(key)
        selected = {field: raw.get(field) for field in fields}
        income(selected)
        hint = crosswalk.get(key, {})
        schools.append(dict(school_id=key, raw=selected, band=band_for(selected), source_row=order,
                            location=dict(hint, **points.get(hint.get('nces_id'), {}))))
    assessments, excluded, seen = [], [], set()
    for order, raw in enumerate(assessment):
        key = (school_id(raw['org_code']), raw['test_grade'], raw['subject_code'])
        if (raw['sy'] != str(YEAR) or raw['org_type'] not in {'Public School', 'Charter School'}
                or raw['stu_grp'] != 'All Students' or raw['subject_code'] not in {'ELA', 'MATH'} or key in seen):
            raise ValueError('Wrong-year, invalid or duplicate MCAS identity')
        seen.add(key)
        selected = {field: raw.get(field) for field in ['sy', 'org_code', 'org_type', 'stu_grp',
                                                     'test_grade', 'subject_code', *RESULT_FIELDS]}
        result(selected)
        record = dict(school_id=key[0], source_row=order, raw=selected)
        (assessments if key[0] in {s['school_id'] for s in schools} else excluded).append(record)
    payload = dict(year=YEAR, school_year='2024-25', retrieved=date.today().isoformat(),
        sources=sources, schools=schools, assessments=assessments, excluded_assessments=excluded,
        count_query_verified=dict(enrollment=1817, assessment=11848),
        technical_evidence=dict(aggregate_rules_pdf_pages=[1115, 1116, 1117],
            business_rules_pages=[25, 26, 27],
            population='Summarize=1 and TestStatus=T, official school; first-year EL and non-score statuses excluded. General assessment only in this E2C dataset.',
            valid_denominator='Sum of Exceeding, Meeting, Partially Meeting and Not Meeting achievement-level counts; separate participation rate unused.'))
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))


def import_data(db, payload):
    if payload['year'] != YEAR or payload['school_year'] != '2024-25':
        raise ValueError('Wrong Massachusetts school year')
    profiles, observations = {}, {}
    for profile in payload['schools']:
        raw, key = profile['raw'], school_id(profile['school_id'])
        if (key != school_id(raw['org_code']) or key in profiles or raw['sy'] != str(YEAR)
                or raw['org_type'] != 'School' or profile['band'] != band_for(raw)):
            raise ValueError('Invalid school identity or grade scope')
        school_id(raw['dist_code'])
        income(raw)
        profiles[key] = profile
    for record in payload['assessments']:
        raw, key = record['raw'], school_id(record['school_id'])
        index = (key, raw['test_grade'], raw['subject_code'])
        if (key != school_id(raw['org_code']) or key not in profiles or index in observations
                or raw['sy'] != str(YEAR) or raw['stu_grp'] != 'All Students'
                or raw['org_type'] not in {'Public School', 'Charter School'}
                or raw['subject_code'] not in {'ELA', 'MATH'}):
            raise ValueError('Invalid same-year MCAS identity')
        result(raw)
        observations[index] = record
    for table in ['model_run', 'assessment_observation', 'economic_observation', 'school', 'source']:
        db.execute(f'DELETE FROM {table} WHERE dataset_id=?', (DATASET,))
    db.execute('DELETE FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))
    db.execute('INSERT OR IGNORE INTO dataset VALUES (?,?,?,?,?)',
        (DATASET, 'MA', 'Massachusetts MCAS 2025', 'Separate grade-school, high-school and mixed-grade MCAS cohorts', 'ready'))
    sources = dict(payload['sources'], **{'ma-extract': dict(path=str(EXTRACT.relative_to(ROOT)),
        url=ASSESSMENT_URL, sha256=digest(EXTRACT))})
    for ident, source in sources.items():
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
            (ident, DATASET, source['path'], source['url'], source['sha256'], payload['retrieved']))
    db.execute('INSERT OR REPLACE INTO economic_definition VALUES (?,?,?,?)',
        ('ma-low-income-2025', 'Massachusetts Low Income 2024–25', ECON_DEFINITION, FILES['ma-income-definition'][1]))
    for band, (level, assessment, _, grade) in BANDS.items():
        db.execute('INSERT INTO assessment_definition VALUES (?,?,?,?,?,?,?,?)',
            (definition_id(DATASET, YEAR, assessment, level), 'MA', assessment, YEAR, level,
             '10' if grade == '10' else '3–8',
             'Spring 2025 Next-Generation MCAS general assessment, published Meeting + Exceeding '
             'Expectations percentage for All Students; native ALL (03-08) school total or grade '
             '10. Score denominators reconcile to four achievement levels. MCAS-Alt is excluded. '
             'Only accountable test-status T students, aggregated to official schools; '
             'not participation, growth, or the federal minimum-95% accountability denominator.',
             FILES['ma-technical-2025'][1]))
    for key, profile in profiles.items():
        raw, hint = profile['raw'], profile['location']
        db.execute('INSERT INTO school VALUES (?,?,?,?,?,?,?,?,?,?)',
            (DATASET, key, raw['org_name'], raw['dist_code'], raw['dist_name'],
             hint.get('city'), hint.get('county'), json.dumps(profile), 'ma-extract', profile['source_row']))
        total, low, pct = income(raw)
        db.execute('INSERT INTO economic_observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (DATASET, key, YEAR, 'ma-low-income-2025', raw['org_name'], total, low, pct,
             'Low Income', json.dumps(raw), 'ma-income-2025', profile['source_row']))
        if profile['band'] not in BANDS:
            continue
        level, assessment, _, grade = BANDS[profile['band']]
        for subject, code in [('math', 'MATH'), ('reading', 'ELA')]:
            record = observations.get((key, grade, code), {})
            result_raw = record.get('raw', {})
            value, tested = result(result_raw)
            db.execute('INSERT INTO assessment_observation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (DATASET, key, definition_id(DATASET, YEAR, assessment, level), subject, value, tested,
                 'reported' if value is not None else 'suppressed_or_not_reported',
                 result_raw.get('m_plus_e_pct'), result_raw.get('stu_cnt'),
                 'ma-assessment-2025', record.get('source_row', 0)))


def prepare(database=DEFAULT_DB):
    payload = json.loads(EXTRACT.read_text())
    with connect(database) as db:
        import_data(db, payload)
        assessments = pl.DataFrame([dict(r) for r in db.execute('''
            SELECT a.school_id, CAST(d.year AS TEXT) AS year, d.level, d.name AS assessment,
                   a.subject, a.proficiency, a.tested FROM assessment_observation a
            JOIN assessment_definition d ON a.definition_id=d.id WHERE a.dataset_id=?''', (DATASET,))])
        incomes = pl.DataFrame([dict(r) for r in db.execute('''
            SELECT school_id, CAST(year AS TEXT) AS year, name, enrollment, low_income, percentage,
                   source_label AS income_label FROM economic_observation WHERE dataset_id=?''', (DATASET,))])
        records, models = build_history(assessments, incomes)
        save_models(db, records, models, DATASET)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Foreign key check failed')
    by_id = {r['school_id']: r for r in records}
    coverage, regions = {}, []
    for folder_name, bands in [('', ['grade', 'high']), ('mixed', ['mixed'])]:
        folder = ROOT / 'data/massachusetts' / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        schools = []
        for profile in payload['schools']:
            band = profile['band']
            if band not in bands:
                continue
            raw, hint, key = profile['raw'], profile['location'], profile['school_id']
            annual = by_id[key]
            for subject in ['math', 'reading']:
                if subject not in annual['subjects'] and annual['exclusions'].get(subject) == 'Missing or suppressed proficiency':
                    annual['exclusions'][subject] = 'DESE did not publish an unsuppressed native MCAS total (minimum 10 scored students)'
            if 'combined' not in annual['subjects']:
                annual['exclusions']['combined'] = '; '.join(
                    f'{"ELA" if s == "reading" else "Math"}: {annual["exclusions"][s]}'
                    for s in ['math', 'reading'] if s in annual['exclusions'])
            schools.append(dict(id=key, name=raw['org_name'], short=raw['org_name'], level=BANDS[band][0],
                program='Unclassified', programs=['Unclassified'], district=raw['dist_name'],
                city=hint.get('city'), county=hint.get('county'), latitude=hint.get('latitude'), longitude=hint.get('longitude'),
                income=annual['income'], enrollment=annual['enrollment'], metrics=annual['subjects'],
                exclusions=annual['exclusions'], history=[annual]))
        names = {BANDS[band][1] for band in bands}
        selected_models = [m for m in models if m['assessment'] in names]
        selected_records = [r for r in records if r['assessment'] in names]
        levels = {BANDS[band][0]: dict(year=YEAR, label=BANDS[band][2], assessment=BANDS[band][1],
            outcome='Meeting + exceeding expectations', math_label='Math',
            note='MCAS grade 10' if band == 'high' else 'MCAS grades 3–8 · native school totals') for band in bands}
        methodology = dict(summary='Separate Massachusetts models compare published MCAS proficiency with same-year Low Income enrollment.',
            details=[ECON_DEFINITION,
                'Use published ALL (03-08) school totals or grade 10 percentages, retaining their whole-percentage-point rounding. No grade rates are averaged and no masked grade outcome is reconstructed.',
                'The four achievement-level counts sum to the number of included scores; Meeting + Exceeding sums to the proficient count. The separate participation rate is never a score denominator. Reporting rules use accountable test-status T students aggregated to official schools; first-year EL and non-score statuses are excluded. This dataset excludes MCAS-Alt.',
                'Grade schools have no October enrolled grade 9 or higher; pure high schools have no enrolled pre-K through grade 8. Mixed-grade schools have a separate grades 3–8 comparison. Their grade 10 outcomes are retained in the audit extract but are not pooled into the pure-high-school model.',
                'Externally studentized residuals use complete state cohort populations by level and subject. Combined is the equally weighted mean of math and ELA. Sampling intervals use verified included-score denominators. Associations do not measure causal school effectiveness.',
                'CCD 2024–25 Massachusetts state IDs provide an exact organization-code crosswalk to NCES 2023–24 coordinates. CCD lunch values are not used for income. Locations never control model membership. One audited year is available; assessment and income definition changes require separate historical audits.'],
            sources=[dict(label=label, url=FILES[key][1]) for key, label in [
                ('ma-assessment-2025', 'Official MCAS results'), ('ma-income-2025', 'Same-year October enrollment'),
                ('ma-income-definition', 'DESE Low Income definition'), ('ma-assessment-definition', 'DESE suppression rules'),
                ('ma-technical-2025', '2025 MCAS technical and reporting rules'),
                ('ma-ccd-crosswalk-2025', 'Official NCES state-ID crosswalk'), ('ma-locations-2024', 'Official NCES coordinates')]])
        mapped = sum(s['latitude'] is not None for s in schools)
        note = (f'{len(schools)} public schools; {mapped} mapped through exact state and NCES IDs. '
            'Spring 2025 Next-Generation MCAS All Students Meeting + Exceeding Expectations, '
            'general assessment only. Native grades 3–8 totals and grade 10 use separate models; '
            'mixed-grade schools have their own grades 3–8 comparison. October 2024 Low Income '
            'enrollment is school year 2024–25. Missing or suppressed totals stay unavailable. '
            'Only 2025 is audited; MCAS-Alt and mixed-school grade 10 are not modeled. '
            'Coordinates are NCES 2023–24, with a 2024–25 CCD identity crosswalk.')
        output = dict(year='2024–25', assessment_year=YEAR, income_label='Reported Low Income enrollment',
            levels=levels, program_options=['Unclassified'], schools=schools,
            models={level: {subject: next((m for m in selected_models if m['level'] == level and m['subject'] == subject), None)
                           for subject in ['math', 'reading', 'combined']} for level in levels},
            history_years=[YEAR], history_models=selected_models, coverage_note=note, methodology=methodology)
        (folder / 'schools.json').write_text(json.dumps(output, separators=(',', ':'), allow_nan=False))
        (folder / 'history.json').write_text(json.dumps(dict(records=selected_records, models=selected_models,
            exclusions=dict(Counter(reason for r in selected_records for reason in r['exclusions'].values()))),
            separators=(',', ':'), allow_nan=False))
        path = str(folder.relative_to(ROOT))
        regions.append(dict(id='massachusetts-mixed' if folder_name else 'massachusetts',
            name='Mixed-grade schools' if folder_name else 'Statewide', dataset=DATASET, status='ready', geography='massachusetts',
            levels=list(levels), schools=path + '/schools.json',
            comparison='Massachusetts · {year} · {outcome} · {note}',
            model_scope='Separate Massachusetts MCAS cohorts by same-year grade population and subject',
            map_source='Exact CCD 2024–25 Massachusetts organization-code crosswalk to NCES 2023–24 coordinates'))
        for band in bands:
            level, assessment, _, _ = BANDS[band]
            cohort = [s for s in schools if s['level'] == level]
            coverage[band] = dict(schools=len(cohort), mapped=sum(s['latitude'] is not None for s in cohort),
                eligible={m['subject']: m['n'] for m in selected_models if m['assessment'] == assessment})
    audit = dict(year=YEAR, bands=coverage, public_enrollment_schools=len(payload['schools']),
        excluded_zero_enrollment_schools=sum(p['band'] == 'no-enrollment' for p in payload['schools']),
        unmatched_assessment_rows=len(payload['excluded_assessments']),
        missing_income_schools=sum(income(p['raw'])[2] is None for p in payload['schools']),
        grade10_mixed_school_rows_retained_not_modeled=sum(r['raw']['test_grade'] == '10' and
            next(p['band'] for p in payload['schools'] if p['school_id'] == r['school_id']) == 'mixed'
            for r in payload['assessments']))
    (ROOT / 'data/massachusetts/catalog.json').write_text(json.dumps(dict(schema_version=1,
        prepare_script='scripts/prepare_massachusetts.py',
        state=dict(id='MA', name='Massachusetts'), regions=regions), indent=2) + '\n')
    (ROOT / 'data/massachusetts/coverage.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract:
        extract()
    prepare(args.database)
