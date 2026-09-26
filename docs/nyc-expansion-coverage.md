# Charter and admissions source audit

Retrieved September 26, 2026, on `codex/nyc-public-schools`. The data are gathered and validated, **not yet substituted into the website's NYCPS models**. The reproducible inputs are in `data/source/nyc-expansion.json`; `data/nyc/expansion-coverage.json` reports coverage and exclusions. Existing site rankings are unchanged.

## Charter assessment and income data

The official [NYSED downloads](https://data.nysed.gov/downloads.php) supply the 2025 Report Card Database (Group 4, revised July 30, 2026) and 2025 Enrollment Database (December 17, 2025). The assessment release contains 2024 and 2025 results; enrollment contains 2023–2025. `YEAR` is the school year's ending year. School-level records are selected through `Institution Grouping`, group 6, and NYC borough BEDS prefixes 31–35, excluding district and city aggregates. The extract retains district schools too, so a future NYC model can use one consistent source for its entire population.

Join assessments, demographics and enrollment on **BEDS code and ending year**. Economic disadvantage is `PER_ECDIS`, with `NUM_ECDIS` and `K12` retained for validation. This is NYSED's economic-assistance definition, distinct from NYCPS Poverty and from Economic Need Index. The [2024–25 SIRS manual](https://www.nysed.gov/sites/default/files/programs/information-reporting-services/sirs-manual-2024-2025.pdf) defines the measure. Do not mix these economic measures within a regression or silently splice their histories.

The [September 2, 2025 charter directory](https://www.nysed.gov/sites/default/files/programs/charter-schools/nys-charter-school-directory-as-of-09-02-2025.xlsx) identifies 299 NYC charter entities, including approved/new schools. Of these, 280 match institutions in the assessment release. This dated roster is not a complete list of historical or closed charters. Unmatched IDs remain in the audit; no identity is inferred from names.

| Charter outcome, 2025 | Source records | Numeric outcome + same-year income + ≥10 valid scores |
| --- | ---: | ---: |
| ELA grades 3–8 | 242 | 236 |
| NYSED mathematics grades 3–8 | 242 | 222 |
| Regents Algebra I | 168 | 162 |
| Regents Common Core ELA | 102 | 100 |

These are outcome coverage counts, **not counts of high schools eligible for a final ranking**. Regents exam takers include middle-school students. Same-year grade enrollment must determine the intended high-school population before fitting. A school may appear in several outcome rows.

ReadMe-confirmed denominators are `NUM_TESTED` for elementary/middle results and `TESTED` for Regents: students with valid scores. Never substitute `TOTAL_COUNT`, participation or accountability denominator fields. Published percentages are rounded to whole points; the audit checks unsuppressed numerator/denominator pairs within half a percentage point. Suppressed or blank percentages remain missing even when other fields could reconstruct them. Economic student groups below five, or equal to the whole K–12 enrollment, can be suppressed.

Two outcome decisions remain before publication:

- **NYSED `MATH3_8` includes Regents mathematics results**, including Level 5. It differs from the NYCPS NYSTP-only math series. Use an explicitly identified NYSED model population, or validate a separate aggregation of NYSTP-only grade counts with suppression preserved. Do not relabel it as the existing NYSTP outcome.
- **2024 contains both Common Core Algebra I and the newer Algebra I exam.** Keep them separate; exam takers may overlap. Do not sum counts or average the two rates to manufacture one school result. The extract preserves both exam identities.

## Identity coverage

The current [LCGMS public download](https://www.nycenet.edu/PublicApps/LCGMS.aspx) contains 1,901 valid DBN records, including 288 managed by charters. It provides an authoritative BEDS-to-DBN mapping for 268 of the 299 state-directory charters, without ambiguous BEDS mappings in this snapshot. Missing mappings are listed explicitly. Preserve both IDs and the crosswalk's retrieval date; a current organization file alone does not establish historical identity after reorganizations or mergers. Do not synthesize a DBN from a BEDS code.

## Admissions coverage

The latest official bulk high-school directory found in NYC Open Data is the [2021 DOE High School Directory](https://data.cityofnewyork.us/d/8b6c-7uty). Its 442 schools contain **882 programs**, and 435 school DBNs match the website's existing NYC directory. The extract keeps each program's code, method and priorities separately. Methods include screened, audition, test, open, educational option, language, zoned and specialized service programs. One school may have multiple methods; these must not become a single mutually exclusive school classification.

**2021 is historical coverage, not current coverage.** Metadata update dates do not change its admissions year. The live MySchools directory returned server errors to downloads during this audit, and the available web-rendered pages did not expose current program records. Elementary/middle program-level admissions and current high-school methods remain uncollected. Do not enable current filters using this old directory or assume every unmatched school is neighborhood/open admission.

The current [NYCPS charter enrollment guidance](https://www.schools.nyc.gov/enrollment/enroll-in-charter-schools/how-to-enroll-in-charter-schools) does establish a general charter framework: open enrollment and random selection when oversubscribed, with enrollment preferences. That supports a charter-level framework label, **not a claim that every applicant has equal priority**. School-specific preferences, eligible grades and deadlines are not collected.

## Rebuild

No downloads happen implicitly. Exact URLs and filenames are in `scripts/gather_nyc_coverage.py` (`SOURCES` and `DIRECTORY_SOURCES`); preserve files under ignored `data/raw/`. Archives and directory downloads have SHA-256 provenance in the extract. Download LCGMS with its public “Downloadable School Data in Excel Format” action; its `.xls` is actually UTF-16 HTML with omitted closing row tags, handled explicitly by the parser. Install `mdbtools` only for raw Access extraction.

```sh
# Regenerate the audit from committed data; no network or MDB dependency:
.venv/bin/python scripts/gather_nyc_coverage.py

# Re-extract all downloaded source data (several minutes):
.venv/bin/python scripts/gather_nyc_coverage.py --extract

# Refresh the downloaded current directories without rescanning Access files:
.venv/bin/python scripts/gather_nyc_coverage.py --directories
```

The gathering script does not alter the canonical model tables or dataset catalog. Publishing charter comparisons next requires a deliberate NYSED outcome/model adapter, not merely adding rows to the existing NYCPS model. Keep the latest NYCPS-only 2026 data distinguishable from the charter-inclusive 2025 source; do not replace its year invisibly.
