# Wisconsin data (WISEdash)

This adapter adds Wisconsin → Statewide, with independent DPI models. It does not pool Wisconsin with Illinois or New York.

## Sources

All inputs are public aggregate files from the Wisconsin Department of Public Instruction (DPI), retrieved from the [WISEdash data files by topic](https://dpi.wi.gov/wisedash/public/download-files) page and the [DPI GIS open data portal](https://data-wi-dpi.opendata.arcgis.com/).

| Purpose | File family | Years | Location |
| --- | --- | --- | --- |
| Grade-school results | `forward_certified_*.zip` | 2015-16 – 2024-25 (no 2019-20) | `/sites/default/files/wise/downloads/` (older years `/sites/default/files/imce/zip/`) |
| High-school results | `act_statewide_certified_*.zip` | 2014-15 – 2024-25 | as above |
| Same-year income | `enrollment_certified_*.zip` | 2014-15 – 2024-25 | as above |
| Directory and coordinates | Public Schools, Wisconsin (GIS item `d383fe81275e46f2a5a5c4f1a0c2eb85`, layer 20) | current 2026-27 | `data/raw/wi-public-schools.csv` |
| State outline | US Census cartographic boundary `cb_2024_us_state_500k` (shoreline-clipped) | 2024 vintage | `data/raw/cb_2024_us_state_500k.zip` |

The download page mixes two URL prefixes by vintage; the exact URL per year is recorded in `scripts/prepare_wisconsin.py` and in `data/source/wisconsin.json`. Raw archives stay in the ignored `data/raw/`. The committed extract records each source's SHA-256. The state outline uses the Census cartographic boundary rather than the TIGERweb jurisdictional State layer: TIGERweb extends Wisconsin into Lake Michigan, which draws a wide school-less band over the lake and hides the Door County coastline. The cartographic boundary is clipped to the shoreline and keeps Washington Island and the other offshore islands.

`enrollment_certified` is the third-Friday-of-September snapshot. The 2024-25 file is the most recent in this release. The DPI directory layer is labeled 2026-27 and was current September 4, 2026; locations can therefore be newer than the assessment snapshot, and schools that closed before 2026-27 may be absent from the directory even when they remain in earlier models.

## Identifier

`school_id` is DPI's unique join code: `S` plus the four-digit district code plus the four-digit school code (for example `S00070020`). Assessment, enrollment and GIS files all expose the district and school code pair; the S-code is computed from it and cross-checked against the GIS layer's `DPI Unique Join Code`. No name matching is used. Districtwide (`[Districtwide]`) and statewide (`0000`) rows are excluded.

## Measures

**Grade schools.** The Forward Exam is administered in English language arts and mathematics in grades 3–8. The model outcome is the share of **students with valid scores** who reached the top two performance levels on the general Forward assessment, aggregated across the school's enrolled grades 3–8 using exact student counts. This differs from DPI's published dashboard percentage, which uses enrolled (FAY) students as the denominator and includes non-testers; the tested-only definition matches the site's tested-count rule. DLM (the alternate assessment, roughly 1% of students) is excluded and its records are counted in the exclusion audit.

**High schools.** The ACT Statewide file covers the state-mandated grade 11 administration. The model outcome is the share of ACT ELA and ACT Mathematics examinees reaching the top two performance levels. DLM grade-11 records are excluded. ACT exam takers are not a fixed graduating cohort and the ELA score's construction changed in 2016-17; these limitations are documented rather than corrected.

**Assessment standards changed in 2023-24.** Before 2023-24 the performance levels were Advanced / Proficient / Basic / Below Basic (proficiency = Advanced + Proficient). From 2023-24 DPI uses Advanced / Meeting / Approaching / Developing (proficiency = Advanced + Meeting). DPI's own Forward trends for ELA and mathematics begin with 2023-24. The two eras are separate assessment identities; history lines break at the change. The ACT levels changed in the same year, so both levels use parallel pairs:

- `Forward (pre-2023-24 levels)` – 2015-16 through 2022-23
- `Forward (2023-24 levels)` – 2023-24 through 2024-25
- `ACT (pre-2023-24 levels)` – 2014-15 through 2022-23
- `ACT (2023-24 levels)` – 2023-24 through 2024-25

**Income.** Each annual model joins the same school year's `enrollment_certified` file. The measure is DPI **Economically Disadvantaged** status: direct certification, National School Lunch Program free/reduced-price eligibility (at or below 185% of the federal poverty guidelines), or an alternate household income form. It is computed as the published Econ Disadv count over the same file's All Students count. DPI evaluates status for every student each year, including Community Eligibility Provision schools, and reports it independently of food-service eligibility. Values suppressed as `[Data Suppressed]` (or a `*` count) remain unavailable; no midpoint, residual or later-year value is imputed.

**Same-year ACT alignment.** The ACT Statewide layout labels `SCHOOL_YEAR` as "school year of expected graduation", but the files are actually labeled by **test administration school year**. Evidence: the 2014-15 file matches ACT Graduates 2015-16 (same students, school-level L1 difference 0.04) rather than ACT Graduates 2014-15 (0.32); the 2019-20 file matches ACT Graduates 2020-21 better than ACT Graduates 2019-20; and DPI's own [ACT about-data](https://dpi.wi.gov/wisedash/public/about-data/act) pairs "2014-15 statewide administration results" with the "2015-16 graduating class". The same-year enrollment file is therefore the correct income join. The 2019-20 Forward file is absent because the spring 2020 Forward administration was waived; ACT Statewide 2019-20 records exist and use 2019-20 enrollment.

## Validation gates

The extractor applies these checks before anything reaches SQLite, and the committed extract retains the underlying counts so they can be repeated:

- Forward rows: no duplicate `school × year × subject × grade × result × test group` keys; the sum of all result counts equals the file's `GROUP_COUNT` in every year and subject.
- ACT rows: no duplicate `school × year × subject × result × college readiness` keys; result counts sum to `GROUP_COUNT`.
- Forward model members must have a complete, non-redacted result set for **every** enrolled grade 3–8 in that subject and year. A redacted or missing grade excludes the school-year-subject instead of silently dropping it; the exclusion reason is published in `data/wisconsin/history.json`.
- Models use the site's existing minimum of ten tested students, at least four schools, and varying income. Sampling intervals use the same Jeffreys-smoothed formulas as the rest of the site.
- Redaction in these files is all-or-nothing per `school × grade × subject` (or `school × subject` for ACT): a redacted record carries `*` in the result, count and group-count fields. Partial numeric groups were not observed.

## Coverage and limitations

Current release (retrieved September 26, 2026). The directory contains 2,374 schools with at least one assessment record; 1,981 have DPI coordinates, and the rest remain list-only. The 2024-25 models contain 1,091 grade-school math, 1,015 grade-school ELA, 935 grade-school combined, 402 high-school math, 410 high-school ELA and 375 high-school combined schools. The published history has 60 annual models (nine Forward years and eleven ACT years, each with three subjects).

The dominant exclusion is DPI grade-level redaction: 12,428 of 29,776 Forward school-year-subject records have at least one redacted grade and are omitted by the complete-grade rule, with a further 420/168 records where the Forward grade set and the enrollment grade snapshot disagree. The history file reports the reason for every excluded school-year-subject. Small-school coverage is therefore lower than DPI's dashboard coverage, which accepts enrolled-denominator school rates.

- School-level assessment records are **FAY** (full academic year) students. The income snapshot is all enrolled students on the third Friday of September. The two populations differ.
- DPI redacts small groups (and occasionally larger groups to prevent indirect disclosure). Because a complete grade set is required, small schools and schools with redacted grades are excluded from the official tested-only models; the history file records each exclusion.
- DLM students are excluded, as are students without valid scores.
- The directory vintage (2026-27) is newer than the assessment snapshot (2024-25); locations are not a historical record.
- No admissions/program classification is available, so every school is `Unclassified`. Charter status exists in the DPI directory and is retained in the profile but is not published as a program filter in this release.
- Cross-state proficiency and residual values are not a common scale.

## Rebuild

Place the raw files from the table above under `data/raw/` with their published filenames (plus `wi-public-schools.csv` and `cb_2024_us_state_500k.zip`), then:

```sh
.venv/bin/python scripts/prepare_wisconsin.py --extract
.venv/bin/python scripts/export_catalog.py
```

`--extract` reads the raw archives and rewrites `data/source/wisconsin.json` and `data/wisconsin/boundary.geojson`. Without `--extract`, `prepare_wisconsin.py` rebuilds SQLite and the website JSON from the committed extract alone. The importer deletes and reinserts only the `wi-dpi` dataset, so Illinois and NYC records are preserved. Run it twice and compare output hashes to confirm repeatability.
