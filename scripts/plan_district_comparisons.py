"""Create a district comparison queue from dated official CCD size records.

Default rendering uses the committed planning extract. --extract reads the
official 2024–25 LEA directory/membership and school directory/membership files
under data/raw. This never imports observations, fits models or changes the site.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

from audit_national_sources import DIRECTORY, MEMBERSHIP, membership_cache, read_ccd, source
from database import ROOT
from prepare_ccd_states import grade_school
from state_registry import OFFICIAL_STATES, load_registry, reported_count

RAW = ROOT / 'data/raw'
EXTRACT = ROOT / 'data/source/district-comparison-candidates.json'
GUIDE = ROOT / 'docs/district-comparisons.md'
LEA_DIRECTORY = 'ccd_lea_029_2425_w_1a_073025'
LEA_MEMBERSHIP = 'ccd_lea_052_2425_l_1a_073025'
MIN_ENROLLMENT = 20000
MAIN_ENROLLMENT = 50000
MIN_COHORT = 30
OPERATIONAL = {'1', '3', '4', '5', '8'}
# Exact geographic LEAs in the native directory; no name/DBN inference or union
# of their membership with the separate Chancellor's Office supervisory LEA.
NYC_GEOGRAPHIC_LEAS = {
    '3600076', '3600077', '3600078', '3600079', '3600081', '3600083',
    '3600084', '3600085', '3600086', '3600087', '3600088', '3600090',
    '3600091', '3600092', '3600094', '3600095', '3600096', '3600097',
    '3600098', '3600099', '3600100', '3600101', '3600102', '3600103',
    '3600119', '3600120', '3600121', '3600122', '3600123', '3600151',
    '3600152', '3600153',
}
RULES = dict(main_enrollment=MAIN_ENROLLMENT, minimum_enrollment=MIN_ENROLLMENT,
             minimum_potential_schools_in_one_cohort=MIN_COHORT,
             ordinary_lea_types=['1', '2'], school_year='2024-2025',
             membership_flags=['Reported'],
             actual_model_approval='At least 30 usable schools separately for each '
                 'year/assessment/population/subject; audit coverage, income '
                 'variation, leverage, studentization and source definitions.')


def read_lea(stem):
    """Stream Deflate64 as well as ordinary ZIP without extracting huge CSVs."""
    archive, member = RAW / (stem + '.zip'), stem + '.csv'
    with zipfile.ZipFile(archive) as zf:
        compression = zf.getinfo(member).compress_type
        if compression != 9:
            with zf.open(member) as binary:
                yield from csv.DictReader(io.TextIOWrapper(binary, encoding='utf-8-sig'))
            return
    process = subprocess.Popen(['unzip', '-p', str(archive), member],
                               stdout=subprocess.PIPE, text=True)
    try:
        yield from csv.DictReader(process.stdout)
        if process.wait() != 0:
            raise ValueError('Official LEA archive could not be decompressed')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def membership_totals(rows):
    totals = {}
    for number, row in enumerate(rows, 2):
        if row['SCHOOL_YEAR'] != RULES['school_year']:
            raise ValueError('Wrong-year LEA membership')
        if row['TOTAL_INDICATOR'] != 'Education Unit Total':
            continue
        key = row['LEAID']
        if not re.fullmatch(r'\d{7}', key) or key in totals:
            raise ValueError('Invalid or duplicate LEA membership total')
        if any(row[field] != 'No Category Codes' for field in ['GRADE', 'RACE_ETHNICITY', 'SEX']):
            raise ValueError('LEA total contains a demographic subtotal')
        totals[key] = dict(row=row, source_row=number)
    return totals


def potential_cohort(profile, total, grades):
    """Grade configuration only, not usable outcome/income or model approval."""
    if reported_count(total) in [None, 0] or not grades:
        return None
    if grade_school(profile, grades, total) and any(
            profile[f'G_{grade}_OFFERED'] == 'Yes' for grade in range(3, 9)):
        return 'ES'
    fields = ['G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)]
    fields += ['G_UG_OFFERED', 'G_AE_OFFERED']
    if profile['IGOFFERED'] != 'As reported' or any(profile[field] not in ['Yes', 'No'] for field in fields):
        return None
    outside = ['G_PK_OFFERED', 'G_KG_OFFERED', 'G_13_OFFERED', 'G_AE_OFFERED']
    outside += [f'G_{g}_OFFERED' for g in range(1, 9)]
    if any(profile[field] != 'No' for field in outside) or not any(
            profile[f'G_{grade}_OFFERED'] == 'Yes' for grade in range(9, 13)):
        return None
    expected = {f'Grade {g}' for g in range(9, 13)}
    counts = [reported_count(row) for grade, row in grades.items() if grade in expected]
    if not counts or any(value is None for value in counts) or sum(counts) != reported_count(total):
        return None
    if any(row['STUDENT_COUNT'] != '0' or row['DMS_FLAG'] not in ['Reported', 'Derived']
           for grade, row in grades.items() if grade not in expected):
        return None
    return 'HS'


def size_tier(enrollment, cohort_counts):
    if enrollment is None or enrollment < MIN_ENROLLMENT or max(cohort_counts.values(), default=0) < MIN_COHORT:
        return None
    return 'main' if enrollment >= MAIN_ENROLLMENT else 'secondary'


def scope(row):
    if row['LEAID'] == '0622710':
        return 'existing_los_angeles'
    if row['LEAID'] == '1200390':
        return 'existing_miami_dade'
    if row['LEAID'] == '1200180':
        return 'existing_broward'
    if row['LEAID'] == '1200870':
        return 'existing_hillsborough'
    if row['LEAID'] == '1201440':
        return 'existing_orange'
    if row['LEAID'] == '1201500':
        return 'existing_palm_beach'
    if row['LEAID'] == '1302550':
        return 'existing_gwinnett'
    if row['LEAID'] == '5101260':
        return 'existing_fairfax'
    if row['LEAID'] == '4823640':
        return 'existing_houston'
    if row['LEAID'] == '3704720':
        return 'existing_wake'
    if row['LEAID'] == '3200060':
        return 'existing_clark_county'
    if row['LEAID'] == '1709930':
        return 'existing_chicago'
    if row['LEAID'] == '1500030':
        return 'existing_hawaii_statewide'
    if row['LEAID'] in NYC_GEOGRAPHIC_LEAS:
        return 'existing_nyc_component'
    if row['LEAID'] == '3600135':
        return 'nyc_special_population_review'
    if row['LEA_TYPE'] not in RULES['ordinary_lea_types']:
        return 'other_agency_scope_review'
    if row['CHARTER_LEA_TEXT'] not in ['Not a charter district', 'Not applicable']:
        return 'district_charter_status_review'
    return 'new_district_candidate'


def extract():
    totals = membership_totals(read_lea(LEA_MEMBERSHIP))
    school_membership = membership_cache()
    cohorts, operational, seen = defaultdict(lambda: dict(ES=[], HS=[])), Counter(), set()
    for school in read_ccd(DIRECTORY):
        if school['SCHOOL_YEAR'] != RULES['school_year'] or school['NCESSCH'] in seen:
            raise ValueError('Wrong-year or duplicate CCD school directory record')
        seen.add(school['NCESSCH'])
        if school['ST'] not in OFFICIAL_STATES or school['UPDATED_STATUS'] not in OPERATIONAL:
            continue
        key = school['LEAID']
        operational[key] += 1
        total = school_membership['totals'].get(school['NCESSCH'])
        grades = school_membership['grades'].get(school['NCESSCH'])
        if total and (total['ST'] != school['ST'] or total['ST_SCHID'] != school['ST_SCHID']):
            raise ValueError('School membership identity crosses the directory namespace')
        level = potential_cohort(school, total, grades)
        if level:
            cohorts[key][level].append(school['NCESSCH'])
    agencies, excluded, seen = [], Counter(), set()
    for number, district in enumerate(read_lea(LEA_DIRECTORY), 2):
        key = district['LEAID']
        if district['SCHOOL_YEAR'] != RULES['school_year'] or not re.fullmatch(r'\d{7}', key) or key in seen:
            raise ValueError('Wrong-year, invalid or duplicate LEA directory record')
        seen.add(key)
        if district['ST'] not in OFFICIAL_STATES or district['UPDATED_STATUS'] not in OPERATIONAL:
            continue
        membership = totals.get(key)
        if membership and any(membership['row'][field] != district[field] for field in ['ST', 'ST_LEAID']):
            raise ValueError('LEA membership identity crosses the directory namespace')
        n = reported_count(membership['row']) if membership else None
        counts = {level: len(ids) for level, ids in cohorts[key].items()}
        tier = size_tier(n, counts)
        if tier is None and not (n is not None and n >= MAIN_ENROLLMENT):
            excluded['below_size_screen_or_unavailable_membership'] += 1
            continue
        agencies.append(dict(nces_lea_id=key, state=district['ST'], name=district['LEA_NAME'],
            native_lea_id=district['ST_LEAID'], enrollment=n,
            enrollment_flag=membership['row']['DMS_FLAG'] if membership else None,
            school_directory_operational_count=operational[key], potential_cohorts=counts,
            potential_school_ids={level: sorted(ids) for level, ids in cohorts[key].items()},
            tier=tier, scope=scope(district),
            directory_raw={field: district[field] for field in ['SCHOOL_YEAR', 'LEAID', 'ST_LEAID',
                'ST', 'LEA_NAME', 'UPDATED_STATUS', 'LEA_TYPE', 'LEA_TYPE_TEXT',
                'CHARTER_LEA', 'CHARTER_LEA_TEXT', 'OPERATIONAL_SCHOOLS']},
            directory_source_row=number, membership_raw=membership['row'] if membership else None,
            membership_source_row=membership['source_row'] if membership else None))
    sources = {key: source(RAW / filename, url) for key, filename, url in [
        ('lea_directory', LEA_DIRECTORY + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + LEA_DIRECTORY + '.zip'),
        ('lea_membership', LEA_MEMBERSHIP + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + LEA_MEMBERSHIP + '.zip'),
        ('school_directory', DIRECTORY + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + DIRECTORY + '.zip'),
        ('school_membership', MEMBERSHIP + '.zip', 'https://nces.ed.gov/ccd/Data/zip/' + MEMBERSHIP + '.zip'),
        ('lea_directory_companion', 'SY_2024-25_LEA_Directory_Companion_2026-005d.xlsx',
         'https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Directory_Companion_2026-005d.xlsx'),
        ('lea_membership_companion', 'SY_2024-25_LEA_Membership_Companion_2026-005d.xlsx',
         'https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Membership_Companion_2026-005d.xlsx'),
    ]}
    payload = dict(schema_version=1, school_year=RULES['school_year'], retrieved=date.today().isoformat(),
                   browser_catalog=False, approved_for_modeling=False, rules=RULES, sources=sources,
                   excluded=dict(excluded), agencies=sorted(agencies, key=lambda r: (-r['enrollment'], r['nces_lea_id'])))
    validate(payload)
    EXTRACT.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    return payload


def validate(payload):
    if (payload['schema_version'] != 1 or payload['rules'] != RULES or
            payload['school_year'] != RULES['school_year'] or payload['browser_catalog'] is not False or
            payload['approved_for_modeling'] is not False):
        raise ValueError('District planning extract cannot grant modeling approval or change rules')
    seen = set()
    for row in payload['agencies']:
        key = row['nces_lea_id']
        raw, membership = row['directory_raw'], row['membership_raw']
        if not re.fullmatch(r'\d{7}', key) or key in seen or row['state'] not in OFFICIAL_STATES:
            raise ValueError('Invalid or duplicate district identity')
        seen.add(key)
        if (raw['LEAID'] != key or raw['ST'] != row['state'] or raw['LEA_NAME'] != row['name'] or
                raw['ST_LEAID'] != row['native_lea_id'] or raw['SCHOOL_YEAR'] != RULES['school_year'] or
                raw['UPDATED_STATUS'] not in OPERATIONAL):
            raise ValueError('District identity differs from native source')
        if (membership is None or membership['LEAID'] != key or membership['ST'] != row['state'] or
                membership['ST_LEAID'] != row['native_lea_id'] or membership['SCHOOL_YEAR'] != RULES['school_year'] or
                membership['TOTAL_INDICATOR'] != 'Education Unit Total' or
                reported_count(membership) != row['enrollment'] or membership['DMS_FLAG'] != row['enrollment_flag']):
            raise ValueError('District enrollment differs from native same-year total')
        ids = [school for level in ['ES', 'HS'] for school in row['potential_school_ids'][level]]
        if len(ids) != len(set(ids)) or any(not re.fullmatch(r'\d{12}', school) or school[:7] != key for school in ids):
            raise ValueError('Potential school cohort contains a foreign or duplicated LEA identity')
        if row['potential_cohorts'] != {level: len(row['potential_school_ids'][level]) for level in ['ES', 'HS']}:
            raise ValueError('Potential cohort count differs from its school IDs')
        if row['tier'] != size_tier(row['enrollment'], row['potential_cohorts']) or row['scope'] != scope(raw):
            raise ValueError('District shortlist tier or scope differs from source policy')


def render(payload):
    validate(payload)
    states = {row['id']: row for row in load_registry()['states']}
    candidates = [row for row in payload['agencies'] if row['tier'] and row['scope'] == 'new_district_candidate']
    main = [row for row in candidates if row['tier'] == 'main']
    secondary = [row for row in candidates if row['tier'] == 'secondary']
    existing = [row for row in payload['agencies'] if row['scope'].startswith('existing_')]
    review = [row for row in payload['agencies'] if not row['scope'].startswith('existing_') and row not in candidates]
    lines = [
        '# District comparison queue', '',
        'Implement these after the statewide basics. A district comparison would fit its own '
        'same-year, assessment, level and subject models, as CPS does. A filter using statewide '
        'predictions remains a district view of the statewide model; it is not a district comparison.', '',
        f'Size screen: official {payload["school_year"]} CCD LEA membership, retrieved {payload["retrieved"]}. '
        f'{len(main)} first-tier and {len(secondary)} second-tier new district candidates. '
        'The screen evaluates the 50 states; it excludes DC and territories. Source size and grade '
        'configuration do not establish usable assessment or income coverage.', '',
        '## Selection and implementation gates', '',
        f'- First tier: at least {MAIN_ENROLLMENT:,} students and {MIN_COHORT} potential pure grade schools '
        'or 30 potential pure high schools. Second tier: 20,000–49,999 students with the same cohort floor.',
        '- Ordinary districts use native LEA types 1/2. Charter operators, supervisory unions, '
        'specialized agencies and regular districts with federal charter designations receive separate scope review.',
        '- Potential ES/HS counts use operational schools, complete same-year reported grade offers '
        'and reconciled reported school membership. Grade schools have at least one grade 3–8 and '
        'no high-school grades; pure high schools have no lower grades. Mixed and ambiguous schools '
        'are not pooled into either count. These are configuration counts, not usable model counts.',
        '- Before adding a comparison, verify at least 30 usable schools separately for Math, ELA '
        'and Combined in each proposed population. Report usable/profile coverage within that '
        'cohort, same-year income spread, leverage and exclusions. Thirty is a practical planning '
        'floor, not a guarantee of a stable regression.',
        '- Resolve state source holds first. Audit exact school-to-district IDs, charter/alternative '
        'scope, source definitions, suppression and every-member interval availability. Never '
        'group by district name or merge unrelated districts to reach the floor.',
        '- Prioritize larger usable cohorts after their audits. Preserve existing CPS and NYC '
        'models. State and district residuals describe different comparison populations and '
        'must remain explicitly labeled.', '',
    ]
    def table(title, rows):
        lines.extend([f'## {title}', '', '| District | State | NCES LEA | Students | Potential ES / HS | State source status |',
                      '| --- | --- | --- | ---: | ---: | --- |'])
        for row in rows:
            state = states[row['state']]
            status = 'Available; district audit pending' if state['status'] == 'statewide_ready' else (
                'State audit pending' if state['status'] == 'implementation' else 'State source hold')
            if row['scope'] == 'existing_chicago':
                status = 'Existing CPS comparison; size reference'
            elif row['scope'] == 'existing_los_angeles':
                status = 'Existing Los Angeles Unified comparison; pure cohorts'
            elif row['scope'] == 'existing_miami_dade':
                status = 'Existing Miami-Dade comparison; pure grade schools only'
            elif row['scope'] == 'existing_broward':
                status = 'Existing Broward comparison; pure grade schools only'
            elif row['scope'] == 'existing_hillsborough':
                status = 'Existing Hillsborough comparison; pure grade schools only'
            elif row['scope'] == 'existing_orange':
                status = 'Existing Orange County comparison; pure grade schools only'
            elif row['scope'] == 'existing_palm_beach':
                status = 'Existing Palm Beach County comparison; pure grade schools only'
            elif row['scope'] == 'existing_gwinnett':
                status = 'Existing Gwinnett County comparison; pure grade schools only'
            elif row['scope'] == 'existing_fairfax':
                status = 'Existing Fairfax County comparison; native grade schools only'
            elif row['scope'] == 'existing_houston':
                status = 'Existing Houston ISD comparison; native published-rate grade schools only'
            elif row['scope'] == 'existing_wake':
                status = 'Existing Wake County comparison; native regular grade-school scope only'
            elif row['scope'] == 'existing_clark_county':
                status = 'Existing Clark County comparison; native grade-school scope only'
            elif row['scope'] == 'existing_hawaii_statewide':
                status = 'Existing statewide comparison'
            elif row['scope'] == 'existing_nyc_component':
                status = 'Optional NYC subdistrict audit' if row['tier'] else 'NYC component; cohort floor review'
            counts = row['potential_cohorts']
            lines.append(f'| {row["name"].replace("|", " / ")} | {row["state"]} | {row["nces_lea_id"]} | '
                         f'{row["enrollment"]:,} | {counts["ES"]} / {counts["HS"]} | {status} |')
        lines.append('')
    table('First tier · largest new district comparisons', main)
    table('Second tier · substantial regional comparisons', secondary)
    lines.extend(['## Existing comparisons and components', '',
        'CPS, Los Angeles Unified, Miami-Dade, Clark County, Broward, Hillsborough, Orange, Palm Beach, Gwinnett, Fairfax, Houston and Wake County have implemented district comparisons with the populations documented below. Hawaii’s single state LEA already has its statewide '
        'comparison. The NYC geographic LEAs below are components of the existing NYC system; '
        'they would be optional subdistrict work, not additional whole-city systems. Do not '
        'add their counts to the Chancellor’s Office supervisory total or include District 75 '
        'or administrative charter category 84 as ordinary geographic districts.', ''])
    table('Existing scope · size references', existing)
    lines.extend(['## Scope or cohort review', '',
        'These agencies meet the district-size/cohort screen, or have at least 50,000 students '
        'but fewer than 30 potential schools in either pure cohort. Their scope needs a separate '
        'decision before entering the ordinary district queue.', '',
        '| Agency | State | NCES LEA | Students | Potential ES / HS | Review reason |',
        '| --- | --- | --- | ---: | ---: | --- |'])
    for row in review:
        reason = ('Fewer than 30 potential schools in either pure cohort' if row['tier'] is None else
                  'NYC District 75 special-school population; separate audit' if row['scope'] == 'nyc_special_population_review' else
                  'Regular district; federal charter designation needs scope review' if row['scope'] == 'district_charter_status_review' else
                  row['directory_raw']['LEA_TYPE_TEXT'])
        counts = row['potential_cohorts']
        lines.append(f'| {row["name"]} | {row["state"]} | {row["nces_lea_id"]} | {row["enrollment"]:,} | '
                     f'{counts["ES"]} / {counts["HS"]} | {reason} |')
    if states['MI']['status'] == 'statewide_ready':
        lines.extend(['', '## Additional native-source follow-up', '',
            'Detroit Public Schools Community District (Michigan; NCES LEA `2601103`) '
            'warrants follow-up beyond the conservative CCD configuration screen. The '
            '[Michigan native audit](michigan-data.md#district-follow-up) resolves grade-school '
            'configuration, but current usable Math and Combined cohorts fall below the '
            '30-school implementation floor. It remains a district source/cohort hold; '
            'it is not included in the CCD-only candidate totals above.', ''])
    lines.extend(['', '## District source and model audits', '',
        'The [Los Angeles Unified roster and model audits](los-angeles-district.md) '
        'use exact official CCD school membership and same-year California records. '
        'They retain charter and alternative-school flags, separate mixed-grade schools, '
        'and document subject exclusions. The district region uses separate audited '
        'fits; statewide California remains its own comparison.', '',
        'The [Miami-Dade roster and numerical audits](miami-dade-district.md) keep exact '
        'CCD district membership separate from Florida\'s native enrolled-grade school '
        'population. They document offered-versus-enrolled grade differences, raw '
        'individual lunch eligibility, collocated/virtual exclusions and missing '
        'score counts. The district region uses independently checked pure grade-school '
        'fits with no sampling intervals; high-school and mixed assessment scope remain '
        'unaudited. Statewide Florida remains its own comparison.', ''])
    lines.extend([
        'The [Clark County source, numerical and integration audits](clark-county-district.md) '
        'retain exact Nevada LEA 3200060 / NV-02 membership and the reported-zero '
        'ungraded-enrollment safeguard. The region retains 289 native source profiles '
        'with independent 286-school Math, ELA and Combined district models. All '
        '299 native lower configurations and wider operational exclusions remain '
        'auditable. Valid-score counts and sampling intervals are unavailable; '
        'high-school and mixed assessment scope remains unaudited. Statewide Nevada '
        'remains its own comparison.', ''])
    lines.extend([
        'The [Broward source, numerical and integration audits](broward-district.md) retain exact Florida '
        'LEA 1200180 / FL-06 membership, same-year individual lunch eligibility and '
        'native School Grades records. Offered and enrolled grade populations, '
        'source exclusions and missing records remain explicit. Three independent '
        '241-school district fits retain external studentization and influence diagnostics '
        'without sampling intervals. The separate region retains all 249 pure lower '
        'profiles, including six primary-only and two missing campus-outcome profiles. '
        'Both historical audits keep approval false; the separately validated adapter '
        'supplies canonical/browser readiness. High-school and mixed assessment scope '
        'remain unaudited. Statewide Florida remains its own comparison.', ''])
    lines.extend([
        'The [Hillsborough source, numerical and integration audits](hillsborough-district.md) retain all 309 original '
        'CCD records for Florida LEA 1200870 / FL-29, including 293 operational schools, '
        'and all same-year native records. Exact operational joins yield 222 pure lower '
        'profiles, 220 offered-applicable schools and 219 usable schools per subject. '
        'Two usable charters absent from the discovery list remain in the source-derived '
        'cohort; planning IDs never select its membership. Primary-only, missing, mixed '
        'and outside-roster records remain explicit. The separate Florida district region '
        'retains all 222 matched profiles and the complete 224-school offered directory '
        'inventory in coverage. Three separate 219-school fits and '
        'all 657 explicit deleted-school checks retain external studentization and '
        'descriptive influence diagnostics without fit-based exclusions. Counts, sampling '
        'variances and intervals remain unavailable. Both immutable audits keep approval '
        'false; the separately validated normalized adapter supplies canonical/browser '
        'readiness. High/mixed assessment scope remains unaudited. Hillsborough is '
        'recorded as an existing comparison; planning membership never approves models.', ''])
    lines.extend([
        'The [Orange County source, numerical and integration audits](orange-district.md) '
        'retain all 282 original CCD records for Florida LEA `1201440` / `FL-48`, '
        'including 275 operational schools and exact same-year Florida records. The '
        'separate pure grade-school region retains all 208 matched profiles and the '
        'complete 209-school offered inventory in coverage, with 206 applicable '
        'schools and independently verified 200-school Math, ELA and Combined fits. '
        'All 600 deleted-school fits and canonical/current/history metrics are '
        'verified without fit-based exclusions. Both eligible zero-income charters '
        'remain included; collocated aggregates, missing outcomes, primary profiles '
        'and mixed offerings remain explicit. Counts, variances and intervals are '
        'unavailable. Both immutable audits keep false approvals; the separately '
        'validated normalized adapter supplies readiness. High/mixed assessment '
        'scope remains unaudited. Orange is an existing comparison; planning '
        'membership never approves models.', ''])
    lines.extend([
        'The [Palm Beach County source, numerical and integration audits](palm-beach-district.md) '
        'retain all 238 original CCD records for Florida LEA `1201500` / `FL-50`, '
        'including 234 operational schools and 230 exact same-year Fall/income profiles. '
        'The separate pure grade-school region retains all 170 matched profiles, '
        '168 applicable schools and independently verified 165-school Math, ELA and '
        'Combined models. All 495 deleted-school fits and canonical/current/history '
        'metrics are verified without fit-based exclusions. Career and Technical '
        'charter South Tech Preparatory Academy remains included; primary-only profiles, '
        'missing campus outcomes, masked mixed-income and provider-specific virtual '
        'records remain explicit. Both immutable historical audits keep false approvals; '
        'the separately validated normalized adapter supplies canonical/browser readiness. '
        'Counts, variances and sampling intervals remain unavailable. High/mixed '
        'assessment scope remains unaudited. Palm Beach is an existing comparison; '
        'planning membership never approves models.', ''])
    lines.extend([
        'The [Gwinnett County source, numerical and integration audits](gwinnett-district.md) '
        'retain exact Georgia LEA `1302550` / `GA-667`, all 141 operational directory '
        'records and original same-year membership, direct-certification and Georgia '
        'Milestones EOG evidence. The separate Georgia region retains all 111 pure '
        'grade-school profiles in independently verified Math, ELA and Combined models, '
        'including New Life charter. All 333 deleted-school fits and canonical/current/history '
        'metrics are verified without fit-based exclusions. Six mixed and 24 high '
        'configurations remain separate; Medicaid/foster, outside-program PK and '
        'later-release roster notes remain explicit. Counts, variances and sampling '
        'intervals stay null modelwide. Both historical audits keep false approvals; '
        'the separately validated normalized adapter supplies readiness. High/mixed '
        'assessment scope remains unaudited. Gwinnett is an existing comparison; '
        'planning membership never approves models.', ''])
    lines.extend([
        'The [Fairfax County source, numerical and integration audits](fairfax-district.md) '
        'retain exact Virginia LEA `5101260` / `VA-029`, all 223 operational CCD records '
        'and 195 native School Quality profiles. The separate Virginia region retains '
        'all 162 native grade-school profiles and independently verified 152-school '
        'Math, ELA and Combined models. Ten unavailable native incomes and 61 outside '
        'records remain explicit, including missing native profiles and Lake Braddock’s '
        'positive Post Graduate count. Individual economic-status income is broader '
        'than FRPL and requires complete same-year September 30 reconciliation. '
        'Direct published All Students SOL/VAAP Passed rates retain the 2025 standards '
        'change; grade/course rates and rounded categories are never averaged or summed '
        'to replace them. All 456 deleted-school fits and canonical/current/history '
        'metrics are verified. Both immutable historical audits keep false approvals; '
        'readiness belongs to the separately validated adapter. Counts, variances and '
        'sampling intervals stay null modelwide. High/mixed cohorts remain below the '
        '30-school floor. Fairfax is an existing comparison; planning counts never '
        'select or approve its models.', ''])
    lines.extend([
        'The [Houston ISD source, published-rate numerical and integration audits](houston-district.md) retain exact '
        'Texas LEA `4823640` / `TX-101912`, all 274 CCD school records and 273 '
        'native TAPR profiles. Same-year native enrolled grades identify 212 grade '
        'school profiles and separate 210-school Math, ELA and Combined models, with '
        'all 630 deleted-school fits and canonical/current/history results verified. Missing and masked results, '
        'ten primary-only campuses, 42 high-only and nine mixed campuses, the '
        'reported-zero EL DAEP record and T H Rogers enrollment/reference-span '
        'difference remain explicit. Income uses reconciled individual October '
        'enrollment status. Reported native performance counts and rates reconcile, '
        'but exact current N/M score-status mapping remains a gate for verified '
        'scored-count and sampling-interval use. The separate numerical contract uses '
        '210 original whole-percent published rates per subject, with null counts, '
        'variances and intervals; 202 Math and 203 ELA values differ from historical '
        'count-ratio precision. Its unknown-count policy does not certify the '
        'ten-valid-scored floor or close #16. Both immutable audit approvals remain '
        'false; readiness belongs to the separately validated normalized adapter. '
        'Texas → Houston ISD is an existing district comparison, separate from statewide '
        'Texas. Planning counts never select or approve its models. High/mixed assessment '
        'populations, admissions classifications, geometry and provider roles remain unaudited.', ''])
    lines.extend([
        'The [Wake County source, numerical and integration audits](wake-district.md) retain exact '
        'North Carolina LEA `3704720` / `NC-920`, all 202 original CCD directory records and '
        '162 complete grade-school configurations. The separate North Carolina → Wake County '
        'comparison retains 160 same-year native April individual EDS profiles and independently '
        'verified 159-school Math/Combined and 160-school ELA models. All 478 deleted-school fits '
        'and canonical/current/history results are verified without diagnostic exclusions; '
        'three eligible Alternative School records remain in every model. Two suppressed incomes '
        'and Mills Park Middle’s suppressed Math remain explicit, alongside all 36 outside '
        'configurations, four future schools and the fall district/school enrollment discrepancy. '
        'Direct regular RG/GS/ALL GLP rates retain Level 3 and above, grade-8 Math 1 and the '
        'summer-2024 source convention; grade/course percentages and accountability-adjusted '
        'rates never replace them. Income uses April individual economic status for the broader '
        'enrolled population. Native tested-count scope and the ten-valid-scored floor remain '
        'uncertified; verified counts, sampling variances and interval endpoints stay null '
        'modelwide. Both immutable historical audits keep false approvals; readiness belongs '
        'to the separately validated normalized adapter. Statewide North Carolina remains a '
        'separate comparison. Wake is an existing district comparison; planning counts never '
        'select or approve its models. High/mixed assessment populations, admissions, geometry '
        'and provider roles remain unaudited.', ''])
    lines.extend(['', '## Provenance and rebuild', '',
        'Enrollment uses the native LEA **Education Unit Total**, with `DMS_FLAG=Reported`; '
        'it is not a sum of school enrollment and is never a tested-score denominator. '
        'Every included agency retains its native raw directory/total records and source-row '
        'numbers. Reconstructed operational counts from the school directory remain separate '
        'from the native LEA operational-school field. The extract retains exact potential '
        'school IDs, source URLs and SHA-256 hashes. '
        'It is a planning artifact and never enables a browser comparison.', '',
        '[Machine-readable planning extract](../data/source/district-comparison-candidates.json) · '
        '[State expansion status](state-expansion.md) · [State source holds](expansion-blockers.md)', ''])
    for key, record in payload['sources'].items():
        lines.append(f'- [{key.replace("_", " ")}](<{record["url"]}>) · SHA-256 `{record["sha256"]}`')
    lines.extend(['', '```sh',
        '.venv/bin/python scripts/plan_district_comparisons.py            # render committed extract offline',
        '.venv/bin/python scripts/plan_district_comparisons.py --extract  # re-screen downloaded CCD files',
        '```', ''])
    GUIDE.write_text('\n'.join(lines))
    print(json.dumps(dict(first_tier=len(main), second_tier=len(secondary),
                          existing_scopes=len(existing), scope_review=len(review)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    args = parser.parse_args()
    render(extract() if args.extract else json.loads(EXTRACT.read_text()))
