"""Native Minnesota 2024–25 valid-score school totals and individual FRPM.

Offline rebuilds use the committed native extract. --extract reads the three
public MDE workbooks; their own column definitions establish score denominators.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import warnings

import openpyxl

from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

YEAR = 2025
DATASET = 'mn-mca-mtas-2025'
RAW = ROOT / 'data/raw/minnesota'
EXTRACT = ROOT / 'data/source/minnesota.json'
OUTPUT = ROOT / 'data/minnesota'
PORTAL = 'https://rc.education.mn.gov/'
DOWNLOAD = ('https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&'
            'RevisionSelectionMethod=latestReleased&Rendition=primary&dDocName=')
FILES = {'math': ('math.xlsx', DOWNLOAD + 'PROD087031'),
         'reading': ('reading.xlsx', DOWNLOAD + 'PROD087032'),
         'enrollment': ('enrollment.xlsx', DOWNLOAD + 'PROD085895'),
         'assessment_guide': ('assessment-guide.pdf', DOWNLOAD + '005342'),
         'student_guide': ('student-guide.docx', DOWNLOAD + '005343')}
DOCUMENTARY = {
    'marss_reference_2024_25': dict(url='https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&allowInterrupt=1&dDocName=060311&dID=137017',
        verified='Official indexed PDF, July 2024, FY 2024–25: individual Economic Indicator 0/1/2/7/8 distinguishes ineligible, reduced, free and direct certification.'),
    'cep_guidance': dict(url='https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&allowInterrupt=1&dDocName=055515&dID=135955',
        verified='Official indexed PDF, revised June 2024: free universal meals do not establish individual eligibility; public CEP schools collect alternate applications annually and report actual eligibility to MARSS.'),
    'alternate_application_2024_25': dict(url='https://education.mn.gov/mdeprod/idcplg?IdcService=GET_DYNAMIC_CONVERSION&dID=136653',
        verified='Official public HTML preview, School Year 2024–25: individual eligibility required under CEP, Provision 2/3 and no meal programs; prior-year approvals cannot be carried into current MARSS reporting.'),
    'privacy_rules': dict(url='https://education.mn.gov/MDE/About/MDE086067',
        verified='Official reporting FAQ: blurring publishes ranges rather than exact numbers; complementary suppression prevents subtraction recovery. Blank and range cells remain missing.'),
    'bie_scope': dict(url='https://education.mn.gov/mdeprod/groups/educ/documents/basic/bwrl/mdc1/~edisp/mde075526.pdf',
        verified='Official MDE SIS Vendor and District Test Plan v10.2, School Classification descriptor: combined classification 40 is limited to District Type 34 Bureau of Indian Education. Native 2024–25 enrollment newly includes tribal-controlled schools; Type 34 is excluded.'),
}
TEST = 'All Standards-Based (MCA/MTAS/ALTMCA)'
INCOME_COUNT = 'Total Students Eligible for Free or Reduced Priced Meals Count'
INCOME_RATE = 'Total Students Eligible for Free or Reduced Priced Meals Percent'
INCOME_FLAG = 'Additional Suppression Free or Reduced Priced Meals Applied'
PROFILE_FIELDS = ['Data Year', 'County Number', 'County Name', 'District Number',
    'District Type', 'District Name', 'School Number', 'School Name',
    'School Classification', 'Grade', 'Total Enrollment', 'Filter Groups',
    INCOME_COUNT, INCOME_RATE, INCOME_FLAG]
GRADE_FIELDS = ['Data Year', 'District Number', 'District Type', 'District Name',
    'School Number', 'School Name', 'School Classification', 'Test Name', 'Grade',
    'Subject', 'Group Category', 'Student Group', 'Total Tested', 'Filter All']
INCOME_DEFINITION = ('Same-year October 1, 2024 MDE enrolled students individually '
    'eligible for free or reduced-price meals; native student eligibility differs '
    'from universal school meal access. Exact reported eligible counts and native '
    'school enrollment are used only when neither is privacy suppressed. '
    'The school total includes all enrolled grades, including PK and ECSE where '
    'reported. It is not a valid-score denominator.')
STANDARD = ('Native 2024–25 schoolwide All Standards-Based MCA-III/MTAS results, '
    'All Categories/All students, Grade 0. The native workbook defines Total '
    'Tested as students receiving a valid score and proficiency as students at '
    'Meets or Exceeds Standards divided by Total Tested. Absent, invalid, refused '
    'and other no-score categories are separate and are not included in that '
    'denominator. Published numeric M/E counts are used directly; suppressed '
    'components are never recovered. Native subject totals are not grade '
    'percentage averages and do not apply a 95% participation denominator. '
    'This one-year population includes alternate standards and makes no '
    'historical standards-continuity claim.')


def school_id(row):
    pieces = []
    for field, width in [('District Number', 4), ('District Type', 2), ('School Number', 3)]:
        raw = row[field]
        if isinstance(raw, bool):
            raise ValueError('Boolean Minnesota school identifier')
        if isinstance(raw, (int, float)):
            if not math.isfinite(raw) or raw != int(raw):
                raise ValueError('Noninteger Minnesota school identifier')
            raw = str(int(raw))
        if not isinstance(raw, str) or not re.fullmatch(r'\d{1,' + str(width) + '}', raw) or int(raw) <= 0:
            raise ValueError('Invalid Minnesota native school identifier')
        pieces.append(raw.zfill(width))
    return '-'.join(pieces)


def count(value):
    if value in [None, '']:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value != int(value):
        raise ValueError('Invalid or unexpected native Minnesota count')
    return int(value)


def fraction(value):
    if value in [None, '']:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Invalid native Minnesota proficiency fraction')
    return float(value)


def profile_cohort(entries):
    rows = {e['raw']['Grade']: e['raw'] for e in entries}
    if len(rows) != len(entries) or 'All Grades' not in rows:
        raise ValueError('Duplicate or missing Minnesota school grade profile')
    allowed = {'All Grades', 'ECSE', 'PK', 'KG'} | {str(g) for g in range(1, 13)}
    if not set(rows) <= allowed:
        raise ValueError('Unknown Minnesota reported grade')
    total = count(rows['All Grades']['Total Enrollment'])
    grade_counts = [count(r['Total Enrollment']) for g, r in rows.items() if g != 'All Grades']
    if total is None or total <= 0 or not grade_counts or any(n is None for n in grade_counts):
        return None, 'Incomplete or suppressed native grade profile'
    if sum(grade_counts) != total:
        return None, 'Native grade enrollment does not reconcile to school total'
    present = {int(g) for g, r in rows.items() if re.fullmatch(r'\d+', g) and count(r['Total Enrollment']) > 0}
    lower, upper = bool(present & set(range(3, 9))), bool(present & set(range(9, 13)))
    if lower and upper:
        return None, 'Mixed tested grade-school and high-school enrollment'
    if lower:
        return 'grade', None
    if upper:
        if any(count(r['Total Enrollment']) > 0 for g, r in rows.items()
               if g in {'ECSE', 'PK', 'KG', '1', '2'}):
            return None, 'High-school ID shares primary or early-childhood enrollment'
        return 'high', None
    return None, 'Outside the tested grade-school and high-school populations'


def income(raw):
    total, eligible = count(raw['Total Enrollment']), count(raw[INCOME_COUNT])
    if raw['Filter Groups'] not in ['N', 'Y'] or raw[INCOME_FLAG] not in ['N', 'Y']:
        raise ValueError('Unexpected Minnesota income privacy flag')
    if total is None or total <= 0 or eligible is None or raw['Filter Groups'] == 'Y' or raw[INCOME_FLAG] == 'Y':
        return total, None, None, 'Native individual eligibility is missing or privacy suppressed'
    if eligible > total:
        raise ValueError('Minnesota individually eligible count exceeds enrollment')
    published = raw[INCOME_RATE]
    if published is not None:
        if not isinstance(published, str) or not re.fullmatch(r'\d{1,3}\.\d{2}%', published):
            raise ValueError('Unexpected Minnesota published income percentage')
        if abs(float(published[:-1]) - 100 * eligible / total) > .005001:
            raise ValueError('Minnesota published eligibility does not reconcile to exact counts')
    return total, eligible, 100 * eligible / total, None


def outcome(entry, subject):
    if entry is None:
        return dict(proficiency=None, tested=None, exclusion='No native schoolwide subject result')
    r = entry['raw']
    if (r['Data Year'], r['Test Name'], r['Grade'], r['Group Category'], r['Student Group'], r['Subject']) != (
            '24-25', TEST, 0, 'All Categories', 'All students', 'Math' if subject == 'math' else 'Reading'):
        raise ValueError('Minnesota assessment crossed year, grade total, test or population')
    if r['Filter All'] not in ['N', 'Y']:
        raise ValueError('Unexpected Minnesota assessment suppression flag')
    tested, meets, exceeds = [count(r[f]) for f in ['Total Tested', 'Count Level M', 'Count Level E']]
    published = fraction(r['Percent Proficient'])
    result = dict(proficiency=None, tested=None, raw=r, raw_tested=r['Total Tested'],
                  source=subject, source_row=entry['source_row'])
    if r['Filter All'] == 'Y' or tested is None or tested <= 0 or meets is None or exceeds is None or published is None:
        return dict(result, exclusion='Native proficiency or valid-score components privacy suppressed')
    if meets + exceeds > tested:
        raise ValueError('Minnesota proficient counts exceed valid scores')
    four = [count(r['Count Level ' + level]) for level in ['D', 'P', 'M', 'E']]
    if all(n is not None for n in four) and sum(four) != tested:
        raise ValueError('Minnesota native four-level counts do not reconcile')
    valid = [count(r[f]) for f in ['Count Valid Scores MCA', 'Count Valid Scores MTAS']]
    if all(n is not None for n in valid) and sum(valid) != tested:
        raise ValueError('Minnesota native valid-score components differ from total')
    if abs(published - (meets + exceeds) / tested) > .00005001:
        raise ValueError('Minnesota native proficient fraction differs from reported counts')
    return dict(result, proficiency=100 * (meets + exceeds) / tested, tested=tested,
                valid_score_evidence='Native 2025 workbook Column Definitions: Total Tested means number receiving a valid score; M+E numerator.', exclusion=None)


def workbook_rows(path, sheet, header_row=1):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        iterator = iter(book[sheet].values)
        for _ in range(header_row - 1):
            next(iterator)
        headers = list(next(iterator))
        for number, values in enumerate(iterator, header_row + 1):
            yield dict(source_row=number, raw=dict(zip(headers, values)))
    finally:
        book.close()


def workbook_metadata(path, info):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return dict(information=[list(r) for r in book[info].values],
                    definitions=[list(r) for r in book['Column Definitions'].values])
    finally:
        book.close()


def extract():
    for key, (file, _) in FILES.items():
        signature = (RAW / file).read_bytes()[:8]
        if file.endswith('.pdf') and not signature.startswith(b'%PDF-') or file.endswith('.docx') and not signature.startswith(b'PK'):
            raise ValueError('Minnesota guide download is an HTML response or invalid document: ' + key)
    metadata = {s: workbook_metadata(RAW / FILES[s][0], 'Enrollment Information' if s == 'enrollment' else 'Assessment Information')
                for s in ['math', 'reading', 'enrollment']}
    for subject in ['math', 'reading']:
        definitions = dict(metadata[subject]['definitions'][1:])
        if definitions['Total Tested'] != 'Number of students receiving a valid score.' or definitions['Percent Proficient'] != 'Count of students who meet or exceed standards divided by the total tested.':
            raise ValueError('Minnesota current native valid-score formula changed')
    profiles = defaultdict(list)
    for entry in workbook_rows(RAW / 'enrollment.xlsx', 'School', 2):
        if entry['raw']['Data Year'] == '24-25':
            entry['raw'] = {f: entry['raw'][f] for f in PROFILE_FIELDS}
            profiles[school_id(entry['raw'])].append(entry)
        elif any(entry['raw'].get(k) is not None for k in ['District Number', 'School Number']):
            raise ValueError('Minnesota enrollment contains a different school year')
    assessments = {}
    for subject in ['math', 'reading']:
        native = []
        for entry in workbook_rows(RAW / FILES[subject][0], 'School'):
            r = entry['raw']
            if (r['Group Category'], r['Student Group']) != ('All Categories', 'All students'):
                continue
            if r['Data Year'] != '24-25' or r['Test Name'] != TEST:
                raise ValueError('Minnesota schoolwide test/year changed')
            school_id(r)
            if r['Grade'] != 0:
                entry['raw'] = {f: r[f] for f in GRADE_FIELDS}
            native.append(entry)
        assessments[subject] = native
    sources = {s: dict(path=str((RAW / file).relative_to(ROOT)), url=url,
                       sha256=hashlib.sha256((RAW / file).read_bytes()).hexdigest())
               for s, (file, url) in FILES.items()}
    payload = dict(schema_version=1, state='MN', year=YEAR, academic_year='2024-2025',
                   retrieved=date.today().isoformat(), sources=sources, metadata=metadata,
                   documentary_evidence=DOCUMENTARY,
                   profiles=[dict(id=k, rows=v) for k, v in sorted(profiles.items())], assessments=assessments)
    EXTRACT.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
    return payload


def normalize(payload):
    if (payload['schema_version'], payload['state'], payload['year'], payload['academic_year']) != (1, 'MN', YEAR, '2024-2025'):
        raise ValueError('Minnesota extract identity or year changed')
    if payload.get('documentary_evidence') != DOCUMENTARY:
        raise ValueError('Minnesota dated individual income definition audit is missing')
    for subject in ['math', 'reading']:
        definitions = dict(payload['metadata'][subject]['definitions'][1:])
        if definitions.get('Total Tested') != 'Number of students receiving a valid score.' or definitions.get('Percent Proficient') != 'Count of students who meet or exceed standards divided by the total tested.':
            raise ValueError('Minnesota valid-score formula is absent from source metadata')
    by_school = defaultdict(lambda: defaultdict(list))
    seen = set()
    for subject, entries in payload['assessments'].items():
        if subject not in ['math', 'reading']:
            raise ValueError('Unexpected Minnesota assessment subject')
        expected = {0, 3, 4, 5, 6, 7, 8, 11 if subject == 'math' else 10}
        for entry in entries:
            r = entry['raw']; key = school_id(r)
            if (r['Data Year'], r['Test Name'], r['Group Category'], r['Student Group'], r['Subject']) != (
                    '24-25', TEST, 'All Categories', 'All students', 'Math' if subject == 'math' else 'Reading') or r['Grade'] not in expected:
                raise ValueError('Minnesota assessment crossed year, native grade scope or population')
            identity = key, subject, r['Grade']
            if identity in seen:
                raise ValueError('Duplicate Minnesota school/subject/grade')
            seen.add(identity)
            by_school[key][subject].append(entry)
    schools, ignored, profile_ids = [], Counter(), set()
    for profile in payload['profiles']:
        key, entries = profile['id'], profile['rows']
        if key in profile_ids or not entries:
            raise ValueError('Duplicate or empty Minnesota school profile')
        profile_ids.add(key)
        for entry in entries:
            if school_id(entry['raw']) != key or entry['raw']['Data Year'] != '24-25':
                raise ValueError('Minnesota economic join crossed native identity or school year')
        if key.split('-')[1] == '34':
            ignored['Tribal/BIE District Type 34 outside state-public jurisdiction'] += 1
            continue
        cohort, reason = profile_cohort(entries)
        total_entry = next(e for e in entries if e['raw']['Grade'] == 'All Grades')
        r = total_entry['raw']
        enrollment, low, pct, income_reason = income(r)
        if cohort is None:
            ignored[reason] += 1
            continue
        actual_grades = {e['raw']['Grade'] for values in by_school[key].values() for e in values if e['raw']['Grade'] != 0}
        if (cohort == 'grade' and actual_grades & {10, 11}) or (cohort == 'high' and actual_grades & set(range(3, 9))):
            ignored['Native test grades establish mixed scope beyond fall grade profile'] += 1
            continue
        outcomes = {}
        for subject in ['math', 'reading']:
            native = by_school[key][subject]
            totals = [e for e in native if e['raw']['Grade'] == 0]
            if len(totals) > 1:
                raise ValueError('Duplicate Minnesota schoolwide assessment')
            outcomes[subject] = outcome(totals[0] if totals else None, subject)
            if totals:
                # Audit the reported denominator against native grade counts;
                # use the published school total, never recover masked bands.
                grades = [e['raw'] for e in native if e['raw']['Grade'] != 0]
                counts = [count(g['Total Tested']) for g in grades]
                n = count(totals[0]['raw']['Total Tested'])
                if grades and n is not None and all(v is not None for v in counts) and sum(counts) != n:
                    raise ValueError('Minnesota native grade score counts differ from school total')
        schools.append(dict(id=key, name=r['School Name'], district_id=key.rsplit('-', 1)[0],
                            district=r['District Name'], county=r['County Name'], cohort=cohort,
                            enrollment=enrollment, low_income=low, income=pct,
                            income_raw=dict(total=total_entry, grade_profile=entries, exclusion=income_reason),
                            income_source='enrollment', income_row=total_entry['source_row'], outcomes=outcomes))
    ignored['Assessment school absent from same-year native enrollment'] = len(set(by_school) - profile_ids)
    cohorts = []
    for ident, level, grades in [('grade', 'ES', '3–8'), ('high', 'HS', 'Math 11; ELA 10')]:
        assessment = 'MCA-III/MTAS · ' + ('grades 3–8' if ident == 'grade' else 'Math 11 / ELA 10')
        note = ('Pure grade schools' if ident == 'grade' else 'Pure high schools') + ' · valid-score school totals · individual October eligibility'
        cohorts.append(dict(id=ident, level=level, assessment=assessment, label='2024–25 ' + assessment,
                            grades=grades, standard=STANDARD, source='math', source_url=FILES['math'][1],
                            outcome='Meets or exceeds standards', note=note, allow_point_only=False))
    details = [
        STANDARD,
        'Native District Number + District Type + School Number establish school identity; all three components match exactly across the October 2024 enrollment and Spring 2025 assessment tables. Names do not establish identity. Enrollment and proficiency belong to the same 2024–25 school year but represent different dates and student populations.',
        'The native 2024–25 enrollment file newly includes tribal-controlled schools. All District Type 34 profiles are explicitly excluded from state-public jurisdiction and preserved in the source audit; school names never supply that jurisdiction decision.',
        'The complete native October grade subtotals must sum exactly to school enrollment before the population is classified. Grade schools have Grades 3–8 and no Grades 9–12; high schools have only Grades 9–12, with no PK, ECSE, KG or Grades 1–8. Mixed enrollment or contrary tested grades exclude the entire school. High-school math tests Grade 11 while ELA tests Grade 10, so Combined averages two subject percentages drawn from different grade cohorts.',
        INCOME_DEFINITION,
        'The dated 2024–25 MARSS economic indicators and June 2024 CEP application guidance distinguish individual eligibility from universal meal access. CEP schools must collect alternate applications and report actual eligibility; universal meals do not justify assigning every student low income.',
        'Privacy blanks remain unavailable. Native school income totals require unsuppressed counts and both native suppression flags clear; missing totals are never reconstructed from grade counts. Native proficiency requires numeric Meets and Exceeds counts, a numeric published proficiency fraction and an unsuppressed valid-score total. Suppressed components remain unavailable even if another cell would reveal a complement.',
        'Math, ELA and Combined each have separate same-year, within-population externally studentized models. Combined is the equally weighted mean of math and ELA proficiency. UI filters never refit models; state proficiency standards do not support a pooled national ranking.',
    ]
    return dict(dataset=DATASET, state=dict(id='MN', name='Minnesota'), year=YEAR, academic_year='2024–25',
                name='Minnesota 2024–25 MCA/MTAS valid-score school totals',
                model_scope='Separate Minnesota pure grade-school and pure high-school valid-score models',
                region='minnesota', prepare_script='scripts/prepare_minnesota.py', source_url=PORTAL,
                retrieved=payload['retrieved'], sources=payload['sources'], cohorts=cohorts, schools=schools,
                income_definition=dict(label='October individual meal eligibility', definition=INCOME_DEFINITION,
                                       url=DOCUMENTARY['cep_guidance']['url']),
                coverage_note='2024–25 native school totals; mixed grade schools and privacy-suppressed income excluded. High-school math and ELA test different grades.',
                methodology=dict(summary='Minnesota native valid-score proficiency versus individual October eligibility, within separate pure grade and high school populations.',
                                 details=details, sources=[dict(label=s.replace('_', ' ').title(), url=v['url']) for s, v in {**payload['sources'], **DOCUMENTARY}.items()]),
                source_audit=dict(exclusions=dict(ignored), native_profile_count=len(profile_ids), metadata=payload['metadata'], documentary_evidence=DOCUMENTARY))


def prepare(database=DEFAULT_DB, output=OUTPUT):
    payload = json.loads(EXTRACT.read_text())
    return prepare_snapshot(normalize(payload), EXTRACT, output, database)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.extract:
        extract()
    print(json.dumps(prepare(args.database, args.output), indent=2))


if __name__ == '__main__':
    main()
