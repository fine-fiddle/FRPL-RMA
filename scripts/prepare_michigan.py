"""Michigan 2024–25 native M-STEP and PSAT8, with individual enrolled ED.

The two assessments have separate grade-school datasets and models. Rebuild
offline from the committed extract; --extract reads the two official bulk CSVs
already obtained through the public form, with pinned native checksums. Delivery
addresses and temporary download URLs are never retained as provenance.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import re

from database import ROOT, DEFAULT_DB
from state_snapshot import prepare_snapshot

EXTRACT = ROOT / 'data/source/michigan.json'
OUTPUT = ROOT / 'data/michigan'
RAW = ROOT / 'data/raw/michigan'
SCHOOL_YEAR = '24 - 25 School Year'
FORM_URL = 'https://www.mischooldata.org/k-12-data-files/'
ASSESSMENT_URL = 'https://www.mischooldata.org/grades-3-8-state-testing-includes-psat-data-proficiency/'
ENROLLMENT_URL = 'https://www.mischooldata.org/student-enrollment-counts-report/'
PUBLIC_ENTITIES = {'LEA School', 'PSA School', 'ISD School', 'State School'}
GRADE_LEVELS = {'Elementary', 'Middle School', 'Elem_Middle School'}
INCOME_LABEL = 'Michigan MSDS individual economic disadvantage'
INCOME_DEFINITION = (
    'Same-record 2024–25 fall unduplicated school headcount: independently '
    'published ECONOMIC_DISADVANTAGED_ENROLLMENT divided by TOTAL_ENROLLMENT. '
    'School records exclude Pre-K. Individual Supplemental Nutrition Eligibility '
    'includes approved household applications or Education Benefits forms, '
    'direct certification and authorized household extensions. The October 24, '
    '2024 MDE memorandum and FY2024–25 Section 31a FAQ require individual '
    'eligibility even at CEP schools and under universal free meals; meal access '
    'and reimbursement claims do not make every pupil economically disadvantaged. '
    'Protected counts remain unavailable. This enrolled population differs from '
    'the spring tested population; administrative eligibility and application '
    'nonresponse can affect the count.')
VALID_SCORE_EVIDENCE = (
    'MI School Data Grades 3–8 State Testing report metadata: these reports '
    'include all valid tests taken by public school students; nonpublic and '
    'home-schooled scores are excluded. NumberAssessed is the native count in '
    'that valid-test report, not fall enrollment, expected participation or '
    'a federal 95%-rule denominator. ' + ASSESSMENT_URL)

# Stable public report/form URLs identify the native files. The checksums pin
# what was actually delivered, independently of later-changing reference PDFs.
APPROVED_SOURCES = {
    'assessment': dict(path='data/raw/michigan/grades-3-8-2025.csv', url=FORM_URL,
        bytes=239163392, sha256='789a4eeeac9f8ed4e3da0f64a8270805250721facf3da6abc52a4253ee8821ce'),
    'student_count': dict(path='data/raw/michigan/student-count-2025.csv', url=FORM_URL,
        bytes=1550519, sha256='498d9234733341fb9ed02c58514fd5d79c13cb55c91c3d2425299e669c2f3818'),
    'assessment_metadata': dict(path='data/raw/michigan/assessment-proficiency-metadata.html', url=ASSESSMENT_URL,
        bytes=196245, sha256='cf5660d51a260aeeb8973393e5bbda13e7588b46b16b100f996750447b17c315'),
    'enrollment_metadata': dict(path='data/raw/michigan/student-enrollment-counts-report.html', url=ENROLLMENT_URL,
        bytes=180533, sha256='31b7dd0f9aaedff617f90adc602c53166159d36e66cd9579fd4dad76abce6f62'),
    'individual_memo': dict(path='data/raw/michigan/at-risk-october2024.pdf',
        url='https://www.michigan.gov/mde/-/media/Project/Websites/mde/Memos/2024/10/At-Risk-Section-31a-Funding.pdf?rev=2427d9e20ff54d15b83adfe1660fe04e',
        bytes=258168, sha256='f100a0f14d0b0691c52bc0411d64c77d12f2924f23e932e5b0cbaf3170a11842'),
    'individual_faq': dict(path='data/raw/michigan/31a-faq-2024-25.pdf',
        url='https://www.michigan.gov/mde/-/media/Project/Websites/mde/OES/Programs/Section-31a/Section_31a_FAQ.pdf?hash=E4B6DA7763F511D87C8736882E3B1F58&rev=9cc53929961542f580dda0fa917f7d49',
        bytes=348727, sha256='7f50a24be7668d3eb2171dff561577b30ac5602e9640856200a724c4ae7aa34a'),
    'dc_faq': dict(path='data/raw/michigan/direct-certification-faq-2024-25.pdf',
        url='https://www.michigan.gov/mde/-/media/Project/Websites/mde/ohns/School-Nutrition-Programs/Direct-Certification/2024-2025--Direct-Certification/FAQ-for-DC-Requirements-SY-24-25.pdf?hash=014F75E3EBA43302752F9560978D2777&rev=1f692a3c3e5c411ea77d58624d96568c',
        bytes=156506, sha256='2c9a1852c917cb7c59dbf729fc40002c72715c126925ed4063f668c1e5814db6'),
    'disclosure': dict(path='data/raw/michigan/assessment-disclosure.pdf',
        url='https://www.michigan.gov/-/media/Project/Websites/cepi/MISchoolData/Grades_38_and_High_School_Assessments_Disclosure_Avoidance.pdf',
        bytes=147228, sha256='737aef7f21ba2e1a294ce0b3373fde05ef6c3defecd1e160753586662aab87f2'),
    'psat8_levels': dict(path='data/raw/michigan/psat8-performance-levels.pdf',
        url='https://www.michigan.gov/mde/-/media/Project/Websites/mde/OEAA/PSAT/PSAT-8_9-for-Grade-8-Performance-Level-Information.pdf?hash=5262B1C6A190B3DEE23168F8015F123B&rev=ae6c6e11dc744013bd37b586f30c2b16',
        bytes=137074, sha256='e0636c07a99d476e1a8a96b636494514e712bd4f8e67fb8a4cab5b20c2e1f69f'),
    'identity_definition': dict(path='data/raw/michigan/msds-section25-guide.pdf',
        url='https://www.michigan.gov/-/media/Project/Websites/cepi/MSDS/Section25_User_Guide.pdf',
        bytes=926937, sha256='a8869f1109176592a6e6d3a8d1510c889edde1ea765ca92873d918803ae95d3a'),
}
SOURCE_CONTRACT = dict(
    school_year=SCHOOL_YEAR, public_school_entities=sorted(PUBLIC_ENTITIES),
    individual_fall_income=True, universal_meals_not_individual_eligibility=True,
    assessment_population='All Students; TestPopulation=N/A; public school entities; native regular test only',
    valid_score_evidence=VALID_SCORE_EVIDENCE,
    native_aggregate='Use independently published TotalMet and NumberAssessed, never components or complements',
    response_protection='Require numeric unbounded PercentMet for every enrolled tested grade, as well as exact counts with NumberAssessed>=10',
    grade_scope='Native pure grade-school type, exact zero grades 9–12 and ungraded; complete explicit enrolled grade set, including <10 as potentially enrolled and therefore required',
    join='Exact SchoolYear+BuildingCode, with identical DistrictCode/ISDCode/EntityType/SchoolLevel across native files',
    sources=APPROVED_SOURCES)

SPECS = {
    'mi-mstep-2025': dict(slug='mstep', testtype='M-STEP', region='michigan-mstep',
        name='Michigan 2025 M-STEP grades 3–7 and individual enrolled disadvantage',
        region_name='Grade schools · M-STEP grades 3–7', grades='3–7',
        assessment='Michigan M-STEP · enrolled grades 3–7 · 2025',
        standard='Native M-STEP Advanced or Proficient under each tested grade\u2019s Math/ELA achievement standards; MI-Access excluded',
        outcome='Proficient or advanced'),
    'mi-psat8-2025': dict(slug='psat8', testtype='PSAT', region='michigan-psat8',
        name='Michigan 2025 PSAT grade 8 and individual enrolled disadvantage',
        region_name='Grade schools · PSAT grade 8', grades='8',
        assessment='Michigan PSAT 8/9 · grade 8 · 2025',
        standard='Native grade 8 PSAT Advanced or Proficient, meeting grade 8 College Board benchmarks: Reading/Writing 390 and Math 430; separate from M-STEP and MI-Access',
        outcome='Meets grade 8 benchmark'),
}
ASSESSMENT_FIELDS = ['SchoolYear', 'TestType', 'TestPopulation', 'ISDCode', 'ISDName',
    'DistrictCode', 'DistrictName', 'BuildingCode', 'BuildingName', 'CountyCode', 'CountyName',
    'EntityType', 'SchoolLevel', 'GradeContentTested', 'Subject', 'ReportCategory',
    'TotalAdvanced', 'TotalProficient', 'TotalPartiallyProficient', 'TotalNotProficient',
    'TotalSurpassed', 'TotalAttained', 'TotalEmergingTowards', 'TotalMet', 'TotalDidNotMeet',
    'NumberAssessed', 'PercentMet']


def count(value):
    """Only independently published nonnegative integer cells are counts."""
    return int(value) if isinstance(value, str) and re.fullmatch(r'\d+', value) else None


def exact_percent(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+)?', value):
        return None
    result = float(value)
    return result if math.isfinite(result) and 0 <= result <= 100 else None


def identity(row):
    if (row.get('SchoolYear') != SCHOOL_YEAR or row.get('EntityType') not in PUBLIC_ENTITIES or
            not isinstance(row.get('BuildingCode'), str) or
            not re.fullmatch(r'\d{5}', row['BuildingCode']) or
            not isinstance(row.get('DistrictCode'), str) or
            not re.fullmatch(r'\d{5}', row['DistrictCode']) or
            not isinstance(row.get('ISDCode'), str) or not re.fullmatch(r'\d{2}', row['ISDCode'])):
        return None
    return row['BuildingCode']


def grade_school(row):
    if identity(row) is None or row.get('SchoolLevel') not in GRADE_LEVELS:
        return False
    if any(row.get(f'GRADE_{g}_ENROLLMENT') != '0' for g in range(9, 13)) or row.get('UNGRADED_ENROLLMENT') != '0':
        return False
    # A protected lower-grade cell may be positive, so its grade is required.
    # Other missing tokens cannot establish the complete expected-grade set.
    fields = ['KINDERGARTEN_ENROLLMENT'] + [f'GRADE_{g}_ENROLLMENT' for g in range(1, 9)]
    return all(count(row.get(f)) is not None or row.get(f) == '<10' for f in fields)


def expected_grades(row, testtype):
    if testtype not in ['M-STEP', 'PSAT']:
        raise ValueError('Unapproved Michigan assessment')
    grades = range(3, 8) if testtype == 'M-STEP' else [8]
    result = []
    for grade in grades:
        value = row.get(f'GRADE_{grade}_ENROLLMENT')
        number = count(value)
        if number is None and value != '<10':
            raise ValueError('Unknown native enrolled tested-grade count')
        if value == '<10' or number > 0:
            result.append(f'{grade:02d}')
    return result


def native_income(row):
    total, disadvantaged = count(row.get('TOTAL_ENROLLMENT')), count(row.get('ECONOMIC_DISADVANTAGED_ENROLLMENT'))
    if total is None or total <= 0 or disadvantaged is None or disadvantaged > total:
        return None, None
    return 100 * disadvantaged / total, disadvantaged


def native_outcome(rows, expectedgrades, subject, testtype):
    """Aggregate a complete explicit grade set; never recover protected rates."""
    if subject not in ['math', 'reading'] or testtype not in ['M-STEP', 'PSAT']:
        raise ValueError('Unapproved Michigan subject/assessment')
    if (not expectedgrades or len(set(expectedgrades)) != len(expectedgrades) or
            expectedgrades != sorted(expectedgrades) or
            any(g not in (['03', '04', '05', '06', '07'] if testtype == 'M-STEP' else ['08']) for g in expectedgrades)):
        raise ValueError('Invalid explicit Michigan expected-grade set')
    raw_rows = [r if 'raw' in r else dict(source_row=0, raw=r) for r in rows]
    grades = {}
    for record in raw_rows:
        row = record['raw']
        if (identity(row) is None or row.get('TestType') != testtype or
                row.get('TestPopulation') != 'N/A' or row.get('ReportCategory') != 'All Students' or
                row.get('Subject') != ('Mathematics' if subject == 'math' else 'ELA') or
                row.get('GradeContentTested') not in (['03', '04', '05', '06', '07'] if testtype == 'M-STEP' else ['08'])):
            raise ValueError('Not the approved same-year public native regular assessment')
        grade = row['GradeContentTested']
        if grade in grades:
            raise ValueError('Duplicate native school/subject/grade assessment')
        grades[grade] = row
    if set(grades) - set(expectedgrades):
        raise ValueError('Native assessed grade lies outside enrolled expected-grade set')
    reason = None
    if set(grades) != set(expectedgrades):
        reason = 'Missing one or more enrolled tested grades in the native subject report'
    numerators, denominators = [], []
    unavailable_count, protected_rate = False, False
    for row in grades.values():
        met, assessed = count(row.get('TotalMet')), count(row.get('NumberAssessed'))
        pct = exact_percent(row.get('PercentMet'))
        if met is not None and assessed is not None:
            if assessed <= 0 or met > assessed:
                raise ValueError('Invalid native proficient/valid-score count pair')
            not_met = count(row.get('TotalDidNotMeet'))
            advanced, proficient = count(row.get('TotalAdvanced')), count(row.get('TotalProficient'))
            bins = [count(row.get(f)) for f in ['TotalAdvanced', 'TotalProficient', 'TotalPartiallyProficient', 'TotalNotProficient']]
            if not_met is not None and met + not_met != assessed:
                raise ValueError('Native aggregate count does not reconcile')
            if advanced is not None and proficient is not None and advanced + proficient != met:
                raise ValueError('Native published proficient aggregate does not reconcile')
            if all(v is not None for v in bins) and sum(bins) != assessed:
                raise ValueError('Native performance-level counts do not reconcile')
            if pct is not None and abs(100 * met / assessed - pct) > .050001:
                raise ValueError('Native published percentage and aggregate count disagree')
        unavailable_count |= met is None or assessed is None or assessed < 10
        protected_rate |= pct is None
        numerators.append(met)
        denominators.append(assessed)
    if reason is None and unavailable_count:
        reason = 'One or more enrolled tested grades have suppressed or unavailable native valid-score counts'
    if reason is None and protected_rate:
        reason = 'One or more enrolled tested grades have a protected or unavailable native PercentMet'
    tested = sum(denominators) if reason is None else None
    return dict(proficiency=100 * sum(numerators) / tested if reason is None else None,
        tested=tested, valid_score_evidence=VALID_SCORE_EVIDENCE if tested is not None else None,
        raw=raw_rows, raw_tested=[dict(source_row=r['source_row'], grade=r['raw']['GradeContentTested'],
            value=r['raw']['NumberAssessed']) for r in raw_rows], source='assessment',
        source_row=min((r['source_row'] for r in raw_rows), default=0), exclusion=reason)


def cohort(spec):
    return dict(id='grade', level='ES', grades=spec['grades'], assessment=spec['assessment'],
        standard=spec['standard'], source='assessment', source_url=FORM_URL,
        label=spec['region_name'], outcome=spec['outcome'],
        note='Regular valid-score tests · individual fall enrolled ED · complete enrolled grade coverage',
        allow_point_only=False)


def model_scope(spec):
    return ('Michigan public pure grade schools with same-year individual fall enrolled economic disadvantage; '
        + spec['region_name'] + '; regular All Students valid-score results only; '
        'MI-Access, mixed grades, high-school and ungraded enrollment excluded')


def exclusion_reason(row, spec):
    if not grade_school(row):
        return 'Mixed, high, ungraded or unknown native grade configuration'
    if native_income(row)[0] is None:
        return 'Individual enrolled economic-disadvantage or total count is protected or unavailable'
    if not expected_grades(row,spec['testtype']):
        return 'No enrolled grade in this assessment population'
    return None


def source_audit(spec, schools, excluded):
    profiles = [s['income_raw'] for s in schools] + [s['income_raw'] for s in excluded]
    eligible = {s:sum(p['outcomes'][s]['proficiency'] is not None for p in schools) for s in ['math','reading']}
    eligible['combined'] = sum(all(p['outcomes'][s]['proficiency'] is not None for s in ['math','reading']) for p in schools)
    return dict(approved_native_regular_valid_scores=True, approved_individual_income=True,
        source_contract=SOURCE_CONTRACT, native_school_profiles=len(profiles),
        pure_grade_profiles=sum(grade_school(p) for p in profiles),
        pure_grade_exact_income_profiles=sum(grade_school(p) and native_income(p)[0] is not None for p in profiles),
        native_assessment_rows=sum(len(o['raw']) for p in schools for o in p['outcomes'].values())
            + sum(len(rows) for p in excluded for rows in p['assessment_raw'].values()),
        directory=len(schools), eligible=eligible,
        subject_exclusions={s:dict(Counter(p['outcomes'][s]['exclusion'] for p in schools if p['outcomes'][s]['exclusion'])) for s in ['math','reading']},
        directory_exclusions=dict(Counter(exclusion_reason(p['income_raw'],spec) for p in excluded)),
        assessment='Native regular '+spec['testtype']+' only; MI-Access FI/SI/P alternate populations remain excluded.',
        proficiency='Sum independently published exact TotalMet and NumberAssessed across the full explicit enrolled tested-grade set, then divide. Numeric unbounded PercentMet is required in every grade; missing grades and protected values are never reconstructed.',
        valid_score_denominator=VALID_SCORE_EVIDENCE,
        tested_vs_enrolled='The native testing report assigns a result to the building where the test was taken; income uses the fall enrollment building. Same-year school-ID matching does not assert identical tested/enrolled students.',
        income=INCOME_DEFINITION,
        identity='Native five-digit BuildingCode+SchoolYear, with exact DistrictCode, ISDCode, EntityType and SchoolLevel agreement; no name join or NCES substitution.',
        grades='Explicit native enrolled grade set; <10 is potentially enrolled and requires that grade. Grades 9–12 and ungraded must each be exact 0. Developmental kindergarten is a subset, ignored; Pre-K is excluded from native school totals.',
        revisions='Dated 2024 income documents establish selected-year eligibility. Current report metadata defines valid tests. Historical interpretive-guide URL revisions returned 2026 contents and are not claimed as dated 2025 evidence.',
        history='Single 2024–25 snapshot, separately fit M-STEP and PSAT grade 8; no incompatible history or national pooling.')


def coverage_note(spec, audit):
    return (f"{audit['directory']} public pure grade-school profiles with exact same-year individual enrolled disadvantage and enrolled {spec['grades']} grades. "
        f"{audit['eligible']['combined']} have complete unsuppressed Math+ELA results. Native regular {spec['testtype']} only; "
        'MI-Access, mixed/high/ungraded schools, missing grades and protected cells limit coverage. '
        'Separate test standards and spring tested/fall enrolled populations; no history.')


def methodology(spec, audit):
    return dict(summary='Native '+spec['region_name']+' valid-score counts and same-year individual enrolled economic disadvantage.',
        details=[INCOME_DEFINITION,audit['proficiency'],VALID_SCORE_EVIDENCE,audit['tested_vs_enrolled'],audit['identity'],audit['grades'],spec['standard'],audit['revisions'],
            ('M-STEP valid-score aggregation weights differ with each school\u2019s enrolled tested-grade composition. The regression does not adjust for grade mix; grade-specific standards remain distinct.'
                if spec['testtype']=='M-STEP' else 'The PSAT comparison uses grade 8 only, independently of M-STEP grades 3–7 and their achievement standards.'),
            'Combined is the equally weighted mean of Math and ELA rates. Every model is fit independently by assessment and subject with externally studentized residuals. Count-based interval propagation uses every eligible model member. Results describe associations, not causal school effectiveness or overall quality.'],
        sources=[dict(label='Official MI School Data 2024–25 bulk CSV request form',url=FORM_URL),
            dict(label='Official valid-test report metadata and assessment scope',url=ASSESSMENT_URL),
            dict(label='Official fall unduplicated enrollment definition',url=ENROLLMENT_URL),
            dict(label='October 24, 2024 individual eligibility under universal meals',url=APPROVED_SOURCES['individual_memo']['url']),
            dict(label='FY2024–25 eligibility and CEP definition',url=APPROVED_SOURCES['individual_faq']['url']),
            dict(label='Native assessment disclosure protection rules',url=APPROVED_SOURCES['disclosure']['url']),
            dict(label='Grade 8 PSAT benchmark performance levels',url=APPROVED_SOURCES['psat8_levels']['url'])])


def extract():
    for item in APPROVED_SOURCES.values():
        path = ROOT / item['path']
        if path.stat().st_size != item['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Native/reference source changed; a fresh source audit is required: ' + item['path'])
    profiles, school_rows, assessment_rows = {}, [], defaultdict(list)
    with (RAW/'student-count-2025.csv').open(encoding='utf-8-sig', newline='') as handle:
        for number, row in enumerate(csv.DictReader(handle), 2):
            if row['SchoolYear'] != SCHOOL_YEAR:
                raise ValueError('Wrong-year Michigan native count CSV')
            if row['EntityType'] not in PUBLIC_ENTITIES:
                continue
            key = identity(row)
            if key is None or key in profiles:
                raise ValueError('Invalid or duplicate native Michigan school identity')
            record = dict(source_row=number, raw=row)
            profiles[key] = record
            school_rows.append(record)
    selected = Counter()
    with (RAW/'grades-3-8-2025.csv').open(encoding='utf-8-sig', newline='') as handle:
        for number, row in enumerate(csv.DictReader(handle), 2):
            if row['SchoolYear'] != SCHOOL_YEAR:
                raise ValueError('Wrong-year Michigan native assessment CSV')
            if (row['EntityType'] not in PUBLIC_ENTITIES or row['ReportCategory'] != 'All Students' or
                    row['TestType'] not in ['M-STEP', 'PSAT'] or row['Subject'] not in ['Mathematics', 'ELA']):
                continue
            if identity(row) is None:
                raise ValueError('Invalid native Michigan assessment identity')
            subject = 'math' if row['Subject'] == 'Mathematics' else 'reading'
            assessment_rows[(row['BuildingCode'], row['TestType'], subject)].append(
                dict(source_row=number, raw={f:row[f] for f in ASSESSMENT_FIELDS}))
            selected[row['TestType']] += 1
    snapshots = []
    for dataset, spec in SPECS.items():
        schools, excluded = [], []
        for key, profile in sorted(profiles.items()):
            row, number = profile['raw'], profile['source_row']
            reason = exclusion_reason(row,spec)
            income, low_income = native_income(row)
            grades = expected_grades(row, spec['testtype']) if reason is None else []
            rows = {s:assessment_rows.get((key,spec['testtype'],s), []) for s in ['math','reading']}
            if reason:
                excluded.append(dict(id=key, source_row=number, income_raw=row, reason=reason,
                    assessment_raw=rows))
                continue
            school = dict(id=key, cohort='grade', name=row['BuildingName'],
                district_id=row['DistrictCode'], district=row['DistrictName'], county=row['CountyName'],
                city=None, enrollment=count(row['TOTAL_ENROLLMENT']), low_income=low_income,
                income=income, income_raw=row, income_source='student_count', income_row=number,
                expected_grades=grades, identity_raw={f:row[f] for f in ['SchoolYear','BuildingCode','DistrictCode','ISDCode','EntityType','SchoolLevel']},
                outcomes={s:native_outcome(records,grades,s,spec['testtype']) for s,records in rows.items()})
            schools.append(school)
        audit = source_audit(spec,schools,excluded)
        if audit['native_assessment_rows'] != selected[spec['testtype']]:
            raise ValueError('Native assessment school has no exact count-file school identity')
        payload = dict(dataset=dataset, year=2025, academic_year='2024–25', school_year=SCHOOL_YEAR,
            state=dict(id='MI',name='Michigan'), name=spec['name'], region=spec['region'],
            prepare_script='scripts/prepare_michigan.py', source_url=FORM_URL, retrieved='2026-10-09',
            model_scope=model_scope(spec), release_status='ready',
            income_definition=dict(label=INCOME_LABEL,definition=INCOME_DEFINITION,url=ENROLLMENT_URL),
            sources=APPROVED_SOURCES, source_audit=audit, cohorts=[cohort(spec)], schools=schools, excluded=excluded,
            coverage_note=coverage_note(spec,audit), methodology=methodology(spec,audit))
        validate(payload)
        snapshots.append(payload)
    result = dict(schema_version=1, year=2025, school_year=SCHOOL_YEAR,
        source_url=FORM_URL, sources=APPROVED_SOURCES,
        native_public_school_profiles=school_rows, snapshots=snapshots)
    EXTRACT.write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
    return result


def validate(snapshot):
    spec = SPECS.get(snapshot.get('dataset'))
    if (spec is None or snapshot.get('year') != 2025 or snapshot.get('academic_year') != '2024–25' or
            snapshot.get('school_year') != SCHOOL_YEAR or snapshot.get('state') != dict(id='MI',name='Michigan')):
        raise ValueError('Unapproved Michigan state/year/dataset')
    if (snapshot.get('cohorts') != [cohort(spec)] or snapshot.get('region') != spec['region'] or
            snapshot.get('prepare_script') != 'scripts/prepare_michigan.py' or snapshot.get('source_url') != FORM_URL or
            snapshot.get('name') != spec['name'] or snapshot.get('model_scope') != model_scope(spec) or
            snapshot.get('release_status') != 'ready'):
        raise ValueError('Michigan assessment/population/source metadata changed')
    if (snapshot.get('sources') != APPROVED_SOURCES or
            snapshot.get('source_audit',{}).get('source_contract') != SOURCE_CONTRACT or
            snapshot.get('source_audit',{}).get('approved_native_regular_valid_scores') is not True or
            snapshot.get('source_audit',{}).get('approved_individual_income') is not True or
            snapshot.get('income_definition') != dict(label=INCOME_LABEL,definition=INCOME_DEFINITION,url=ENROLLMENT_URL)):
        raise ValueError('Michigan native source/definition contract changed')
    seen = set()
    for school in snapshot['schools']:
        row = school['income_raw']
        key = identity(row)
        if (key is None or key != school['id'] or key in seen or not grade_school(row) or school['cohort'] != 'grade' or
                row['DistrictCode'] != school['district_id'] or
                school.get('identity_raw') != {f:row[f] for f in ['SchoolYear','BuildingCode','DistrictCode','ISDCode','EntityType','SchoolLevel']}):
            raise ValueError('Michigan native identity/year/grade scope changed')
        seen.add(key)
        income, low_income = native_income(row)
        if (income is None or school['income'] != income or school['low_income'] != low_income or
                school['enrollment'] != count(row['TOTAL_ENROLLMENT']) or
                school['income_source'] != 'student_count' or not isinstance(school['income_row'],int) or school['income_row'] < 2):
            raise ValueError('Michigan economic values are not exact native enrolled individual counts')
        # Check native total independently when the grade operands are visible;
        # protected lower-grade values do not prevent a conservative grade set.
        grade_counts = [count(row[f]) for f in ['KINDERGARTEN_ENROLLMENT'] + [f'GRADE_{g}_ENROLLMENT' for g in range(1,13)] + ['UNGRADED_ENROLLMENT']]
        if all(v is not None for v in grade_counts) and sum(grade_counts) != school['enrollment']:
            raise ValueError('Native K–12 grade counts do not reconcile to school enrollment')
        grades = expected_grades(row,spec['testtype'])
        if not grades or school.get('expected_grades') != grades or set(school['outcomes']) != {'math','reading'}:
            raise ValueError('Michigan explicit expected grades/subject pair changed')
        for subject, outcome in school['outcomes'].items():
            for record in outcome['raw']:
                native = record['raw']
                if (identity(native) != key or any(native[f] != row[f] for f in ['DistrictCode','ISDCode','EntityType','SchoolLevel']) or
                        not isinstance(record['source_row'],int) or record['source_row'] < 2):
                    raise ValueError('Michigan assessment school/year/population join changed')
            if outcome != native_outcome(outcome['raw'],grades,subject,spec['testtype']):
                raise ValueError('Michigan outcome is not the exact protected complete native grade aggregate')
    for profile in snapshot['excluded']:
        row = profile['income_raw']
        key = identity(row)
        if (key is None or key != profile['id'] or key in seen or
                not exclusion_reason(row,spec) or profile['reason'] != exclusion_reason(row,spec)):
            raise ValueError('Michigan excluded profile identity/scope/reason changed')
        seen.add(key)
    audit = source_audit(spec,snapshot['schools'],snapshot['excluded'])
    if (snapshot['source_audit'] != audit or snapshot.get('coverage_note') != coverage_note(spec,audit) or
            snapshot.get('methodology') != methodology(spec,audit)):
        raise ValueError('Michigan coverage/audit/methodology differs from validated source rows and definitions')


def prepare(database=DEFAULT_DB):
    payload = json.loads(EXTRACT.read_text())
    if (payload.get('schema_version') != 1 or payload.get('year') != 2025 or payload.get('school_year') != SCHOOL_YEAR or
            payload.get('source_url') != FORM_URL or payload.get('sources') != APPROVED_SOURCES or
            [s.get('dataset') for s in payload.get('snapshots',[])] != list(SPECS)):
        raise ValueError('Wrong Michigan two-assessment extract topology/source contract')
    # Validate both complete payloads before either mutates the canonical store.
    for snapshot in payload['snapshots']:
        validate(snapshot)
    audits, regions = {}, []
    for snapshot in payload['snapshots']:
        spec = SPECS[snapshot['dataset']]
        destination = OUTPUT / spec['slug']
        audits[spec['slug']] = prepare_snapshot(snapshot,EXTRACT,destination,database)
        descriptor = json.loads((destination/'catalog.json').read_text())
        descriptor['regions'][0]['name'] = spec['region_name']
        regions.extend(descriptor['regions'])
        # Keep the nested descriptor accurate for direct inspection. Only the
        # parent descriptor is discovered by the statewide catalog/dispatcher.
        (destination/'catalog.json').write_text(json.dumps(descriptor,indent=2)+'\n')
    parent = dict(schema_version=1,state=dict(id='MI',name='Michigan'),
        prepare_script='scripts/prepare_michigan.py',regions=regions)
    (OUTPUT/'catalog.json').write_text(json.dumps(parent,indent=2)+'\n')
    return audits


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract',action='store_true')
    parser.add_argument('--database',default=DEFAULT_DB)
    args = parser.parse_args()
    if args.extract:
        extract()
    print(json.dumps(prepare(args.database),indent=2))
