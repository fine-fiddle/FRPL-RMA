"""Merge audited state exports without adding a catalog branch for every state."""
import json
from pathlib import Path, PurePosixPath

from database import ROOT
from state_registry import OFFICIAL_STATES


def local_asset(root, value):
    """Only repository-relative data assets can be published by a descriptor."""
    if not isinstance(value, str):
        raise ValueError('Expected a relative data asset path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not value.startswith('data/') or '\\' in value:
        raise ValueError(f'Invalid relative data asset: {value!r}')
    resolved = (Path(root) / value).resolve()
    if not resolved.is_relative_to(Path(root).resolve()) or not resolved.is_file():
        raise ValueError(f'Missing data asset: {value}')
    return resolved


def canonical_models(db, dataset):
    """Index models by their actual definition and keep their per-school results."""
    models = {}
    for row in db.execute('''
            SELECT m.id,m.definition_id,m.subject,m.summary_json,d.year,d.level,d.name
            FROM model_run m JOIN assessment_definition d ON m.definition_id=d.id
            WHERE m.dataset_id=?''', (dataset,)):
        key = (row['year'], row['level'], row['name'], row['subject'])
        summary = json.loads(row['summary_json'])
        if key in models or tuple(summary.get(k) for k in ['year', 'level', 'assessment', 'subject']) != key:
            raise ValueError(f'Ambiguous or inconsistent canonical model: {dataset} {key}')
        models[key] = dict(id=row['id'], definition=row['definition_id'], summary=summary)
    results = {(row['model_id'], row['school_id']): dict(row) for row in db.execute('''
        SELECT r.* FROM model_result r JOIN model_run m ON r.model_id=m.id
        WHERE m.dataset_id=?''', (dataset,))}
    counts = {(row['definition_id'], row['school_id'], row['subject']): row['tested']
              for row in db.execute('''SELECT definition_id,school_id,subject,tested
                  FROM assessment_observation WHERE dataset_id=?''', (dataset,))}
    return models, results, counts


def validate_metric(metric, school_id, model, results, counts, context):
    canonical = results.get((model['id'], school_id))
    if canonical is None or not isinstance(metric, dict):
        raise ValueError(f'Exported school metric differs from SQLite: {context} {school_id}')
    for field in ['actual', 'predicted', 'studentized', 'low', 'high']:
        if field not in metric or metric[field] != canonical[field]:
            raise ValueError(f'Exported school metric differs from SQLite: {context} {school_id} {field}')
    if metric.get('residual') != canonical['actual'] - canonical['predicted']:
        raise ValueError(f'Exported school metric differs from SQLite: {context} {school_id} residual')
    subject = model['summary']['subject']
    if subject == 'combined':
        ns = [counts.get((model['definition'], school_id, s)) for s in ['math', 'reading']]
        tested = min(ns) if all(n is not None for n in ns) else None
    else:
        tested = counts.get((model['definition'], school_id, subject))
    if 'tested' not in metric or metric['tested'] != tested or metric.get('cohort_n') != model['summary']['n']:
        raise ValueError(f'Exported school metric differs from SQLite: {context} {school_id} count')


def validate_model_exports(db, dataset, output, levels, schools_path):
    models, results, counts = canonical_models(db, dataset)
    current = {}
    for level in levels:
        if level not in output.get('levels', {}) or level not in output.get('models', {}):
            raise ValueError(f'Missing {level} metadata in {schools_path}')
        info = output['levels'][level]
        for subject in ['math', 'reading', 'combined']:
            key = (info.get('year'), level, info.get('assessment'), subject)
            canonical = models.get(key)
            model = output['models'][level].get(subject)
            if model != (canonical['summary'] if canonical else None):
                raise ValueError(f'Exported model differs from SQLite: {schools_path} {level} {subject}')
            if canonical:
                current[level, subject] = canonical
    if not current:
        raise ValueError(f'No fitted models in {schools_path}')
    seen = set()
    for school in output['schools']:
        school_id, level = school['id'], school.get('level')
        if school_id in seen or level not in levels:
            raise ValueError(f'Invalid exported school identity/level: {schools_path} {school_id}')
        seen.add(school_id)
        for subject, metric in school.get('metrics', {}).items():
            model = current.get((level, subject))
            if model is None:
                raise ValueError(f'Exported metric has no matching model: {schools_path} {school_id} {subject}')
            validate_metric(metric, school_id, model, results, counts, str(schools_path))
        # A directory may intentionally omit other model members, but it may not
        # omit a canonical result belonging to a school it does display.
        for subject in ['math', 'reading', 'combined']:
            model = current.get((level, subject))
            if model and (model['id'], school_id) in results and subject not in school.get('metrics', {}):
                raise ValueError(f'Missing exported school metric: {schools_path} {school_id} {subject}')
        for record in school.get('history', []):
            if record.get('school_id') != school_id:
                raise ValueError(f'Historical school identity differs: {schools_path} {school_id}')
            for subject, metric in record.get('subjects', {}).items():
                key = (record.get('year'), record.get('level'), record.get('assessment'), subject)
                model = models.get(key)
                if model is None:
                    raise ValueError(f'Historical metric has no matching model: {schools_path} {school_id}')
                validate_metric(metric, school_id, model, results, counts, str(schools_path))


def merge_state_exports(db, catalog, root=ROOT):
    """Descriptors are published only after their dataset and models exist in SQLite.

    Discovery status lives in the separate all-state audit, never in ready choices.
    Existing Illinois/NYC/Wisconsin regions retain their order and definitions.
    """
    states = {state['id']: state for state in catalog['states']}
    for descriptor in sorted((Path(root) / 'data').glob('*/catalog.json')):
        payload = json.loads(descriptor.read_text())
        state = payload['state']
        if (payload.get('schema_version') != 1 or len(state['id']) != 2
                or not state['id'].isascii() or not state['id'].isalpha() or not state['id'].isupper()
                or state['id'] not in OFFICIAL_STATES
                or state.get('name') != OFFICIAL_STATES[state['id']][0] or not payload.get('regions')):
            raise ValueError(f'Invalid state catalog descriptor: {descriptor}')
        for region in payload['regions']:
            dataset = db.execute('SELECT state,status FROM dataset WHERE id=?',
                                 (region['dataset'],)).fetchone()
            if dataset is None or dataset['status'] != 'ready':
                continue
            if dataset['state'] != state['id'] or region.get('status') != 'ready':
                raise ValueError(f'Descriptor state/status differs from SQLite: {descriptor}')
            for key in ['id', 'name', 'geography', 'comparison', 'model_scope', 'map_source']:
                if not isinstance(region.get(key), str) or not region[key]:
                    raise ValueError(f'Missing {key} in {descriptor}')
            levels = region.get('levels')
            if not levels or len(levels) != len(set(levels)) or not set(levels) <= {'ES', 'HS'}:
                raise ValueError(f'Invalid levels in {descriptor}')
            schools_path = local_asset(root, region['schools'])
            if region.get('boundaries'):
                local_asset(root, region['boundaries'])
            output = json.loads(schools_path.read_text())
            if not output.get('schools') or not output.get('methodology'):
                raise ValueError(f'Empty directory or missing methodology: {schools_path}')
            validate_model_exports(db, region['dataset'], output, levels, schools_path)
            target = states.get(state['id'])
            if target is None:
                target = dict(id=state['id'], name=state['name'], regions=[])
                catalog['states'].append(target)
                states[state['id']] = target
            elif target['name'] != state['name']:
                raise ValueError(f'Conflicting state name in {descriptor}')
            if any(existing['id'] == region['id'] for existing in target['regions']):
                raise ValueError(f'Duplicate state/region in {descriptor}: {region["id"]}')
            prepared_region = dict(region)
            prepared_region.setdefault('statewide', True)
            target['regions'].append(prepared_region)
    # Preserve Illinois/Chicago as the default; keep every other ready state findable.
    catalog['states'][1:] = sorted(catalog['states'][1:], key=lambda state: state['name'])


def check_catalog_preservation(catalog, destination, allow_reduced=False):
    if allow_reduced or not Path(destination).exists():
        return
    previous = json.loads(Path(destination).read_text())
    def ready_regions(payload):
        return {(state['id'], region['id']) for state in payload['states']
                for region in state['regions'] if region['status'] == 'ready'}
    lost = ready_regions(previous) - ready_regions(catalog)
    if lost:
        labels = ', '.join(f'{state}/{region}' for state, region in sorted(lost))
        raise ValueError(f'Refusing to remove ready comparisons: {labels}. '
                         'Reimport the missing datasets, or use --allow-reduced-catalog '
                         'for an intentional reduced export.')
