"""Inventory 2025 EDC school totals and exact same-year CCD identities/flags.

This audit grants no modeling approval and never changes the browser catalog.
EDC CSVs and official CCD archives are downloaded explicitly into ignored data/raw.
The published audit contains counts, provenance and concrete source obstacles.
Table obstacles describe the initial national EDC/CCD path, not current readiness;
state-native adapters can resolve them, and docs/state-expansion.md is the current
release queue.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import urllib.request
import zipfile

from database import ROOT
from state_registry import OFFICIAL_STATES, reported_count

RAW = ROOT / 'data/raw'
EDC = RAW / 'edc-2025'
AUDIT = ROOT / 'data/source/national-snapshot-audit.json'
MEMBERSHIP = 'ccd_sch_052_2425_l_1a_073025'
DIRECTORY = 'ccd_sch_029_2425_w_1a_073025'
LUNCH = 'ccd_sch_033_2425_l_2a_073025'
SPECIAL_DC_NOTES = {
    'AK': '2025 DC counts return closer to historical averages after unusually low 2024 reporting.',
    'LA': 'Louisiana first reports CCD DC in 2024–25; there is no compatible DC history before this year.',
    'ME': '2025 DC expands to students previously reported as reduced-price lunch; keep this definition era separate.',
    'NM': 'DC includes Medicaid free and reduced eligibility starting 2023–24; collection system changed and matured in 2025.',
    'NV': 'Some districts classified DC students as reduced-price rather than free lunch. This does not justify replacing DC with free lunch counts.',
    'OH': 'Some LEAs consolidate lunch/DC reporting under one school. The named error lists only identify counts exceeding membership, not an exhaustive set of allocated counts. The entire CCD DC path remains blocked until individual-school allocation can be established.',
    'RI': 'One school reports lunch under its main school while membership is absent; exclude any absent/zero membership.',
    'SD': 'Local reporting changed from free lunch to DC for some districts; the SEA is clarifying standardized definitions. Single-year DC-only results would require an explicit reporting caveat.',
}
DC_OVER_MEMBERSHIP_EXCLUSIONS = {'390437504274', '390437800485', '390451605918', '390452302128', '390495003615'}


def source(path, url):
    return dict(path=str(path.relative_to(ROOT)), url=url, bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def nces_id(value, state):
    """EDC drops leading zeroes in numeric NCES IDs; restore their official width."""
    if not re.fullmatch(r'\d{11,12}', value):
        raise ValueError(f'Invalid EDC NCES ID: {value!r}')
    padded = value.zfill(12)
    if not padded.startswith(OFFICIAL_STATES[state][1]):
        raise ValueError('EDC NCES ID is outside the state namespace')
    return padded


def exact_rate(value):
    if not re.fullmatch(r'(?:0?\.\d+|[01](?:\.\d+)?)', value):
        return None
    parsed = float(value)
    return parsed if 0 <= parsed <= 1 else None


def read_ccd(stem):
    with zipfile.ZipFile(RAW / (stem + '.zip')) as archive:
        with archive.open(stem + '.csv') as binary:
            yield from csv.DictReader(io.TextIOWrapper(binary, encoding='utf-8-sig'))


def download_edc():
    EDC.mkdir(exist_ok=True)
    def fetch(state):
        path = EDC / (state.lower() + '.csv')
        if not path.exists():
            temporary = path.with_suffix('.download')
            url = f'https://www.eddatacenter.org/api/data/3.1?state={state}&year=2025'
            with urllib.request.urlopen(url, timeout=180) as response, temporary.open('wb') as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
            temporary.replace(path)
        return state
    with ThreadPoolExecutor(max_workers=6) as pool:
        for future in as_completed([pool.submit(fetch, state) for state in OFFICIAL_STATES]):
            print('Downloaded ' + future.result(), flush=True)


def membership_cache():
    path = RAW / 'ccd-2025-membership-totals-grades.json'
    if path.exists():
        return json.loads(path.read_text())
    # The official archive uses Deflate64; the system unzip supports it while the
    # standard-library zip reader does not. Stream 2.35GB; do not extract to disk.
    process = subprocess.Popen(['unzip', '-p', str(RAW / (MEMBERSHIP + '.zip')),
                                MEMBERSHIP + '.csv'], stdout=subprocess.PIPE, text=True)
    totals, grades, count = {}, defaultdict(dict), 0
    try:
        for row in csv.DictReader(process.stdout):
            count += 1
            if row['SCHOOL_YEAR'] != '2024-2025':
                raise ValueError('Wrong-year CCD membership')
            key = row['NCESSCH']
            if row['TOTAL_INDICATOR'] == 'Education Unit Total':
                if key in totals:
                    raise ValueError('Duplicate CCD enrollment total')
                totals[key] = {field: row[field] for field in ['NCESSCH', 'ST', 'ST_SCHID',
                    'STUDENT_COUNT', 'DMS_FLAG', 'GRADE', 'RACE_ETHNICITY', 'SEX']}
            elif row['TOTAL_INDICATOR'] == 'Subtotal 4 - By Grade':
                if row['GRADE'] in grades[key]:
                    raise ValueError('Duplicate CCD grade subtotal')
                grades[key][row['GRADE']] = {field: row[field] for field in ['STUDENT_COUNT', 'DMS_FLAG']}
        if process.wait() != 0:
            raise ValueError('Official membership archive could not be decompressed')
    except BaseException:
        process.kill()
        process.wait()
        raise
    output = dict(records=count, totals=totals, grades=dict(grades))
    path.write_text(json.dumps(output, separators=(',', ':')))
    return output


def edc_inventory(state):
    path = EDC / (state.lower() + '.csv')
    counts, grades, g38, all_rows = Counter(), Counter(), [], []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        if 'GradeLevel' not in reader.fieldnames:
            raise ValueError('EDC API response is not the documented CSV')
        for row in reader:
            counts['records'] += 1
            if row['StateAbbrev'] != state or row['SchYear'] != '2024-25':
                raise ValueError('Wrong-state or wrong-year EDC CSV')
            if (row['DataLevel'] != 'School' or row['StudentGroup'] != 'All Students'
                    or row['StudentSubGroup'] != 'All Students' or row['Subject'] not in ['ela', 'math']):
                continue
            all_rows.append(row)
            grades[row['GradeLevel']] += 1
            if row['GradeLevel'] == 'G38':
                g38.append(row)
    # Compact raw rows are only a local convenience; the original CSV's checksum
    # remains the source identity and suppressed/ranged values are preserved.
    (EDC / (state.lower() + '-all-students.json')).write_text(json.dumps(all_rows, separators=(',', ':')))
    return dict(**source(path, f'https://www.eddatacenter.org/api/data/3.1?state={state}&year=2025'),
        rows=counts['records'], all_student_math_ela_rows=len(all_rows), grade_rows=dict(grades),
        g38_rows=len(g38), g38_exact_rate_rows=sum(exact_rate(r['ProficientOrAbove_percent']) is not None for r in g38),
        g38_assessments=dict(Counter(r['AssmtName'] + '|' + r['AssmtType'] for r in g38))), g38


def audit():
    directory = {r['NCESSCH']: r for r in read_ccd(DIRECTORY)}
    lunch = {r['NCESSCH']: r for r in read_ccd(LUNCH) if r['DATA_GROUP'] == 'Direct Certification'}
    membership = membership_cache()
    for collection in [directory.values(), lunch.values()]:
        if any(r['SCHOOL_YEAR'] != '2024-2025' for r in collection):
            raise ValueError('Wrong-year CCD directory or lunch')
    sources = {key: source(RAW / filename, url) for key, filename, url in [
        ('ccd_directory_2025', DIRECTORY + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + DIRECTORY + '.zip'),
        ('ccd_membership_2025', MEMBERSHIP + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + MEMBERSHIP + '.zip'),
        ('ccd_lunch_2025', LUNCH + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + LUNCH + '.zip'),
        ('ccd_state_notes_2025', 'SY_2024-25_CCD_Final_2a_Data_Notes.xlsx', 'https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx'),
        ('edc_codebook_v3_1', 'EDC_codebook_v3.1.xlsx', 'https://www.eddatacenter.org/data_codebooks/EDC_codebook_v3.1.xlsx'),
        ('edc_technical_v3_1', 'EDC_technical_documentation_v3.1.pdf', 'https://www.eddatacenter.org/data_documentation/EDC_technical_documentation_v3.1.pdf'),
        ('nces_lunch_definitions', 'ccd-lunch-definition.html', 'https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data'),
    ]}
    states = []
    for state, (name, fips) in sorted(OFFICIAL_STATES.items()):
        inventory, g38 = edc_inventory(state)
        by_id, joined, exclusions = defaultdict(list), Counter(), Counter()
        for row in g38:
            key = nces_id(row['NCESSchoolID'], state)
            by_id[key].append(row)
        valid_grade_ids = []
        for key, observations in by_id.items():
            joined['g38_schools'] += 1
            profile, total, direct = directory.get(key), membership['totals'].get(key), lunch.get(key)
            if not profile:
                exclusions['missing_same_year_directory'] += 1
                continue
            joined['directory_joined'] += 1
            if profile['ST'] != state or (total and total['ST'] != state) or (direct and direct['ST'] != state):
                raise ValueError('NCES join crossed state namespaces')
            if profile['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8']:
                exclusions['nonoperational_school'] += 1
                continue
            n, dc = reported_count(total), reported_count(direct)
            if n is None or n <= 0:
                exclusions['unreported_or_zero_membership'] += 1
                continue
            joined['reported_positive_membership'] += 1
            if dc is None:
                exclusions['missing_or_unreported_direct_certification'] += 1
                continue
            joined['reported_direct_certification'] += 1
            if dc > n or key in DC_OVER_MEMBERSHIP_EXCLUSIONS:
                exclusions['direct_certification_population_exceeds_or_consolidates_membership'] += 1
                continue
            try:
                high = int(profile['GSHI'])
            except ValueError:
                high = None
            if high is None or high > 8 or profile['G_AE_OFFERED'] == 'Yes' or profile['G_13_OFFERED'] == 'Yes':
                exclusions['outside_grade_school_population'] += 1
                continue
            joined['grade_school_dc_membership'] += 1
            if (len(observations) != 2 or {r['Subject'] for r in observations} != {'ela', 'math'}
                    or any(r['AssmtType'] != 'Regular' for r in observations)):
                exclusions['missing_or_ambiguous_regular_subject_pair'] += 1
                continue
            if any(exact_rate(r['ProficientOrAbove_percent']) is None for r in observations):
                exclusions['suppressed_ranged_or_missing_subject_rate'] += 1
                continue
            joined['both_exact_grade_school_dc_membership'] += 1
            valid_grade_ids.append(key)
        dc_state = [r for r in lunch.values() if r['ST'] == state]
        enrollment_state = [r for r in membership['totals'].values() if r['ST'] == state]
        grade_state = [r for r in directory.values() if r['ST'] == state]
        blockers = []
        if not g38:
            blockers.append('No EDC school G38 math/ELA totals; audit complete grade coverage and primary valid-score weights or obtain native totals.')
        if not any(reported_count(r) is not None for r in dc_state):
            blockers.append('No reported numeric CCD direct-certification totals; audit a CEP-safe state income source separately.')
        if joined['both_exact_grade_school_dc_membership'] < 4:
            blockers.append('Fewer than four complete exact-rate grade schools with reported same-year DC and enrollment in this source path.')
        if state == 'OH':
            blockers.append('CCD Final 2a notes permit LEA-wide lunch/DC allocation under one school; over-membership error IDs do not identify all affected LEAs. Obtain authoritative individual-school DC or an exhaustive allocation crosswalk before modeling.')
        if state == 'SD':
            blockers.append('CCD Final 2a SEA note says standardized DC reporting definitions still require clarity and consistency. Verify current individual eligibility definitions before approving the predictor.')
        if state == 'RI':
            blockers.append('CCD names LEA 4400150 school lunch allocation with absent membership; exclude the entire named LEA pending allocation clarification.')
        native = dict(provenance='EDC codebook GradeLevel G38 source column: SEA; aggregated grades 3–8.',
            source_id='edc_codebook_v3_1', primary_total_crosscheck='not_independently_verified',
            outcome_counts='EDC may construct level counts; not approved for intervals.', approved_for_modeling=False)
        if state == 'RI':
            native.update(primary_total_crosscheck='All 231 EDC G38 school rows per subject match official RIDE By_School totals, rates and tested values.',
                primary_urls=[f'https://www3.ride.ri.gov/ADP/Default/QuickReport?subject={s}&schYear=2024-25&type=school' for s in [5, 6]],
                validation_path='data/raw/ri-native-g38-comparison.json')
        states.append(dict(id=state, name=name, fips=fips, edc=inventory, native_g38=native,
            ccd_directory_schools=len(grade_state), ccd_directory_grade_metadata_flags=dict(Counter(r['IGOFFERED'] for r in grade_state)),
            ccd_membership_schools=len(enrollment_state), ccd_membership_flags=dict(Counter(r['DMS_FLAG'] for r in enrollment_state)),
            ccd_direct_certification_schools=len(dc_state), ccd_direct_certification_flags=dict(Counter(r['DMS_FLAG'] for r in dc_state)),
            joined=dict(joined), exclusions=dict(exclusions), candidate_eligible_nces_ids=valid_grade_ids,
            direct_certification_definition_note=SPECIAL_DC_NOTES.get(state), blockers=blockers,
            approved_for_modeling=False))
        print(state, 'G38', len(g38), 'exact grade/DC/membership', joined['both_exact_grade_school_dc_membership'], flush=True)
    output = dict(schema_version=1, audit_date=date.today().isoformat(), school_year='2024-25',
        browser_catalog=False, grants_modeling_approval=False, sources=sources,
        path_obstacles_context='Table obstacles describe the initial national EDC/CCD path, not current readiness; state-native adapters can resolve them, and docs/state-expansion.md is the current release queue.',
        membership_records=membership['records'], states=states,
        schemas=dict(edc_csv=list(g38[0]) if g38 else list(json.loads((EDC/'ak-all-students.json').read_text())[0]),
            ccd_directory=list(next(iter(directory.values()))), ccd_lunch=list(next(iter(lunch.values()))),
            ccd_membership_used_fields=['SCHOOL_YEAR', 'NCESSCH', 'ST', 'ST_SCHID', 'STUDENT_COUNT',
                'DMS_FLAG', 'GRADE', 'RACE_ETHNICITY', 'SEX', 'TOTAL_INDICATOR'],
            ccd_membership_total='TOTAL_INDICATOR=Education Unit Total',
            ccd_membership_grades='TOTAL_INDICATOR=Subtotal 4 - By Grade'),
        specification=dict(outcome='Exact published EDC G38 All Students math/ELA regular-assessment rates only; SEA-native provenance must be audited.',
            income='Reported CCD direct-certification Education Unit Total divided by Reported positive same-year CCD Membership Education Unit Total, via exact 12-digit NCES school ID.',
            scope='Grade schools only, using same-year directory GSHI<=08, excluding grade13/adult offers; separate state/subject cohorts.',
            intervals='Unavailable: never use constructed level counts, enrollment proxies or unchecked tested values.',
            missingness='Exclude ranges, suppression, missing or nonreported flags; never zero-fill. No FRPL fallback.',
            limitations='DC is a benefits-based proxy with state variation and incomplete reporting coverage, not full FRPL or a common national income definition.'))
    AUDIT.write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-edc', action='store_true')
    args = parser.parse_args()
    if args.download_edc:
        download_edc()
    audit()
