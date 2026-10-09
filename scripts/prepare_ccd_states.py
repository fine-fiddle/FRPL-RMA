"""Audited 2025 SEA grade totals + school-level CCD direct certification.

Default rebuilds use the committed extract, with no network dependency. --extract
reads the downloaded EDC v3.1 CSVs and official CCD 2024–25 releases described in
docs/ccd-state-data.md. Counts from EDC are retained as raw source cells only;
these models have no sampling intervals.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import re

from audit_national_sources import (RAW, EDC, MEMBERSHIP, DIRECTORY, LUNCH,
    exact_rate, nces_id, read_ccd, membership_cache, source, SPECIAL_DC_NOTES)
from database import ROOT, DEFAULT_DB
from state_registry import OFFICIAL_STATES, reported_count
from state_snapshot import prepare_snapshot

EXTRACT = ROOT / 'data/source/ccd-state-snapshots.json'
STATES = ('AK', 'GA', 'LA', 'ME', 'NM', 'NV', 'RI', 'TN')
SLUGS = dict(AK='alaska', GA='georgia', LA='louisiana', ME='maine',
             NM='new-mexico', NV='nevada', RI='rhode-island', TN='tennessee')
ASSESSMENTS = dict(AK='AK STAR', GA='Georgia Milestones EOG', LA='LEAP 2025',
                   ME='Maine Through Year Assessment', NM='NM-MSSA', NV='SBAC',
                   RI='RICAS', TN='TNReady')
SEA = dict(AK='https://education.alaska.gov/compass/Report/2024-2025',
    GA='https://goews.georgia.gov/dashboards-data-report-card/downloadable-data',
    LA='https://doe.louisiana.gov/data-and-reports/elementary-and-middle-school-performance',
    ME='https://www.maine.gov/doe/dashboard',
    NM='https://newmexicoschools.com/',
    NV='https://nevadareportcard.nv.gov/di/main/assessment',
    RI='https://www3.ride.ri.gov/ADP',
    TN='https://www.tn.gov/education/districts/federal-programs-and-oversight/data/data-downloads.html')
# RIDE's CCD note says one no-membership site reports lunch in its main school.
# Until individual-school allocation is clarified, exclude the entire named LEA.
EXCLUDED_LEAS = {'RI': {'4400150'}}
DEFINITION = (
    'Reported school-level CCD 2024–25 Direct Certification Education Unit Total '
    'divided by reported positive same-year CCD Membership Education Unit Total, '
    'including pre-K where enrolled. Direct certification identifies individual '
    'students categorically eligible through benefits and other qualifying statuses '
    '(for example SNAP, TANF, FDPIR, foster care, migrant, homeless and Head Start; '
    'Medicaid eligibility varies by state). It is a benefits-based economic proxy, '
    'not all students eligible through household income or all students receiving '
    'free meals at a CEP school. No CEP multiplier, universal-meal count, FRPL '
    'fallback, tested-subgroup ratio or prior-year income is used. CCD membership '
    'is the fall snapshot; counts use the same academic year and exact NCES ID.')
RAW_OUTCOME_FIELDS = ['SchYear', 'DataLevel', 'StateAbbrev', 'NCESSchoolID',
    'StateAssignedSchID', 'NCESDistrictID', 'StateAssignedDistID', 'AssmtName',
    'AssmtType', 'Subject', 'GradeLevel', 'StudentGroup', 'StudentSubGroup',
    'StudentSubGroup_TotalTested', 'ProficiencyCriteria', 'ProficientOrAbove_percent',
    'ProficientOrAbove_count', 'ParticipationRate', 'Flag_AssmtNameChange',
    'Flag_CutScoreChange_ELA', 'Flag_CutScoreChange_math', 'Version']


def grade_school(profile, grades=None, total=None):
    """Require complete, unadjusted same-year grade offers, with no high grades."""
    if profile['IGOFFERED'] != 'As reported' or not re.fullmatch(r'0[1-8]', profile['GSHI']):
        return False
    fields = ['G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] + ['G_UG_OFFERED', 'G_AE_OFFERED']
    if any(profile[field] not in ['Yes', 'No'] for field in fields):
        return False
    if any(profile[field] == 'Yes' for field in
           [f'G_{g}_OFFERED' for g in range(9, 14)] + ['G_AE_OFFERED']):
        return False
    if not grades:
        return False
    expected = ['Pre-Kindergarten', 'Kindergarten'] + [f'Grade {g}' for g in range(1, 9)]
    values = [reported_count(row) for grade, row in grades.items() if grade in expected]
    if (not values or any(value is None for value in values) or
            sum(values) != reported_count(total)):
        return False
    for grade, row in grades.items():
        if grade not in expected and (row['STUDENT_COUNT'] != '0' or
                row['DMS_FLAG'] not in ['Reported', 'Derived']):
            return False
    if profile['G_UG_OFFERED'] == 'Yes':
        # Nevada offers ungraded programs at every school. A reported zero and
        # reconciled same-year enrolled grades establish the grade-only scope.
        if not grades or reported_count(grades.get('Ungraded')) != 0:
            return False
    return True


def eligibility(state, profile, total, direct, grades=None):
    if profile is None:
        return 'Missing same-year CCD directory identity'
    if profile['UPDATED_STATUS'] not in ['1', '3', '4', '5', '8']:
        return 'School not operational in the same-year CCD directory'
    if profile['LEAID'] in EXCLUDED_LEAS.get(state, set()):
        return 'Known LEA lunch allocation scope requires clarification'
    if not grade_school(profile, grades, total):
        return 'Not an unambiguous grade school in the same-year CCD directory'
    n, dc = reported_count(total), reported_count(direct)
    if n is None or n <= 0:
        return 'Same-year CCD membership is missing, nonreported or zero'
    if dc is None:
        return 'CCD direct certification is missing, suppressed or nonreported'
    if dc > n:
        return 'Direct-certification count exceeds individual-school membership'
    if (direct['DATA_GROUP'] != 'Direct Certification' or
            direct['TOTAL_INDICATOR'] != 'Education Unit Total' or
            total.get('TOTAL_INDICATOR', 'Education Unit Total') != 'Education Unit Total'):
        raise ValueError('CCD count is outside the approved school-total category')
    for row in [profile, total, direct]:
        if row['ST'] != state or row.get('SCHOOL_YEAR', '2024-2025') != '2024-2025':
            raise ValueError('CCD exact-ID join crossed state or year')
    if total['NCESSCH'] != direct['NCESSCH'] or total['ST_SCHID'] != direct['ST_SCHID']:
        raise ValueError('CCD membership and direct certification identities disagree')
    return None


def compact_outcome(row):
    return {field: row[field] for field in RAW_OUTCOME_FIELDS}


def extract():
    inventory = json.loads((ROOT / 'data/source/national-snapshot-audit.json').read_text())
    sources = inventory['sources']
    directory = {row['NCESSCH']: row for row in read_ccd(DIRECTORY)}
    lunch = {row['NCESSCH']: (number, row) for number, row in enumerate(read_ccd(LUNCH), 2)
             if row['DATA_GROUP'] == 'Direct Certification'}
    membership_data = membership_cache()
    membership = membership_data['totals']
    notes = json.loads((RAW / 'ccd-2025-lunch-state-notes.json').read_text())
    snapshots = []
    for state in STATES:
        state_sources = dict(sources)
        state_sources['edc_2025'] = source(EDC / (state.lower() + '.csv'),
            f'https://www.eddatacenter.org/api/data/3.1?state={state}&year=2025')
        rows = json.loads((EDC / (state.lower() + '-all-students.json')).read_text())
        pairs = defaultdict(list)
        for number, row in enumerate(rows, 1):
            if row['GradeLevel'] != 'G38':
                continue
            if (row['SchYear'] != '2024-25' or row['StateAbbrev'] != state or
                row['DataLevel'] != 'School' or row['StudentGroup'] != 'All Students' or
                row['StudentSubGroup'] != 'All Students'):
                raise ValueError('EDC grade total is outside the audited population')
            pairs[nces_id(row['NCESSchoolID'], state)].append((number, row))
        schools, excluded, criteria = [], [], set()
        for key, observations in sorted(pairs.items()):
            profile, total = directory.get(key), membership.get(key)
            if total is not None:
                # membership_cache filters these exact source fields before
                # writing its compact rows; retain their verified provenance.
                total = dict(total, SCHOOL_YEAR='2024-2025', TOTAL_INDICATOR='Education Unit Total')
            grades = membership_data['grades'].get(key)
            income_row, direct = lunch.get(key, (0, None))
            reason = eligibility(state, profile, total, direct, grades)
            if reason is None and (len(observations) != 2 or
                    {row['Subject'] for _, row in observations} != {'ela', 'math'} or
                    any(row['AssmtType'] != 'Regular' or row['AssmtName'] != ASSESSMENTS[state]
                        for _, row in observations)):
                reason = 'Missing or ambiguous native regular-assessment subject pair'
            if reason:
                excluded.append(dict(nces_id=key, reason=reason,
                    outcomes=[compact_outcome(row) for _, row in observations],
                    membership=total, membership_grades=grades, direct_certification=direct))
                continue
            n, dc = reported_count(total), reported_count(direct)
            outcomes = {}
            for number, row in observations:
                criteria.add(row['ProficiencyCriteria'])
                pct = exact_rate(row['ProficientOrAbove_percent'])
                outcomes['reading' if row['Subject'] == 'ela' else 'math'] = dict(
                    proficiency=None if pct is None else 100*pct, tested=None,
                    source='edc_2025', source_row=number,
                    source_row_basis='Ordinal in reproducible All Students school math/ELA compact extract',
                    raw=compact_outcome(row), raw_tested=row['StudentSubGroup_TotalTested'],
                    exclusion=None if pct is not None else 'Published native grade total is suppressed, ranged or missing')
            schools.append(dict(id=key, cohort='grade', name=profile['SCH_NAME'],
                district_id=profile['LEAID'], district=profile['LEA_NAME'], city=profile['LCITY'],
                county=None, enrollment=n, low_income=dc, income=100*dc/n,
                income_source='ccd_lunch_2025', income_row=income_row,
                income_raw=dict(direct_certification=direct, membership=total),
                membership_grades_raw=grades,
                identity_raw=dict(nces_id=key, state_id=profile['ST_SCHID'],
                    edc_nces_id=observations[0][1]['NCESSchoolID'],
                    normalization='Restore official 12-digit NCES width with leading zero; no name matching'),
                directory_raw={field: profile[field] for field in ['SCHOOL_YEAR', 'NCESSCH',
                    'ST_SCHID', 'LEAID', 'UPDATED_STATUS', 'GSLO', 'GSHI', 'IGOFFERED'] +
                    ['G_PK_OFFERED', 'G_KG_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)] +
                    ['G_UG_OFFERED', 'G_AE_OFFERED']}, outcomes=outcomes))
        if len(criteria) != 1:
            raise ValueError(f'{state}: expected one proficiency threshold, found {criteria}; {len(schools)} schools')
        name = OFFICIAL_STATES[state][0]
        assessment = ASSESSMENTS[state] + ' grades 3–8 · grade schools · CCD DC'
        note = SPECIAL_DC_NOTES.get(state, 'No school-allocation warning is published in the audited CCD 2a state notes.')
        if state == 'RI':
            note += ' Exclude every school in LEA 4400150 pending individual-school allocation clarification.'
        source_audit = dict(native_g38_provenance=
            'EDC v3.1 GradeLevel codebook labels G38 as SEA-sourced aggregate grades 3–8. '
            'Use exact published ProficientOrAbove_percent only; EDC may sum achievement-level '
            'percentages within this native total. No grade aggregation is performed.',
            tested_denominator='Unverified; retained raw but excluded from every model and interval.',
            school_year='2024-25', proficiency_criteria=next(iter(criteria)),
            ccd_release='Directory/membership Final 1a; lunch Final 2a June 2026',
            excluded_lea_ids=sorted(EXCLUDED_LEAS.get(state, set())),
            state_lunch_notes=[r for r in notes if r['State or Jurisdiction'] == name],
            approved_point_only=True,
            approval_basis='SEA-native G38 grade total documented in EDC v3.1 codebook; '
                'exact published rate, one regular assessment/threshold, same-year reported '
                'individual-school CCD DC and membership, audited grade scope and state notes.',
            source_schools=len(pairs), exclusions=dict(Counter(r['reason'] for r in excluded)))
        if state == 'RI':
            source_audit['primary_crosscheck'] = 'All 231 school G38 rows per subject match official RIDE By_School rates and raw tested values.'
            for subject in [5, 6]:
                state_sources[f'ride_native_{subject}'] = source(RAW / f'ri-ricas-2025-{subject}.xlsx',
                    f'https://www3.ride.ri.gov/ADP/Default/QuickReport?subject={subject}&schYear=2024-25&type=school')
        details = [DEFINITION, note,
            'Each state has separate externally studentized math, ELA and Combined models. '
            'Combined is the equally weighted mean of the two proficiency rates. State '
            'thresholds and benefits eligibility differ; results do not support national rankings.',
            'Use only native G38 school totals for All Students, Regular assessment. '
            'Exclude mixed/high/unknown grade configurations and adjusted CCD grade metadata. '
            'Published suppression, ranges and missing values remain unavailable.',
            'Sampling intervals are unavailable for every model: EDC tested and constructed '
            'level counts have not been verified as valid-score denominators. One audited '
            'snapshot is available; no assessment or income history is inferred.',
            source_audit['native_g38_provenance']]
        snapshots.append(dict(dataset=state.lower()+'-edc-ccd-dc', year=2025,
            academic_year='2024–25', state=dict(id=state, name=name), name=name+' 2025 EDC + CCD direct certification',
            region=SLUGS[state], prepare_script='scripts/prepare_ccd_states.py',
            source_url=state_sources['edc_2025']['url'], retrieved=date.today().isoformat(),
            model_scope=name+' public grade schools with exact native rates and reported same-year school DC and membership',
            income_definition=dict(label='Direct certification', definition=DEFINITION+' '+note,
                url=sources['nces_lunch_definitions']['url']), sources=state_sources,
            cohorts=[dict(id='grade', level='ES', assessment=assessment, grades='3–8',
                standard=next(iter(criteria))+'; '+name+' 2025 regular assessment; separate state model',
                source='edc_2025', source_url=SEA[state], label='Grade schools · '+ASSESSMENTS[state],
                outcome='Proficient or above', note='Grade schools · native grades 3–8 totals · direct certification',
                allow_point_only=True)], schools=schools, excluded=excluded, source_audit=source_audit,
            coverage_note=f'{len(schools)} grade schools with same-year reported school direct certification and enrollment; '
                'subject coverage excludes suppressed, ranged and missing published rates. High schools and history are unavailable.',
            methodology=dict(summary='Native '+name+' grade-school proficiency with same-year school direct certification.',
                details=details, sources=[dict(label='EDC v3.1 source and definitions', url='https://www.eddatacenter.org/data'),
                    dict(label=name+' assessment source', url=SEA[state]),
                    dict(label='NCES school-lunch definitions', url=sources['nces_lunch_definitions']['url']),
                    dict(label='CCD 2024–25 Final 2a state notes', url=sources['ccd_state_notes_2025']['url'])])))
    output = dict(schema_version=1, school_year='2024-25', states=snapshots)
    EXTRACT.write_text(json.dumps(output, separators=(',', ':'), allow_nan=False)+'\n')
    return output


def validate_snapshot(snapshot):
    state = snapshot['state']['id']
    if (state not in STATES or snapshot['year'] != 2025 or snapshot['academic_year'] != '2024–25'
            or snapshot['dataset'] != state.lower()+'-edc-ccd-dc'
            or snapshot['source_audit']['approved_point_only'] is not True):
        raise ValueError('State snapshot is outside the approved single-year path')
    criteria = 'Levels 4-5' if state == 'LA' else 'Levels 3-4'
    name = OFFICIAL_STATES[state][0]
    expected_cohort = dict(id='grade', level='ES', allow_point_only=True, grades='3–8',
        assessment=ASSESSMENTS[state]+' grades 3–8 · grade schools · CCD DC',
        standard=criteria+'; '+name+' 2025 regular assessment; separate state model',
        source='edc_2025', source_url=SEA[state])
    if (len(snapshot['cohorts']) != 1 or
            any(snapshot['cohorts'][0].get(field) != value for field, value in expected_cohort.items()) or
            snapshot['cohorts'][0].get('allow_point_only') is not True):
        raise ValueError('CCD snapshot requires the approved 2025 ES native G38 cohort metadata')
    if (snapshot['state']['name'] != name or snapshot['region'] != SLUGS[state] or
            snapshot['source_audit']['school_year'] != '2024-25' or
            snapshot['source_audit']['proficiency_criteria'] != criteria):
        raise ValueError('CCD snapshot state, year or threshold metadata disagrees with the approved population')
    expected_sources = {'edc_2025': (str((EDC/(state.lower()+'.csv')).relative_to(ROOT)),
            f'https://www.eddatacenter.org/api/data/3.1?state={state}&year=2025')}
    for key, stem in [('ccd_directory_2025', DIRECTORY), ('ccd_membership_2025', MEMBERSHIP),
                      ('ccd_lunch_2025', LUNCH)]:
        expected_sources[key] = (str((RAW/(stem+'.zip')).relative_to(ROOT)),
                                'https://nces.ed.gov/ccd/Data/zip/'+stem+'.zip')
    for key, (path, url) in expected_sources.items():
        recorded = snapshot['sources'].get(key, {})
        if recorded.get('path') != path or recorded.get('url') != url:
            raise ValueError('CCD snapshot source is outside the approved state/year/release contract')
    for school in snapshot['schools']:
        raw, profile = school['income_raw'], school['directory_raw']
        if (school['id'] != nces_id(school['identity_raw']['edc_nces_id'], state)
                or school['id'] != raw['membership']['NCESSCH']
                or school['id'] != profile['NCESSCH']
                or school['cohort'] != 'grade'
                or school['income_source'] != 'ccd_lunch_2025'):
            raise ValueError('School identity or cohort disagrees with authoritative source')
        # The compact directory keeps the exact state and year for offline validation.
        directory = dict(profile, ST=state)
        if eligibility(state, directory, raw['membership'], raw['direct_certification'],
                       school['membership_grades_raw']) is not None:
            raise ValueError('Committed snapshot includes an ineligible CCD school')
        n, dc = reported_count(raw['membership']), reported_count(raw['direct_certification'])
        if (school['income'] != 100*dc/n or school['enrollment'] != n or school['low_income'] != dc):
            raise ValueError('Economic values disagree with same-year school DC and membership')
        for subject, outcome in school['outcomes'].items():
            row = outcome['raw']
            if (subject not in ['math', 'reading'] or outcome['tested'] is not None or
                    outcome['source'] != 'edc_2025' or
                    row['SchYear'] != '2024-25' or row['StateAbbrev'] != state or
                    row['GradeLevel'] != 'G38' or row['DataLevel'] != 'School' or
                    row['StudentGroup'] != 'All Students' or row['StudentSubGroup'] != 'All Students' or
                    row['AssmtType'] != 'Regular' or row['AssmtName'] != ASSESSMENTS[state] or
                    row['Subject'] != ('ela' if subject == 'reading' else 'math') or
                    row['ProficiencyCriteria'] != criteria or
                    nces_id(row['NCESSchoolID'], state) != school['id']):
                raise ValueError('Assessment is outside the approved native point-only total')
            rate = exact_rate(row['ProficientOrAbove_percent'])
            if outcome['proficiency'] != (None if rate is None else 100*rate):
                raise ValueError('Outcome reconstructs or replaces the native published rate')


def prepare(database=DEFAULT_DB, states=None):
    payload = json.loads(EXTRACT.read_text())
    if payload['school_year'] != '2024-25' or {s['state']['id'] for s in payload['states']} != set(STATES):
        raise ValueError('Unexpected approved state snapshot inventory')
    audits = {}
    for snapshot in payload['states']:
        state = snapshot['state']['id']
        if states is not None and state not in states:
            continue
        validate_snapshot(snapshot)
        audit = prepare_snapshot(snapshot, EXTRACT, ROOT / 'data' / SLUGS[state], database)
        audits[state] = audit
        print(state, json.dumps(audit['cohorts']), flush=True)
    return audits


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--state', action='append', choices=STATES)
    args = parser.parse_args()
    if args.extract:
        extract()
    prepare(args.database, args.state)
