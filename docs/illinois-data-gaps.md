# Illinois source-gap audit

Checked September 2026. The snapshot remains spring 2024; adding a newer assessment year is a separate task because Illinois changed standards in 2025.

## Added in this pass

- **2017 PARCC and SAT:** the [ISBE Data Library](https://www.isbe.net/ilreportcarddata) links `rc17.zip`, `rc17_assessment.zip`, and `RC17_layout.xlsx`. Use the documented school-wide subject percentages, not the combined ALL TESTS columns. Match the same-year demographic archive by RCDTS. The extractor checks proficiency against the sum of the two proficient performance levels and verifies the level distribution sums to 100 within rounding tolerance. All 7,380 reported school/subject rates reconcile. Counts remain unavailable, so intervals are omitted.
- **2018 SAT:** `Report-Card-Public-Data-Set.xlsx` provides subject performance levels and same-year income. Its demographic headers and uppercase school-type labels differ from later workbooks. The year-specific adapter preserves suppression and uses levels 3 + 4.
- **CPS identifiers and classifications:** the [official city dataset](https://data.cityofchicago.org/d/c7jj-qjvh) links CPS, ISBE and NCES IDs. Because it describes 2013–14, accept only unique mappings independently agreeing with the 2024 state/NCES pair and present in CPS 2023–24 profiles. This yields 481 matches. Keep exclusions with reasons. Transfer current CPS classification only through accepted IDs; do not copy 2014 classification or assume other schools are neighborhood schools.

## Still unresolved

### SAT and 2017 PARCC tested counts

The annual school proficiency records used here do not establish exact valid-score denominators. The linked 2017 SAT subgroup performance workbook has state totals, not school counts. Participation columns in annual workbooks are not a verified substitute for proficiency denominators.

The 2018 PARCC/SAT Proficiency Report's notes define its tested denominator using the larger of valid scores or 95% of testing enrollment. Do not use those counts to attach sampling intervals to ordinary proficiency rates. Similarly, College Board graduating-class reports do not represent the same spring grade-11 assessment cohort.

Next useful source: an ISBE school/year/subject export documenting the valid-score population, exclusions, and suppression rules. Reconcile both rates and scope before attaching counts. An aggregate public-data request may be needed; do not send one without user authorization.

### Grade-school history between 2017 and 2023

The 2018 PARCC and 2019/2021/2022 IAR workbook sheets checked provide grade-level performance percentages. The ELA/Math totals also include other assessments, including DLM. Neither an unweighted grade average nor a mixed-assessment aggregate is the desired school-wide regular-assessment measure.

[EDC v3.1 documentation](https://www.eddatacenter.org/data_documentation/EDC_technical_documentation_v3.1.pdf) identifies substituted EDFacts counts in earlier Illinois years; its verified 2023/2024 ISBE counts do not establish earlier-year weights. The public Report Card chart endpoint inspected did not return a usable bulk historical response. Keep those years as gaps until an authoritative school-wide aggregate or matching grade weights are obtained.

### Complete admissions classifications and crosswalk

The public CPS Profile API documents CPS program and classification fields; it does not supply a verified statewide taxonomy. Classical/selective/neighborhood are not interchangeable with NCES governance, charter status, or magnet status. Keep unmatched schools Unclassified and label filter coverage explicitly.

The historical CPS crosswalk contains shared charter-network IDs, missing identifiers, and NCES disagreements. Resolving these needs a current campus-level crosswalk; names or nearby coordinates alone are insufficient. Do not splice CPS and statewide historical series together solely because a directory match exists.

## Reproduction and release checks

The committed compact extracts contain source checksums and raw values. Use the importer commands in the README, regenerate statewide JSON/catalog, and run import twice. Verify same-year income, independent regression fits, unknown-count intervals, ambiguity exclusions, and unchanged current-year metrics. Browser-check history gaps, school-type filters, and shared URLs. Keep this work on its branch until approved for merging.
