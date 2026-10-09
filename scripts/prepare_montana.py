"""Montana 2025 native MAST grade totals and non-CEP individual NSLP eligibility.

Default rebuilds are offline. --extract reads official downloaded sources into
the committed audit extract; no grade rates, suppression values or valid-score
counts are reconstructed. See docs/montana-data.md for the restricted population.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import json
import re

import openpyxl

from audit_national_sources import RAW, EDC, DIRECTORY, MEMBERSHIP, exact_rate, read_ccd, membership_cache, source
from database import ROOT, DEFAULT_DB
from prepare_ccd_states import grade_school, compact_outcome
from state_registry import reported_count
from state_snapshot import prepare_snapshot

EXTRACT = ROOT / 'data/source/montana.json'
OUTPUT = ROOT / 'data/montana'
ASSESSMENT_URL = 'https://www.eddatacenter.org/api/data/3.1?state=MT&year=2025'
NUTRITION_URL = ('https://gemsapi.opi.mt.gov/Report/ExportReport/?reportPath=%2FGEMS_SSRS_Reports%2FStudent_Reports%2FSchoolNutrition_ERate&format=Csv&strProgramYear=2025&strStateCounty=0&UserName=opigemsanon&ReportViewerEnablePaging=True')
CLAIMS_URL = 'https://opifiles.mt.gov/Portals/182/Page%20Files/School%20Nutrition/Agreements,%20Claims,%20%26%20Data/NSLP_ClaimCountsFor_20260416.xlsx'
CLAIM_FIELDS_URL = 'https://opifiles.mt.gov/Portals/182/Page%20Files/School%20Nutrition/Agreements,%20Claims,%20%26%20Data/Claim%20Meal%20Count%20Reports%20-%20Field%20Definition%20List.xlsx'
INCOME_DEFINITION = (
    'Individual free/reduced-price NSLP eligibility divided by native lunch '
    'enrollment in the October 2024 claim, within school year 2024–25. Retain '
    'only public schools participating in the regular program and without any '
    'GEMS CEP base-year flag. The exact GEMS Program Year 2025 eligible count '
    'and enrolled count must both equal the October 2024 school claim. OPI '
    'defines free/reduced eligibility through household income applications '
    'and qualifying direct certification. This is individual eligibility, '
    'not meals served or a CEP claiming multiplier. Native NSLP enrollment '
    'can differ from fall school membership; displayed enrollment is separate '
    'same-year CCD membership. This restricted cohort excludes all CEP, '
    'nonregular, nonpublic and ambiguous school identities.')


def native_key(district, school):
    # OPI also assigns six-digit site IDs to certain nonpublic/non-school sites;
    # retain them in the exclusions rather than dropping native records.
    if not re.fullmatch(r'\d{4}', str(district)) or not re.fullmatch(r'(?:\d{4}|\d{6})', str(school)):
        return None
    return district + '-' + school


def raw_count(value):
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value)):
        return None
    return int(value)


def native_income(raw):
    gems, claim = raw['gems'], raw['october_claim']
    if raw['program_year'] != 2025 or claim['Claim Period'] != '2024-10-01T00:00:00':
        raise ValueError('Income is not the same-year October2024 school claim')
    if (native_key(gems['District_Entity_Number1'], gems['School_Entity_Number']) !=
            native_key(claim['Sponsor ID'], claim['SiteNbr']) or
            claim['Program'] != 'NSLP' or str(claim['State']).upper() != 'MT'):
        raise ValueError('Native nutrition school identities or population disagree')
    if (gems['CEP_Base_Year'] or claim['School Type'] != 'Public' or
            claim['Site Participates In'] != 'Participates in Regular Program'):
        return None
    eligible = raw_count(gems['Students_Eligible_for_Free_Reduced_Count'])
    enrolled = raw_count(gems['Total_Students_Enrolled'])
    if eligible is None or not enrolled or eligible > enrolled:
        return None
    if (eligible != raw_count(claim['Lunch Free or Reduced Eligible']) or
            enrolled != raw_count(claim['Lunch Enrollment'])):
        raise ValueError('GEMS2025 and October2024 individual eligibility counts disagree')
    # The claim workbook's NCES Id is the five-digit site suffix, not NCESSCH.
    if claim['NCES Id'] != gems['NCES_Code'][-5:]:
        raise ValueError('Native NCES site suffix and GEMS school ID disagree')
    return 100 * eligible / enrolled


def native_outcome(row, number, subject):
    if (row['SchYear'] != '2024-25' or row['StateAbbrev'] != 'MT' or
            row['DataLevel'] != 'School' or row['StudentGroup'] != 'All Students' or
            row['StudentSubGroup'] != 'All Students' or row['GradeLevel'] != 'G38' or
            row['AssmtName'] != 'MAST' or row['AssmtType'] != 'Regular' or
            row['ProficiencyCriteria'] != 'Levels 3-4' or row['Version'] != 'V3.1' or
            row['Flag_AssmtNameChange'] != 'Y' or row['Flag_CutScoreChange_ELA'] != 'Y' or
            row['Flag_CutScoreChange_math'] != 'Y' or
            row['Subject'] != ('ela' if subject == 'reading' else 'math')):
        raise ValueError('Not the audited native MAST school G38 total')
    rate = exact_rate(row['ProficientOrAbove_percent'])
    return dict(proficiency=None if rate is None else 100*rate, tested=None,
        source='edc_2025', source_row=number, raw=row,
        raw_tested=dict(tested=row['StudentSubGroup_TotalTested'],
            proficient=row['ProficientOrAbove_count'], participation=row['ParticipationRate']),
        exclusion=None if rate is not None else 'Native G38 proficient rate is suppressed, ranged or unavailable')


def nutrition_rows():
    with (RAW/'mt-nutrition-erate-2025.csv').open() as handle:
        for _ in range(3):
            next(handle)
        result = {}
        for number, row in enumerate(csv.DictReader(handle), 5):
            key = native_key(row['District_Entity_Number1'], row['School_Entity_Number'])
            if not key:
                continue
            if key in result:
                raise ValueError('Duplicate native nutrition school ID')
            result[key] = (number, row)
        return result


def claim_rows():
    workbook = openpyxl.load_workbook(RAW/'mt-nslp-claims.xlsx', read_only=True, data_only=True)
    rows = iter(workbook['Site'].values)
    headers = next(rows)
    result = {}
    for number, values in enumerate(rows, 2):
        row = dict(zip(headers, values))
        if row['Claim Period'] != datetime(2024, 10, 1):
            continue
        key = native_key(row['Sponsor ID'], row['SiteNbr'])
        if not key or key in result:
            raise ValueError('Invalid or duplicate October2024 sponsor/site ID')
        row = {k: v.isoformat() if isinstance(v, datetime) else v for k,v in row.items()}
        result[key] = (number, row)
    workbook.close()
    return result


def extract():
    nutrition, claims, membership = nutrition_rows(), claim_rows(), membership_cache()
    profiles = {r['NCESSCH']:r for r in read_ccd(DIRECTORY) if r['ST']=='MT'}
    assessments = defaultdict(dict)
    with (EDC/'mt.csv').open() as handle:
        for number, row in enumerate(csv.DictReader(handle), 2):
            if (row['DataLevel']=='School' and row['StudentGroup']=='All Students' and
                    row['StudentSubGroup']=='All Students' and row['GradeLevel']=='G38' and
                    row['Subject'] in ['ela','math']):
                key = native_key(row['StateAssignedDistID'],row['StateAssignedSchID'])
                subject = 'reading' if row['Subject']=='ela' else 'math'
                if not key or subject in assessments[key]:
                    raise ValueError('Ambiguous native G38 assessment identity')
                assessments[key][subject] = (number,compact_outcome(row))
    schools, excluded = [], []
    for key,(number,gems) in sorted(nutrition.items()):
        claim_number, claim = claims.get(key,(None,None))
        profile = profiles.get(gems['NCES_Code'])
        total = membership['totals'].get(profile['NCESSCH']) if profile else None
        grades = membership['grades'].get(profile['NCESSCH']) if profile else None
        raw = dict(program_year=2025,gems=gems,october_claim=claim,claim_source_row=claim_number)
        outcomes = assessments.get(key,{})
        reason = None
        if claim is None:
            reason='Missing exact native October2024 school claim'
        elif gems['CEP_Base_Year'] or claim['Site Participates In']!='Participates in Regular Program':
            reason='CEP or nonregular nutrition program'
        elif claim['School Type']!='Public':
            reason='Nonpublic nutrition school'
        elif (not profile or profile['ST_SCHID']!='MT-'+key or
                claim['NCES Id']!=gems['NCES_Code'][-5:]):
            reason='Missing or disagreeing exact state and NCES school identity'
        elif profile['SCHOOL_YEAR']!='2024-2025' or profile['UPDATED_STATUS'] not in ['1','3','4','5','8']:
            reason='School not operational in same-year CCD directory'
        elif not grade_school(profile,grades,total):
            reason='Mixed, high, untested or unknown grade configuration'
        elif native_income(raw) is None:
            reason='Individual eligible count or native NSLP enrollment is suppressed or unavailable'
        elif set(outcomes) != {'math','reading'}:
            reason='Missing native G38 math/ELA subject pair'
        elif any(row['NCESSchoolID']!=profile['NCESSCH'] for _,row in outcomes.values()):
            reason='Assessment and nutrition NCES school identities disagree'
        if reason:
            excluded.append(dict(state_school_id=key,reason=reason,income=raw,
                directory=profile,membership=total,membership_grades=grades,
                outcomes={s:r for s,(_,r) in outcomes.items()}))
            continue
        schools.append(dict(id=key,cohort='grade',name=profile['SCH_NAME'],
            district_id=profile['ST_LEAID'],district=profile['LEA_NAME'],
            city=profile['LCITY'],county=None,enrollment=reported_count(total),
            income=native_income(raw),low_income=None,income_raw=raw,
            income_source='gems_nutrition',income_row=number,
            directory_raw=profile,membership_raw=total,membership_grades_raw=grades,
            identity_raw=dict(nces_id=profile['NCESSCH'],ccd_state_id=profile['ST_SCHID'],
                normalization='Exact four-digit native sponsor/site strings and full12-digitNCES ID; no sponsor or district repairs'),
            outcomes={s:native_outcome(r,n,s) for s,(n,r) in outcomes.items()}))
    # The all-row crosscheck independently establishes the GEMS program-year
    # mapping, including schools subsequently excluded by the model scope.
    crosschecked = 0
    for key,(_,gems) in nutrition.items():
        if (not gems['CEP_Base_Year'] and raw_count(gems['Students_Eligible_for_Free_Reduced_Count']) is not None and
                raw_count(gems['Total_Students_Enrolled']) is not None):
            claim = claims[key][1]
            if (raw_count(gems['Total_Students_Enrolled'])!=raw_count(claim['Lunch Enrollment']) or
                    raw_count(gems['Students_Eligible_for_Free_Reduced_Count'])!=raw_count(claim['Lunch Free or Reduced Eligible'])):
                raise ValueError('Native GEMS program-year crosscheck failed')
            crosschecked += 1
    sources = {
        'edc_2025':source(EDC/'mt.csv',ASSESSMENT_URL),
        'edc_codebook':source(RAW/'EDC_codebook_v3.1.xlsx','https://www.eddatacenter.org/data_codebooks/EDC_codebook_v3.1.xlsx'),
        'edc_technical':source(RAW/'EDC_technical_documentation_v3.1.pdf','https://www.eddatacenter.org/data_documentation/EDC_technical_documentation_v3.1.pdf'),
        'gems_nutrition':source(RAW/'mt-nutrition-erate-2025.csv',NUTRITION_URL),
        'gems_nutrition_definition':source(RAW/'mt-nutrition-2025.pdf',NUTRITION_URL.replace('format=Csv','format=Pdf')),
        'opi_october_claims':source(RAW/'mt-nslp-claims.xlsx',CLAIMS_URL),
        'opi_claim_definitions':source(RAW/'mt-claim-field-definitions.xlsx',CLAIM_FIELDS_URL),
        'opi_cep_definition':source(RAW/'mt-cep-packet.pdf','https://opifiles.mt.gov/Portals/182/Page%20Files/School%20Nutrition/Meal%20Eligibility/CEP/MAPS%20CEP%20Application%20Packet%20Instructions.pdf?ver=2021-04-02-094718-623'),
        'ccd_directory':source(RAW/(DIRECTORY+'.zip'),'https://nces.ed.gov/ccd/Data/zip/'+DIRECTORY+'.zip'),
        'ccd_membership':source(RAW/(MEMBERSHIP+'.zip'),'https://nces.ed.gov/ccd/Data/zip/'+MEMBERSHIP+'.zip')}
    audit = dict(approved_point_only=True,restricted_income_population=True,
        native_nutrition_rows=len(nutrition),native_october_claim_rows=len(claims),
        program_year_crosscheck=dict(numeric_non_cep_rows=crosschecked,mismatches=0,claim_period='2024-10-01T00:00:00'),
        native_population='EDC3.1 school AllStudents Regular MAST G38 math/ELA; G38 is the SEA-native grades3–8 total according to EDC codebook. No local grade aggregation.',
        assessment_provenance='EDC3.1 technical documentation AppendixB cites OPI GEMS student achievement dashboard and OPI data requests. G38 provenance follows the EDC codebook; no independent2025 school-total recapture is claimed. Retain exact ProficientOrAbove_percent only, never reconstruct a range or masked value.',
        denominator='EDC tested/level counts and participation cells are retained only as raw audit values. Valid-score business rules are not independently approved. All model tested counts and sampling intervals are null.',
        income=INCOME_DEFINITION,
        identity='Require exact native sponsor-school strings equal the CCD MT-district-school namespace, full GEMS NCES ID equal CCD and EDC, and claim five-digitNCES suffix equal GEMS. Native high-school CNP sponsors sometimes differ from CCD separate high-school LEAs: no repair or name crosswalk.',
        grades='Only unadjusted same-year CCD pure grade schools with reconciled grade membership; no mixed/high/unknown configurations.',
        standards='MAST is new in2024–25; EDC flags new assessment and new Math/ELA cut scores. The current snapshot does not extend SBAC history or include alternate standards.',
        excluded=dict(Counter(r['reason'] for r in excluded)))
    payload=dict(dataset='mt-mast-nslp',year=2025,academic_year='2024–25',state=dict(id='MT',name='Montana'),
        name='Montana 2025 MAST and individual non-CEP NSLP eligibility',region='montana',
        prepare_script='scripts/prepare_montana.py',source_url=ASSESSMENT_URL,retrieved=date.today().isoformat(),
        model_scope='Montana public pure grade schools in regular non-CEP NSLP with exact same-year native school identities; native MAST G38 totals',
        income_definition=dict(label='Individual NSLP eligible · non-CEP',definition=INCOME_DEFINITION,url=NUTRITION_URL),
        sources=sources,source_audit=audit,schools=schools,excluded=excluded,
        cohorts=[dict(id='grade',level='ES',grades='3–8',assessment='Montana MAST · native G38 · 2025',
            standard='MAST 2025 Levels 3–4; refreshed regular assessment and cut scores',source='edc_2025',
            source_url=ASSESSMENT_URL,label='Grade schools · MAST',outcome='Proficient or advanced',
            note='Non-CEP individual NSLP eligibility · native G38 · point-only',allow_point_only=True)],
        coverage_note=f'{len(schools)} public grade-school profiles in the regular non-CEP NSLP cohort. CEP, nonregular programs, mixed/high schools and ambiguous IDs are excluded. Native suppression limits subject coverage. First-year MAST; no sampling intervals or history.',
        methodology=dict(summary='Native MAST grade totals and same-year individual NSLP eligibility in a restricted non-CEP public-school cohort.',
            details=[INCOME_DEFINITION,audit['native_population'],audit['assessment_provenance'],audit['denominator'],audit['identity'],audit['grades'],audit['standards'],
                'Combined is the equal Math/ELA mean. Separate externally studentized regressions describe associations, not causal school effectiveness. Exclusion of CEP schools limits representativeness.'],
            sources=[dict(label='EDC3.1 Montana source',url=ASSESSMENT_URL),dict(label='OPI native assessment dashboards',url='https://gems.opi.mt.gov/student-data'),
                dict(label='OPI GEMS ProgramYear2025 nutrition report',url=NUTRITION_URL),dict(label='Official OPI dated school claims',url=CLAIMS_URL),
                dict(label='Official OPI claim-field definitions',url=CLAIM_FIELDS_URL),dict(label='EDC3.1 codebook',url='https://www.eddatacenter.org/data_codebooks/EDC_codebook_v3.1.xlsx')]))
    validate(payload)
    EXTRACT.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n')
    return payload


def validate(payload):
    if payload['year']!=2025 or payload['academic_year']!='2024–25' or payload['state']['id']!='MT':
        raise ValueError('Wrong-year/state Montana snapshot')
    if len(payload['cohorts'])!=1 or payload['cohorts'][0]['id']!='grade' or payload['cohorts'][0]['level']!='ES' or not payload['cohorts'][0]['allow_point_only']:
        raise ValueError('Expected restricted point-only grade-school cohort')
    for school in payload['schools']:
        profile,raw=school['directory_raw'],school['income_raw']
        gems,claim=raw['gems'],raw['october_claim']
        if (school['id']!=native_key(gems['District_Entity_Number1'],gems['School_Entity_Number']) or
                profile['ST_SCHID']!='MT-'+school['id'] or profile['NCESSCH']!=gems['NCES_Code'] or
                profile['SCHOOL_YEAR']!='2024-2025' or profile['ST']!='MT' or
                profile['UPDATED_STATUS'] not in ['1','3','4','5','8'] or
                not grade_school(profile,school['membership_grades_raw'],school['membership_raw'])):
            raise ValueError('School identity/year/grade scope is invalid')
        if (school['income']!=native_income(raw) or school['income'] is None or school['low_income'] is not None or
                school['enrollment']!=reported_count(school['membership_raw']) or not school['enrollment']):
            raise ValueError('Economic values are not individual native NSLP eligibility')
        if (school['membership_raw']['NCESSCH']!=profile['NCESSCH'] or school['membership_raw']['ST_SCHID']!=profile['ST_SCHID'] or
                set(school['outcomes'])!={'math','reading'}):
            raise ValueError('Membership identity or native subject pair is invalid')
        for subject,outcome in school['outcomes'].items():
            row=outcome['raw']
            if (native_key(row['StateAssignedDistID'],row['StateAssignedSchID'])!=school['id'] or
                    row['NCESSchoolID']!=profile['NCESSCH'] or outcome['tested'] is not None or
                    outcome['proficiency']!=native_outcome(row,outcome['source_row'],subject)['proficiency']):
                raise ValueError('Outcome is not the exact point-only native G38 rate')


def prepare(database=DEFAULT_DB):
    payload=json.loads(EXTRACT.read_text())
    validate(payload)
    return prepare_snapshot(payload,EXTRACT,OUTPUT,database)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract',action='store_true')
    parser.add_argument('--database',default=DEFAULT_DB)
    args=parser.parse_args()
    if args.extract: extract()
    print(json.dumps(prepare(args.database),indent=2))
