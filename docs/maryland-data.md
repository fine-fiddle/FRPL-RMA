# Maryland 2024–25 snapshot

Maryland uses native regular MCAP school proficiency totals and same-year individual direct certification. The release covers grade schools, with separate Math, ELA and Combined models. Published rates support point estimates; every tested count and sampling interval is unavailable.

## Official sources and exact identities

The [MSDE download page](https://www.reportcard.msde.maryland.gov/Graphs/#/DataDownloads/datadownload/3/17/6/99/XXXX/2025), with **Download Files 2025** selected, provides four files:

- [MCAP ELA and Mathematics](https://www.reportcard.msde.maryland.gov/DataDownloads/FileDownload/562): regular administrative performance workbooks, using `School_Level`, `Year=2025`, `Student Group=All Students`, and the native subject `All Grades` total.
- [Special services](https://www.reportcard.msde.maryland.gov/DataDownloads/FileDownload/561): school individual economic-disadvantage count, percentage, and its own total-student denominator from Early Attendance.
- [Enrollment by grade](https://www.reportcard.msde.maryland.gov/DataDownloads/FileDownload/541): September enrollment, used only to verify historical grade scope.
- [School directory](https://www.reportcard.msde.maryland.gov/DataDownloads/FileDownload/539): native 2025 school identifiers, grade span and authoritative NCES crosswalk.

Keep native two-digit LEA and four-digit school codes, including leading zeros. Join every collection on both exact codes and the same year. The directory's native NCES number joins the [2024–25 CCD directory](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip) directly; do not infer a state-school-ID conversion or use school names. Native E/M/EM grade spans, unadjusted CCD offered grades, and September grade rows must all exclude high-school grades. Mixed, high, unknown or unmatched units remain excluded with raw evidence.

## Income collection and disclosure

[MSDE definitions](https://www.reportcard.msde.maryland.gov/Definitions/Index) identify economic disadvantage through individual direct certification: SNAP/FSP, TANF/TCA, foster care, Medicaid and other qualifying categorical statuses. Medicaid entered the definition in 2022–23. This measure differs from FARMS eligibility and universal meal access.

Use the native `Economically Disadvantaged Cnt` divided by the **same row's** `Total Student Cnt`, after checking that the published percentage reconciles within its one-decimal rounding precision. Early Attendance and September enrollment have different denominators. September enrollment must never replace the income denominator. The definitions do not establish a more precise Early Attendance observation date, so the extract retains the collection name without inventing one.

For schools with multiple grade-band income rows, use the native whole-school `School Type=All` row. Do not average bands. A single elementary or middle row can establish its school's complete income population. Suppressed or ranged counts and percentages remain unavailable even when another field would allow reconstruction. There is no prior-year backfill.

## Actual proficiency and model scope

The native regular MCAP `All Grades` performance total avoids averaging grade percentages. Math includes course-level Algebra I, Geometry and Algebra II taken at grade schools, retaining accelerated middle-school students. Alternate assessments are published in a separate download and are excluded. Accountability files and their achievement indicators are separate and are not used.

Use the native numeric `Proficient Pct` as published. When both raw counts are numeric, their ratio must reconcile to that percentage. Suppressed rates are never recovered from counts or level percentages. The administrative `Tested Count` label alone does not independently establish the exact valid-score rules needed for sampling intervals; retain it raw and set every normalized tested count to null. Enrollment and participation are not substitutes.

The models use externally studentized residuals within Maryland's fixed grade-school population. Combined is the equally weighted mean of Math and ELA proficiency. UI filters never refit models. The release has one year, no assessment-history connections, no admissions classification and no audited map coordinates. Coverage and exclusions are recorded in `data/maryland/audit.json`.

## Rebuild

The committed [source extract](../data/source/maryland.json) preserves native selected rows, excluded schools, definitions, checksums and URLs. Normal rebuilding is offline:

```sh
.venv/bin/python scripts/prepare_maryland.py
.venv/bin/python scripts/export_catalog.py
```

To refresh, select year 2025 on the official download page and save the four ZIPs under `data/raw/maryland-{mcap,enrollment,special-services,directory}-2025.zip`; save the definitions page as `data/raw/maryland-definitions.html`. These public downloads worked in the normal browser session when direct HTTP download requests returned errors. Then run `scripts/prepare_maryland.py --extract`. The same-year CCD directory is also required. Raw downloads and local SQLite files remain ignored.

Tests reject wrong-year and foreign-ID substitutions, high-grade membership, adjusted CCD scope, grade-specific proficiency, suppressed income reconstruction and fabricated tested counts. Independent deleted-school calculations verify all three model results, and repeated imports must preserve unrelated datasets.
