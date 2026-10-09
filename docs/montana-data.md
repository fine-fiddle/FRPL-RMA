# Montana 2024–25 MAST and individual NSLP eligibility

This snapshot supports grade schools in a restricted public-school population: regular National School Lunch Program participants with individual eligibility counts, excluding every CEP and nonregular program flag. It fits separate Math, ELA and Combined models against individual free/reduced eligibility. It is not a statewide ranking of all Montana schools and does not extend assessment history. High schools are not included.

## Assessment source and population

[EDC v3.1 Montana 2025 CSV](https://www.eddatacenter.org/api/data/3.1?state=MT&year=2025) supplies school `All Students`, `Regular`, `MAST`, `G38` math/ELA records. The [EDC codebook](https://www.eddatacenter.org/data_codebooks/EDC_codebook_v3.1.xlsx) identifies `G38` as the SEA-native grades 3–8 aggregate. The [technical documentation](https://www.eddatacenter.org/data_documentation/EDC_technical_documentation_v3.1.pdf), Appendix B, identifies OPI data requests and the [native GEMS student dashboard](https://gems.opi.mt.gov/student-data) as Montana sources. This adapter follows that documented native aggregate provenance; it does not claim an independent recapture of every 2025 school total.

Use only an exact numeric `ProficientOrAbove_percent` for levels 3–4. Suppression, ranges and missing cells remain unavailable. No local grade averaging or reconstruction from tested counts, achievement levels, participation or complementary percentages occurs. EDC tested and proficient counts remain in the extract as unused raw cells. Valid-score denominator rules have not been independently approved; every modeled tested count and interval endpoint is null.

MAST is the new 2024–25 regular assessment. The source flags assessment-name and Math/ELA cut-score changes. The snapshot labels that standards era and does not connect it to SBAC history or alternate assessments.

## Same-year individual income evidence

The official [GEMS Program Year 2025 Free & Reduced Eligibility / E-Rate report](https://gemsapi.opi.mt.gov/Report/ExportReport/?reportPath=%2FGEMS_SSRS_Reports%2FStudent_Reports%2FSchoolNutrition_ERate&format=Csv&strProgramYear=2025&strStateCounty=0&UserName=opigemsanon&ReportViewerEnablePaging=True) contains native sponsor/school identifiers, full NCES school IDs, individual eligible count, enrolled count, and CEP base year. [OPI School Nutrition](https://opi.mt.gov/Leadership/Management-Operations/School-Nutrition/) links both the GEMS report and the downloadable claim files.

The official [NSLP Claim Counts workbook](https://opifiles.mt.gov/Portals/182/Page%20Files/School%20Nutrition/Agreements,%20Claims,%20%26%20Data/NSLP_ClaimCountsFor_20260416.xlsx), `Site` sheet, supplies `Claim Period=2024-10-01`, native sponsor/site strings, program participation flags, school type, `Lunch Enrollment` and `Lunch Free or Reduced Eligible`. The [official field definitions](https://opifiles.mt.gov/Portals/182/Page%20Files/School%20Nutrition/Agreements,%20Claims,%20%26%20Data/Claim%20Meal%20Count%20Reports%20-%20Field%20Definition%20List.xlsx) define these as enrolled students and eligible students; meal-service counts are separate fields. All 492 numeric non-CEP GEMS rows exactly match both October 2024 claim counts. This establishes the program-year mapping directly, rather than assuming that a report labeled 2025 means fall 2025.

For eligible public schools, income is `100 × individual free/reduced eligible / native lunch enrollment`. Both exact counts must be available, enrollment must be positive, eligible cannot exceed enrollment, and the GEMS and dated claim values must agree. Free/reduced eligibility reflects household income applications and qualifying direct certification. It is not the number of meals served.

Exclude any GEMS CEP base-year flag, any claim participation value other than `Participates in Regular Program`, and any school type other than `Public`. This excludes the union of source flags, rather than accepting an unflagged row from one source when another identifies special meal treatment. [OPI CEP packet instructions](https://opifiles.mt.gov/Portals/182/Page%20Files/School%20Nutrition/Meal%20Eligibility/CEP/MAPS%20CEP%20Application%20Packet%20Instructions.pdf?ver=2021-04-02-094718-623), page 2, describe the CEP claiming percentage and base-year mechanism; those constructed values cannot substitute for individual eligibility.

The GEMS report's definitions acknowledge that public-school meal-program enrollment corresponds to enrolled students but may not perfectly match the school enrollment count. Consequently, retain the native NSLP denominator for the economic percentage. Displayed enrollment comes separately from [same-year CCD membership](https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip). Of the 280 included school profiles, native lunch enrollment equals CCD membership for 70 and differs for 210. The adapter never divides the native eligible count by CCD membership, estimates an eligible count from a rounded percentage, or silently substitutes a denominator.

## Identity and grade scope

Native four-digit sponsor and school strings must join exactly to the [same-year CCD directory](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip) `MT-district-school` identity. The full GEMS NCES ID must agree with CCD and EDC; the claim workbook's `NCES Id` is only a five-digit school suffix and must agree with the GEMS suffix. The claim's sponsor/site strings must also agree. Names establish no identity. Preserve six-digit nonpublic/non-school site records in exclusions; do not truncate them into school IDs.

Some native high-school CNP sponsors differ from CCD's separate high-school LEA namespace. No district replacement or name repair is applied. These are excluded rather than falsely joined.

Included schools must have operational, unadjusted same-year CCD directory metadata, complete grade-offer flags, no high/adult offered grades, and reported grade membership that reconciles to total membership. Positive unknown, high or ungraded enrollment is excluded. Native G38 math/ELA rows must form an unambiguous exact subject pair. Suppressed subjects remain visible as exclusions and do not enter those regressions; Combined requires both exact rates.

## Coverage and validation

The snapshot has 280 grade-school profiles: 240 Math, 228 ELA and 220 Combined model members. Of the 791 native nutrition sites, exclusions comprise 289 CEP/nonregular programs, 17 nonpublic sites, 115 unavailable or disagreeing exact identities, 61 mixed/high/unknown grade configurations, 19 unavailable individual eligibility counts, and 10 missing native G38 subject pairs. Restrictions and suppression limit representativeness, particularly because CEP schools are omitted.

[The committed extract](../data/source/montana.json) retains included and excluded rows, dated native claims and workbook row numbers, unused assessment counts, directory/member flags, grade subtotals, official URLs and SHA-256 checksums. Raw sources remain ignored under `data/raw/`.

```sh
.venv/bin/python scripts/prepare_montana.py
# Explicit extraction from the already downloaded raw files:
.venv/bin/python scripts/prepare_montana.py --extract
```

Six tests verify exact rates and dated income, union CEP/program exclusions, suppressed/ranged values, rejected identity/year/population/count mutations, independent deleted-school studentization and repeatable imports that preserve other datasets. Two isolated database imports produced byte-identical JSON and a clean foreign-key check. Every assessment count and sampling interval remains unavailable; Combined is the equal Math/ELA mean. The relationships are associations, not causal school effectiveness.
