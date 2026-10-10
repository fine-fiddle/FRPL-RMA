"""Canonical and static Montgomery published-rate comparisons from frozen audits."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path

import audit_montgomery as roster_audit
import audit_montgomery_models as model_audit
from database import ROOT, DEFAULT_DB, connect, definition_id
from state_snapshot import prepare_snapshot

DATASET = 'md-montgomery-2025'
EXTRACT = ROOT / 'data/source/montgomery.json'
OUTPUT = ROOT / 'data/montgomery'
NUMERICAL_SHA = 'dc08918759239918732e09e3a166f66fe4f3526999ce7fabef7ca828953c230f'
NUMERICAL_BYTES = 14086386
NUMERICAL_CODE = ROOT / 'scripts/audit_montgomery_models.py'
NUMERICAL_CODE_SHA = '48409c43aa984662709a35655cee4e73c5e7fec5681b6216a8ebb05ead147e60'
NUMERICAL_TEST = ROOT / 'tests/test_montgomery_models.py'
NUMERICAL_TEST_SHA = '42a6ba3733cf5fd6faee27726e1d3ed36fe250e1da34394a6e27fbd3cba9cf1f'
PROJECT_SOURCE = 'https://github.com/robot-assisted-projects/FRPL-RMA/blob/expansion/all-states/'
EXPECTED_N = {'math': 166, 'reading': 167, 'combined': 166}
MODEL_SCOPE = (
    'Montgomery County independent 2024–25 Maryland grade-school district models: exact '
    'operational NCES LEA 2400480 / CCD native MD-15 / MSDE LEA 15 identities. All 172 '
    'audited grade-school profiles remain visible, including four masked individual '
    'Early Attendance incomes. Native regular MCAP School_Level All Grades All Students '
    'published Levels 3+4 proficiency supports 166 Math, 167 ELA and 166 Combined fits. '
    'Accelerated Algebra I, Geometry and Algebra II courses remain in native Math totals. '
    'Valid-score count scope and the ten-valid-scored floor remain uncertified; sampling '
    'intervals are unavailable for every model. High, mixed, primary, unknown and district '
    'aggregate records remain outside this separate published-rate district release.')
COUNT_NOTE = (
    'Valid-score count scope and the ten-valid-scored floor remain uncertified. '
    'Native administrative Tested Count, Early Attendance income denominators, September '
    'enrollment, CCD membership and participation are never substituted as valid-score '
    'denominators. Sampling intervals are unavailable.')


def same(actual, expected):
    """Typed exact evidence equality; bool/int equality cannot substitute source data."""
    return roster_audit.fingerprint(actual) == roster_audit.fingerprint(expected)


def require_numerical_pins():
    for path, expected in [(NUMERICAL_CODE, NUMERICAL_CODE_SHA), (NUMERICAL_TEST, NUMERICAL_TEST_SHA)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Montgomery frozen numerical code/tests fingerprint changed; re-audit release')
    content = model_audit.OUTPUT.read_bytes()
    if len(content) != NUMERICAL_BYTES or hashlib.sha256(content).hexdigest() != NUMERICAL_SHA:
        raise ValueError('Montgomery complete numerical evidence fingerprint changed; re-audit release')
    return json.loads(content)


def require_frozen_inputs(roster, numerical):
    """Direct normalization requires all six immutable source/model evidence pins."""
    model_audit.require_frozen_roster(roster)
    if not same(numerical, require_numerical_pins()):
        raise ValueError('Montgomery in-memory numerical evidence fingerprint changed')


def load_inputs():
    roster = model_audit.load_roster()
    numerical = require_numerical_pins()
    model_audit.validate(numerical, model_audit.build(roster))
    if (numerical['hard_holds'] or numerical['approved_for_source'] is not False
            or numerical['approved_for_modeling'] is not False or roster['approved_for_source'] is not False
            or roster['approved_for_modeling'] is not False or len(numerical['models']) != 3
            or {(m['level'], m['subject']) for m in numerical['models']} != {('ES', s) for s in model_audit.SUBJECTS}
            or len(numerical['frozen_population']['grade_school_configuration_ids']) != 172
            or len(numerical['frozen_population']['usable_income_school_ids']) != 168
            or any(m['status'] != 'numerically_verified_pending_integration'
                or m['coefficients']['n'] != EXPECTED_N[m['subject']]
                or m['intervals']['available_for_entire_model'] is not False
                or m['coverage']['ten_valid_scored_floor_certified'] is not False for m in numerical['models'])):
        raise ValueError('Montgomery numerical audit has unresolved release or population holds')
    return roster, numerical


def cohorts():
    return [dict(id='grade', level='ES', assessment=model_audit.ASSESSMENT,
        label='Grade schools · regular MCAP', grades='3–8 plus accelerated math courses',
        standard=model_audit.STANDARD, source_url=roster_audit.SOURCES['msde_assessment']['url'],
        source='msde_assessment', allow_point_only=True, outcome='Proficient · Levels 3 and 4',
        note='Native regular All Grades All Students · accelerated Algebra I/Geometry/Algebra II included · '
             'individual Early Attendance income · valid-score count scope and ten-valid-scored floor '
             'uncertified · sampling intervals unavailable')]


def outcome(value, entry):
    rate = model_audit.exact_percent(entry['raw']['Proficient Pct'])
    if not same(rate, value['native_rate']) or not same(entry['raw']['Proficient Pct'], value['raw_rate']):
        raise ValueError('Montgomery native published proficiency differs from frozen source audit')
    # Matching income masks do not erase a directly published assessment rate.
    return dict(proficiency=rate, tested=None, valid_score_evidence=None, raw_tested=None,
        exclusion=value['exclusion'], source=entry['source'] if 'source' in entry else 'msde_assessment',
        source_row=entry['source_row'], raw=dict(applicable=value['applicable'],
            native_usable=value['usable'], native_outcome=copy.deepcopy(value),
            assessment_record=copy.deepcopy(entry), assessment_raw=copy.deepcopy(entry['raw']),
            native_rate=entry['raw']['Proficient Pct'], native_school_id=roster_audit.native_identity(entry['raw']),
            valid_score_count=None, sampling_variance=None, interval_availability=False,
            ten_valid_scored_floor_certified=False, count_note=COUNT_NOTE))


def build_snapshot(roster, numerical):
    """Reconstruct original native records and retain the complete fixed cohort."""
    require_frozen_inputs(roster, numerical)
    raw = roster['raw_inputs']
    ccd = {roster_audit.ccd_identity(e['raw']): e for e in raw['directory']['records']}
    native_directory = {roster_audit.native_identity(e['raw']): e for e in raw['native_directory']['records']}
    incomes, enrollments, native = defaultdict(list), defaultdict(list), {}
    for e in raw['native_income']['records']:
        incomes[roster_audit.native_identity(e['raw'], income=True, aggregate=True)].append(e)
    for e in raw['native_enrollment']['records']:
        enrollments[roster_audit.native_identity(e['raw'], aggregate=True)].append(e)
    for e in raw['native_assessment']['records']:
        r = e['raw']; label = r['Assessment'].strip()
        if e['worksheet'] != 'School_Level' or r['Year'] != 2025 or r['Student Group'] != 'All Students':
            continue
        subject = {'Mathematics All Grades':'math','English Language Arts All Grades':'reading'}.get(label)
        if subject:
            key = roster_audit.native_identity(r)
            if subject in native.setdefault(key, {}):
                raise ValueError('Duplicate exact Montgomery native regular All Grades subject')
            native[key][subject] = e
    configurations = set(numerical['frozen_population']['grade_school_configuration_ids'])
    schools, excluded = [], []
    for link in sorted(roster['roster_links'], key=lambda r:r['school_id']):
        key = link['school_id']; directory = native_directory[key]; profile = directory['raw']; directory_ccd = ccd[link['ncessch']]
        original_scope = model_audit.native_grade_scope(profile, directory_ccd['raw'], enrollments[key])
        if original_scope != (key in configurations) or original_scope != link['source_profile_eligible']:
            raise ValueError('Montgomery original grade scope differs from complete audited population')
        if not original_scope:
            excluded.append(copy.deepcopy(link)); continue
        rows = incomes[key]
        if len(rows) != 1 or rows[0]['raw']['School Type'] != ('Elementary' if profile['Grade Span']=='E' else 'Middle'):
            raise ValueError('Montgomery grade-school income requires its exact whole native band')
        income = link['income']; entry = rows[0]; r = entry['raw']
        denominator = model_audit.exact_count(r['Total Student Cnt']); count = model_audit.exact_count(r['Economically Disadvantaged Cnt'])
        published = model_audit.exact_percent(r['Economically Disadvantaged Pct'])
        pct = 100*count/denominator if denominator and count is not None and published is not None else None
        if pct is not None and (count > denominator or abs(pct-published) > .0500001):
            raise ValueError('Montgomery original individual income rounding/counts do not reconcile')
        if not same((pct, denominator, count), (income['percentage'],income['early_attendance_enrollment'],income['individual_low_income_count'])):
            raise ValueError('Montgomery own Early Attendance ratio differs from frozen income evidence')
        outcomes = {s:outcome(link['subjects'][s], native[key][s]) for s in ['math','reading']}
        schools.append(dict(id=key, ncessch=link['ncessch'], cohort='grade', name=profile['School Name'],
            district_id=roster_audit.LEA, district=directory_ccd['raw']['LEA_NAME'], city=directory_ccd['raw']['LCITY'] or None,
            county=None, enrollment=denominator, low_income=count, income=pct, income_source='msde_income', income_row=entry['source_row'],
            income_raw=dict(early_attendance_income=copy.deepcopy(entry), individual_income_evidence=copy.deepcopy(income),
                own_denominator=denominator, own_individual_count=count, valid_score_denominator=False),
            identity_raw=dict(ncessch=link['ncessch'], native_school_id=link['native_school_id'],
                native_directory=copy.deepcopy(directory), ccd=copy.deepcopy(directory_ccd),
                native_grade_span=link['native_grade_span'], offered_evidence=copy.deepcopy(link['offered']),
                enrolled_evidence=copy.deepcopy(link['enrolled']), ccd_flags=copy.deepcopy(link['ccd_flags']),
                native_september_enrollment=copy.deepcopy(enrollments[key]),
                early_attendance_minus_ccd=link['early_attendance_minus_ccd'],
                early_attendance_minus_september=link['early_attendance_minus_september']), outcomes=outcomes))
    if len(schools) != 172 or len(excluded) != 39 or sum(s['income'] is not None for s in schools) != 168:
        raise ValueError('Montgomery release requires 172 full grade profiles, 168 incomes and 39 outside records')
    for model in numerical['models']:
        subject=model['subject']; selected=[]
        for s in schools:
            rates={k:s['outcomes'][k]['proficiency'] for k in ['math','reading']}
            y=(rates['math']+rates['reading'])/2 if subject=='combined' and all(v is not None for v in rates.values()) else rates.get(subject)
            if s['income'] is not None and y is not None:
                selected.append(dict(school_id=s['id'],ncessch=s['ncessch'],name=s['name'],income_pct=s['income'],outcome_pct=y,
                    early_attendance_enrollment=s['enrollment'],individual_low_income_count=s['low_income']))
        expected=[{k:r[k] for k in selected[0]} for r in model['inputs']]
        if not same(selected,expected):
            raise ValueError('Montgomery normalized observations differ from exact audited numerical inputs')
    source_audit = dict(operational_roster=copy.deepcopy(roster['coverage']), cohorts=copy.deepcopy(roster['cohorts']),
        excluded_operational_roster_records=excluded, nonoperational_directory=copy.deepcopy(roster['nonoperational_directory']),
        unmatched_ccd_directory=copy.deepcopy(roster['unmatched_ccd_directory']), outside_directory_records=copy.deepcopy(roster['outside_directory_records']),
        subject_coverage={m['subject']:copy.deepcopy(m['coverage']) for m in numerical['models']},
        native_assessment_definition=dict(state='MD', name=model_audit.ASSESSMENT,year=2025,level='ES',
            grades=cohorts()[0]['grades'],standard=model_audit.STANDARD,source_url=roster_audit.SOURCES['msde_assessment']['url']),
        source_definition_evidence=copy.deepcopy(roster['source_definition_evidence']), planning_identity_reconciliation=copy.deepcopy(roster['planning']),
        retained_raw_inputs=copy.deepcopy(raw), raw_input_fingerprint=roster_audit.RAW_INPUT_SHA,
        retained_source_headers={k:dict(source_id=v['source_id'],header_source_row=v['header_source_row'],header=v['header'],records=len(v['records']))
            for k,v in raw.items() if isinstance(v,dict) and 'records' in v},
        historical_state_extract=copy.deepcopy(roster['state_extract']),count_definition_status=copy.deepcopy(numerical['count_definition_status']),
        historical_source_status=roster['status'],historical_source_scope=roster['scope'],historical_numerical_status=numerical['status'],historical_numerical_scope=numerical['scope'],
        release_basis=dict(exact_source_roster_replayed=True,numerical_audit_without_holds=True,minimum_subject_schools=30,
            historical_audits_approved_for_source=False,historical_audits_approved_for_modeling=False,all_models_point_only=True,
            normalized_source_approved=True,district_modeling_approved=True,
            note='Historical source and numerical approvals remain false. This separate published-rate adapter validates every normalized, canonical and static fit. Historical coverage fields are retained evidence. Valid-score scope and ten-valid-scored floor remain uncertified. No high, mixed, primary, unknown, provider, admissions or geography release is approved.'))
    selection = dict(policy=copy.deepcopy(model_audit.POLICY),frozen_source_population=copy.deepcopy(numerical['frozen_population']),
        directory_school_ids=[s['id'] for s in schools],subject_models={m['model_id']:dict(level=m['level'],subject=m['subject'],
            school_ids=[r['school_id'] for r in m['inputs']],population_sha256=m['population_sha256']) for m in numerical['models']})
    selection['sha256']=roster_audit.fingerprint(selection)
    sources=copy.deepcopy(roster['sources'])
    for key,path,sha in [('roster_audit',model_audit.ROSTER,model_audit.ROSTER_SHA),('source_audit_code',model_audit.SOURCE_CODE,model_audit.SOURCE_CODE_SHA),
            ('source_audit_tests',model_audit.SOURCE_TEST,model_audit.SOURCE_TEST_SHA),('numerical_audit',model_audit.OUTPUT,NUMERICAL_SHA),
            ('numerical_audit_code',NUMERICAL_CODE,NUMERICAL_CODE_SHA),('numerical_audit_tests',NUMERICAL_TEST,NUMERICAL_TEST_SHA)]:
        relative=str(path.relative_to(ROOT));sources[key]=dict(path=relative,url=PROJECT_SOURCE+relative,sha256=sha)
    coverage_note=(
        'Montgomery County independent district comparison, 2024–25: exact NCES LEA 2400480 / CCD MD-15 / MSDE 15. '
        'All 172 grade-school profiles are searchable; 168 have usable individual Early Attendance income; 166 Math/167 ELA/166 Combined enter separate district fits. '
        'Four masked income profiles and Carl Sandburg masked Math/ELA retain source exclusions; Montgomery Village Middle masked Math retains its usable ELA. '
        'Native regular MCAP All Grades All Students Levels 3+4 totals retain accelerated Algebra I, Geometry and Algebra II courses, separately from alternate DLM. '
        'The complete source audit retains 211 operational identities and 39 outside grade-school configurations. Income, September/CCD enrollment and assessment populations differ. '
        'Valid-score count scope and the ten-valid-scored floor remain uncertified; sampling intervals are unavailable modelwide. '
        'No audited admissions classifications, provider roles, coordinates or boundaries; one year only.')
    details=[MODEL_SCOPE,
        'Three independent unweighted district OLS fits reproduce all 499 audited results and explicit deleted-school checks. Combined is the equal mean of native Math and ELA percentages with its own 166-school fit and externally studentized residuals, not proficiency in both. Filters never refit models. Associations do not establish causal effectiveness or overall school quality.',
        'Use native regular MCAP School_Level Year 2025 All Students All Grades published proficiency Levels 3 and 4. Preserve complete original rows and masks; do not average grades or reconstruct outcomes from rounded levels. Alternate DLM, district aggregates, subgroup rates and accountability indicators are separate populations.',
        'The original March 2025 MSDE overview documents grade 6–7 high-school math course substitution for 2024–25 through 2027–28. Native All Grades retains accelerated Algebra I, Geometry and Algebra II. Among grade schools 43/40/23 course rows exist but only 40/40/3 have numeric administrative Tested Count. Three elementary Algebra I rows are entirely starred; presence alone never verifies participation.',
        roster_audit.maryland.ECON,
        'Divide each unsuppressed Economically Disadvantaged count by its own same-year Early Attendance Total Student Cnt and reconcile published one-decimal rounding. Preserve four masked incomes; missingness is never zero. Native September and CCD school membership total 159181; Early Attendance district denominator 159872 differs from known-school sum 159747 by 125, left unallocated. 197 school denominators differ from fall enrollment.',
        COUNT_NOTE+' Every valid-score count, sampling variance and interval endpoint is null. Studentization uses the residual scale estimated from the other N−1 schools with N−3 degrees of freedom; it provides no enrollment adjustment or shrinkage.',
        'All 172 audited grade-school profiles remain visible. Six primary native E/M units, 27 CCD high, 5 CCD mixed and 7 CCD primary offered configurations are distinct scope descriptions; the 39 outside configurations never enter these fits. Carl Sandburg special education remains a source profile; its regular rates are masked. Names, school type, program labels, residuals, leverage and fit quality never select observations.',
        'Every full/deleted fit has rank two and positive finite scale. Largest deleted prediction shifts over observed incomes are 0.583442 Math, 0.374375 ELA and 0.409386 Combined percentage points. Influence flags remain descriptive; they never remove a member or create school quality labels.',
        'One year only. No admissions classifications, provider-role comparisons, coordinates or boundaries are audited. Visible programs are Unclassified. State proficiency thresholds and economic definitions do not form a common national ranking.']
    return dict(schema_version=1,dataset=DATASET,year=2025,academic_year='2024–25',state=dict(id='MD',name='Maryland'),
        name='Montgomery County 2024–25 district comparison',region='montgomery',region_name='Montgomery County',statewide=False,
        comparison='Montgomery County · {year} · {assessment} · {note}',prepare_script='scripts/prepare_montgomery.py',
        source_url=roster_audit.SOURCES['msde_assessment']['url'],retrieved='2026-10-10',model_scope=MODEL_SCOPE,release_status='ready',
        approved_for_source=True,approved_for_modeling=True,
        map_source='School coordinates and district boundaries are unavailable in the audited Montgomery County source release.',
        income_definition=dict(label='Economically disadvantaged',definition=roster_audit.maryland.ECON,url=roster_audit.maryland.DEFINITIONS),
        sources=sources,cohorts=cohorts(),schools=schools,selection=selection,source_audit=source_audit,coverage_note=coverage_note,
        methodology=dict(summary='Montgomery County independent grade-school district models with same-year individual Early Attendance income and native regular MCAP Levels 3+4; valid-score count scope and ten-valid-scored floor uncertified, sampling intervals unavailable.',
            details=details,sources=[dict(label=label,url=sources[key]['url']) for key,label in [
                ('msde_directory','MSDE native school identities'),('msde_enrollment','MSDE September grade enrollment'),
                ('msde_income','MSDE individual Early Attendance income'),('msde_assessment','MSDE regular MCAP original published totals'),
                ('msde_definitions','MSDE economic and assessment definitions'),('msde_reportcard','MSDE proficiency Levels 3 and 4'),
                ('msde_mcap_overview','Original March 2025 MCAP grade/course scope'),('ccd_directory','CCD exact district directory'),
                ('ccd_membership','CCD school totals and grade evidence'),('ccd_lea_membership','CCD district total and grade evidence')]]))

def build():
    return build_snapshot(*load_inputs())

def validate(payload, expected=None):
    expected = build() if expected is None else expected
    if not same(payload, expected):
        raise ValueError('Montgomery County normalized extract differs from pinned source/model evidence, scope or selection policy')
    return payload['source_audit']


def extract(destination=EXTRACT):
    payload = build()
    Path(destination).write_text(json.dumps(payload, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return payload


def validate_canonical(payload, database, numerical, extract_path=EXTRACT):
    """Read every scoped canonical input/result and compare with the passed audits."""
    validate(payload, build_snapshot(model_audit.load_roster(), numerical))
    cohort = payload['cohorts'][0]
    assessment_id = definition_id(DATASET, 2025, cohort['assessment'], 'ES')
    income_id = DATASET + ':income'
    profiles = {s['id']: s for s in payload['schools']}
    number = lambda value: None if value is None else float(value)
    namespace = DATASET + ':%'
    with closing(connect(database)) as db:
        datasets = [dict(r) for r in db.execute('SELECT * FROM dataset WHERE id=? OR id LIKE ?', (DATASET, namespace))]
        if not same(datasets, [dict(id=DATASET, state='MD', name=payload['name'],
                model_scope=payload['model_scope'], status='ready')]):
            raise ValueError('Montgomery County canonical dataset release metadata changed')
        sources = dict(payload['sources'])
        sources['extract'] = dict(path=str(Path(extract_path).resolve().relative_to(ROOT)),
                                 url=payload['source_url'], sha256=hashlib.sha256(Path(extract_path).read_bytes()).hexdigest())
        expected_sources = {DATASET + ':' + key: dict(id=DATASET + ':' + key, dataset_id=DATASET,
            path=source['path'], url=source['url'], sha256=source['sha256'], imported_at=payload['retrieved'])
            for key, source in sources.items()}
        actual_sources = {r['id']: dict(r) for r in db.execute(
            'SELECT * FROM source WHERE dataset_id=? OR id LIKE ?', (DATASET, namespace))}
        if not same(actual_sources, expected_sources):
            raise ValueError('Montgomery County canonical source provenance changed')
        definitions = [dict(r) for r in db.execute('SELECT * FROM assessment_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_definition = dict(id=assessment_id, state='MD', name=cohort['assessment'], year=2025,
            level='ES', grades=cohort['grades'], standard=cohort['standard'], source_url=cohort['source_url'])
        income_rows = [dict(r) for r in db.execute('SELECT * FROM economic_definition WHERE id LIKE ?', (DATASET + ':%',))]
        expected_income = dict(id=income_id, name=payload['income_definition']['label'],
            definition=payload['income_definition']['definition'], source_url=payload['income_definition']['url'])
        if not same(definitions, [expected_definition]) or not same(income_rows, [expected_income]):
            raise ValueError('Montgomery County canonical native assessment/income definition changed')
        # SQLite foreign keys verify each referenced identity but do not require
        # source/definition/model ownership to match the observation's dataset.
        # Include every namespace reference so a foreign owner cannot hide rows
        # from an otherwise correct dataset-only count. Native school IDs remain
        # shared with Maryland's independent statewide release.
        school_rows = list(db.execute('SELECT * FROM school WHERE dataset_id=? OR source_id LIKE ?',
                                      (DATASET, namespace)))
        economic_rows = list(db.execute('''SELECT * FROM economic_observation WHERE
            dataset_id=? OR definition_id LIKE ? OR source_id LIKE ?''', (DATASET, namespace, namespace)))
        observation_rows = list(db.execute('''SELECT * FROM assessment_observation WHERE
            dataset_id=? OR definition_id LIKE ? OR source_id LIKE ?''', (DATASET, namespace, namespace)))
        if len(school_rows) != 172 or len(economic_rows) != 172 or len(observation_rows) != 344:
            raise ValueError('Montgomery County canonical profile/observation row counts changed')
        schools = {r['school_id']: dict(r) for r in school_rows}
        economic = {r['school_id']: dict(r) for r in economic_rows}
        observations = {(r['school_id'], r['subject']): dict(r) for r in observation_rows}
        if set(schools) != set(profiles) or set(economic) != set(profiles) or set(observations) != {(key, subject) for key in profiles for subject in ['math', 'reading']}:
            raise ValueError('Montgomery County canonical profile/observation membership changed')
        for order, profile in enumerate(payload['schools']):
            key = profile['id']
            school = dict(schools[key]); school['profile_json'] = json.loads(school['profile_json'])
            expected_school = dict(dataset_id=DATASET, school_id=key, name=profile['name'], district_id=profile['district_id'],
                district_name=profile['district'], city=profile['city'], county=profile['county'], profile_json=profile,
                source_id=DATASET + ':extract', source_order=order)
            econ = dict(economic[key]); econ['raw_json'] = json.loads(econ['raw_json'])
            expected_econ = dict(dataset_id=DATASET, school_id=key, year=2025, definition_id=income_id,
                name=profile['name'], enrollment=number(profile['enrollment']), low_income=number(profile['low_income']),
                percentage=profile['income'], source_label=payload['income_definition']['label'], raw_json=profile['income_raw'],
                source_id=DATASET + ':' + profile['income_source'], source_order=profile['income_row'])
            if not same(school, expected_school) or not same(econ, expected_econ):
                raise ValueError('Montgomery County canonical raw profile/same-year individual income changed')
            for subject in ['math', 'reading']:
                value = profile['outcomes'][subject]
                actual = dict(observations[(key, subject)])
                actual['raw_value'], actual['raw_tested'] = json.loads(actual['raw_value']), json.loads(actual['raw_tested'])
                expected = dict(dataset_id=DATASET, school_id=key, definition_id=assessment_id, subject=subject,
                    proficiency=number(value['proficiency']), tested=None,
                    status='reported' if value['proficiency'] is not None else 'suppressed_or_not_reported',
                    raw_value=value['raw'], raw_tested=None, source_id=DATASET + ':' + value['source'], source_order=value['source_row'])
                if not same(actual, expected):
                    raise ValueError('Montgomery County canonical native outcome/raw exclusion/count evidence changed')
        model_rows = list(db.execute('''SELECT * FROM model_run WHERE
            dataset_id=? OR id LIKE ? OR definition_id LIKE ?''', (DATASET, namespace, namespace)))
        runs = {r['subject']: dict(r) for r in model_rows}
        if len(model_rows) != 3 or len(runs) != 3 or set(runs) != set(model_audit.SUBJECTS):
            raise ValueError('Montgomery County canonical models require exactly three ES subject fits')
        digest = hashlib.sha256(json.dumps([(key, actual_sources[key]['sha256']) for key in sorted(actual_sources)]).encode()).hexdigest()
        total = 0
        for model in numerical['models']:
            subject = model['subject']; run = runs[subject]
            summary = json.loads(run.pop('summary_json'))
            expected_run = dict(id=f'{assessment_id}:{subject}:ols-v1:{digest[:12]}', dataset_id=DATASET,
                definition_id=assessment_id, subject=subject, method_version='ols-studentized-v1', input_sha256=digest)
            expected_summary = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                assessed_schools=172, excluded_schools=172 - model['coefficients']['n'], **model['coefficients'])
            exact = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
            if (not same(run, expected_run) or not same({k: summary.get(k) for k in exact}, {k: expected_summary[k] for k in exact})
                    or not model_audit.numeric_equal(summary, expected_summary)):
                raise ValueError('Montgomery County canonical model metadata/coefficients differ from audited fits')
            saved = {r['school_id']: dict(r) for r in db.execute('SELECT * FROM model_result WHERE model_id=?', (run['id'],))}
            reference = {r['school_id']: r for r in model['results']}
            if set(saved) != set(reference):
                raise ValueError('Montgomery County canonical result membership changed')
            for key, result in reference.items():
                actual = saved[key]
                exact_result = dict(model_id=run['id'], dataset_id=DATASET, school_id=key, actual=float(result['actual']), low=None, high=None)
                expected_result = exact_result | dict(predicted=result['predicted'], studentized=result['studentized'])
                if (not same({k: actual.get(k) for k in exact_result}, exact_result)
                        or not model_audit.numeric_equal(actual, expected_result)):
                    raise ValueError('Montgomery County canonical point-only result differs from audited district fit')
            total += len(saved)
        if total != 499 or db.execute('SELECT count(*) FROM model_result WHERE dataset_id=? OR model_id LIKE ?',
                                      (DATASET, namespace)).fetchone()[0] != total:
            raise ValueError('Montgomery County canonical result count changed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Montgomery County canonical foreign-key integrity failed')
    return {'schools': len(profiles), 'observations': len(observations), 'models': len(runs), 'results': total}


def validate_exports(payload, output, numerical):
    validate(payload, build_snapshot(model_audit.load_roster(), numerical))
    output = Path(output)
    schools = json.loads((output / 'schools.json').read_text())
    history = json.loads((output / 'history.json').read_text())
    coverage = json.loads((output / 'coverage.json').read_text())
    descriptor = json.loads((output / 'catalog.json').read_text())
    exported = {s['id']: s for s in schools['schools']}
    records = {r['school_id']: r for r in history['records']}
    profiles = {s['id']: s for s in payload['schools']}
    if (len(schools['schools']) != 172 or len(history['records']) != 172
            or set(exported) != set(profiles) or set(records) != set(profiles)):
        raise ValueError('Montgomery County exported native source directory/history identities differ from selection')
    if set(schools['models']) != {'ES'} or set(schools['models']['ES']) != set(model_audit.SUBJECTS):
        raise ValueError('Montgomery County export requires only the three independently audited ES models')
    expected_keys = {(2025, 'ES', model_audit.ASSESSMENT, m['subject']) for m in numerical['models']}
    for summaries in [schools['history_models'], history['models']]:
        keyed = {(m['year'], m['level'], m['assessment'], m['subject']): m for m in summaries}
        if len(summaries) != 3 or len(keyed) != 3 or set(keyed) != expected_keys:
            raise ValueError('Montgomery County history must retain exactly three audited ES model populations')
        if any(not same(summary, schools['models']['ES'][key[3]]) for key, summary in keyed.items()):
            raise ValueError('Montgomery County historical model summaries differ from current district fits')
    for model in numerical['models']:
        subject = model['subject']
        actual_model = schools['models']['ES'][subject]
        expected_model = dict(year=2025, level='ES', assessment=model_audit.ASSESSMENT, subject=subject,
                              assessed_schools=172, excluded_schools=172 - model['coefficients']['n'], **model['coefficients'])
        exact_model = ['year', 'level', 'assessment', 'subject', 'assessed_schools', 'excluded_schools', 'n']
        if (not same({k: actual_model.get(k) for k in exact_model}, {k: expected_model[k] for k in exact_model})
                or not model_audit.numeric_equal(actual_model, expected_model)):
            raise ValueError('Montgomery County exported district coefficients/coverage differ from numerical audit')
        reference = {r['school_id']: r for r in model['results']}
        eligible = {s['id'] for s in schools['schools'] if subject in s['metrics']}
        if eligible != set(reference):
            raise ValueError('Montgomery County exported subject membership differs from passed district audit')
        for key, result in reference.items():
            fields = ['actual', 'predicted', 'residual', 'studentized', 'low', 'high', 'leverage']
            metric = exported[key]['metrics'][subject]
            expected_metric = {k: result[k] for k in fields} | dict(tested=None, cohort_n=model['coefficients']['n'])
            exact = ['actual', 'tested', 'low', 'high', 'cohort_n']
            if (not same({k: metric.get(k) for k in exact}, {k: expected_metric[k] for k in exact})
                    or not model_audit.numeric_equal(metric, expected_metric)
                    or not same(metric, records[key]['subjects'][subject])):
                raise ValueError('Montgomery County per-school point-only metric differs from verified district fit')
    for key, school in exported.items():
        profile = profiles[key]
        record = records[key]
        expected_subjects = {m['subject'] for m in numerical['models'] if key in {r['school_id'] for r in m['results']}}
        if set(school['metrics']) != expected_subjects or set(record['subjects']) != expected_subjects:
            raise ValueError('Montgomery County profile/history subject set differs from exact audited eligibility')
        expected_exclusions = {s: profile['outcomes'][s]['exclusion'] for s in ['math', 'reading']
                               if profile['outcomes'][s]['exclusion'] is not None}
        if expected_exclusions:
            expected_exclusions['combined'] = '; '.join(
                ('Math' if s == 'math' else 'ELA') + ': ' + expected_exclusions[s]
                for s in ['math', 'reading'] if s in expected_exclusions)
        profile_fields = dict(level='ES', name=profile['name'], short=profile['name'],
            district=profile['district'], income=profile['income'], enrollment=None if profile['enrollment'] is None else float(profile['enrollment']),
            city=profile['city'], county=profile['county'], latitude=None, longitude=None,
            program='Unclassified', programs=['Unclassified'], exclusions=expected_exclusions)
        record_fields = dict(level='ES', year=2025, income_year=2025,
            assessment=model_audit.ASSESSMENT, name=profile['name'], income=profile['income'],
            enrollment=None if profile['enrollment'] is None else float(profile['enrollment']), income_label=payload['income_definition']['label'],
            exclusions=expected_exclusions)
        if (set(school) != set(profile_fields) | {'id', 'metrics', 'history'}
                or set(record) != set(record_fields) | {'school_id', 'subjects'}
                or not same({k: school.get(k) for k in profile_fields}, profile_fields)
                or not same({k: record.get(k) for k in record_fields}, record_fields)
                or not same(school['history'], [record])):
            raise ValueError('Montgomery County profile/history/exclusion/geography evidence changed')
    expected_coverage = {'grade': {'directory': 172, 'eligible': {m['subject']: m['coefficients']['n'] for m in numerical['models']}}}
    if not same(coverage, dict(year=2025, schools=172, cohorts=expected_coverage,
            source_audit=payload['source_audit'], exclusions=dict(Counter(
                reason for r in records.values() for reason in r['exclusions'].values())))):
        raise ValueError('Montgomery County exported coverage/source exclusions differ from approved selection')
    cohort = payload['cohorts'][0]
    expected_levels = {'ES': dict(year=2025, label=cohort['label'], assessment=cohort['assessment'],
                                  outcome=cohort['outcome'], math_label='Math', note=cohort['note'])}
    header = dict(year=payload['academic_year'], assessment_year=2025,
        income_label=payload['income_definition']['label'], program_options=['Unclassified'],
        levels=expected_levels, history_years=[2025], coverage_note=payload['coverage_note'],
        methodology=payload['methodology'])
    if (set(schools) != set(header) | {'schools', 'models', 'history_models'}
            or set(history) != {'records', 'models'}
            or not same({k: schools.get(k) for k in header}, header)):
        raise ValueError('Montgomery County exported native assessment definition or methodology changed')
    expected_descriptor = dict(schema_version=1, state=payload['state'], prepare_script=payload['prepare_script'],
        regions=[dict(id='montgomery', geography='montgomery', name=payload['region_name'], dataset=DATASET,
            statewide=False, status='ready', levels=['ES'], boundaries=None, comparison=payload['comparison'],
            audit=str((output / 'coverage.json').relative_to(ROOT)),
            schools=str((output / 'schools.json').relative_to(ROOT)),
            model_scope=payload['model_scope'], map_source=payload['map_source'])])
    if not same(descriptor, expected_descriptor):
        raise ValueError('Montgomery County ready descriptor must retain distinct district and point-only scope')
    return {m['model_id']: m['coefficients']['n'] for m in numerical['models']}


def prepare(database=DEFAULT_DB, output=OUTPUT, extract_path=EXTRACT):
    output, extract_path = Path(output).resolve(), Path(extract_path).resolve()
    # The shared helper emits repository-relative provenance/catalog links.
    # Reject unsupported destinations before opening any database transaction.
    output.relative_to(ROOT)
    extract_path.relative_to(ROOT)
    roster, numerical = load_inputs()
    payload = json.loads(Path(extract_path).read_text())
    validate(payload, build_snapshot(roster, numerical))
    coverage = prepare_snapshot(payload, extract_path, output, database)
    descriptor_path = Path(output) / 'catalog.json'
    descriptor = json.loads(descriptor_path.read_text())
    descriptor['regions'][0].update(name=payload['region_name'], statewide=False,
        comparison=payload['comparison'], audit=str((Path(output) / 'coverage.json').relative_to(ROOT)))
    descriptor_path.write_text(json.dumps(descriptor, indent=2) + '\n')
    validate_exports(payload, output, numerical)
    validate_canonical(payload, database, numerical, extract_path)
    return coverage


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--extract-only', action='store_true', help='Rebuild normalized evidence without database import or exports')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.extract or args.extract_only:
        extract()
    if args.extract_only:
        print(json.dumps({'dataset': DATASET, 'normalized_extract': str(EXTRACT)}, sort_keys=True))
    else:
        result = prepare(args.database, args.output)
        print(json.dumps({k: result[k] for k in ['year', 'schools', 'cohorts']}, sort_keys=True))
