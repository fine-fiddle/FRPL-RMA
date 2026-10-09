# Colorado data guide

Colorado is a 2024–25 snapshot with separate statewide CMAS grades 3–8 and digital SAT grade 11 models, matched to the same-year Student October Count K–12 FRL eligibility file. Results describe assessment cohorts and their association with reported economic disadvantage.

## Official sources

- [CDE 2025 CMAS results](https://ed.cde.state.co.us/assessment/cmas-dataandresults-2025), including the Math/ELA/CSLA district and school summary workbook. The source identifies its standards as the **2020 Colorado Academic Standards**. Only school-level English ELA and mathematics **All Grades** rows are used. Spanish Language Arts (CSLA) and CoAlt are separate assessments and are excluded.
- [CDE PSAT/SAT results](https://ed.cde.state.co.us/assessment/sat-psat/sat-psat-data), using the 2025 district and school summary workbook's **SAT Grade 11** rows in Reading and Writing and mathematics. PSAT grades 9 and 10, PSAT/SAT All Grades rows and mean scores are excluded. The outcome is the source's **Met or Exceeded Expectations** category. The workbook warns against direct comparisons with the paper tests used before 2024; this release includes one year.
- [CDE 2024–25 pupil membership archive](https://ed.cde.state.co.us/cdereval/pupilmembership-statistics/data-insights-resources-archives), using its K–12 FRL eligibility by school and grade-level membership workbooks. IDs join the exact four-digit organization code and four-digit school code; leading zeros are preserved. The detention aggregate `99999999` is not a school.
- [CDE eligibility guidance](https://ed.cde.state.co.us/nutrition/manage-program-operations/determine-program-eligibility): Healthy School Meals for All provides no-cost meals irrespective of eligibility. Student October eligibility still relies on documented household income or categorical/direct certification criteria. No universal meal receipt or LCFF/other state's economic measure is substituted.

Download URLs, SHA-256 checksums, source worksheet rows and original fields are retained in [the compact source extract](../data/source/colorado.json). The two official assessment file layouts are recorded as additional provenance. The CMAS layout explicitly excludes students without scores from proficiency denominators; the public workbooks separately name **Number of Valid Scores** and **Number of Total Records**.

## Calculation and exclusions

We divide the directly published number meeting or exceeding expectations by the directly published valid-score count. The ratio must reconcile to the source's one-decimal percentage within rounding tolerance. These school totals are published directly, so no grade percentages are averaged and no suppressed grade components are reconstructed. The source's total records, participation rate and no-score counts cannot replace valid-score denominators.

Suppression markers (`- -`, `*`, `N/A`) and bounded counts such as `< 16` remain unavailable. A zero proficient count paired with a published zero rate is valid. All eligible members have exact denominators, supporting the existing conditional sampling intervals. Combined is the equally weighted mean of math and ELA proficiency and has its own regression.

Income uses the source's published FRL eligibility fraction, preserving its three-decimal rounding, reconciled to K–12 FRL counts and enrollment. Suppressed eligibility is not inferred from other counts. Grades and income describe the same 2024–25 Student October collection; assessment results are spring 2025. No later-year income or name-based identity matching is used.

The directory includes 1,823 schools. Combined models contain 1,232 CMAS and 249 SAT assessment cohorts. Many SAT schools have suppressed proficiency or income; [the audit](../data/colorado/audit.json) reports exclusions. Any school with enrolled grades 9–12 is listed only under high schools, while its eligible CMAS results may still enter the independent grades 3–8 model. Schoolwide income and assessed-grade populations differ. Participation, representativeness and grade mix remain limitations. No verified admissions classifications or coordinates are included; the searchable list, charts and tables remain available.

## Rebuild

Download the six native files explicitly using the official links recorded in `scripts/prepare_colorado.py` and the source extract:

```sh
mkdir -p data/raw/colorado
curl -L --fail 'https://ed.cde.state.co.us/fs/resource-manager/view/5c130960-c90c-444a-98dc-41b35c11431b' -o data/raw/colorado/cmas2025.xlsx
curl -L --fail 'https://ed.cde.state.co.us/fs/resource-manager/view/37066be1-57a4-40f4-8235-3c1b10cb0e75' -o data/raw/colorado/sat2025.xlsx
curl -L --fail 'https://ed.cde.state.co.us/fs/resource-manager/view/edf7f72b-6728-4b48-a3aa-ae75ab2ad968' -o data/raw/colorado/frl2025.xlsx
curl -L --fail 'https://ed.cde.state.co.us/fs/resource-manager/view/7efacffc-8335-4735-9b12-fee840351810' -o data/raw/colorado/grades2025.xlsx
curl -L --fail 'https://ed.cde.state.co.us/fs/resource-manager/view/f6b76141-39d7-4787-b7e9-5a5777952cb7' -o data/raw/colorado/cmas2025-layout.pdf
curl -L --fail 'https://ed.cde.state.co.us/fs/resource-manager/view/7bd1ffa6-490b-44b9-9dee-933d32a9c0c7' -o data/raw/colorado/sat2025-layout.pdf
.venv/bin/python scripts/prepare_colorado.py --extract
```

Offline rebuilds use `.venv/bin/python scripts/prepare_colorado.py`. Only the Colorado dataset is replaced transactionally, preserving other states. Use an existing canonical database with its schema; rebuilding Chicago alone would remove other states. Export the full catalog after preparing all required states with `.venv/bin/python scripts/export_catalog.py`. Run `.venv/bin/python -m unittest discover -s tests -p 'test_colorado.py' -v`.
