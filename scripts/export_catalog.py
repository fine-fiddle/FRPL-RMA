"""Export a small catalog and statewide import audit from canonical SQLite."""
import argparse
import json
from pathlib import Path
from database import ROOT, DEFAULT_DB, connect

COMPARABILITY = (
    'States set their own tests and proficiency thresholds. Proficiency percentages '
    'and studentized residuals are not a common achievement scale across states or '
    'assessment systems. Low-income eligibility definitions also vary. Compare '
    'results within the named year, assessment and model population.'
)


def export(database=DEFAULT_DB, output=ROOT/'data'):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with connect(database) as db:
        sources = [dict(r) for r in db.execute('SELECT id,dataset_id,path,url,sha256 FROM source ORDER BY id')]
        catalog = dict(schema_version=1, comparability=COMPARABILITY,
                       sources=sources,
                       assessments=[dict(r) for r in db.execute('SELECT * FROM assessment_definition ORDER BY id')],
                       economic_measures=[dict(r) for r in db.execute('SELECT * FROM economic_definition ORDER BY id')],
                       model_runs=[dict(r) for r in db.execute(
                           'SELECT id,dataset_id,definition_id,subject,method_version,input_sha256 FROM model_run ORDER BY id')],
                       states=[dict(id='IL', name='Illinois', regions=[
                           dict(id='chicago', name='Chicago', dataset='cps', status='ready',
                                model_scope='CPS annual assessment cohorts', schools='data/schools.json',
                                boundaries='data/chicago-areas.geojson')])])
        if db.execute("SELECT 1 FROM dataset WHERE id='isbe-2024'").fetchone():
            schools = [dict(r) for r in db.execute('''
                SELECT s.school_id,s.name,s.district_id,s.district_name,s.city,s.county,
                       e.year,e.enrollment,e.low_income,e.percentage AS economic_disadvantage,
                       e.definition_id AS economic_measure
                FROM school s JOIN economic_observation e USING(dataset_id,school_id)
                WHERE s.dataset_id='isbe-2024' ORDER BY s.school_id''')]
            assessments = [dict(r) for r in db.execute('''
                SELECT a.school_id,d.name AS assessment,d.level,a.subject,a.proficiency,
                       a.tested,a.status,a.raw_value,a.source_order AS worksheet_row
                FROM assessment_observation a JOIN assessment_definition d ON a.definition_id=d.id
                WHERE a.dataset_id='isbe-2024' ORDER BY a.school_id,d.name,a.subject''')]
            ready = db.execute("SELECT status FROM dataset WHERE id='isbe-2024'").fetchone()[0] == 'ready_iar'
            audit = dict(year=2024, status='ready_iar' if ready else 'awaiting_tested_counts',
                         reason='The public workbook provides proficiency rates without tested counts. '
                                'No statewide residuals or sampling intervals are published until denominators '
                                'and the existing minimum-tested rule can be validated.',
                         source='isbe-2024', schools=schools, assessments=assessments)
            folder = output/'illinois'
            folder.mkdir(exist_ok=True)
            (folder/'import-2024.json').write_text(json.dumps(audit, separators=(',', ':'), allow_nan=False))
            catalog['states'][0]['regions'].append(dict(
                id='statewide', name='Statewide', dataset='isbe-2024', status='ready' if ready else audit['status'],
                schools='data/illinois/schools.json', boundaries=None, levels=['ES'],
                model_scope='Illinois statewide assessment cohorts',
                audit='data/illinois/import-2024.json'))
            if ready:
                audit['reason'] = 'IAR counts validated from EDC v3.1. SAT tested counts remain unavailable.'
                (folder/'import-2024.json').write_text(json.dumps(audit, separators=(',', ':'), allow_nan=False))
            catalog['statewide_coverage'] = dict(
                schools=len(schools),
                schools_with_income=sum(s['economic_disadvantage'] is not None for s in schools),
                reported_subject_rates=sum(a['proficiency'] is not None for a in assessments),
                tested_counts=sum(a['tested'] is not None for a in assessments))
        (output/'manifest.json').write_text(json.dumps(catalog, indent=2, allow_nan=False)+'\n')
        print(json.dumps(catalog.get('statewide_coverage', {}), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--output', type=Path, default=ROOT/'data')
    args = parser.parse_args()
    export(args.database, args.output)
