# Los Angeles Unified district audit

This is a source and cohort audit for a possible 2024–25 Los Angeles Unified comparison under [issue #3](https://github.com/robot-assisted-projects/FRPL-RMA/issues/3). It does not add a comparison, fit district regressions or approve modeling. Existing California results retain their statewide comparison populations.

## Exact roster and reporting scope

The baseline roster is the official 2024–25 CCD school directory's operational schools attached to **NCES LEA 0622710**, native **CA-1964733**. The exact published school identity `CA-1964733-sssssss` maps to California CDS `1964733sssssss`; names never join. The retained directory has 785 records: 784 operational and one closed. Of the operational records, 783 match supported same-year CDE FRPM school profiles. One infant/preschool record, CDS **19647330117226**, has no matching FRPM profile; its income is unavailable, not zero. Closed CDS **19647330126474** remains separately recorded.

The native CDE reporting prefix also contains **218 supported charter profiles outside this exact CCD roster**. Of these, 216 have verified CAASPP Type 9 **Direct Funded Charter School** records; two have no assessment rows, so their assessment funding type is unavailable. Their reporting association does not establish district roster membership or a proven alternate CCD LEA mapping. They are retained as excluded records. One additional native FRPM row has an unsupported/non-school grade configuration.

The matched baseline includes **732 noncharter profiles and 51 charter profiles**. The 51 charter matches have CAASPP Type 10 **Locally Funded Charter School** records. Native FRPM charter flags, including published whitespace, are retained and reconcile to CCD flags. The source baseline includes these exact roster members; any later choice of district-operated versus affiliated-charter comparison population requires explicit documentation and separate models.

## Pure cohorts and usable observations

Native FRPM low/high grade bounds and pure/mixed classification agree with the complete CCD offered-grade flags for all 783 matches: **589 pure grade-school, 147 pure high-school and 47 mixed profiles**. Bounds agreement does not imply that every interior grade is offered. Outcome aggregation keeps the existing conservative California rule: every expected grade in the native FRPM span must have a published, valid record.

| 2024–25 pure population | Profiles | Assessment applicable | Usable Math | Usable ELA | Usable Combined |
| --- | ---: | ---: | ---: | ---: | ---: |
| Grade schools, Smarter Balanced grades 3–8 | 589 | 572 | 561 | 561 | 561 |
| High schools, Smarter Balanced grade 11 | 147 | 144 | 137 | 137 | 136 |

The [district queue](district-comparisons.md) has **572 / 147 potential ES / HS schools**. Its exact school IDs reconcile to this audit. The 17 other pure grade-school profiles serve only K, K–1 or K–2 and have no grades 3–8 assessment. Three pure high-school profiles serve grade 12 only and have no grade-11 assessment. The difference is assessment applicability, not a failed enrollment reconciliation. These planning counts never establish usable outcome or income coverage.

For each pure grade-school subject, six applicable profiles lack an expected grade and five have missing/suppressed valid-score counts or proficiency. For each pure high-school subject, three lack grade 11 and four have missing/suppressed results. Subject-specific exclusions leave eight high-school profiles outside Combined. Missing and suppressed values remain unavailable.

Mixed schools remain separate audit records. Thirty have eligible grades 3–8 Combined outcomes and 32 have eligible grade-11 Combined outcomes in the existing statewide assessment populations. They do not enter either proposed pure district cohort. Adding them would change the comparison population and require its own review.

Income is same-year Census Day K–12 FRPM eligibility, including income applications/forms, direct certification and categorical eligibility. The pure Combined income range is **10.42–100%** for grade schools and **56.60–100%** for high schools. It describes the whole school, while proficiency describes the tested grades. Valid-score counts come exclusively from CAASPP's exact scored performance-level denominator; CCD membership and FRPM enrollment never substitute for those counts. Combined is the equally weighted mean of Math and ELA rates. Grade 13 totals never recover missing or suppressed components.

## Remaining model gates

- Decide and label the intended district roster population, preserving affiliated-charter, alternative and special-education flags. The current usable pure Combined cohorts include 541 regular plus 20 alternative grade schools, and 85 regular plus 51 alternative high schools. Excluding a type changes the population and requires fresh counts and fits.
- Fit separate district models by year, assessment, pure level and subject. Review coverage, income spread, leverage, externally studentized residuals and influential observations. The 30-school planning floor alone is not approval.
- Verify every eligible model member's valid-score counts before propagating sampling intervals; one member missing counts removes intervals for the entire model. No shrinkage or enrollment adjustment is provided by studentization.
- Keep California thresholds, FRPM meaning, whole-school versus assessed-grade limitations and the one-year history explicit. Preserve statewide California, Chicago and NYC results. District residuals describe associations within the district population, not causal effectiveness or an interchangeable national scale.

## Sources and replay

The [committed audit](../data/source/los-angeles-district-audit.json) retains all selected native CCD directory rows and original CSV row references, exact school/district/NCES IDs, operational/charter/type/grade flags, full linked native FRPM profiles and source rows, excluded/unmatched records, complete expected-grade assessment raw values and source row references, and per-subject coverage/exclusions. Pinned SHA-256 values cover the official directory archive, its retained record subset, the compact California extract, and its official FRPM, assessment and field-layout sources. Input changes require a fresh source audit; successful source replay never grants model approval.

- [Official CCD 2024–25 school directory](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip): CSV member `ccd_sch_029_2425_w_1a_073025.csv`, including LEA attachment and published grade/charter flags.
- [Official 2024–25 CDE FRPM workbook](https://www.cde.ca.gov/Ds/ad/documents/frpm2425.xlsx): exact CDS components, same-year income fields and native school grade bounds.
- [2025 CAASPP Smarter Balanced research archive](https://caaspp-elpac.ets.org/caaspp/researchfiles/sb_ca2025_1_csv_v1.zip) and [official research-file layout](https://caaspp-elpac.ets.org/caaspp/docs/2025_SBAC_Research%20File%20Layout.xlsx): native school scope, funding types, subjects, tested grades, suppression and scored denominator.
- [California data guide](california-data.md) and [compact California extract](../data/source/california.json): the audited existing source and aggregation contract.

Normal offline validation reads the committed audit's retained directory inputs and the pinned California extract. It does not need raw downloads, alter SQLite, fit models or change the browser catalog:

```sh
.venv/bin/python scripts/audit_los_angeles.py
.venv/bin/python -m unittest discover -s tests -p 'test_los_angeles_district.py' -v
```

With the pinned official CCD archive already downloaded, reproduce the extract:

```sh
.venv/bin/python scripts/audit_los_angeles.py --extract
```

Extraction also checks exact pure cohort IDs against the committed CCD district planning queue. Two extraction runs should produce identical audit bytes. A source checksum, year, native ID, grade configuration, count or suppression change fails replay and requires renewed review.
