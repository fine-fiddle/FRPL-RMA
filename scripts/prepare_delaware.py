"""Prepare native Delaware 2024–25 regular SBAC/SAT school totals, offline.

--download refreshes the public Socrata totals and metadata; --extract rebuilds
the committed exact-ID source snapshot. No names or grade means establish joins.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import re
import urllib.parse
import urllib.request

from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

RAW = ROOT / 'data/raw'
EXTRACT = ROOT / 'data/source/delaware.json'
OUTPUT = ROOT / 'data/delaware'
PORTAL = 'https://data.delaware.gov/'
INCOME_URL = 'https://education.delaware.gov/community/funding-contracts/federal-and-state-programs/title-programs/low-income-measure-and-title-i-schools/'
BASE_FILTER = "schoolyear='2025' and race='All Students' and gender='All Students' and geography='All Students' and grade='All Students'"
COHORTS = {'grade': ('ES', 'Smarter Balanced Summative Assessment', '3–8', 'Grade schools · Smarter'),
           'high': ('HS', 'SAT School-Day (Spring)', '11', 'High schools · SAT')}
INCOME = ('Same-year individual SNAP/TANF direct-certification Low-Income count '
    'over its native end-of-year enrollment denominator. DDOE defines its general '
    'Low-Income measure through TANF/SNAP; Medicaid is separately added for '
    'Consolidated Grant Application purposes and is not substituted here. This '
    'is not meal access, a CEP claiming rate, fall enrollment or a tested subgroup. '
    'Suppression remains missing. No prior-year income backfill.')


def urls():
    result = {}
    for name, resource, where in [
        ('assessment', 'ms6b-mt82', BASE_FILTER + " and specialdemo='All Students'"),
        ('enrollment', '6i7v-xnmf', BASE_FILTER + " and specialdemo in ('All Students','Low-Income')"),
        ('directory', 'p3ez-si4g', "schoolyear='2025'")]:
        result[name] = PORTAL + 'resource/' + resource + '.json?' + urllib.parse.urlencode(
            {'$where': where, '$limit': 50000, '$order': 'districtcode,schoolcode'})
        result[name + '_metadata'] = PORTAL + 'api/views/' + resource + '.json'
    return result


def download():
    for key, url in urls().items():
        raw = urllib.request.urlopen(url, timeout=60).read()
        payload = json.loads(raw)
        if isinstance(payload, list) and len(payload) >= 50000:
            raise ValueError('Delaware download reached its limit; paginate explicitly')
        (RAW / f'delaware-{key}.json').write_bytes(raw)


def exact_id(row):
    values = [row['districtcode'], row['schoolcode']]
    if any(not isinstance(v, str) or not re.fullmatch(r'\d+', v) or int(v) <= 0 for v in values):
        raise ValueError('Invalid authoritative Delaware district/school code')
    return '-'.join(values)


def number(value, integer=False):
    if isinstance(value, bool) or not re.fullmatch(r'\d+' if integer else r'\d+(?:\.\d+)?', str(value)):
        return None
    return int(value) if integer else float(value)


def cohort(row):
    def grade(value):
        return {'PR': -2, 'PK': -1, 'KN': 0, 'KG': 0}.get(value, number(value, True))
    low, high = grade(row['lowestgrade']), grade(row['highestgrade'])
    if row['schooltype'].upper() != 'PUBLIC' or row.get('org_state') != 'DE' or low is None or high is None or low > high:
        return None
    if 3 <= high <= 8: return 'grade'
    if low >= 9 and 11 <= high <= 13: return 'high'
    return None


def income_value(row):
    if not row:
        return None, None, None
    if (row['schoolyear'] != '2025' or row['specialdemo'] != 'Low-Income' or
            any(row[k] != 'All Students' for k in ['race', 'gender', 'grade', 'geography']) or row['subgroup'] != 'Low Income'):
        raise ValueError('Not native same-year enrolled individual Low-Income')
    n = number(row.get('eoyenrollment'), True)
    low, pct = number(row.get('students'), True), number(row.get('pctofeoyenrollment'))
    if row['rowstatus'] != 'REPORTED' or n is None or n <= 0 or low is None or pct is None:
        return n, None, None
    if low > n or not 0 <= pct <= 100 or abs(100 * low / n - pct) > .0050001:
        raise ValueError('Delaware native income denominator/percentage mismatch')
    return n, low, 100 * low / n


def outcome(row, key):
    if (row['schoolyear'] != '2025' or row['assessmentname'] != COHORTS[key][1] or
            any(row[k] != 'All Students' for k in ['race', 'gender', 'grade', 'specialdemo', 'geography', 'subgroup']) or
            row['contentarea'].upper() not in ['MATH', 'ELA']):
        raise ValueError('Not the native regular school All Students total')
    pct = number(row.get('pctproficient')) if row['rowstatus'] == 'REPORTED' else None
    n, proficient = number(row.get('tested'), True), number(row.get('proficient'), True)
    if pct is not None and not 0 <= pct <= 100:
        raise ValueError('Invalid Delaware proficiency')
    if pct is not None and n is not None and proficient is not None:
        if n <= 0 or proficient > n or abs(100 * proficient / n - pct) > .0050001:
            raise ValueError('Delaware native valid-score ratio mismatch')
    return dict(proficiency=pct, tested=n if n and row['rowstatus'] == 'REPORTED' else None,
        valid_score_evidence=PORTAL+'api/views/ms6b-mt82.json: Tested defines completed assessments with valid scores',
        raw=row, raw_tested=row.get('tested'), source='assessment', source_row=row['source_row'],
        exclusion=None if pct is not None else 'Native regular proficiency is redacted or unavailable')


def unique(rows):
    """Only byte-equivalent JSON records may be collapsed, never conflicts."""
    seen, result = set(), []
    for number, row in enumerate(rows, 1):
        token = json.dumps(row, sort_keys=True, separators=(',', ':'))
        if token not in seen:
            seen.add(token)
            result.append(dict(row, source_row=number))
    return result


def extract():
    resources = {k: json.loads((RAW / f'delaware-{k}.json').read_text()) for k in urls()}
    metadata = {c['fieldName']: c for c in resources['assessment_metadata']['columns']}
    if metadata['tested'].get('description') != 'The number of students who completed the statewide summative assessment listed with a valid score':
        raise ValueError('Delaware valid-score definition changed; re-audit')
    directory, incomes, results = defaultdict(list), defaultdict(list), defaultdict(dict)
    for row in unique(resources['directory']):
        if row['schoolyear'] != '2025': raise ValueError('Wrong Delaware directory year')
        if row['schoolcode'] != '0' and row['districtcode'] != '0' and row['schooltype'].upper() == 'PUBLIC':
            directory[exact_id(row)].append(row)
    for row in unique(resources['enrollment']):
        if row['schoolyear'] != '2025': raise ValueError('Wrong Delaware enrollment year')
        if row['schoolcode'] != '0' and row['districtcode'] != '0' and row['specialdemo'] == 'Low-Income':
            incomes[exact_id(row)].append(row)
    for row in unique(resources['assessment']):
        if row['schoolyear'] != '2025': raise ValueError('Wrong Delaware assessment year')
        if row['schoolcode'] == '0' or row['districtcode'] == '0' or row['contentarea'].upper() not in ['MATH', 'ELA']:
            continue
        candidates = [k for k, c in COHORTS.items() if row['assessmentname'] == c[1]]
        if not candidates: continue
        key, model = exact_id(row), candidates[0]
        subject = 'math' if row['contentarea'].upper() == 'MATH' else 'reading'
        if (model, subject) in results[key]: raise ValueError('Conflicting native assessment total')
        results[key][(model, subject)] = row
    schools, excluded = [], []
    for key, profiles in sorted(directory.items()):
        reason = 'Conflicting native public-school directory units' if len(profiles) != 1 else None
        model = cohort(profiles[0]) if reason is None else None
        if reason is None and model is None: reason = 'Mixed, untested or unknown native grade scope'
        if reason:
            excluded.append(dict(id=key, reason=reason, directory=profiles, income=incomes[key],
                outcomes=list(results[key].values())))
            continue
        if len(incomes[key]) > 1: raise ValueError('Conflicting native individual income rows')
        raw = incomes[key][0] if incomes[key] else {}
        n, low, pct = income_value(raw)
        profile = profiles[0]
        schools.append(dict(id=key, cohort=model, name=profile['organization_name'], district_id=profile['districtcode'],
            district=profile['districtname'], city=profile.get('org_city'), county=profile.get('org_county'),
            enrollment=n, low_income=low, income=pct, income_raw=raw, income_source='enrollment',
            income_row=raw.get('source_row', 0), directory_raw=profile,
            outcomes={s: outcome(r, model) for (c, s), r in results[key].items() if c == model}))
    sources = {k: dict(path=f'data/raw/delaware-{k}.json', url=u,
        sha256=hashlib.sha256((RAW / f'delaware-{k}.json').read_bytes()).hexdigest()) for k, u in urls().items()}
    cohorts = [dict(id=k, level=level, assessment=assessment+' · Delaware · 2025', grades=grades,
        standard='Regular native school performance; SBAC Levels3/4 or SAT state proficiency benchmarks, alternate assessments excluded.',
        source='assessment', source_url=sources['assessment']['url'], label=label, outcome='Proficient',
        note='Native regular school totals · individual end-of-year SNAP/TANF', allow_point_only=True)
        for k, (level, assessment, grades, label) in COHORTS.items()]
    details = [INCOME,
        'Use native regular All Students school totals. SBAC grades3–8 and SAT grade11 have separate models. DeSSA alternate, science/social studies, ACCESS and mixed-grade schools are excluded. No grade percentages are averaged.',
        'The native public field dictionary defines Tested as completed assessments with valid scores. Numeric counts are used only from reported regular totals; no counts or suppressed rates are reconstructed. If an eligible member lacks counts, every interval in its model is unavailable.',
        'Native 2025 public directory codes and grade scope must establish a unique reporting unit. Conflicting public records or multiple campuses under one school code are excluded; names never establish joins. Exact duplicate enrollment records are collapsed only after full raw equality is checked.',
        'The predictor uses end-of-year enrollment from the native low-income row, not September enrollment. Individual SNAP/TANF status differs from FRPL and grant-specific Medicaid expansion. Combined is the equally weighted Math/ELA mean. Externally studentized state models describe associations, not causal effectiveness. One year; no historical connections or audited coordinates.']
    payload = dict(schema_version=1, dataset='de-native-2025', state=dict(id='DE', name='Delaware'),
        year=2025, academic_year='2024–25', retrieved=date.today().isoformat(), name='Delaware regular SBAC/SAT and individual SNAP/TANF 2024–25',
        region='delaware', prepare_script='scripts/prepare_delaware.py', source_url=PORTAL+'Education/Student-Assessment-Performance/ms6b-mt82',
        sources=sources, cohorts=cohorts, income_definition=dict(label='Individual SNAP/TANF direct certification', definition=INCOME, url=INCOME_URL),
        model_scope='Delaware unique public reporting units: separate pure grade-school SBAC and pure high-school SAT, same-year individual SNAP/TANF',
        schools=schools, excluded=excluded, source_audit=dict(native_public_units=len(directory),
            excluded=dict(Counter(r['reason'] for r in excluded)),
            identical_enrollment_duplicates=len(resources['enrollment'])-len(unique(resources['enrollment'])),
            valid_score_definition=metadata['tested']['description'], income_definition_url=INCOME_URL),
        coverage_note='Regular native totals with same-year individual SNAP/TANF. Ambiguous reporting units, mixed grades and alternate assessments excluded. One year; no audited map coordinates.',
        methodology=dict(summary='Delaware regular native SBAC/SAT school performance with individual SNAP/TANF direct certification.',
            details=details, sources=[dict(label='DDOE assessment field dictionary', url=PORTAL+'Education/Student-Assessment-Performance/ms6b-mt82'),
                dict(label='DDOE enrollment field dictionary', url=PORTAL+'Education/Student-Enrollment/6i7v-xnmf'),
                dict(label='DDOE individual low-income definition', url=INCOME_URL)]))
    validate(payload)
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    return payload


def validate(payload):
    if (payload['state']['id'], payload['year'], payload['dataset']) != ('DE', 2025, 'de-native-2025'):
        raise ValueError('Wrong Delaware snapshot identity')
    expected = {(k, c[0], c[1] + ' · Delaware · 2025', c[2]) for k, c in COHORTS.items()}
    if len(payload['cohorts']) != 2 or {(c['id'], c['level'], c['assessment'], c['grades']) for c in payload['cohorts']} != expected:
        raise ValueError('Wrong Delaware separate assessment cohorts')
    for school in payload['schools']:
        profile = school['directory_raw']
        if profile['schoolyear'] != '2025' or exact_id(profile) != school['id'] or cohort(profile) != school['cohort']:
            raise ValueError('Invalid native historical Delaware identity/scope')
        row = school['income_raw']
        if row and exact_id(row) != school['id']: raise ValueError('Foreign Delaware income identity')
        if (school['enrollment'], school['low_income'], school['income']) != income_value(row):
            raise ValueError('Income must use native individual end-of-year counts')
        for subject, native in school['outcomes'].items():
            row = native['raw']
            if exact_id(row) != school['id'] or subject != ('math' if row['contentarea'].upper() == 'MATH' else 'reading'):
                raise ValueError('Foreign Delaware outcome identity/subject')
            approved = outcome(row, school['cohort'])
            if any(native[k] != approved[k] for k in ['proficiency', 'tested', 'valid_score_evidence']):
                raise ValueError('Not native actual proficiency and valid-score count')


def prepare(database=DEFAULT_DB):
    payload = json.loads(EXTRACT.read_text()); validate(payload)
    return prepare_snapshot(payload, EXTRACT, OUTPUT, database)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', default=DEFAULT_DB)
    args = parser.parse_args()
    if args.download: download()
    if args.extract: extract()
    print(json.dumps(prepare(args.database), indent=2))
