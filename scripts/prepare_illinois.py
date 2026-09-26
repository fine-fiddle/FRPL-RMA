"""Validate EDC grade denominators against ISBE rates and export statewide IAR models.

EDC v3.1 all-student regular IAR rows only. No suppressed counts are imputed.
The compact extract is reproducible with --extract path/to/edc-il-2024.csv.
"""
import argparse
import json
import re
from pathlib import Path
import polars as pl
from database import ROOT, DEFAULT_DB, connect, add_source, save_models
from prepare_data import build_history, category

EXTRACT = ROOT/'data/source/illinois-iar-counts-2024.csv'
URL = 'https://eddatacenter.org/api/data/3.1?state=IL&year=2024'
COLUMNS = ['StateAssignedSchID', 'Subject', 'GradeLevel',
           'StudentSubGroup_TotalTested', 'ProficientOrAbove_percent']


def extract(path):
    frame = pl.read_csv(path, infer_schema=False).filter(
        (pl.col('DataLevel') == 'School') & (pl.col('StudentGroup') == 'All Students') &
        (pl.col('StudentSubGroup') == 'All Students') & (pl.col('AssmtName') == 'IAR') &
        (pl.col('AssmtType') == 'Regular') & (pl.col('SchYear') == '2023-24') &
        pl.col('Subject').is_in(['math', 'ela']))
    frame.select(COLUMNS).sort(COLUMNS[:3]).write_csv(EXTRACT)


def validate_counts(rows, proficiency, grades_served=None):
    """Reject ambiguous, duplicate, suppressed or non-reconciling grade records."""
    grades = [r['GradeLevel'] for r in rows]
    if len(grades) != len(set(grades)) or not set(grades) <= {f'G0{i}' for i in range(3, 9)}:
        return None
    if grades_served is not None:
        endpoints = re.fullmatch(r'(PK|K|\d+) - (PK|K|\d+)', grades_served)
        if not endpoints:
            return None
        start, end = [int(v) if v.isdigit() else 0 for v in endpoints.groups()]
        expected = {f'G0{i}' for i in range(max(3, start), min(8, end)+1)}
        if set(grades) != expected:
            return None
    try:
        ns = [int(r['StudentSubGroup_TotalTested']) for r in rows]
        ps = [float(r['ProficientOrAbove_percent']) for r in rows]
    except (ValueError, TypeError):
        return None
    if not ns or min(ns) <= 0 or any(not 0 <= p <= 1 for p in ps) or proficiency is None:
        return None
    # Both files round published rates. Keep a conservative reconciliation gate;
    # a failed check means unavailable, never a guessed denominator.
    average = 100 * sum(n*p for n, p in zip(ns, ps)) / sum(ns)
    return sum(ns) if abs(average-proficiency) <= .11 else None


def prepare(database=DEFAULT_DB):
    counts = pl.read_csv(EXTRACT, infer_schema=False)
    location_source = ROOT/'data/source/illinois-locations.json'
    locations = {r['school_id']: r for r in json.loads(location_source.read_text())['locations']}
    crosswalk_source = ROOT/'data/source/cps-illinois-crosswalk.json'
    crosswalk = {r['school_id']:r['cps_id'] for r in json.loads(crosswalk_source.read_text())['matches']}
    cps_profiles = {r['School_ID']: r for r in pl.read_csv(ROOT/'data/source/cps-profile-sy2324.csv', infer_schema=False).to_dicts()}
    count_ids = set(counts['StateAssignedSchID'])
    with connect(database) as db:
        from import_illinois_history import import_history
        import_history(db)
        from import_illinois_sat_history import import_history as import_sat_history
        import_sat_history(db)
        from import_illinois_2017 import import_history as import_2017_history
        import_2017_history(db)
        db.execute("DELETE FROM source WHERE id='cps-state-crosswalk'")
        add_source(db, 'cps-state-crosswalk', 'isbe-2024', crosswalk_source,
                   'https://data.cityofchicago.org/d/c7jj-qjvh')
        db.execute("DELETE FROM source WHERE id='nces-illinois-locations'")
        add_source(db, 'nces-illinois-locations', 'isbe-2024', location_source,
                   'https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2324/MapServer/0')
        profiles = {r['school_id']: dict(r) for r in db.execute("SELECT * FROM school WHERE dataset_id='isbe-2024'")}
        db.execute("DELETE FROM source WHERE id='edc-iar-2024'")
        add_source(db, 'edc-iar-2024', 'isbe-2024', EXTRACT, URL)
        db.execute("UPDATE assessment_observation SET tested=NULL, raw_tested=NULL WHERE dataset_id='isbe-2024' AND definition_id LIKE 'isbe-2024:2024:%'")
        accepted = rejected = 0
        for (sid, subject), group in counts.group_by(COLUMNS[:2]):
            subject = 'reading' if subject == 'ela' else subject
            row = db.execute("SELECT proficiency FROM assessment_observation WHERE dataset_id='isbe-2024' AND school_id=? AND subject=? AND definition_id='isbe-2024:2024:IAR:ES'", (sid, subject)).fetchone()
            grades = json.loads(profiles[sid]['profile_json'])['Grades Served'] if sid in profiles else ''
            n = validate_counts(group.to_dicts(), row[0] if row else None, grades)
            if n is None:
                rejected += 1
                continue
            db.execute("UPDATE assessment_observation SET tested=?,raw_tested=? WHERE dataset_id='isbe-2024' AND school_id=? AND subject=? AND definition_id='isbe-2024:2024:IAR:ES'", (n, str(n), sid, subject))
            accepted += 1
        assessments = pl.DataFrame([dict(r) for r in db.execute("SELECT a.school_id,d.year,d.level,d.name assessment,a.subject,a.proficiency,a.tested FROM assessment_observation a JOIN assessment_definition d ON a.definition_id=d.id WHERE a.dataset_id='isbe-2024'")], infer_schema_length=None)
        incomes = pl.DataFrame([dict(r) for r in db.execute("SELECT school_id,year,name,enrollment,low_income,percentage FROM economic_observation WHERE dataset_id='isbe-2024'")], infer_schema_length=None)
        records, models = build_history(assessments, incomes, point_only_assessments=('SAT', 'PARCC'))
        save_models(db, records, models, 'isbe-2024')
        schools = []
        for record in records:
            if record['year'] != 2024:
                continue
            p = profiles[record['school_id']]
            profile = json.loads(p['profile_json'])
            expected_level = 'HS' if profile['School Type'] == 'High School' else 'ES' if profile['School Type'] in ('Elementary School', 'Middle/Junior High School') else None
            if record['level'] != expected_level:
                continue
            if record['level'] == 'ES' and not record['subjects'] and record['school_id'] not in count_ids:
                continue
            cps_id = crosswalk.get(record['school_id'])
            classification = cps_profiles.get(cps_id, {}).get('Classification_Description')
            schools.append(dict(id=record['school_id'], name=p['name'], short=p['name'],
                level=record['level'], program=category(classification) if classification else 'Unclassified',
                cps_id=cps_id, program_source='CPS 2023–24 school-level classification' if classification else None,
                district=p['district_name'], city=p['city'],
                county=p['county'], income=record['income'], enrollment=record['enrollment'],
                latitude=locations.get(record['school_id'], {}).get('latitude'),
                longitude=locations.get(record['school_id'], {}).get('longitude'),
                metrics=record['subjects'], history=[r for r in records if r['school_id'] == record['school_id'] and r['level'] == record['level']]))
        by_level = {level: {m['subject']: m for m in models if m['level'] == level and m['year'] == 2024} for level in ['ES', 'HS']}
        output = dict(year='2023–24', assessment_year=2024, schools=schools, models=by_level,
            history_years=sorted({r['year'] for r in records}), history_models=models, counts_validation=dict(accepted=accepted, rejected=rejected),
            coverage_note='2024 IAR and SAT rankings. Grade-school history includes 2017 PARCC and 2023–24 IAR; SAT covers 2017–19 and 2021–24. Each model uses same-year income. SAT and 2017 PARCC tested counts are unavailable: residuals are shown without sampling intervals. IAR requires verified EDC counts for every expected grade. School aggregates for 2018 PARCC and 2019–22 IAR remain unavailable. School-type labels are available only for verified CPS crosswalk matches using CPS 2023–24 classifications; all other schools are Unclassified, not presumed neighborhood schools. Map locations use an exact state-ID to NCES-ID crosswalk and the NCES 2023–24 directory.')
        folder = ROOT/'data/illinois'
        folder.mkdir(exist_ok=True)
        (folder/'schools.json').write_text(json.dumps(output, separators=(',', ':'), allow_nan=False))
        db.execute("UPDATE dataset SET status='ready_iar' WHERE id='isbe-2024'")
        print(json.dumps(dict(validation=output['counts_validation'], models={s:m['n'] for s,m in by_level['ES'].items()}), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    if args.extract:
        extract(args.extract)
    prepare(args.database)
