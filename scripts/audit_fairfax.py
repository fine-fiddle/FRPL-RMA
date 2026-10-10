"""Replay Fairfax County's 2024–25 native source/cohort evidence; never fit or import."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import subprocess
import zipfile

import prepare_virginia as virginia
from state_registry import reported_count

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/source/fairfax-district-audit.json'
LEA, NATIVE_LEA = '5101260', 'VA-029'
YEAR, ACADEMIC_YEAR = 2025, '2024-2025'
OPERATIONAL = {'1', '3', '4', '5', '8'}
GRADES = ['PK', 'KG'] + [str(g) for g in range(1, 14)] + ['UG', 'AE']
STATE_EXTRACT_SHA = 'fff223450f4a03d1763e8704d7b2b95cd67fde27213e67582c457de24febfccc'
RAW_INPUT_SHA = '8be5fa3da5953fe1a9229e574a5ac67db7486e30ec73de80e365e26bcf75f7bd'
CCD_SOURCES = {
    'ccd_directory_2025': dict(path='data/raw/ccd_sch_029_2425_w_1a_073025.zip', url='https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip', bytes=13352819, sha256='39326da788aa322353d20ceaf8ad4baed26272502cd05b066cf6c594988b21ab'),
    'ccd_membership_2025': dict(path='data/raw/ccd_sch_052_2425_l_1a_073025.zip', url='https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip', bytes=212696691, sha256='4a7f660c5fc5eaae488dd02fd43498f349fc828b227edd0970d5b6995ead4d4d'),
    'ccd_lunch_2025': dict(path='data/raw/ccd_sch_033_2425_l_2a_073025.zip', url='https://nces.ed.gov/ccd/Data/zip/ccd_sch_033_2425_l_2a_073025.zip', bytes=14029439, sha256='97bda749e778ee74cb731d181bbcdaf0f9c6cd6edf94cb31518a5bbeab411dd6'),
    'ccd_state_notes_2025': dict(path='data/raw/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx', url='https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx', bytes=210984, sha256='6476b6b28b700389e261b87377d9cd249935503d53b5919fe1b7ef8b1052d1a7'),
}
POLICY = {
    'roster': 'Complete exact 2024–25 CCD LEA 5101260 / VA-029 directory, including all statuses, complete retained total/grade membership and lunch rows. Missing native school profiles remain explicit holds; names never join.',
    'identity': 'CCD ST_SCHID is VA-029- plus the already complete seven-digit native division/school key. Remove only that exact prefix and cross-check division 29 and the native school number from the same official profile. Never prepend division again, match names, or infer missing profiles.',
    'native_populations': 'Reuse the audited Virginia 2024–25 enrolled-grade contract: positive grades 3–8 only, high-only, and mixed grade 3–8 plus grades 9–12 are separate prospective populations. Positive unrecognized grades remain unclassified. Offered-versus-enrolled and strict CCD offered intersections are completeness diagnostics, never new population filters.',
    'income': virginia.ECON_DEFINITION,
    'income_reconciliation': 'Use native same-profile All Students and ED counts only when ED and non-ED exactly sum to All Students and every year-matched grade subtotal and total reconcile. Every required count and published ED percentage must be unsuppressed. Retain stale display percentages; never infer suppressed counts or replace missing native status with CCD direct certification.',
    'assessment': 'Native School Quality profile subject option 0, All Students subgroup 5, 2024-2025 Mathematics or English Reading Passed table/chart values. SOL plus VAAP; proficient plus advanced. Direct whole-subject totals only; no grade/course averaging. Retain every displayed year and raw performance category, but spring 2025 new 2023 mathematics and 2024 English standards exclude older years from the proposed snapshot.',
    'definition_urls': [virginia.PROFILE_PAGE, virginia.DOWNLOAD_PAGE, virginia.GLOSSARY, virginia.STANDARDS],
    'types': 'Retain all authoritative CCD charter/type flags and current native category labels. Current labels, names, offered grades, selective admissions and fit quality never filter the native source populations. This extract does not establish admissions classifications or virtual status.',
    'counts': 'No verified exact valid-score denominator. Enrollment, ED counts, CCD membership, portal Record Count, and participation never substitute for tested counts. Every verified denominator, sampling variance and interval stays unavailable for every prospective model.',
    'combined': 'Equal mean of eligible Math and ELA native pass percentages, not the fraction proficient in both.',
    'approval': 'Source/cohort audit only: status and scope audit_pending; source/modeling approvals false. Prospective grade-school release requires independent numerical diagnostics, canonical integration and browser checks. High/mixed cohorts below 30 remain unreleased; no fits are produced.',
}
PLANNING = dict(source='data/source/district-comparison-candidates.json', operational_roster=223,
                enrollment=179323, potential_ES=162, potential_HS=25,
                explanation='Discovery only. Exact IDs and original membership must reconcile independently; planning does not approve native outcomes, income, population membership or high/mixed models.')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def native_cell(value):
    return {'cell_type': type(value).__name__, 'iso8601': value.isoformat()} if isinstance(value, (datetime, date)) else value


def native_definition_fragments(markup):
    patterns = {
        'assessment_scope': r'The annual pass rate data reported on the Assessment tab includes[^<]*\.',
        'reading_population': r'This chart displays the percentage of students passing state reading tests\..*?</div>',
        'math_population': r'This chart displays the percentage of students passing state mathematics tests\..*?</div>',
        'fall_membership': r'title="Schools report annually on the number of students enrolled on September 30\..*?"',
        'individual_economic_status': r'A student is reported as economically disadvantaged.*?</ul>',
    }
    fragments = []
    for label, pattern in patterns.items():
        matches = list(re.finditer(pattern, markup, re.S))
        if len(matches) != 1:
            raise ValueError('Native school profile lacks unique original definition: ' + label)
        match = matches[0]
        fragments.append(dict(label=label, source_line=markup[:match.start()].count('\n') + 1, raw_markup=match.group()))
    return fragments


def load_virginia(path=virginia.EXTRACT):
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != STATE_EXTRACT_SHA:
        raise ValueError('Complete committed Virginia source fingerprint changed; fresh source audit required')
    payload = json.loads(content)
    if (payload.get('schema_version'), payload.get('state'), payload.get('year'), payload.get('academic_year')) != (1, 'VA', YEAR, ACADEMIC_YEAR):
        raise ValueError('Virginia source identity/year mismatch')
    seen = set()
    for entry in payload['profiles']:
        key = virginia.school_id(entry['raw'])
        if key != entry['school_id'] or key in seen or entry['source'] != 'va-profile-' + key or entry['source'] not in payload['sources']:
            raise ValueError('Invalid/duplicate native Virginia profile identity')
        seen.add(key)
        virginia.income_values(entry['raw']); virginia.band_for(entry['raw'])
        for subject in ['math', 'reading']:
            virginia.assessment_value(entry['raw'], subject)
    if len(seen) != 1812 or payload['inventory']['total_schools'] != 1812:
        raise ValueError('Virginia complete native inventory changed')
    return payload


def ccd_identity(raw, *, directory=False):
    if (raw.get('SCHOOL_YEAR') != ACADEMIC_YEAR or raw.get('ST') != 'VA'
            or raw.get('LEAID') != LEA or raw.get('ST_LEAID') != NATIVE_LEA
            or not re.fullmatch(LEA + r'\d{5}', raw.get('NCESSCH', ''))
            or not re.fullmatch(r'VA-029-029\d{4}', raw.get('ST_SCHID', ''))):
        raise ValueError('Fairfax requires exact same-year NCES and native CCD identities')
    if directory and raw.get('SY_STATUS') not in {'1', '2', '3', '4', '5', '6', '7', '8'}:
        raise ValueError('Unrecognized native CCD school status')
    return raw['ST_SCHID'][len(NATIVE_LEA) + 1:]


def offered_evidence(raw):
    flags = {g: raw.get('G_' + g + '_OFFERED') for g in GRADES}
    complete = raw.get('IGOFFERED') == 'As reported' and raw.get('NOGRADES') == 'No' and all(v in {'Yes', 'No'} for v in flags.values())
    offered = [g for g, value in flags.items() if value == 'Yes']
    lower, high = any(str(g) in offered for g in range(3, 9)), any(str(g) in offered for g in range(9, 13))
    no_grades = raw.get('NOGRADES') == 'Yes' and all(v == 'No' for v in flags.values())
    band = ('no_offered_grades' if no_grades else 'uncertain' if not complete else 'other' if '13' in offered or 'AE' in offered or 'UG' in offered
            else 'mixed' if lower and high else 'grade' if lower else 'high' if high else 'primary')
    return dict(flags=flags, complete_reported_flags=complete, no_reported_grades=no_grades, offered=offered,
                strict_offered_band=band, low=raw.get('GSLO'), high=raw.get('GSHI'), level=raw.get('LEVEL'))


def native_grade_evidence(raw):
    table = raw['grade_table']; index = table['years'].index(ACADEMIC_YEAR)
    values = [dict(label=r['label'], raw_count=r['values'][index], reported_count=virginia.number(r['values'][index], integral=True)) for r in table['rows']]
    known = {'Pre-Kindergarten', 'Pre-kindergarten', 'Preschool', 'Pre-K', 'Kindergarten'}
    unknown = [r['label'] for r in values if r['label'] != 'Total Enrollment' and r['reported_count'] not in {None, 0}
               and r['label'] not in known and not re.fullmatch(r'Grade (?:[1-9]|1[0-2])', r['label'])]
    band = virginia.band_for(raw)
    reason = ('Positive native grade outside classified PK–12: ' + ', '.join(unknown) if unknown
              else 'No classified positive native grade 3–8 or high-school enrollment' if band is None else None)
    return dict(year=YEAR, academic_year=ACADEMIC_YEAR, native_band=band, native_grade_values=values,
                positive_unrecognized_grades=unknown, missing_or_suppressed_grades=[r['label'] for r in values if r['reported_count'] is None],
                native_scope_exclusion=reason)


def income_evidence(raw):
    total, low, pct = virginia.income_values(raw)
    groups = raw['enrollment_subgroups']; display = virginia.number(groups.get('3', {}).get('pct'))
    grade = native_grade_evidence(raw)
    reason = None
    if pct is None:
        if total in {None, 0}: reason = 'Native All Students count missing, suppressed or zero'
        elif virginia.number(groups.get('3', {}).get('cnt'), integral=True) is None: reason = 'Native individual ED count missing or suppressed'
        elif display is None: reason = 'Native ED display percentage missing or suppressed'
        elif virginia.number(groups.get('18', {}).get('cnt'), integral=True) is None: reason = 'Native non-ED count missing or suppressed'
        elif grade['missing_or_suppressed_grades']: reason = 'At least one native same-year grade count is missing or suppressed'
        else: reason = 'Native ED/non-ED or complete grade counts do not reconcile to All Students'
    return dict(year=YEAR, definition=virginia.ECON_DEFINITION, reported_all_students=total, verified_ed_count=low,
                published_ed_percentage=display, percentage=pct,
                stale_display_percentage=pct is not None and abs(display - pct) > .00051,
                exclusion=reason, source='Native same-year economic-status subgroups; CCD lunch is retained supplemental evidence only')


def subjects_evidence(raw, income, operational=True):
    band = virginia.band_for(raw); values = {}
    for subject in ['math', 'reading']:
        native = virginia.assessment_value(raw, subject)
        reason = ('CCD school is not operational in the same year' if not operational else
                  native_grade_evidence(raw)['native_scope_exclusion'] or income['exclusion'] or
                  ('Native schoolwide All Students pass rate suppressed or not reported' if native is None else None))
        values[subject] = dict(applicable=operational and band is not None, native_rate=native,
                               raw_rate=raw['assessments'][subject]['school_values'][raw['assessments'][subject]['years'].index(ACADEMIC_YEAR)],
                               exclusion=reason, usable=reason is None, valid_scores=None, sampling_variance=None,
                               sampling_interval_available=False)
    usable = all(r['usable'] for r in values.values())
    values['combined'] = dict(applicable=operational and band is not None, native_rate=(values['math']['native_rate'] + values['reading']['native_rate']) / 2 if usable else None,
        usable=usable, exclusion='; '.join(s + ': ' + r['exclusion'] for s, r in values.items() if r['exclusion']) or None,
        valid_scores=None, sampling_variance=None, sampling_interval_available=False, definition=POLICY['combined'])
    return values


def summarize(links, band):
    selected = [r for r in links if r['native_profile_present'] and r['native_grade']['native_band'] == band and r['operational']]
    subjects = {}
    for subject in ['math', 'reading', 'combined']:
        members = [r for r in selected if r['subjects'][subject]['usable']]
        incomes = [r['income']['percentage'] for r in members]
        subjects[subject] = dict(applicable=sum(r['subjects'][subject]['applicable'] for r in selected), usable=len(members), eligible_school_ids=[r['school_id'] for r in members],
            eligible_ncessch=[r['ncessch'] for r in members], prospective_30_school_floor_met=len(members) >= 30,
            exclusions=dict(sorted(Counter(r['subjects'][subject]['exclusion'] for r in selected if not r['subjects'][subject]['usable']).items())),
            verified_valid_score_counts=0, model_sampling_intervals_available=False,
            income=dict(minimum=min(incomes) if incomes else None, maximum=max(incomes) if incomes else None,
                        distinct=len(set(incomes)), sample_standard_deviation=statistics.stdev(incomes) if len(incomes) > 1 else None))
    return dict(profiles=len(selected), school_ids=[r['school_id'] for r in selected], membership_basis=POLICY['native_populations'], subjects=subjects,
                strict_offered_intersection=[r['school_id'] for r in selected if r['offered']['strict_offered_band'] == band],
                offered_band_differences=[dict(school_id=r['school_id'], native_band=band, strict_offered_band=r['offered']['strict_offered_band']) for r in selected if r['offered']['strict_offered_band'] != band])


def expected_sources(payload):
    sources = dict(CCD_SOURCES)
    sources['virginia_extract_2025'] = dict(path='data/source/virginia.json', url=virginia.PROFILE_PAGE, sha256=STATE_EXTRACT_SHA)
    sources.update({e['source']: payload['sources'][e['source']] for e in payload['profiles'] if int(e['raw']['division_number']) == 29})
    return sources


def derive(document, payload):
    if (type(document.get('schema_version')) is not int or document.get('schema_version') != 1
            or document.get('state') != 'VA' or type(document.get('year')) is not int or document.get('year') != YEAR
            or document.get('academic_year') != ACADEMIC_YEAR or document.get('nces_lea_id') != LEA or document.get('native_lea_id') != NATIVE_LEA
            or document.get('status') != 'audit_pending' or document.get('scope') != 'audit_pending'
            or document.get('approved_for_source') is not False or document.get('approved_for_modeling') is not False
            or fingerprint(document.get('sources')) != fingerprint(expected_sources(payload))
            or fingerprint(document.get('policy')) != fingerprint(POLICY) or fingerprint(document.get('planning')) != fingerprint(PLANNING)
            or document.get('state_extract') != dict(path='data/source/virginia.json', sha256=STATE_EXTRACT_SHA)):
        raise ValueError('Fairfax source-only audit identity/provenance/policy changed')
    inputs = document['raw_inputs']
    if fingerprint(inputs) != RAW_INPUT_SHA:
        raise ValueError('Retained full original Fairfax source records/headers/references changed')
    profiles = {e['school_id']: e for e in payload['profiles'] if int(e['raw']['division_number']) == 29}
    if fingerprint(inputs['native_profiles']['records']) != fingerprint([profiles[k] for k in sorted(profiles)]):
        raise ValueError('Native Fairfax subset differs from complete Virginia source')
    if inputs['native_profiles']['source_inventory'] != payload['inventory']:
        raise ValueError('Native statewide inventory provenance changed')
    directory, ncids, seen_rows = {}, {}, set()
    for entry in inputs['directory']['records']:
        raw = entry['raw']; key = ccd_identity(raw, directory=True)
        if key in directory or raw['NCESSCH'] in ncids or entry['source_row'] in seen_rows or type(entry['source_row']) is not int or entry['source_row'] < 2:
            raise ValueError('Duplicate/invalid original CCD directory identity or row')
        directory[key] = entry; ncids[raw['NCESSCH']] = key; seen_rows.add(entry['source_row'])
    totals, grades, lunch = {}, defaultdict(dict), defaultdict(list)
    for label in ['membership', 'lunch']:
        rows = set()
        for entry in inputs[label]['records']:
            raw = entry['raw']; key = ccd_identity(raw)
            if (key not in directory or raw['NCESSCH'] != directory[key]['raw']['NCESSCH']
                    or entry['source_row'] in rows or type(entry['source_row']) is not int or entry['source_row'] < 2):
                raise ValueError('Original CCD count row has invalid/duplicate identity/reference')
            rows.add(entry['source_row']); reported_count(raw)
            if label == 'lunch': lunch[key].append(entry)
            elif raw['TOTAL_INDICATOR'] == 'Education Unit Total':
                if key in totals: raise ValueError('Duplicate CCD membership total')
                totals[key] = entry
            elif raw['TOTAL_INDICATOR'] == 'Subtotal 4 - By Grade':
                if raw['GRADE'] in grades[key]: raise ValueError('Duplicate CCD membership grade')
                grades[key][raw['GRADE']] = entry
            else: raise ValueError('Unexpected CCD membership population')
    if not set(totals) <= set(directory) or not set(profiles) <= set(directory):
        raise ValueError('Directory/member/native profile coverage no longer reconciles')
    links = []
    for key, entry in sorted(directory.items()):
        raw = entry['raw']; native = profiles.get(key); operational = raw['SY_STATUS'] in OPERATIONAL
        total_entry = totals.get(key)
        total = reported_count(None if total_entry is None else total_entry['raw'])
        grade_values = [dict(label=g, source_row=e['source_row'], raw_count=e['raw']['STUDENT_COUNT'], flag=e['raw']['DMS_FLAG'], reported_count=reported_count(e['raw'])) for g, e in sorted(grades[key].items())]
        link = dict(school_id=key, ncessch=raw['NCESSCH'], native_school_id=raw['ST_SCHID'], directory_source_row=entry['source_row'],
            operational=operational, name=raw['SCH_NAME'], native_profile_present=native is not None,
            ccd_flags=dict(status=raw['SY_STATUS_TEXT'], school_type=raw['SCH_TYPE_TEXT'], charter=raw['CHARTER_TEXT'], virtual_status=None),
            offered=offered_evidence(raw), ccd_membership=dict(present=total_entry is not None, total=total,
                raw_total=None if total_entry is None else total_entry['raw']['STUDENT_COUNT'], flag=None if total_entry is None else total_entry['raw']['DMS_FLAG'],
                total_source_row=None if total_entry is None else total_entry['source_row'], grade_values=grade_values,
                reported_grade_sum=sum(r['reported_count'] for r in grade_values) if grade_values and all(r['reported_count'] is not None for r in grade_values) else None),
            supplemental_ccd_lunch_source_rows=[e['source_row'] for e in lunch[key]],
            profile_exclusion=None if native else 'Exact CCD school has no profile in the complete audited native Virginia inventory; do not substitute CCD income/outcomes')
        if native:
            if virginia.school_id(native['raw']) != key or int(native['raw']['division_number']) != 29:
                raise ValueError('Native profile does not cross-check exact CCD code')
            link.update(native_source_id=native['source'], native_source_row=native['source_row'], native_grade=native_grade_evidence(native['raw']), income=income_evidence(native['raw']))
            link['subjects'] = subjects_evidence(native['raw'], link['income'], operational)
            link['membership_difference_native_minus_ccd'] = None if total is None or link['income']['reported_all_students'] is None else link['income']['reported_all_students'] - total
        else:
            link.update(native_source_id=None, native_source_row=None, native_grade=None, income=None,
                subjects={s: dict(applicable=False, usable=False, native_rate=None, exclusion=link['profile_exclusion'], valid_scores=None, sampling_variance=None, sampling_interval_available=False) for s in ['math', 'reading', 'combined']})
            link['membership_difference_native_minus_ccd'] = None
        links.append(link)
    cohorts = {band: summarize(links, band) for band in ['grade', 'high', 'mixed', None]}
    cohorts['unclassified'] = cohorts.pop(None)
    operative = [r for r in links if r['operational']]
    planning = inputs['planning']['record']
    if (planning['nces_lea_id'], planning['state'], planning['native_lea_id'], planning['enrollment'], planning['school_directory_operational_count'], planning['potential_cohorts']) != (LEA, 'VA', NATIVE_LEA, PLANNING['enrollment'], PLANNING['operational_roster'], {'ES': PLANNING['potential_ES'], 'HS': PLANNING['potential_HS']}):
        raise ValueError('Planning identity/count evidence changed')
    current_ids = {r['ncessch'] for r in operative}
    if any(not set(planning['potential_school_ids'][s]) <= current_ids for s in ['ES', 'HS']):
        raise ValueError('Discovery identities absent from exact operational roster')
    reconciled = dict(potential_school_ids=planning['potential_school_ids'], source='Discovery only, never membership approval',
        school_total_sum=sum(r['ccd_membership']['total'] for r in operative if r['ccd_membership']['total'] is not None),
        missing_or_nonreported_school_totals=[r['school_id'] for r in operative if r['ccd_membership']['total'] is None],
        native_grade_not_planning_ES=sorted(set(cohorts['grade']['school_ids']) - {ncids[n] for n in planning['potential_school_ids']['ES']}),
        planning_ES_not_native_grade=sorted({ncids[n] for n in planning['potential_school_ids']['ES']} - set(cohorts['grade']['school_ids'])))
    coverage = dict(directory_records=len(directory), operational_schools=len(operative), nonoperational_schools=len(links)-len(operative),
        operational_statuses=dict(sorted(Counter(r['ccd_flags']['status'] for r in operative).items())),
        operational_ccd_school_types=dict(sorted(Counter(r['ccd_flags']['school_type'] for r in operative).items())),
        operational_ccd_charter=dict(sorted(Counter(r['ccd_flags']['charter'] for r in operative).items())),
        operational_strict_offered_bands=dict(sorted(Counter(r['offered']['strict_offered_band'] for r in operative).items())),
        native_profiles=len(profiles), missing_native_profiles=len(directory)-len(profiles),
        native_grade_bands={k: v['profiles'] for k, v in cohorts.items()},
        income_unavailable=sum(r['native_profile_present'] and r['income']['percentage'] is None for r in links),
        stale_native_income_display_percentages=sum(r['native_profile_present'] and r['income']['stale_display_percentage'] for r in links),
        ccd_membership_schools=len(totals), ccd_membership_absent_schools=len(directory)-len(totals),
        native_membership_sum=sum(r['income']['reported_all_students'] for r in links if r['native_profile_present'] and r['income']['reported_all_students'] is not None),
        ccd_membership_sum_for_native_profiles=sum(r['ccd_membership']['total'] for r in links if r['native_profile_present'] and r['ccd_membership']['total'] is not None),
        native_ccd_membership_differences=sum(r['membership_difference_native_minus_ccd'] not in {None, 0} for r in links),
        raw_membership_rows=len(inputs['membership']['records']), raw_lunch_rows=len(inputs['lunch']['records']),
        verified_valid_score_counts=0, sampling_intervals_available=False)
    return dict(coverage=coverage, roster_links=links, cohorts=cohorts, planning_identity_reconciliation=reconciled,
        missing_native_profiles=[dict(school_id=r['school_id'], ncessch=r['ncessch'], name=r['name'], offered=r['offered'], ccd_membership=r['ccd_membership'], exclusion=r['profile_exclusion']) for r in links if not r['native_profile_present']],
        state_definition_evidence=inputs['definitions'], prospective_population='grade', hard_holds=[],
        release_holds=dict(grade=[], high=['Only 23 usable schools per subject; below prospective 30-school floor.'],
            mixed=['Only one usable school per subject; below prospective 30-school floor.'],
            unclassified=['Three native primary-only profiles and Lake Braddock with positive Post Graduate enrollment have no classified native assessment population.'],
            missing_native=['28 exact operational CCD schools lack audited native profiles; no native income or outcomes are substituted.']),
        coverage_notes=[
            'Grade-school source membership is complete for 162 exact operational native profiles: 152 usable per subject and ten native income exclusions. Numerical, canonical and browser release gates remain pending.',
            '24 exact directory programs report NOGRADES=Yes, every offered-grade flag No, and no original CCD membership rows. Absence is not zero or Ungraded enrollment.',
            'Four missing-native preschool centers have 784 reported CCD pupils. CCD membership/lunch never supply missing native status or rates.',
            'Fifteen native profiles across all bands have unavailable or unreconciled individual economic status; no masked grade, ED or non-ED count is inferred.',
        ])


def validate(document, payload=None):
    payload = load_virginia() if payload is None else payload
    # Pin the complete extract, even when callers supply an in-memory payload.
    if fingerprint(payload) != fingerprint(load_virginia()):
        raise ValueError('Virginia in-memory source differs from pinned complete extract')
    expected = derive(document, payload)
    for key, value in expected.items():
        if fingerprint(document.get(key)) != fingerprint(value):
            raise ValueError('Fairfax derived source evidence changed: ' + key)
    if 'models' in document or 'model_results' in document:
        raise ValueError('Source-only audit must not contain fits')
    return expected['coverage']


def extract_raw_inputs(payload, membership_evidence=None):
    for source in CCD_SOURCES.values():
        path = ROOT / source['path']
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != source['sha256'] or path.stat().st_size != source['bytes']:
            raise ValueError('Pinned original source archive changed: ' + source['path'])
    inputs = {}
    for label, source_id in [('directory', 'ccd_directory_2025'), ('lunch', 'ccd_lunch_2025')]:
        path = ROOT / CCD_SOURCES[source_id]['path']; member = path.stem + '.csv'
        with zipfile.ZipFile(path) as archive, archive.open(member) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig'))
            records = [dict(source_row=i, raw=row) for i, row in enumerate(reader, 2) if row['LEAID'] == LEA or row['ST_LEAID'] == NATIVE_LEA]
            header = reader.fieldnames
        inputs[label] = dict(source_id=source_id, member=member, header_source_row=1, header=header, records=records)
    source_id = 'ccd_membership_2025'; path = ROOT / CCD_SOURCES[source_id]['path']; member = path.stem + '.csv'
    if membership_evidence:
        evidence = json.loads(Path(membership_evidence).read_text())
        if any(evidence.get(k) != CCD_SOURCES[source_id][k] for k in ['path', 'url', 'sha256']):
            raise ValueError('Original membership bootstrap provenance changed')
        header, records = evidence['header'], evidence['records']
    else:
        process = subprocess.Popen(['unzip', '-p', str(path), member], stdout=subprocess.PIPE, text=True, encoding='utf-8-sig')
        try:
            reader = csv.DictReader(process.stdout)
            records = [dict(source_row=i, raw=row) for i, row in enumerate(reader, 2) if (row['LEAID'] == LEA or row['ST_LEAID'] == NATIVE_LEA) and row['TOTAL_INDICATOR'] in {'Education Unit Total', 'Subtotal 4 - By Grade'}]
            header = reader.fieldnames
            if process.wait() != 0: raise ValueError('Original membership archive streaming failed')
        finally:
            process.stdout.close()
            if process.poll() is None: process.terminate(); process.wait()
    inputs['membership'] = dict(source_id=source_id, member=member, header_source_row=1, header=header,
        selection='Every district Education Unit Total and Subtotal 4 - By Grade; all original fields and CSV row references. Race/sex subgroups never become denominators.', records=records)
    profiles = sorted([e for e in payload['profiles'] if int(e['raw']['division_number']) == 29], key=lambda e: e['school_id'])
    definitions = []
    for entry in profiles:
        source = payload['sources'][entry['source']]; path = ROOT / source['path']
        markup = path.read_text()
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256'] or fingerprint(virginia.parse_profile(markup)) != fingerprint(entry['raw']):
            raise ValueError('Original native school HTML no longer reproduces committed profile: ' + entry['school_id'])
        definitions.append(dict(school_id=entry['school_id'], source_id=entry['source'], fragments=native_definition_fragments(markup)))
    inputs['native_profiles'] = dict(selection='All exact native division 29 profiles from the complete 1,812-profile extract; all native years, grades, subgroups and raw performance categories retained.', source_inventory=payload['inventory'], records=profiles)
    import openpyxl
    workbook = openpyxl.load_workbook(ROOT / CCD_SOURCES['ccd_state_notes_2025']['path'], read_only=True, data_only=True)
    try:
        worksheets = [dict(worksheet=sheet.title, rows=[dict(source_row=i, raw=[native_cell(v) for v in row]) for i, row in enumerate(sheet.iter_rows(values_only=True), 1)]) for sheet in workbook]
    finally:
        workbook.close()
    inputs['definitions'] = dict(source_id='ccd_state_notes_2025', complete_workbook_worksheets=worksheets,
        native_definition_source_ids=[e['source'] for e in profiles], original_native_profile_definitions=definitions,
        native_profile_explanations='Full source HTML checksums and original definition fragments retained; Assessment tab includes SOL and VAAP; native Fall Membership economic-status definitions govern income. Complete CCD notes are supplemental, never substituted for native ED.')
    planning = json.loads((ROOT / PLANNING['source']).read_text()); agency = next(a for a in planning['agencies'] if a['nces_lea_id'] == LEA)
    fields = ['nces_lea_id', 'state', 'native_lea_id', 'enrollment', 'enrollment_flag', 'school_directory_operational_count', 'potential_cohorts', 'potential_school_ids', 'directory_raw', 'directory_source_row', 'membership_raw', 'membership_source_row']
    inputs['planning'] = dict(source=PLANNING['source'], sources=planning['sources'], record={k: agency[k] for k in fields})
    return inputs


def extract(output=OUTPUT, membership_evidence=None):
    payload = load_virginia(); inputs = extract_raw_inputs(payload, membership_evidence)
    document = dict(schema_version=1, state='VA', year=YEAR, academic_year=ACADEMIC_YEAR, nces_lea_id=LEA, native_lea_id=NATIVE_LEA,
        status='audit_pending', scope='audit_pending', approved_for_source=False, approved_for_modeling=False,
        sources=expected_sources(payload), policy=POLICY, planning=PLANNING, raw_inputs=inputs,
        state_extract=dict(path='data/source/virginia.json', sha256=STATE_EXTRACT_SHA))
    document.update(derive(document, payload)); validate(document, payload)
    Path(output).write_text(json.dumps(document, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return document['coverage']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--membership-evidence', type=Path, help='Separately verified complete original district membership subset')
    args = parser.parse_args()
    result = extract(args.output, args.membership_evidence) if args.extract else validate(json.loads(args.output.read_text()))
    print(json.dumps(result, sort_keys=True))
