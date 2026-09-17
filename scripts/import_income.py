"""Extract school income counts from official CPS annual demographic workbooks.

Usage: python scripts/import_income.py /path/to/manifest.json
Manifest entries contain year (school-year ending year), file and official url.
"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
import openpyxl
import xlrd

ROOT = Path(__file__).resolve().parents[1]

def convert(manifest_path):
    output, sources, seen = [], [], set()
    for source in sorted(json.loads(Path(manifest_path).read_text()), key=lambda s: s['year']):
        path = Path(source['file'])
        if path.suffix == '.xls':
            book = xlrd.open_workbook(path)
            sheet = book.sheet_by_name('Schools' if 'Schools' in book.sheet_names() else 'All Schools')
            rows = [sheet.row_values(i) for i in range(sheet.nrows)]
        else:
            book = openpyxl.load_workbook(path, read_only=True, data_only=True)
            rows = list(book['Schools'].values)
        header_index = next(i for i, row in enumerate(rows) if 'School ID' in row)
        header = rows[header_index]
        id_col, name_col, total_col = [header.index(s) for s in ('School ID', 'School Name', 'Total')]
        group = rows[header_index-1]
        income_col = next(i for i, cell in enumerate(group)
                          if 'Economically Disadvantaged' in str(cell) or 'Free/Reduced' in str(cell))
        label = ' '.join(str(group[income_col]).split())
        count = 0
        for row in rows[header_index+1:]:
            school_id = str(row[id_col]).removesuffix('.0')
            if not re.fullmatch(r'\d{6}', school_id):
                continue
            key = (school_id, source['year'])
            if key in seen:
                raise ValueError(f'Duplicate school/year: {key}')
            seen.add(key)
            total, low = row[total_col], row[income_col]
            # Keep suppression/blank tokens intact; eligibility is decided during modeling.
            output.append([school_id, source['year'], row[name_col], total, low, label])
            count += 1
        sources.append(dict(year=source['year'], school_year=f"{source['year']-1}-{source['year']}",
                            url=source['url'], sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            sheet=sheet.name if path.suffix == '.xls' else 'Schools',
                            income_label=label, schools=count))
    with (ROOT/'data/source/income-history.csv').open('w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(['school_id', 'year', 'name', 'enrollment', 'low_income', 'income_label'])
        writer.writerows(output)
    (ROOT/'data/source/income-sources.json').write_text(json.dumps(sources, indent=2)+'\n')
    print(json.dumps({s['year']: s['schools'] for s in sources}))

if __name__ == '__main__':
    convert(sys.argv[1])
