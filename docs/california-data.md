# California data guide

The California comparison is a 2024–25 statewide snapshot of CAASPP Smarter Balanced Standard Met or Exceeded results in ELA and mathematics. It uses official all-students school records and matching Census Day K–12 FRPM eligibility. Grades 3–8 and grade 11 have separate annual models; California Alternate Assessments are outside this source.

## Official sources

- [2025 CAASPP Smarter Balanced research files](https://caaspp-elpac.ets.org/caaspp/ResearchFileListSB?lstCounty=00&lstDistrict=00000&lstTestType=B&lstTestYear=2025&ps=true): the statewide All Students ZIP includes the results file and annual entity list. The source suppresses results for groups with fewer than 11 students. School Type IDs 7, 9 and 10 include public schools and direct or locally funded charters. State, county and district summaries are excluded.
- [2025 research-file layout](https://caaspp-elpac.ets.org/caaspp/docs/2025_SBAC_Research%20File%20Layout.xlsx): Test ID 1 is ELA and 2 is mathematics; Student Group ID 1 is All Students. Grade 13 combines grades 3–8 **and 11** and is never used to substitute for suppressed grades.
- [Official 2024–25 FRPM workbook](https://www.cde.ca.gov/Ds/ad/documents/frpm2425.xlsx), including its field-definition sheet, and [CDE FRPM information](https://www.cde.ca.gov/ds/ad/filesspfrpm.asp): Census Day enrollment and eligibility describe 2024–25. The school identifier is the exact concatenation of two county digits, five district digits and seven school digits. Leading zeros are preserved.

Raw download URLs, SHA-256 checksums, worksheet or research-file row numbers and original fields are retained in [the compact extract](../data/source/california.json). Raw files are ignored under `data/raw/california/`.

## Aggregation and eligibility

The research-file layout defines **Overall Total** as the number with a score in any performance level and **Count Standard Met and Above** as the proficient numerator. These exact integer counts are summed over the applicable grades. Overall Total must equal Total Students Tested with Scores; the published grade percentage must agree with the count ratio within its two-decimal rounding tolerance. Total Students Tested and enrollment are retained for audit but never used as valid-score denominators.

Grades 3–8 aggregation requires every grade in the intersection of the same-year FRPM school grade span and grades 3–8. Grade 11 uses its separate row. Any absent grade, suppressed numerator, denominator or rate makes that subject unavailable. School totals cannot recover suppressed components. This conservative rule may exclude schools with irregular grade offerings. Combined is the equally weighted mean of the eligible math and ELA rates, fitted as its own model.

Schools serving any high-school grades are listed only under high schools. A mixed-grade school's eligible grades 3–8 results can still enter the separate statewide grades 3–8 assessment model, while its grade-11 results enter the high-school model. No aggregate mixes grade 11 with younger grades. Whole-school income and assessed-grade populations differ, and grade composition remains a limitation.

Income uses the published K–12 FRPM eligibility fraction, reconciled to its K–12 numerator and enrollment. Eligibility includes household applications, alternate income forms, direct certification and categorical eligibility. It measures eligibility rather than receipt of meals offered universally. The LCFF Unduplicated Pupil Count and its broader time window are not used. Missing or suppressed values remain unavailable.

The directory contains 9,863 schools. Combined models contain 7,090 grades 3–8 assessment cohorts and 2,157 grade-11 cohorts. Every eligible member has a verified valid-score denominator, supporting the existing conditional sampling intervals. All models use externally studentized residuals and same-year income. [The coverage audit](../data/california/audit.json) records exclusions. This release has one year, no verified admissions classifications and no school coordinates; schools remain searchable with chart and table alternatives.

## Rebuild

Download the three official files explicitly:

```sh
mkdir -p data/raw/california
curl -L --fail 'https://caaspp-elpac.ets.org/caaspp/researchfiles/sb_ca2025_1_csv_v1.zip' -o data/raw/california/sb_ca2025_1_csv_v1.zip
curl -L --fail 'https://www.cde.ca.gov/Ds/ad/documents/frpm2425.xlsx' -o data/raw/california/frpm2425.xlsx
curl -L --fail 'https://caaspp-elpac.ets.org/caaspp/docs/2025_SBAC_Research%20File%20Layout.xlsx' -o data/raw/california/2025_SBAC_Research_File_Layout.xlsx
.venv/bin/python scripts/prepare_california.py --extract
```

Offline rebuilds use `.venv/bin/python scripts/prepare_california.py`. Imports replace only the California dataset transactionally and can be repeated. The existing canonical database must already have its schema; rebuilding a Chicago-only database first would remove other states. Run `.venv/bin/python scripts/export_catalog.py` after preparing all required datasets, then `.venv/bin/python -m unittest discover -s tests -p 'test_california.py' -v`.
