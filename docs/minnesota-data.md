# Minnesota native 2024–25 data

Minnesota uses official schoolwide 2024–25 MCA-III/MTAS proficiency and same-year individual meal eligibility. Pure grade schools and pure high schools have separate math, ELA and Combined models. Mixed grade schools are excluded. High-school math assesses Grade 11 while ELA assesses Grade 10; Combined therefore averages two subject rates from different grade cohorts.

## Official sources and identifiers

The [MDE Data Center](https://education.mn.gov/MDE/Data/) public Assessment and Student selectors produced authentic workbooks through their ordinary file download links on October 9, 2026:

- [2024–25 Math assessment](https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&RevisionSelectionMethod=latestReleased&Rendition=primary&dDocName=PROD087031), native `School` and `Column Definitions` sheets.
- [2024–25 Reading/ELA assessment](https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&RevisionSelectionMethod=latestReleased&Rendition=primary&dDocName=PROD087032), using the same native fields.
- [2024–25 October enrollment](https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&RevisionSelectionMethod=latestReleased&Rendition=primary&dDocName=PROD085895), native `School`, `Enrollment Information` and `Column Definitions` sheets.
- [Assessment Files User Guide](https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&RevisionSelectionMethod=latestReleased&Rendition=primary&dDocName=005342), current September 2026 revision, and [Student Data guide](https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&RevisionSelectionMethod=latestReleased&Rendition=primary&dDocName=005343). The current assessment guide covers newer assessments as well; the **2025 workbooks' own definitions and year fields** establish the imported historical definition.

All records explicitly identify `Data Year=24-25`. Identity is the exact combination of **District Number, District Type and School Number**, normalized as `0001-01-002`. District type cannot be discarded: equal district numbers can represent different organizational units. The three components match across assessment and enrollment; names never establish a join. Each native record retains its original worksheet row number. The 2024–25 enrollment notes newly include tribal-controlled schools. The [official MDE SIS vendor definition](https://education.mn.gov/mdeprod/groups/educ/documents/basic/bwrl/mdc1/~edisp/mde075526.pdf) explicitly identifies District Type 34 as Bureau of Indian Education. All four Type 34 profiles are retained in the extract and explicitly excluded from state-public jurisdiction: Fond du Lac Ojibwe, Bug-O-Nay-Ge-Shig, Circle of Life and Nay-Ah-Shing. Other native public/cooperative and alternative types remain eligible under the same numerical and grade-scope rules. Assessment IDs absent from the same-year October enrollment remain excluded; income is not backfilled from another year.

## Individual economic eligibility despite universal meals

The [MARSS Reference Guide FY 2024–25](https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&allowInterrupt=1&dDocName=060311&dID=137017), dated July 2024, distinguishes individually ineligible, reduced-price, free and directly certified eligibility codes. The [Annual Application requirement](https://education.mn.gov/mdeprod/idcplg?IdcService=GET_FILE&allowInterrupt=1&dDocName=055515&dID=135955), revised June 2024, explicitly requires actual eligibility reporting in MARSS even though students receive universal free meals. Public CEP schools collect alternate applications annually.

The [2024–25 alternate application instructions](https://education.mn.gov/mdeprod/idcplg?IdcService=GET_DYNAMIC_CONVERSION&dID=136653) extend individual economic documentation to CEP, Provision 2/3 and schools without a meal program. They expressly forbid carrying prior-year application or direct-certification approvals into current MARSS reporting. These dated definitions affirm that the enrollment workbook's eligible count is an individual measure rather than schoolwide access to meals. Application nonresponse can still limit reported individual eligibility.

The enrollment workbook defines its numerator as enrolled students eligible for free or reduced-price meals and its denominator as native total October 1 enrollment. School totals include all reported grades, including PK and ECSE. Their exact count ratio is used; the native two-decimal displayed percentage must reconcile within rounding precision and is preserved alongside the counts. The enrolled student population differs from students with Spring 2025 valid scores. Enrollment is never substituted for the assessment denominator.

MDE's [privacy reporting FAQ](https://education.mn.gov/MDE/About/MDE086067) defines data blurring as ranges instead of exact values and explains complementary suppression. The native workbook states that blanks are protected data. Both `Filter Groups` and `Additional Suppression Free or Reduced Priced Meals Applied` must be `N`, and both enrollment and eligible count must be numeric, before income enters a model. Of 2,431 school total profiles, 2,080 have unsuppressed numeric eligible counts and 351 are unavailable. Suppressed school totals are never recovered from grade subtotals or another demographic component. Exact published numeric zero is retained; a blank, bound or range never becomes zero or a midpoint.

## Valid-score proficiency and model scope

Both 2025 assessment workbooks define `Total Tested` as the number receiving a **valid score**. They define proficiency as students meeting or exceeding standards divided by that total. Separate fields report absent, invalid, refused and other no-score cases; those fields are not added to the score denominator. The native valid MCA and MTAS counts independently reconcile to the school total where both are published. There is no 95% expected-participation substitution.

The adapter retains `All Standards-Based (MCA/MTAS/ALTMCA)`, `All Categories`, `All students`, and native `Grade=0` schoolwide totals. The 2025 math/ELA valid-score columns identify MCA-III and MTAS. Alternate achievement standards are included in the published total. Numeric native Meets and Exceeds counts yield actual proficiency divided by verified valid scores; that ratio must reconcile to the native four-decimal fraction. Suppressed numerator components are never inferred through complements. The adapter uses the schoolwide totals directly, not averages of grade percentages. Native per-grade score counts provide a separate total-reconciliation audit, not substitute weights or missing-grade reconstruction.

All 2,431 native school enrollment totals reconcile exactly to their full numeric reported grade subtotals. Grade-school profiles have enrolled Grades 3–8 and no Grades 9–12. High-school profiles have only Grades 9–12, with no PK, ECSE, KG or Grades 1–8 enrollment. Four tribal/BIE profiles are explicitly excluded by jurisdiction; 417 other profiles have mixed tested grades and 211 are outside these tested populations. One high-school ID also shares 156 ECSE students (Fairview Program, `0623-01-732`) and is excluded. Contrary actual assessment grades exclude a further 22 high profiles, preserving pure populations even when fall enrollment and spring testing differ. Fairview was already among the earlier contrary-grade exclusions, so the stricter primary/early-childhood check does not change model populations. The modeled directory has 1,275 grade-school and 501 high-school profiles, including records with missing or suppressed outcomes for visible exclusions.

| Population | Math model | ELA model | Combined model |
| --- | ---: | ---: | ---: |
| Pure grade schools | 1,129 | 1,128 | 1,128 |
| Pure high schools | 266 | 240 | 235 |

Each subject and population has its own externally studentized model. Combined is the equally weighted mean of math and ELA proficiency. All eligible members have verified valid-score counts, so all six models publish propagated sampling intervals. UI filters never refit the models. Results describe associations rather than causal effectiveness; Minnesota standards are not pooled with other states into a national ranking. This one-year release does not connect incompatible historical assessments or make a standards-continuity claim.

## Rebuild and verification

The committed `data/source/minnesota.json` preserves selected native fields, grade profiles, schoolwide outcomes, suppression flags, source URLs, checksums and workbook definitions. Unneeded ethnicity and mean-scale-score fields are omitted; no fields used in identity, eligibility, scope or numerical transformations are dropped. The three native workbooks and two authentic general guides have content checksums. Dated eligibility and privacy documents have exact official documentary URLs and observed definitions; failed HTML download responses are not represented as PDF checksums.

```sh
.venv/bin/python scripts/prepare_minnesota.py
.venv/bin/python scripts/export_catalog.py
.venv/bin/python -m unittest discover -s tests -p test_minnesota.py -v
```

To refresh, save the five authentic files in `FILES` under `data/raw/minnesota` and run `scripts/prepare_minnesota.py --extract`. This re-reads the native workbooks and retains the dated individual-eligibility audit. Reaudit definitions if the files or school year change. Raw downloads are ignored by Git.

Eight tests check three-part IDs and same-year joins, complete grade reconciliation, mixed exclusions, native valid-score counts, component suppression, individual income flags, repeat imports and independent deleted-school studentization plus interval propagation in all six models. A fresh native extraction, two isolated imports and two coordinated canonical imports produced byte-identical exports. All nine unrelated canonical tables and all 173 existing served JSON files, including Chicago and the four Minnesota outputs, retained identical fingerprints; foreign-key checks were clean. Local evidence is saved in `data/build/minnesota-isolated-preservation.json` and `data/build/minnesota-canonical-preservation.json`. No audited school coordinates are available; map boundaries remain null and the catalog states that limitation.
