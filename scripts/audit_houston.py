"""Replay Houston ISD's 2024–25 original-source/cohort audit; never fit or import."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/source/houston-district-audit.json'
LEA = '4823640'
NATIVE_LEA = 'TX-101912'
DISTRICT = '101912'
YEAR = '2024-2025'
OPERATIONAL = {'1', '3', '4', '5', '8'}
GRADES = ['CPNTGEEC', 'CPNTGPKC', 'CPNTGKNC'] + ['CPNTG%02dC' % g for g in range(1, 13)]
FIELDS = {s: ['CDA38A%s0E025D' % letter, 'CDA38A%s0E225N' % letter,
              'CDA38A%s0E225R' % letter] for s, letter in [('math', 'M'), ('reading', 'R')]}
STATE_EXTRACT_SHA = 'bb8a0882cc64fd569168bed05853cd9070d4ec4e0940fa27a2c6a029e1d78aac'
RAW_INPUT_SHA = '2868e49d097bd84249d609f642fcc25b858fde77bb9f18213e23747d59bb298b'
MANUAL_PAGES = [173, 177, 204]
SOURCES = {'assessment': {'bytes': 3806149, 'path': 'data/raw/tx_assessment_2025.csv', 'sha256': 'dcc2e16290ba99a47ace88e2bf3bafc60cb409f6d27d792fd7659df1c74cdf0d', 'url': 'https://rptsvr1.tea.texas.gov/cgi/sas/broker/?_service=marykay&_program=perfrept.perfmast.sas&_debug=0&ccyy=2025&tapr=all_c&sumlev=C&level=Campus&id=&prgopt=reports%2Ftapr%2Fdd%2Fdd_tapr_step_7.sas&datafmt=csv&dsname=STAAR_GR38&key=38AR0E2%7C38AR0E0&key=38AM0E2%7C38AM0E0&var_type=N&var_type=D&var_type=R'}, 'ccd_state_notes': {'bytes': 210984, 'path': 'data/raw/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx', 'sha256': '6476b6b28b700389e261b87377d9cd249935503d53b5919fe1b7ef8b1052d1a7', 'url': 'https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx'}, 'dictionary': {'bytes': 270385, 'path': 'data/raw/tx_dictionary_2025.html', 'sha256': '100f1f3d128bbe8a6be2a00e327b907dd15d5e2acc0e680c526bf9b59b4caf66', 'url': 'https://rptsvr1.tea.texas.gov/cgi/sas/broker?_service=marykay&_program=perfrept.perfmast.sas&_debug=0&ccyy=2025&sumlev=C&dsname=STAAR_GR38&dd=performance&asvab=&prgopt=reports%2Ftapr%2Fdd%2Fdd_tapr_dictionary.sas'}, 'directory': {'bytes': 13352819, 'path': 'data/raw/ccd_sch_029_2425_w_1a_073025.zip', 'sha256': '39326da788aa322353d20ceaf8ad4baed26272502cd05b066cf6c594988b21ab', 'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip'}, 'glossary': {'bytes': 834427, 'path': 'data/raw/tx_glossary_2025.pdf', 'sha256': '846810954d479a13467d9e4add3b0ed626247bd48ca9b677ff8a5ec11aedd416', 'url': 'https://tea.texas.gov/school-and-district-leaders/accountability/academic-accountability/performance-reporting/2024-25-comprehensive-tapr-glossary-0.pdf'}, 'income-extension': {'bytes': 151080, 'path': 'data/raw/tx_income_extension_2025.html', 'sha256': '9f2137a25a1e3bc2006b0b3dfee413bc38b1d6928c155574dd04934bd99a04ef', 'url': 'https://tea.texas.gov/taa-letters/school-year-2024-2025-income-eligibility-verification-forms-extension'}, 'income-guide': {'bytes': 4673648, 'path': 'data/raw/tx_income_reporting_2025.pdf', 'sha256': '05de25f2c0fcc21368d3810ff3124d2866d86289fcc7b5548232bcccc262ac3a', 'url': 'https://www.texasstudentdatasystem.org/sites/texasstudentdatasystem.org/files/TEDS_Data_Submission_Requirements_Student_Identification_and_Demographics_Domain.pdf'}, 'lea_directory': {'bytes': 2830266, 'path': 'data/raw/ccd_lea_029_2425_w_1a_073025.zip', 'sha256': '2745169e4bc7cd53adff179830c3d4b9bb035ac79580ecea01ef389a161936a9', 'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_lea_029_2425_w_1a_073025.zip'}, 'lea_membership': {'bytes': 68497561, 'path': 'data/raw/ccd_lea_052_2425_l_1a_073025.zip', 'sha256': '501d72720a01c26e0e041cd3b1aa6653d0a94725ba0a1e85c42c4f183bc627ba', 'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_lea_052_2425_l_1a_073025.zip'}, 'masking': {'bytes': 55298, 'path': 'data/raw/tx_masking_2025.html', 'sha256': '7b6e5840645656bf3c0d977431e7f9fcd6ea984bb1734b6387471f8ad4851de8', 'url': 'https://rptsvr1.tea.texas.gov/perfreport/tapr/2025/masking.html'}, 'membership': {'bytes': 212696691, 'path': 'data/raw/ccd_sch_052_2425_l_1a_073025.zip', 'sha256': '4a7f660c5fc5eaae488dd02fd43498f349fc828b227edd0970d5b6995ead4d4d', 'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip'}, 'ref': {'bytes': 827863, 'path': 'data/raw/tx_ref_2025.csv', 'sha256': '8c75df541a408dfb0f49161aef8c0c0229ff6f5e73765bebf6ce5ef070cdac72', 'url': 'https://rptsvr1.tea.texas.gov/cgi/sas/broker/?_service=marykay&_program=perfrept.perfmast.sas&_debug=0&ccyy=2025&tapr=all_c&sumlev=C&level=Campus&id=&prgopt=reports%2Ftapr%2Fdd%2Fdd_tapr_step_7.sas&datafmt=csv&dsname=REF&key=GRDSPAN&key=GRDTYPE&key=COUNTY%7CCNTYNAME&key=CFLALTED'}, 'stud': {'bytes': 3015524, 'path': 'data/raw/tx_stud_2025.csv', 'sha256': '24e2b867023b8c979d0f7f5d662db4d1eeb3eca00f0413b12bd059790eb7b6f6', 'url': 'https://rptsvr1.tea.texas.gov/cgi/sas/broker/?_service=marykay&_program=perfrept.perfmast.sas&_debug=0&ccyy=2025&tapr=all_c&sumlev=C&level=Campus&id=&prgopt=reports%2Ftapr%2Fdd%2Fdd_tapr_step_7.sas&datafmt=csv&dsname=STUD&key=ETALL%7CNTALL&key=NTECO%7CNTNED%7CNT504%7CNTLEP%7CNTDSL%7CNTFOS%7CNTHOM%7CNTIMM%7CNTMIG%7CNTTT1%7CNTMLC%7CNTRSK%7CNTBIL&key=ETECO%7CETNED%7CET504%7CETLEP%7CETDIS%7CETDSL%7CETFOS%7CETHOM%7CETIMM%7CETMIG%7CETTT1%7CETMLC%7CETRSK&key=NTGEEC%7CNTGEEP%7CNTGPKC%7CNTGPKP%7CNTGP3C%7CNTGP3P%7CNTGP4C%7CNTGP4P%7CNTGKNC%7CNTGKNP%7CNTG01C%7CNTG01P%7CNTG02C%7CNTG02P%7CNTG03C%7CNTG03P%7CNTG04C%7CNTG04P%7CNTG05C%7CNTG05P%7CNTG06C%7CNTG06P%7CNTG07C%7CNTG07P%7CNTG08C%7CNTG08P%7CNTG09C%7CNTG09P%7CNTG10C%7CNTG10P%7CNTG11C%7CNTG11P%7CNTG12C%7CNTG12P&var_type=N&var_type=D&var_type=R'}, 'accountability-manual': {'path': 'data/raw/tx_accountability_manual_2025.pdf', 'url': 'https://tea.texas.gov/texas-schools/accountability/academic-accountability/performance-reporting/2025-accountability-manual-full.pdf', 'bytes': 7524901, 'sha256': '8734f5ce994c9e255ff34da3a8ddf3b2430a17e3d7f18cbff06bba85ae6b649f'}, 'performance-listing': {'path': 'data/raw/tx_performance_participation_listing_2025.pdf', 'url': 'https://sboe.texas.gov/texas-schools/accountability/academic-accountability/performance-reporting/interpreting-staar-performance-participation-student-list-2025.pdf', 'bytes': 319035, 'sha256': '1c1e59441f6733b6f77b70946deeed401c59714a6cbdc4e8609d15a49741b6b1'}}
POLICY = {
    'identity': 'Exact 2024–25 CCD NCES LEA 4823640 / ST_LEAID TX-101912; CCD ST_SCHID TX-101912-101912sss crosswalks to the complete nine-digit TAPR CAMPUS 101912sss with DISTRICT 101912. Names never join.',
    'population': 'Use complete native 2025 fall enrolled counts EE, PK, K, 1–12 reconciled to CPNTALLC. No positive grades9–12, plus positive grades3–8, defines the prospective grade-school population. Retain primary-only, high-only, mixed, unknown, zero and absent records separately. Do not select by CCD level, reference GRDTYPE/GRDSPAN, school type, charter status or residuals.',
    'income': 'Individual October25,2024 PEIMS fall economic status, CP NTECO / NTALL, including free/reduced meal eligibility or other public assistance, codes01/02/99. Same-year all-enrolled EE–12 denominator; ED+nonED and native tenth-percent display must reconcile. This broader state-specific proxy is not uniform FRPL or household income; it does not exactly describe tested pupils.',
    'income_limits': 'CEP requires individual direct certification and annual local income surveys; universal meals do not classify all children. Provision2 can retain base-year eligibility for continuously enrolled students. Missing surveys may be00; undercount unknown. Jan16,2025 resubmission extension requires enrolled/eligible October25,2024; not another-year backfill.',
    'assessment': 'Exact native 2024–25 All Students TAPR enrolled-grades3–8 Math/Reading Including EOC, At Meets Grade Level or Above: native #Tests, #Meets-or-above and published rate. Accountability subset requires same district/campus on fall snapshot and testing date. STAAR with/without accommodations, Spanish STAAR, Alternate2 and corresponding AlgebraI/EnglishI–II EOC are included as documented. Separate TPRS all-testers, both-subject passing and participation measures are not used.',
    'counts': 'Native #Tests/Meets/rate performance arithmetic is reconciled, not a participation/enrollment substitution. Current manual verifies CAF corrections feed TAPR and A/O performance exclusions, but mapping N(NAAR)/M(medical exemptions) to these exact enrolled-grade fields remains unverified. Verified valid-score denominators, sampling variances and intervals remain null/unavailable until that primary-source gate is resolved. Counts retained below are reported native performance denominators, not approved valid-score counts.',
    'suppression': 'Empty, bullet/asterisk and -1/-2/-3 are unavailable, never zero. Never reconstruct a masked rate from visible counts. Native source suppresses small denominators1–4; reported #Tests below10 are a distinct prospective repository exclusion; the valid-scored10 floor cannot be certified until score-status verification. Zero proficiency is real if its published fields are unmasked.',
    'combined': 'Equal mean of eligible Math and ELA exact proficiency ratios, not the native fraction passing both. Never average grades or weight by enrollment.',
    'approval': 'Source/cohort audit only. Source and modeling approval false; no model, residual, variance, interval, canonical import, served comparison or location crosswalk. Separate numerical audit and canonical/browser integration remain required. High/mixed observations are retained but their assessment populations remain unaudited for district models.',
}
PLANNING = {'source': 'data/source/district-comparison-candidates.json', 'operational_roster': 274,
            'enrollment': 176727, 'potential_ES': 212, 'potential_HS': 42,
            'explanation': 'Discovery only; original CCD identities/membership replay independently. Planning counts do not approve source/model populations.'}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def number(raw):
    if not isinstance(raw, str): raise ValueError('Native Texas cells must remain strings')
    if raw in {'', '-1', '-2', '-3', '*', '**', '•'}: return None
    try: value = Decimal(raw)
    except InvalidOperation as exc: raise ValueError('Invalid native Texas numeric cell') from exc
    if not value.is_finite() or value < 0: raise ValueError('Invalid native Texas numeric cell')
    return float(value)


def count(raw):
    value = number(raw)
    if value is not None: value = Decimal(raw)
    if value is not None and value != int(value): raise ValueError('Nonintegral native Texas count')
    return None if value is None else int(value)


def native_identity(raw):
    key = raw.get('CAMPUS')
    if not isinstance(key, str) or not re.fullmatch(DISTRICT + r'\d{3}', key) or raw.get('DISTRICT') != DISTRICT:
        raise ValueError('Houston requires exact nine-digit native campus and six-digit district')
    return key


def ccd_identity(raw, school=True):
    if raw.get('SCHOOL_YEAR') != YEAR or raw.get('ST') != 'TX' or raw.get('LEAID') != LEA or raw.get('ST_LEAID') != NATIVE_LEA:
        raise ValueError('Houston CCD identity/year mismatch')
    if school:
        key, native = raw.get('NCESSCH'), raw.get('ST_SCHID')
        if not isinstance(key, str) or not re.fullmatch(LEA + r'\d{5}', key) or not isinstance(native, str) or not re.fullmatch(NATIVE_LEA + '-' + DISTRICT + r'\d{3}', native):
            raise ValueError('Houston requires complete authoritative CCD school/native identifiers')
        return key, native.rsplit('-', 1)[1]
    return LEA


def grade_evidence(raw):
    values = {k: count(raw[k]) for k in GRADES}; total = count(raw['CPNTALLC'])
    complete = all(v is not None for v in values.values()) and total is not None
    if complete and sum(values.values()) != total: raise ValueError('Native enrolled grades fail enrollment reconciliation')
    lower = sum(values[k] for k in GRADES[:-4]) if complete else None
    high = sum(values[k] for k in GRADES[-4:]) if complete else None
    tested = sum(values['CPNTG%02dC' % g] for g in range(3, 9)) if complete else None
    scope = ('unknown' if not complete else 'zero' if total == 0 else 'mixed' if lower and high
             else 'high' if high else 'grade-school' if tested else 'primary-only')
    return {'raw_grade_counts': {k: raw[k] for k in GRADES}, 'counts': values,
            'enrollment': total, 'complete_reconciled': complete, 'lower_enrollment': lower,
            'high_enrollment': high, 'tested_grades_enrollment': tested, 'scope': scope,
            'no_high_grades': complete and high == 0,
            'prospective_grade_school': scope == 'grade-school',
            'pk_subcategories': {k: raw[k] for k in ['CPNTGP3C', 'CPNTGP4C']},
            'pk_subcategories_note': 'PK3/PK4 are retained subcategories, never added to the enrollment sum twice.'}


def income_evidence(raw):
    total, low, other = [count(raw[k]) for k in ['CPNTALLC', 'CPNTECOC', 'CPNTNEDC']]
    display = number(raw['CPNTECOP'])
    reason = 'Native same-year individual economic status missing or masked' if None in (total, low, other, display) else 'Native enrollment is zero' if total == 0 else None
    if reason is None and (low + other != total or not 0 <= display <= 100 or abs(100 * low / total - display) > .050001):
        raise ValueError('Native economic counts/display percentage do not reconcile')
    return {'raw': {k: raw[k] for k in ['CPNTALLC', 'CPNTECOC', 'CPNTNEDC', 'CPNTECOP']},
            'enrollment': total, 'economic_disadvantage': low, 'not_economic_disadvantage': other,
            'published_percentage': display, 'percentage': None if reason else 100 * low / total,
            'exclusion': reason, 'snapshot_date': '2024-10-25',
            'definition': POLICY['income'], 'limits': POLICY['income_limits']}


def subject_evidence(raw, subject, applicable, income):
    fields = FIELDS[subject]; cells = [raw[k] for k in fields]
    tested, passed, display = count(cells[0]), count(cells[1]), number(cells[2])
    reason = 'Native TAPR subject result missing or masked; suppression preserved' if None in (tested, passed, display) else None
    if reason is None:
        if tested < 5 or passed > tested or not 0 <= display <= 100 or abs(100 * passed / tested - display) > .500001:
            raise ValueError('Native TAPR performance counts fail published-rate reconciliation')
        rate = 100 * passed / tested
    else: rate = None
    reported_performance_denominator = None if reason else tested
    exclusion = ('Outside the separately audited positive grades3–8/no-high-grade population' if not applicable
                 else income['exclusion'] if income['exclusion'] else reason
                 if reason else 'Fewer than10 reported performance tests; valid-scored floor verification held' if tested < 10 else None)
    return {'fields': fields, 'raw': cells, 'raw_tested': cells[0], 'raw_meets_or_above': cells[1],
            'raw_published_rate': cells[2], 'reported_tested': tested, 'reported_meets_or_above': passed,
            'published_rate': display, 'proficiency': rate, 'reported_performance_denominator': reported_performance_denominator, 'valid_scores': None,
            'count_evidence': 'Dictionary native performance #Tests plus glossary pp1–3; all three native fields reconciled. Manual AppendixH proves A/O exclusions and CAF/TAPR linkage. Exact N/M score-status mapping remains a hold; no verified valid-score count.',
            'native_fields_usable': income['exclusion'] is None and reason is None and tested >= 10,
            'outcome_exclusion': reason, 'applicable': applicable,
            'source_usable': exclusion is None, 'exclusion': exclusion,
            'valid_score_verification_status': 'held_pending_exact_2025_N_M_score_status_mapping',
            'sampling_variance': None, 'sampling_interval_available': False}


def ccd_count(raw):
    if raw is None or raw.get('DMS_FLAG') not in {'Reported', 'Derived'}: return None
    return count(raw['STUDENT_COUNT'])


def load_texas(path=ROOT / 'data/source/texas.json'):
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != STATE_EXTRACT_SHA:
        raise ValueError('Historical Texas extract changed; separate source review required')
    document = json.loads(content)
    if fingerprint([document.get(k) for k in ['state', 'year', 'academic_year']]) != fingerprint(['TX', 2025, '2024-25']):
        raise ValueError('Historical Texas snapshot/year changed')
    return document


def summarize(links, predicate, note):
    rows = [r for r in links if predicate(r)]
    subjects = {}
    for subject in ['math', 'reading', 'combined']:
        members = [r for r in rows if r['subjects'][subject]['source_usable']]
        subjects[subject] = {'applicable': sum(r['subjects'][subject]['applicable'] for r in rows),
            'usable': len(members), 'native_fields_usable': sum(r['subjects'][subject]['native_fields_usable'] for r in rows), 'prospective_native_school_ids': [r['native_school_id'] for r in members],
            'prospective_nces_school_ids': [r['school_id'] for r in members],
            'exclusions': dict(sorted(Counter(r['subjects'][subject]['exclusion'] for r in rows if r['subjects'][subject]['exclusion']).items())),
            'prospective_30_school_floor_met': len(members) >= 30,
            'approved_for_modeling': False,
            'availability_note': 'Prospective unmasked native performance/count availability only. Reported #Tests>=10 does not certify the minimum10 valid-scored requirement; exact N/M mapping remains held.'}
    return {'profiles': len(rows), 'native_school_ids': [r['native_school_id'] for r in rows],
            'nces_school_ids': [r['school_id'] for r in rows], 'note': note, 'subjects': subjects,
            'ccd_charter': dict(sorted(Counter(r['ccd_flags']['charter'] for r in rows).items())),
            'ccd_school_type': dict(sorted(Counter(r['ccd_flags']['school_type'] for r in rows).items()))}


def derive(document, snapshot=None):
    expected_base = {'schema_version': 1, 'state': 'TX', 'year': 2025, 'academic_year': YEAR,
        'nces_lea_id': LEA, 'native_lea_id': NATIVE_LEA, 'native_district_id': DISTRICT,
        'status': 'audit_pending', 'scope': 'source_cohort_audit_only',
        'approved_for_source': False, 'approved_for_modeling': False,
        'sources': SOURCES, 'policy': POLICY, 'planning': PLANNING,
        'state_extract': {'path': 'data/source/texas.json', 'sha256': STATE_EXTRACT_SHA}}
    if any(fingerprint(document.get(k)) != fingerprint(v) for k, v in expected_base.items()):
        raise ValueError('Houston source-only identity, metadata, flags or policy changed')
    inputs = document['raw_inputs']
    if fingerprint(inputs) != RAW_INPUT_SHA: raise ValueError('Original Houston input evidence changed')
    snapshot = load_texas() if snapshot is None else snapshot
    if fingerprint(snapshot) != fingerprint(load_texas()): raise ValueError('Historical Texas snapshot drift')
    directory = {}; by_native = {}; totals = {}; grades = defaultdict(dict)
    for entry in inputs['directory']['records']:
        key, native = ccd_identity(entry['raw'])
        if key in directory or native in by_native: raise ValueError('Duplicate CCD school/native identity')
        directory[key] = entry; by_native[native] = key
    for entry in inputs['membership']['records']:
        raw = entry['raw']; key, native = ccd_identity(raw)
        if key not in directory or by_native[native] != key: raise ValueError('CCD membership has no exact directory attachment')
        if raw['TOTAL_INDICATOR'] == 'Education Unit Total':
            if key in totals: raise ValueError('Duplicate CCD enrollment total')
            totals[key] = entry
        elif raw['TOTAL_INDICATOR'] == 'Subtotal 4 - By Grade':
            if raw['GRADE'] in grades[key]: raise ValueError('Duplicate CCD native grade')
            grades[key][raw['GRADE']] = entry
        else: raise ValueError('Unexpected CCD retained aggregation')
    native_tables = {}
    required = {'ref': ['CAMPUS', 'DISTRICT', 'GRDTYPE', 'GRDSPAN'],
                'stud': ['CAMPUS', 'DISTRICT', 'CPNTALLC', 'CPNTECOC', 'CPNTNEDC', 'CPNTECOP'] + GRADES,
                'assessment': ['CAMPUS', 'DISTRICT'] + sum(FIELDS.values(), [])}
    for table in ['ref', 'stud', 'assessment']:
        source = inputs[table]; rows = {}
        if len(set(source['header'])) != len(source['header']) or len(source['header']) != len(source['labels']) or not set(required[table]) <= set(source['header']):
            raise ValueError('Native TAPR header/label schema changed')
        for field in required[table]:
            label = source['labels'][source['header'].index(field)]
            if (field.startswith('CPNT') and '2025' not in label) or (field.startswith('CDA') and 'SY 2024-25' not in label):
                raise ValueError('Native required TAPR field is not same-year2025')
        for entry in source['records']:
            key = native_identity(entry['raw'])
            if key in rows or key not in by_native or set(entry['raw']) != set(source['header']):
                raise ValueError('Native duplicate, missing CCD identity or incomplete raw row')
            rows[key] = entry
        native_tables[table] = rows
    if len({fingerprint(sorted(v)) for v in native_tables.values()}) != 1:
        raise ValueError('Native same-year table identities differ')
    lea_directory = inputs['lea_directory']['records']
    if len(lea_directory) != 1: raise ValueError('Exact CCD agency absent/duplicated')
    ccd_identity(lea_directory[0]['raw'], False)
    lea_total = [e for e in inputs['lea_membership']['records'] if e['raw']['TOTAL_INDICATOR'] == 'Education Unit Total']
    if len(lea_total) != 1: raise ValueError('Exact same-year CCD agency membership absent/duplicated')
    for e in inputs['lea_membership']['records']: ccd_identity(e['raw'], False)
    from plan_district_comparisons import potential_cohort
    potential = {level: sorted(key for key, e in directory.items() if e['raw']['UPDATED_STATUS'] in OPERATIONAL
        and potential_cohort(e['raw'], totals.get(key, {}).get('raw'), {g: r['raw'] for g, r in grades[key].items()}) == level)
        for level in ['ES', 'HS']}
    planning = inputs['planning']['record']
    if (fingerprint(planning['potential_school_ids']) != fingerprint(potential)
            or fingerprint(planning['directory_raw']) != fingerprint({k: lea_directory[0]['raw'][k] for k in planning['directory_raw']})
            or fingerprint(planning['membership_raw']) != fingerprint(lea_total[0]['raw'])
            or planning['directory_source_row'] != lea_directory[0]['source_row']
            or planning['membership_source_row'] != lea_total[0]['source_row']
            or planning['enrollment'] != ccd_count(lea_total[0]['raw'])
            or planning['school_directory_operational_count'] != sum(e['raw']['UPDATED_STATUS'] in OPERATIONAL for e in directory.values())):
        raise ValueError('Planning identities/enrollment fail original CCD replay')
    historical = {p['id']: p for p in snapshot['profiles'] if p['profile']['DISTRICT'] == DISTRICT}
    links = []; differences = []
    for key, entry in directory.items():
        raw = entry['raw']; native = ccd_identity(raw)[1]; native_row = native_tables['stud'].get(native)
        ccd_total = ccd_count(totals.get(key, {}).get('raw'))
        ccd_grades = {g: {'source_row': r['source_row'], 'raw_count': r['raw']['STUDENT_COUNT'],
                         'dms_flag': r['raw']['DMS_FLAG'], 'reported_count': ccd_count(r['raw'])} for g, r in sorted(grades[key].items())}
        ref = native_tables['ref'].get(native); outcome = native_tables['assessment'].get(native)
        enrolled = grade_evidence(native_row['raw']) if native_row else None
        income = income_evidence(native_row['raw']) if native_row else {'percentage': None, 'exclusion': 'Native same-year TAPR campus absent'}
        applicable = raw['UPDATED_STATUS'] in OPERATIONAL and bool(enrolled and enrolled['prospective_grade_school'])
        subjects = {s: subject_evidence(outcome['raw'], s, applicable, income) for s in FIELDS} if outcome else {
            s: {'applicable': False, 'source_usable': False, 'exclusion': 'Native same-year TAPR campus absent',
                'proficiency': None, 'valid_scores': None, 'native_fields_usable': False, 'reported_performance_denominator': None, 'sampling_variance': None, 'sampling_interval_available': False} for s in FIELDS}
        reasons = [subjects[s]['exclusion'] for s in FIELDS if subjects[s]['exclusion']]
        subjects['combined'] = {'applicable': applicable, 'source_usable': not reasons,
            'exclusion': '; '.join(dict.fromkeys(reasons)) if reasons else None,
            'proficiency': (subjects['math']['proficiency'] + subjects['reading']['proficiency']) / 2 if all(subjects[s]['proficiency'] is not None for s in FIELDS) else None,
            'native_fields_usable': all(subjects[s]['native_fields_usable'] for s in FIELDS),
            'valid_scores': None, 'sampling_variance': None, 'sampling_interval_available': False,
            'definition': POLICY['combined']}
        if native_row:
            old = historical.get(native)
            if old is None or old['profile_row'] != native_row['source_row'] or old['reference_row'] != ref['source_row'] or old['assessment_row'] != outcome['source_row']:
                raise ValueError('Original CSV row identity disagrees with historical Texas snapshot')
            if any(fingerprint(old['profile'][k]) != fingerprint(native_row['raw'][k]) for k in old['profile']) or fingerprint(old['reference']) != fingerprint(ref['raw']) or any(fingerprint(old['outcomes'][s]) != fingerprint([outcome['raw'][f] for f in FIELDS[s]]) for s in FIELDS):
                raise ValueError('Original native cells disagree with pinned historical snapshot')
            if ccd_total != enrolled['enrollment']: differences.append({'school_id': key, 'native_school_id': native, 'ccd_membership': ccd_total, 'native_enrollment': enrolled['enrollment']})
        offered = {g: raw.get('G_' + g + '_OFFERED') for g in ['PK', 'KG'] + [str(g) for g in range(1, 14)] + ['UG', 'AE']}
        contradiction = bool(enrolled and enrolled['high_enrollment'] and ref['raw']['GRDTYPE'] in {'E', 'M'})
        links.append({'school_id': key, 'native_school_id': native, 'ccd_native_school_id': raw['ST_SCHID'],
            'name': raw['SCH_NAME'], 'ccd_source_row': entry['source_row'],
            'ccd_flags': {'status': raw['UPDATED_STATUS_TEXT'], 'operational': raw['UPDATED_STATUS'] in OPERATIONAL,
                          'school_type': raw['SCH_TYPE_TEXT'], 'charter': raw['CHARTER_TEXT'], 'level': raw['LEVEL'],
                          'virtual_status': None, 'virtual_status_note': 'No virtual field in this CCD directory.'},
            'ccd_offered': {'flags': offered, 'as_reported': raw['IGOFFERED'], 'no_grades': raw['NOGRADES'], 'low': raw['GSLO'], 'high': raw['GSHI']},
            'ccd_membership': {'total_source_row': totals.get(key, {}).get('source_row'), 'reported_total': ccd_total, 'grades': ccd_grades},
            'native_present': native_row is not None,
            'native_peims_membership': {'raw_count': native_row['raw']['CPETALLC'], 'count': count(native_row['raw']['CPETALLC']),
                'note': 'Separate TAPR membership excludes some under-two-hour pupils; never substitutes for native enrollment income denominator.'} if native_row else None,
            'native_source_rows': {s: native_tables[s][native]['source_row'] for s in ['ref', 'stud', 'assessment']} if native_row else {},
            'native_reference': ref['raw'] if ref else None, 'native_enrolled': enrolled,
            'native_reference_conflicts_with_positive_high_enrollment': contradiction,
            'income': income, 'subjects': subjects,
            'exclusion': 'Native same-year TAPR campus absent' if not native_row else None if applicable else 'Outside positive grades3–8/no-high-grade cohort: ' + enrolled['scope']})
    cohorts = {'native_no_high_grade_profiles': summarize(links, lambda r: bool(r['native_enrolled'] and r['native_enrolled']['no_high_grades']), 'Complete native EE–8 enrollment profiles; primary-only retained separately, not model members.'),
        'prospective_grade_school': summarize(links, lambda r: bool(r['native_enrolled'] and r['native_enrolled']['prospective_grade_school']), 'Positive native grades3–8, zero native grades9–12; income/count/rate/minimum10 rules select each subject separately.'),
        'primary_only': summarize(links, lambda r: bool(r['native_enrolled'] and r['native_enrolled']['scope'] == 'primary-only'), 'No positive tested grades3–8; native outcome absence preserved.'),
        'high_only': summarize(links, lambda r: bool(r['native_enrolled'] and r['native_enrolled']['scope'] == 'high'), 'Outside audited grade-school population; high-school assessment audit remains required.'),
        'mixed_grade': summarize(links, lambda r: bool(r['native_enrolled'] and r['native_enrolled']['scope'] == 'mixed'), 'Any positive high-grade enrollment excludes this grades3–8-only population, regardless of native reference label.')}
    enrollment = {'ccd_lea_reported': ccd_count(lea_total[0]['raw']), 'ccd_operational_school_sum': sum(r['ccd_membership']['reported_total'] for r in links if r['ccd_flags']['operational']),
        'native_campus_sum': sum(r['native_enrolled']['enrollment'] for r in links if r['native_present']),
        'native_peims_membership_sum': sum(r['native_peims_membership']['count'] for r in links if r['native_present']),
        'native_enrollment_membership_differences': [{'native_school_id': r['native_school_id'], 'enrollment': r['native_enrolled']['enrollment'], 'membership': r['native_peims_membership']['count']} for r in links if r['native_present'] and r['native_enrolled']['enrollment'] != r['native_peims_membership']['count']],
        'native_economic_disadvantage_sum': sum(r['income']['economic_disadvantage'] for r in links if r['native_present']),
        'matched_school_enrollment_differences': differences,
        'definition_note': 'TAPR enrolled and CCD reported membership are independent administrative concepts; equality here does not make either a tested denominator.'}
    coverage = {'directory_records': len(links), 'operational_schools': sum(r['ccd_flags']['operational'] for r in links),
        'native_campuses': len(native_tables['stud']), 'native_scope_counts': dict(sorted(Counter(r['native_enrolled']['scope'] for r in links if r['native_present']).items())),
        'ccd_school_types': dict(sorted(Counter(r['ccd_flags']['school_type'] for r in links).items())),
        'ccd_charter': dict(sorted(Counter(r['ccd_flags']['charter'] for r in links).items())),
        'native_usable_income': sum(r['income']['exclusion'] is None for r in links),
        'prospective_subject_members': {s: cohorts['prospective_grade_school']['subjects'][s]['usable'] for s in ['math', 'reading', 'combined']},
        'native_absent_from_ccd': sorted(set(native_tables['stud']) - set(by_native)),
        'ccd_absent_from_native': [r['school_id'] for r in links if not r['native_present']],
        'native_reference_high_grade_contradictions': [r['native_school_id'] for r in links if r['native_reference_conflicts_with_positive_high_enrollment']],
        'verified_valid_score_counts': 0,
        'reported_reconciled_performance_denominators': {s: sum(r['subjects'][s]['reported_performance_denominator'] is not None for r in links) for s in FIELDS},
        'valid_score_verification_hold': 'Current2025 primary documentation must map N/NAAR and M/medical exemption score statuses to these exact native enrolled-grade3–8 TAPR #Tests fields.',
        'sampling_intervals_available': False, 'model_results': 0, 'canonical_import_performed': False, 'served_comparison_created': False}
    outside = [r for r in links if r['exclusion'] is not None]
    eligible = cohorts['prospective_grade_school']['subjects']['combined']['prospective_nces_school_ids']
    return {'roster_links': links, 'cohorts': cohorts, 'coverage': coverage,
        'outside_grade_school_population': outside, 'enrollment_reconciliation': enrollment,
        'planning_identity_reconciliation': {'potential_school_ids': potential,
            'source_usable_school_ids': eligible, 'source_not_planning_ES': sorted(set(eligible) - set(potential['ES'])),
            'planning_ES_not_source_usable': sorted(set(potential['ES']) - set(eligible)),
            'scope_note': 'Discovery IDs independently replayed; they never select source outcomes or grant model approval.'},
        'historical_state_consistency': {'matched_native_profiles': len(historical), 'original_csv_cells_and_rows_verified': True,
            'district_source_approval': False, 'district_modeling_approval': False}}


def validate(document, snapshot=None):
    expected = derive(document, snapshot)
    fields = {'schema_version', 'state', 'year', 'academic_year', 'nces_lea_id', 'native_lea_id', 'native_district_id',
              'status', 'scope', 'approved_for_source', 'approved_for_modeling', 'sources', 'policy', 'planning', 'raw_inputs', 'state_extract'}
    if set(document) != fields | set(expected) or any(fingerprint(document.get(k)) != fingerprint(v) for k, v in expected.items()):
        raise ValueError('Houston derived memberships, exclusions or arithmetic failed exact replay')
    return expected['coverage']


def native_cell(v):
    return {'cell_type': type(v).__name__, 'iso8601': v.isoformat()} if isinstance(v, (date, datetime)) else v


def extract_raw_inputs():
    for metadata in SOURCES.values():
        p = ROOT / metadata['path']
        if p.stat().st_size != metadata['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest() != metadata['sha256']:
            raise ValueError('Pinned original source changed: ' + str(p))
    inputs = {}
    for key in ['directory', 'lea_directory', 'membership', 'lea_membership']:
        p = ROOT / SOURCES[key]['path']; member = p.stem + '.csv'
        if key in {'directory', 'lea_directory'}:
            with zipfile.ZipFile(p) as a, a.open(member) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                rows = [{'source_row': i, 'raw': r} for i, r in enumerate(reader, 2) if r['LEAID'] == LEA or r['ST_LEAID'] == NATIVE_LEA]
                header = reader.fieldnames
        else:
            process = subprocess.Popen(['unzip', '-p', str(p), member], stdout=subprocess.PIPE, text=True, encoding='utf-8-sig')
            try:
                reader = csv.DictReader(process.stdout)
                rows = [{'source_row': i, 'raw': r} for i, r in enumerate(reader, 2) if (r['LEAID'] == LEA or r['ST_LEAID'] == NATIVE_LEA)
                        and r['TOTAL_INDICATOR'] in {'Education Unit Total', 'Subtotal 4 - By Grade'}]
                if process.wait() != 0: raise ValueError('Failed original CCD membership stream')
                header = reader.fieldnames
            finally:
                process.stdout.close()
                if process.poll() is None: process.terminate(); process.wait()
        inputs[key] = {'source_id': key, 'member': member, 'header_source_row': 1, 'header': header, 'records': rows}
    for key in ['ref', 'stud', 'assessment']:
        with (ROOT / SOURCES[key]['path']).open(newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f); labels = next(reader); codes = next(reader); rows = []
            for i, values in enumerate(reader, 3):
                if len(values) != len(codes): raise ValueError('Malformed original TAPR row')
                raw = dict(zip(codes, values))
                if raw['DISTRICT'] == DISTRICT or raw['CAMPUS'].startswith(DISTRICT): rows.append({'source_row': i, 'raw': raw})
        inputs[key] = {'source_id': key, 'labels_source_row': 1, 'codes_source_row': 2,
                       'labels': labels, 'header': codes, 'records': rows}
    from pypdf import PdfReader
    import openpyxl
    definitions = {}
    for key, pages in [('glossary', [1, 2, 3, 5, 6, 28, 29]), ('income-guide', [36, 37, 38, 39, 40])]:
        pdf = PdfReader(ROOT / SOURCES[key]['path'])
        definitions[key] = {'source_id': key, 'pages': [{'pdf_page': n, 'text': pdf.pages[n-1].extract_text(extraction_mode='layout')} for n in pages]}
    workbook = openpyxl.load_workbook(ROOT / SOURCES['ccd_state_notes']['path'], read_only=True, data_only=True)
    sheets = []
    try:
        for sheet in workbook:
            rows = [{'source_row': i, 'raw': [native_cell(v) for v in row]} for i, row in enumerate(sheet.iter_rows(values_only=True), 1)
                if i <= 3 or any(isinstance(v, str) and ('Texas' in v or 'Houston' in v or v == 'TEXAS') for v in row)]
            if any(r['source_row'] > 3 for r in rows): sheets.append({'worksheet': sheet.title, 'rows': rows})
    finally: workbook.close()
    definitions['ccd_state_notes'] = {'source_id': 'ccd_state_notes', 'worksheets': sheets}
    for key in ['dictionary', 'masking', 'income-extension']:
        encoding = 'utf-8' if key == 'income-extension' else 'cp1252'
        lines = (ROOT / SOURCES[key]['path']).read_text(encoding=encoding).splitlines()
        rows = [{'source_line': i, 'html': line} for i, line in enumerate(lines, 1)
                if key != 'dictionary' or any(field in line for field in sum(FIELDS.values(), []))]
        definitions[key] = {'source_id': key, 'encoding': encoding, 'lines': rows}
    # Supplemental performance score-code proof is retained as complete PDF pages.
    manual = PdfReader(ROOT / SOURCES['accountability-manual']['path'])
    definitions['accountability-manual'] = {'source_id': 'accountability-manual', 'pages': [
        {'pdf_page': n, 'text': manual.pages[n-1].extract_text(extraction_mode='layout')} for n in MANUAL_PAGES]}
    listing = PdfReader(ROOT / SOURCES['performance-listing']['path'])
    definitions['performance-listing'] = {'source_id': 'performance-listing', 'pages': [{'pdf_page': n, 'text': listing.pages[n-1].extract_text(extraction_mode='layout')} for n in [4, 6, 8]]}
    inputs['definitions'] = definitions
    planning = json.loads((ROOT / PLANNING['source']).read_text())
    agency = next(r for r in planning['agencies'] if r['nces_lea_id'] == LEA)
    fields = ['nces_lea_id', 'state', 'native_lea_id', 'enrollment', 'enrollment_flag', 'school_directory_operational_count',
              'potential_cohorts', 'potential_school_ids', 'directory_raw', 'directory_source_row', 'membership_raw', 'membership_source_row']
    inputs['planning'] = {'source': PLANNING['source'], 'sources': planning['sources'], 'record': {k: agency[k] for k in fields}}
    return inputs


def build(inputs, output=OUTPUT):
    # Original extraction and independent bootstrap may insert definition evidence
    # in different dictionary positions. Normalize that position for stable bytes.
    inputs = dict(inputs)
    if 'definitions' in inputs: inputs['definitions'] = inputs.pop('definitions')
    document = {'schema_version': 1, 'state': 'TX', 'year': 2025, 'academic_year': YEAR,
        'nces_lea_id': LEA, 'native_lea_id': NATIVE_LEA, 'native_district_id': DISTRICT,
        'status': 'audit_pending', 'scope': 'source_cohort_audit_only', 'approved_for_source': False, 'approved_for_modeling': False,
        'sources': SOURCES, 'policy': POLICY, 'planning': PLANNING, 'raw_inputs': inputs,
        'state_extract': {'path': 'data/source/texas.json', 'sha256': STATE_EXTRACT_SHA}}
    document.update(derive(document)); validate(document)
    Path(output).write_text(json.dumps(document, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')
    return document['coverage']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true', help='Reopen all pinned original CSV/PDF/HTML/CCD files')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build(extract_raw_inputs(), args.output) if args.extract else validate(json.loads(args.output.read_text()))
    print(json.dumps(result, sort_keys=True))
