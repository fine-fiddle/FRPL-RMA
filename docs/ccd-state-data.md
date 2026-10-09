# EDC grade totals and CCD direct certification, 2024–25

This single-year adapter adds Alaska, Georgia, Louisiana, Maine, New Mexico, Nevada, Rhode Island and Tennessee. Each state fits separate grade-school math, ELA and Combined models. It does not pool states or extend any assessment history. Direct certification is a distinct benefits-based economic proxy; it is not the full state economically disadvantaged population, household-income FRPL eligibility, or the proportion receiving universal free meals.

## Sources and approval boundary

[EDC v3.1](https://www.eddatacenter.org/data) was released in June 2026. Its [codebook](https://www.eddatacenter.org/data_codebooks/EDC_codebook_v3.1.xlsx) identifies `GradeLevel=G38` as the SEA-sourced aggregate for grades 3–8. The [technical documentation](https://www.eddatacenter.org/data_documentation/EDC_technical_documentation_v3.1.pdf), grade section and Appendix B, describes the source populations and SEA sources. This adapter uses only school, All Students, Regular, native G38 rows, with one documented assessment and threshold per state. It never aggregates grades or reconstructs suppressed rates.

The exact published `ProficientOrAbove_percent` is retained. EDC can derive this overall percentage by adding achievement-level percentages within the same native total; that operation does not combine grades. Nonexact ranges, suppression markers and missing values remain unavailable. EDC may construct achievement-level counts from percentages and tested counts; neither those constructed counts nor EDC tested values are approved valid-score denominators here. Every subject and Combined model has `tested=null` and unavailable sampling intervals.

Rhode Island received an additional direct primary-source crosscheck: all 231 EDC G38 school rows per subject exactly match the official RIDE `By_School` workbook percentages and raw tested values, joining through the published state school code. [ELA workbook](https://www3.ride.ri.gov/ADP/Default/QuickReport?subject=5&schYear=2024-25&type=school), [math workbook](https://www3.ride.ri.gov/ADP/Default/QuickReport?subject=6&schYear=2024-25&type=school). This check does not verify valid-score denominator business rules, so Rhode Island also remains point-only. The other seven states rely on EDC's documented SEA-native grade-total provenance; their source-level business rules and valid-score counts are not independently approved.

Income uses the [CCD 2024–25 school lunch Final 2a file](https://nces.ed.gov/ccd/Data/zip/ccd_sch_033_2425_l_2a_073025.zip), published June 2026, with the [same-year membership Final 1a](https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip) and [directory Final 1a](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip). The [Final 2a SEA notes](https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx) and [NCES school-lunch definitions](https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data) were audited before approval. Final 2a suppresses Pennsylvania school-lunch data for quality; the earlier Final 1a values must not be reused as a substitute.

Direct-certification `Education Unit Total` divided by membership `Education Unit Total` supplies the percentage. Both must be `DMS_FLAG=Reported`, numeric and nonnegative, enrollment must be positive, and DC must not exceed membership. Enrollment includes pre-K where enrolled. The direct-certification category describes individual eligibility through qualifying benefits/statuses, rather than counting every child attending a CEP school; no claiming multiplier or meal-availability count is used. Medicaid/free/reduced eligibility and reporting coverage vary by state. There is no FRPL fallback for missing DC, no tested-subgroup income ratio and no prior-year backfill.

## Approved snapshots

| State | Native assessment / proficiency | Profiles | Math | ELA | Combined | State-specific source limitation |
|---|---|---:|---:|---:|---:|---|
| Alaska | AK STAR, levels 3–4 | 193 | 191 | 189 | 189 | 2025 DC returns closer to historical averages after unusually low 2024 reporting; leading-zero NCES width is restored. |
| Georgia | Georgia Milestones EOG, levels 3–4 | 1,714 | 1,714 | 1,714 | 1,714 | No school-allocation warning in the audited CCD notes; benefits eligibility remains distinct from full state economic disadvantage. |
| Louisiana | LEAP 2025, levels 4–5 | 861 | 838 | 854 | 834 | First CCD DC reporting year is 2024–25; earlier years cannot supply compatible DC history. |
| Maine | Maine Through Year Assessment, levels 3–4 | 386 | 378 | 378 | 374 | This year's DC includes students previously reported as reduced lunch, an explicit income definition era. |
| New Mexico | NM-MSSA, levels 3–4 | 579 | 535 | 565 | 534 | Medicaid free/reduced direct certification began in 2023–24; collection matured in 2024–25. |
| Nevada | SBAC, levels 3–4 | 528 | 513 | 514 | 511 | Some districts classified DC students as reduced rather than free lunch; DC category remains separate. All included schools require reported zero ungraded enrollment and reconciled grade subtotals. |
| Rhode Island | RICAS, levels 3–4 | 220 | 214 | 218 | 214 | Entire LEA `4400150` excluded pending clarification of main-school lunch allocation; adjusted grade metadata excluded. |
| Tennessee | TNReady, levels 3–4 | 1,317 | 1,300 | 1,304 | 1,297 | No FRPL values are reported in CCD; only individual DC is used. No school-allocation warning in audited notes. |

The Combined population contains 5,667 schools. Profiles with a suppressed subject remain visible with explicit exclusions; they do not enter that subject's regression. Combined requires both exact subject rates and is their equally weighted mean.

The state primary assessment sources are [Alaska](https://education.alaska.gov/compass/Report/2024-2025), [Georgia](https://goews.georgia.gov/dashboards-data-report-card/downloadable-data), [Louisiana](https://doe.louisiana.gov/data-and-reports/elementary-and-middle-school-performance), [Maine](https://www.maine.gov/doe/dashboard), [New Mexico](https://newmexicoschools.com/), [Nevada](https://nevadareportcard.nv.gov/di/main/assessment), [Rhode Island](https://www3.ride.ri.gov/ADP), and [Tennessee](https://www.tn.gov/education/districts/federal-programs-and-oversight/data/data-downloads.html).

## Identity and grade population

Every assessment, membership and DC observation joins through the authoritative 12-digit `NCESSCH` and school year 2024–25. EDC represents NCES IDs numerically, dropping Alaska's leading zero; restoring documented NCES width is the only normalization. The state FIPS prefix must agree. Names do not establish identity.

Schools must be operational with unadjusted `IGOFFERED=As reported`, a highest offered grade of 1–8, complete Yes/No grade-offer flags, and no offered grades 9–13 or adult education. Positive same-year grade membership subtotals must be reported and sum to total enrollment. Unknown, high, adult or ungraded enrollment must be zero, with explicit raw flags retained. Nevada's directory offers ungraded programs at every school; inclusion requires explicitly reported zero ungraded students and full reconciliation of enrolled PK–8 grades. Classification is never inferred from an assessment's tested grades or a school name.

## Audited blockers

Ohio has exact native G38 rates and numeric CCD DC, but the SEA explains that some LEAs report all lunch/DC counts under one school. The error lists name schools whose counts exceed membership; they are not an exhaustive list of LEAs with allocated counts. A count below enrollment cannot establish individual-school scope. This CCD path remains blocked until an authoritative allocation repair or individual-school income source is obtained.

South Dakota's SEA note says it is still ensuring clarity and consistency in standardized DC reporting definitions, with local shifts from free-lunch statuses to DC. Reported flags alone do not resolve that definition uncertainty. This path remains blocked pending confirmation of individual eligibility rules.

The [all-50 inventory](../data/source/national-snapshot-audit.json) records G38 presence, exact-rate availability, CCD directory/member/DC coverage and flags, same-year joins and concrete obstacles. Discovery counts do not imply approval. Thirty states have no EDC G38 math/ELA school totals; they require native school totals or a complete grade population with independently verified valid-score aggregation weights. Other states with G38 lack numeric DC and need a separately audited state income source.

## Rebuild and validation

The offline extract is [ccd-state-snapshots.json](../data/source/ccd-state-snapshots.json). It retains exact native rates, suppressed/ranged raw values, unused tested cells, same-year DC/member rows and flags, grade membership subtotals, directory grade metadata, excluded records and reasons, official URLs and SHA-256 hashes. Raw EDC CSVs and official CCD archives are ignored under `data/raw/`.

```sh
.venv/bin/python scripts/prepare_ccd_states.py
.venv/bin/python scripts/export_catalog.py
```

For explicit extraction from the already downloaded raw sources:

```sh
.venv/bin/python scripts/audit_national_sources.py
.venv/bin/python scripts/prepare_ccd_states.py --extract
```

The CCD membership archive uses Deflate64; `unzip -p` streams it into a compact ignored grade/total cache. It is not necessary for ordinary offline rebuilds. Tests compare model output with independent deleted-school regressions, require every interval endpoint/tested value to remain unavailable, reject grade/suppression/year/scope changes, and verify repeated canonical imports preserve unrelated datasets.
