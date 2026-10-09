# Indiana: ILEARN grades 3–8, 2024–25

Indiana uses IDOE's native Spring 2025 **School Total** math and ELA results. The two comparisons have separate Indiana regressions, separate assessment identities, and one year of history. They never pool with other states.

| Comparison | Same-year enrolled grade rule | Schools retained | Math / ELA / Combined eligible | Mapped |
| --- | --- | ---: | ---: | ---: |
| Grade schools | No enrollment in grade 9 or above | 1,416 | 1,328 / 1,328 / 1,328 | 1,392 |
| Mixed-grade schools | Enrollment in both grades 3–8 and grade 9 or above | 187 | 169 / 169 / 169 | 177 |

The 288 public schools with only high-school/adult grade enrollment are outside this ILEARN release. This is **not statewide high-school proficiency**: the mixed comparison's outcome still covers only grades 3–8. Its internal `HS` level marks the school as serving high-school grades so that grade-school filters exclude it. Same-year enrolled grades, including `Grade 12+/Adult`, define the partition; current directory spans never backfill it. Both comparisons retain unavailable schools in the searchable directory.

## Official sources and definitions

The [IDOE archived downloads](https://www.in.gov/doe/it/data-center-and-reports/data-reports-archive/) explicitly label the enrollment releases **SY 2024–2025**; their `2025` worksheet means school-year ending 2025. Spring 2025 ILEARN and the 2025 enrollment/grade tabs therefore describe the same school year.

| Purpose | Official file | Raw local filename |
| --- | --- | --- |
| Proficiency and score denominators | [2025 ILEARN Grade 3–8 School Results](https://www.in.gov/doe/files/ILEARN-2025-Grade3-8-Final-School_20250714-2.xlsx) | `in_assessment_2025.xlsx` |
| Economic eligibility counts | [School Enrollment by Ethnicity and Free/Reduced Price Meal Status, 2006–2025](https://www.in.gov/doe/files/school-enrollment-ethnicity-and-free-reduced-price-meal-status-2006-25-final.xlsx) | `in_income_history.xlsx` |
| Same-year grade counts | [School Enrollment by Grade Level, 2006–2025](https://www.in.gov/doe/files/school-enrollment-grade-2006-25.xlsx) | `in_grades_history.xlsx` |
| Explicit state-to-NCES identifier crosswalk | [2025–26 Indiana School Directory](https://www.in.gov/doe/files/2025-2026-school-directory-2026-03-23.xlsx), `SCHL` sheet | `in_directory_2026.xlsx` |
| Coordinates | [NCES 2023–24 public-school locations](https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2324/MapServer/0) | `in_nces_locations_2024.json` |
| Assessment definition | [2024–25 ILEARN Technical Report](https://www.in.gov/doe/students/assessment/assessment-files/ILEARN%20Summative_Technical%20Report_SP25_Mainbody_Final_v0.1%20%281%29.PDF) | `in_ilearn_technical_2025.pdf` |
| Individual eligibility reporting | [How to Report Pupil Enrollment](https://idoe.atlassian.net/wiki/spaces/IKHTV/pages/473890839), [eligibility tutorial](https://idoe.atlassian.net/wiki/spaces/IKHTV/pages/407470085) | `in_frpl_reporting_2025.json`, `in_frpl_eligibility_2025.json` |
| CEP individual eligibility rules | [IDOE June 18, 2025 nutrition bulletin](https://www.in.gov/doe/files/June-18%2C-2025-School-Nutrition.pdf), page 1 | `in_cep_guidance_2025.pdf` |
| State outline | [Census 2024 cartographic states](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_500k.zip), `STATEFP=18` | `cb_2024_us_state_500k.zip` |

**Proficiency.** The outcome is the published `Proficient %` in the native **School Total** group, converted from a proportion to a percentage. Proficient means **At + Above Proficiency**. Each numeric total must pass three independent checks: the four performance-level counts sum to `Total Tested`; At + Above equals `Total Proficient`; and Total Proficient / Total Tested matches the published rate within `1e-8` before percentage conversion. Consequently the denominator is students assigned a performance level, not enrollment or the accountability participation denominator. Technical-report table 35 separately reports students tested and students reported, reinforcing that those concepts differ.

The workbook notes describe all Spring 2025 ILEARN testers except ESA testers, assigned to schools by **tested location**. There is no FAY filter in this release. I AM alternate assessments, IREAD foundational reading, SAT, Biology, and the publisher's `ELA & Math` intersection are not imported. **Combined is the equally weighted mean of the two separate subject percentages.** It does not use the workbook's percentage proficient in both.

**Economic disadvantage.** `Free/Reduced Price Meals / TOTAL ENROLLMENT × 100` uses the same `2025` tab and exact school ID. IDOE's pupil-enrollment reporting guide links individual School Food Services eligibility records active on Fall Count Day at a student's primary school to its published economically disadvantaged subgroup. It instructs schools to omit records for ineligible students. The eligibility tutorial specifies a household application or Direct Certification. The CEP bulletin distinguishes universally free meals from individual qualification; it permits Direct Certification and approved alternate applications to establish individual status. Thus the numerator is **reported individual eligibility**, not all students receiving a free meal under CEP or the CEP reimbursement multiplier.

This proxy can undercount disadvantage when eligible families do not complete applications or schools do not identify/report eligibility. The files do not reveal each school's application coverage. Census enrollment also includes pre-K/adult students when present and differs from grades 3–8 testers. `Paid Meals` is retained as the source label, although the reporting guide describes students without an active eligibility record as N/A; the workbook's label is not evidence that each student purchases meals. No external-year counts, nutrition-program claim counts, enrollment-based test counts, or guessed eligibility are substituted.

## Identities, suppression, and coverage

School identifiers retain leading zeros. The public enrollment registry supplies the population, joined to assessments by the exact IDOE school code. The state schools for the Blind (`C460`) and Deaf (`C695`) legitimately have alphanumeric public IDs and are retained. A blanket numeric-only filter would wrongly discard them. Nonpublic assessment rows absent from that registry are excluded; names never establish identity.

The workbook masks groups with fewer than ten students using `***`. Masked native totals stay unavailable, even when some grade results are numeric. Conversely, an independently published unsuppressed school total may be used when grade-level results are masked: no suppressed grade count is reconstructed. The extract records all selected native totals and the publisher's suppression notes.

Grade-school exclusions from Combined: 83 have no enrolled grades 3–8, four have no published total, and one has suppressed totals. Mixed exclusions: eight have no totals, nine have both totals suppressed, and one has ELA suppressed and no math total. An additional 688 source assessment rows lack a matching public same-year enrollment row: 686 alphanumeric nonpublic rows and two subject rows for Porter County Education Services (`6811`). Those rows are retained in the source exclusion audit and receive no income backfill. Their eligibility is unavailable.

Models require at least ten students with scores, valid same-year income, four schools, and income variation. All eligible Indiana observations have verified score denominators, so sampling intervals propagate every member's variance. Residuals are externally studentized. No enrollment weighting, shrinkage, or causal effectiveness interpretation is introduced.

Map coordinates use the current directory's explicit NCES ID, joined exactly to the NCES location file. They have older/newer vintages than the outcome and may not represent the 2025 campus. Locations never determine model eligibility. The current directory lists `6864` twice under different districts; its crosswalk is treated as ambiguous and no location is selected. Missing or invalid locations remain list-only. No names or approximate addresses are geocoded.

## Rebuilding and verification

The compact committed [`indiana.json`](../data/source/indiana.json) retains raw identity cells, meal-status counts, enrolled-grade counts, native total counts/rates, worksheet row numbers, guide versions, exclusion records, official URLs, and raw-file SHA-256 checksums. Raw inputs stay in ignored `data/raw/`. SQLite imports only `in-ilearn`; unrelated datasets are preserved. Exports are `data/indiana/` and `data/indiana/mixed/`. The generated descriptor `data/indiana/catalog.json` lets the shared catalog discover both ready comparisons.

```sh
# Offline rebuild from the committed extract.
.venv/bin/python scripts/prepare_indiana.py
.venv/bin/python scripts/export_catalog.py

# Regenerate the extract after placing every official input above in data/raw/.
.venv/bin/python scripts/prepare_indiana.py --extract
.venv/bin/python -m unittest discover -s tests -p test_indiana.py -v
```

The two guide JSON files are unmodified public Confluence REST responses from `/wiki/rest/api/content/473890839?expand=body.storage,version` and `/wiki/rest/api/content/407470085?expand=body.storage,version`. The NCES response uses `/query` with `where=STATE='IN'`, `outFields=NCESSCH,NAME,CITY,NMCNTY,LAT,LON,SCHOOLYEAR`, `orderByFields=NCESSCH`, `returnGeometry=false`, `resultRecordCount=3000`, and `f=json`; incomplete pagination is rejected.

Tests independently refit leave-one-school-out regressions, verify native denominators, same-year eligibility, grade partitions, missing/suppressed coverage, exact-ID maps, and repeated imports. This release contains one snapshot only. Indiana's 2025–26 through-year redesign and any older series need a separate standards and comparability audit before history can be extended.
