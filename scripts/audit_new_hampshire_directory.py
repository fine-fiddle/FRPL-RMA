"""Retain and validate NH 2024–25 income/directory IDs; never import assessment data."""
import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/source/new-hampshire-directory-crosswalk.json'
INCOME = ROOT / 'data/raw/new-hampshire/income.xlsx'
DIRECTORY = ROOT / 'data/raw/ccd_sch_029_2425_w_1a_073025.zip'
GRADES = ('PK', 'KG', '1', '2', '3', '4', '5', '6', '7', '8',
          '9', '10', '11', '12', '13', 'UG', 'AE')
HEADERS = ['SAU #', 'SAU Name', 'District #', 'District Name', 'School #',
           'School Name', 'Enroll (1)', 'Free and Reduced\nEligible (1)', '% Eligible']
SOURCES = {
    'income': {
        'url': 'https://my.doe.nh.gov/iPlatform/Report/Report?categoryId=18&categoryName=Free+and+Reduced+School+Lunch+Eligibility&name=Free+Reduced+K-12+School+Lunch+Eligibility+Rates+by+School&path=%2FBDMQ%2FiPlatform+Reports%2FDemographic+Data%2FFree+and+Reduced+School+Lunch+Eligibility%2FFree+Reduced+K-12+School+Lunch+Eligibility+Rates+by+School',
        'sha256': '90161004ef11e1a486301e1b2de183b2085827f2bc485d4f5eefa45e30c68296',
    },
    'directory': {
        'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip',
        'sha256': '39326da788aa322353d20ceaf8ad4baed26272502cd05b066cf6c594988b21ab',
        'member': 'ccd_sch_029_2425_w_1a_073025.csv',
    },
}


def native_integer(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Native income identity must be an exact positive integer')
    if int(value) != value or value <= 0:
        raise ValueError('Native income identity must be an exact positive integer')
    return int(value)


def directory_identity(raw):
    match = re.fullmatch(r'NH-(\d+)-(\d+)', raw.get('ST_SCHID', ''))
    if (raw.get('ST') != 'NH' or raw.get('SCHOOL_YEAR') != '2024-2025'
            or not match or raw.get('ST_LEAID') != 'NH-' + match[1]):
        raise ValueError('Directory must publish matching NH school/district IDs in 2024–25')
    return int(match[1]), int(match[2])


def directory_scope(raw):
    """Classify reported offered grades, independently of tested/enrolled population."""
    if raw.get('SY_STATUS') not in {'1', '3', '4', '5', '8'}:
        return 'nonoperational'
    if (raw.get('NOGRADES') != 'No' or raw.get('IGOFFERED') != 'As reported'
            or any(raw.get('G_' + grade + '_OFFERED') not in {'Yes', 'No'} for grade in GRADES)):
        return 'uncertain_grade_reporting'
    if any(raw['G_' + grade + '_OFFERED'] == 'Yes' for grade in ('13', 'UG', 'AE')):
        return 'other_grade_population'
    elementary = any(raw['G_' + grade + '_OFFERED'] == 'Yes' for grade in GRADES[1:10])
    high = any(raw['G_' + grade + '_OFFERED'] == 'Yes' for grade in ('9', '10', '11', '12'))
    if elementary and high:
        return 'mixed'
    return 'grade_school' if elementary else 'high_school' if high else 'preschool_only'


def derive(document):
    if (document.get('schema_version') != 1 or document.get('state') != 'NH'
            or document.get('year') != 2025 or document.get('academic_year') != '2024-25'
            or document.get('status') != 'assessment_identity_pending'
            or document.get('approved_for_modeling') is not False
            or document.get('sources') != SOURCES or document.get('income_headers') != HEADERS):
        raise ValueError('Crosswalk audit contract changed; no modeling approval exists')
    by_identity = defaultdict(list)
    directory_records = document['directory_records']
    income_records = document['income_records']
    if len({r['source_record'] for r in directory_records}) != len(directory_records):
        raise ValueError('Duplicate directory source records')
    if len({r['source_row'] for r in income_records}) != len(income_records):
        raise ValueError('Duplicate income source records')
    for record in directory_records:
        by_identity[directory_identity(record['raw'])].append(record)
    matches, missing = [], []
    seen_income = set()
    for record in income_records:
        raw = record['raw']
        district, school = native_integer(raw['District #']), native_integer(raw['School #'])
        key = district, school
        if key in seen_income:
            raise ValueError('Duplicate native district/school pair in income')
        seen_income.add(key)
        candidates = by_identity.get(key, [])
        if len(candidates) > 1:
            raise ValueError('Ambiguous native district/school pair in directory')
        if not candidates:
            missing.append({'income_row': record['source_row'], 'district_id': district,
                            'school_id': school, 'reason': 'native_pair_absent_from_NH_CCD_directory'})
            continue
        candidate = candidates[0]
        matches.append({'income_row': record['source_row'],
                        'directory_record': candidate['source_record'],
                        'district_id': district, 'school_id': school,
                        'ncessch': candidate['raw']['NCESSCH'],
                        'offered_grade_scope': directory_scope(candidate['raw'])})
    linked_records = {r['directory_record'] for r in matches}
    unlinked = [r['source_record'] for r in directory_records if r['source_record'] not in linked_records]
    coverage = {'income_schools': len(income_records), 'NH_directory_records': len(directory_records),
                'exact_native_id_matches': len(matches), 'income_unmatched': len(missing),
                'directory_unmatched': len(unlinked),
                'matched_offered_grade_scope': dict(sorted(Counter(r['offered_grade_scope'] for r in matches).items()))}
    return {'matches': matches, 'unmatched_income': missing,
            'unmatched_directory_records': unlinked, 'coverage': coverage}


def validate(document):
    expected = derive(document)
    if any(document.get(key) != value for key, value in expected.items()):
        raise ValueError('Crosswalk links/coverage must exactly replay the native IDs and reported grades')
    return expected['coverage']


def extract(income=INCOME, directory=DIRECTORY, output=OUTPUT):
    for name, path in [('income', income), ('directory', directory)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCES[name]['sha256']:
            raise ValueError(f'{name} source changed; perform a fresh source audit')
    workbook = openpyxl.load_workbook(income, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    rows = list(sheet.values)
    if list(rows[9]) != HEADERS or rows[6][0] != '2024 - 2025 Free Reduced School Lunch Eligibility Rates by School (K-12)':
        raise ValueError('Native income report year/headers changed')
    records, other = [], []
    for number, row in enumerate(rows, 1):
        if len(row) > 5 and isinstance(row[4], (int, float)) and isinstance(row[2], (int, float)):
            records.append({'source_row': number, 'raw': dict(zip(HEADERS, row))})
        else:
            other.append({'source_row': number, 'raw': list(row)})
    with zipfile.ZipFile(directory) as archive:
        reader = csv.DictReader(io.TextIOWrapper(archive.open(SOURCES['directory']['member']), encoding='utf-8-sig'))
        directory_records = [{'source_record': number, 'raw': row}
                             for number, row in enumerate(reader, 2) if row['ST'] == 'NH']
    result = {'schema_version': 1, 'state': 'NH', 'year': 2025, 'academic_year': '2024-25',
              'status': 'assessment_identity_pending', 'approved_for_modeling': False,
              'sources': SOURCES, 'income_headers': HEADERS,
              'income_records': records, 'income_other_records': other,
              'directory_records': directory_records}
    result.update(derive(result))
    validate(result)
    output.write_text(json.dumps(result, separators=(',', ':'), ensure_ascii=False) + '\n')
    return result['coverage']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--income', type=Path, default=INCOME)
    parser.add_argument('--directory', type=Path, default=DIRECTORY)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    coverage = extract(args.income, args.directory, args.output) if args.extract else validate(json.loads(args.output.read_text()))
    print(json.dumps(coverage, sort_keys=True))
