# Idaho 2024–25 data

The `id-isat-2025` snapshot fits separate Idaho Math, ELA and Combined models from native ISAT/IDAA school totals and same-year individual economic eligibility. It includes 480 operational grade-school profiles; 345 have Math models, 357 ELA and 336 Combined. This is conservative complete-count coverage, not every Idaho school. State proficiency standards are not a national scale, and the residuals describe associations rather than causal school effectiveness.

## Official source files

The [Idaho Report Card data-files page](https://www.idahoreportcard.org/datafiles) provides a public download dialog. Select ISAT ELA Proficiency, ISAT Math Proficiency, Total Enrollment and School Information; select 2024–2025, all districts, economic-disadvantage and complementary groups, CSV and long format. The observed public download uses `POST https://www.idahoreportcard.org/api/DataExport/csv`, with the exact JSON request checked into `data/source/idaho.json` and `prepare_idaho.py`. This endpoint responded without authentication or cookies. Its 29,196,052-byte CSV had 92,617 rows, including 739 school identities plus district/state rows and additional automatically included assessment groups. Unused groups and measures are excluded from the compact extract.

Every retained row has the literal `School Year=2024-2025`. Preserve the raw `Rate`, `Text Value`, `Student Count`, `NSize`, `Suppression Type`, measure/group and original CSV row number. Source checksums are in the extract; raw downloads are ignored under `data/raw`.

The [official 2024–25 CCD directory](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip) supplies historical grade offers and operational status. Join the exact three-digit native district and four-digit school codes to `ST_SCHID=ID-DDD-SSSS`; all 739 native identities match. Never join by name. Names and city come from this historical directory.

## Individual income eligibility

Use `Pct Enrollment / Students Economically Disadvantaged` **Student Count divided by NSize**, reconciling that NSize to the independently published same-year `Total Enrollment / All Students` count. This is the first-Friday-of-May K–12 population, not the displayed directory Enrollment field, fall membership, a tested-subgroup fraction or a CEP funding percentage. Native income percentages are rounded to whole percentages, so the model uses exact published counts.

The [official glossary](https://www.idahoreportcard.org/glossary) defines economic disadvantage as individual students ever identified during the reporting year as free eligible, reduced eligible, directly certified or eligible through a household income survey in ISEE `econDisStatus`. It also warns that students whose eligibility is undetermined under Provision 2 or CEP may be recorded as not eligible. Thus this is reported individual eligibility with unknown undercount and survey coverage; universal free meals do not make everyone eligible. The [current reporting guide](https://www.sde.idaho.gov/wp-content/uploads/2026/08/2026-Accountability-and-Reporting-Business-Rules.pdf), pp. 47–48, says this definition began in 2018–19. Seventy-nine grade profiles have unavailable economic counts. A blurred percentage or masked count stays unavailable even if a complementary count could reveal it.

## Native proficiency and valid-score proof

Use native `ELA Proficiency` and `Math Proficiency`, All Students, including ISAT and Idaho Alternate Assessment. Proficient means Level 3 or 4. Grade-school scope uses complete, unadjusted 2024–25 CCD grade offers: no grades 9–13, ungraded or adult programs; maximum grade 8. There is no averaging across grade percentages.

The [2025 official draft guide](https://www.sde.idaho.gov/wp-content/uploads/2025/09/2025-Accountability-Reporting-Business-Rules-Draft.pdf), pp. 35–38, describes continuous enrollment and a denominator equal to the greater of valid scores and 95% of eligible enrollment. The draft remains indexed with readable official content, but its direct PDF URL returned HTTP 404 during this audit. Its earlier [official-host copy](https://iyspp.sde.idaho.gov/assessment/Accountability/files/general/business-rules/2025%20Accountability%20%20Reporting%20Business%20Rules%20Draft.pdf) also failed direct download. The downloaded current guide independently confirms valid-score and privacy rules; it announces a 2026 continuous-enrollment change on p. 7, so these snapshots must not be silently connected across that change. The current guide contains inconsistent remaining continuous-enrollment text; it is not used to reinterpret the 2025 population.

A native `NSize` is **not automatically a tested count**, and an accountability-adjusted rate is not accepted as the proficiency response. For each school/subject, require all four native level counts to be independently published with `Suppression Type=None`, empty Text Value and numeric counts/NSize. Their sum must equal the common NSize on every level and the native proficiency row; Level 3 plus Level 4 must equal the native proficient count. The sum must also equal the independently published participation `Student Count`. The 2025 guide, pp. 24 and 27–28, defines that numerator as students with valid scale scores and excludes nonparticipants, including forced incomplete scores. This independently distinguishes scored students from accountability-assigned failures. The exact proficient/valid fraction must agree with the native one-decimal rate within 0.05 percentage points. If a level or valid-score numerator is masked, do not obtain it by subtraction. If NSize exceeds the complete score total, exclude that subject entirely.

All 1,042 native school/subject rows with complete visible score levels reconciled to the independently published valid-score numerator, including 48 with participation below 95%. For example, `084-0047` Math has 460 level-count students and valid scores, against 491 participation-eligible students (93.7% participation). Its proficiency NSize is 460, not the eligibility denominator or 95% of that denominator. There are 799 complete grade-school subject rows before income exclusions. The adapter enforces this equality rather than assuming every native proficiency denominator is valid.

Valid scores require completed/submitted CAT and Performance Task for ISAT ELA/Math, or a completed alternate assessment; valid IDAA early-stopping rules apply. A forced-submitted incomplete test's score is not valid for accountability/reporting. Participation enrollment, roster counts and directory Enrollment are never substituted. These rules are confirmed in the current guide, pp. 24–28; the 2025 draft specifically distinguishes incomplete tests on p. 8.

Masked, dynamically blurred, not-applicable and missing rows remain unavailable. Counts below five and secondary cells may be protected; `None` in the suppression column does not override a literal `*`. The complete-level rule excludes additional schools even when their overall rate is numeric. It narrows the model population and can affect representativeness. All eligible model members have verified valid counts, so sampling intervals are available. Combined is the equally weighted mean of Math and ELA rates.

## Historical directory and map limits

The report-card download presents directory metadata alongside historical rows; those metadata cannot establish historical grade scope. Four school IDs have conflicting high-grade status relative to the 2024–25 CCD directory: `479-1341`, `493-1371`, `532-1424`, `594-1501`. In particular, current display K–8 at `493-1371` and K–6 at `532-1424` does not override historical K–12 and K–11. The adapter excludes those two schools. In total 259 native profiles are outside operational historical grade-school scope.

The native download contains current directory coordinates. Historical campus identity at those coordinates was not established, so no map points are exported. Every retained profile remains searchable and accessible in lists/charts. History contains only 2025.

## Rebuild and verification

Default rebuilds need only the committed extract and initialized SQLite store:

```sh
.venv/bin/python scripts/prepare_idaho.py
.venv/bin/python -m unittest discover -s tests -p test_idaho.py -v
```

To refresh extraction, have the official CCD directory ZIP under `data/raw`, then run `prepare_idaho.py --download`. This downloads the native 2024–25 query and current reference documents and rebuilds the compact extract. `--extract` parses existing raw files. `--database PATH` supports an independently initialized test store. Default rebuilding is offline and does not depend on the inaccessible 2025 PDF.

Tests reject inflated accountability denominators, score-level totals differing from valid-score numerators, masked level reconstruction, blurred/complementary income reconstruction, wrong-year/ID joins and high-school grade offers. Independent deleted-school OLS fits check externally studentized residuals for all three models. Repeat imports and output hashes, foreign keys and unrelated canonical observations are checked separately before integration.
