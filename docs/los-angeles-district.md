# Los Angeles Unified district audit

This guide records source, cohort and independent numerical audits for a possible 2024–25 Los Angeles Unified comparison under [issue #3](https://github.com/robot-assisted-projects/FRPL-RMA/issues/3). Separate district fits have been checked, but they have not been imported or added to the browser, and the source audit's modeling approval remains false. Existing California results retain their statewide comparison populations.

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

## Independent district model audit

The [numerical audit](../data/source/los-angeles-model-audit.json) fits six new district models directly from this exact roster and the audited proficiency/income inputs. It never copies statewide residuals. The predeclared baseline retains locally funded charters and alternative schools attached to the exact CCD LEA, excludes outside-roster reporting associations and mixed schools, and fits pure grade-school and pure high-school populations separately. Each subject has its own membership and fit; the practical minimum is 30 usable schools.

| Pure population | Subject | Schools | Income slope | R² | Maximum leverage | Maximum Cook's distance |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Grades 3–8 | Math | 561 | −0.6395 | 0.6681 | 0.0216 | 0.0274 |
| Grades 3–8 | ELA | 561 | −0.6374 | 0.7244 | 0.0216 | 0.0277 |
| Grades 3–8 | Combined | 561 | −0.6384 | 0.7188 | 0.0216 | 0.0281 |
| Grade 11 | Math | 137 | −0.9122 | 0.3002 | 0.1221 | 0.3344 |
| Grade 11 | ELA | 137 | −1.2854 | 0.2622 | 0.1226 | 0.1236 |
| Grade 11 | Combined | 136 | −1.1011 | 0.3023 | 0.1226 | 0.1461 |

Slopes describe the fitted change in percentage-point proficiency for one percentage point of FRPM eligibility. These associations do not establish school effectiveness. High-school income is tightly clustered: means are 91.34–91.40%, population standard deviations 8.76–8.78 points, and the range is 56.60–100%. Schools toward the lower end of that income range have greater leverage. The audit retains school identities, charter/alternative markers, deleted-fit coefficient and prediction changes, and influence diagnostics for review. Removing one member changes predictions within the observed income range by up to **3.50 proficiency points in high-school models**, versus **0.32 points in grade-school models**. No school is removed because of its residual, leverage or fit quality. The high-school Combined population includes 51 alternative schools among 136 schools; this remains an explicit population limitation.

All six income designs have rank two, nonzero outcome/residual variation and finite deleted-school scales. Every member of each subject model has verified native valid-score counts, so all six currently support conditional sampling intervals. Subject variances use the same Jeffreys-smoothed binomial approximation as California. Combined uses the equally weighted mean and the conservative covariance upper bound `(sqrt(v_math) + sqrt(v_ELA))² / 4`; the minimum subject count is retained only for display and never substitutes as a common variance denominator. If a future eligible member lacks a verified required count, intervals are omitted for the entire model.

An independent centered full fit checks coefficients, predictions, residuals and R². Every fitted school is also checked against an explicit leave-one-out least-squares fit with income recentered for that training set. A separately constructed centered hat matrix propagates every member's sampling variance through `I−H` and checks both interval endpoints. Maximum discrepancies are below **3.2 × 10⁻¹²** across all checks in this run, and below **9.5 × 10⁻¹⁴** for deletion/studentization/interval checks, within the fixed **2 × 10⁻⁹** independent-verification tolerance. No numerical hard holds were found. Numerical consistency does not itself approve source scope, import or publication.

## Remaining integration and release gates

- Preserve and label the chosen exact attached-LEA baseline, including locally funded charters and alternatives, in the eventual dataset's source snapshot. The usable pure Combined cohorts include 541 regular plus 20 alternative grade schools, and 85 regular plus 51 alternative high schools. Changing a type policy requires new membership, source review and fits.
- Import the independently checked district models as a distinct canonical dataset and browser comparison. Retain the selected population policy, identities and source fingerprints in provenance. Verify repeatable import, complete catalog preservation and district-versus-state labeling before release.
- Review the high-school income clustering, leverage, alternative-heavy composition and deleted-fit influence during integration. Numerical success and the 30-school floor alone are not approval. No shrinkage or enrollment adjustment is provided by studentization.
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

The numerical audit also runs entirely offline from the pinned committed roster audit and California source. It writes only its source-review JSON, never SQLite, site exports or a browser catalog:

```sh
.venv/bin/python scripts/audit_los_angeles_models.py
.venv/bin/python scripts/audit_los_angeles_models.py --check
.venv/bin/python -m unittest discover -s tests -p 'test_los_angeles_models.py' -v
```

Its selected policy and per-model school IDs have their own fingerprint. Repeated builds on the same environment should produce identical bytes. Replay permits an absolute tolerance of **2 × 10⁻¹⁰** or a relative tolerance of **2 × 10⁻¹⁰**, whichever is larger, for computed floating-point metrics across NumPy/BLAS platforms. Source identities, hashes, configuration, membership, valid counts and numerical inputs still compare exactly; numerical tolerance cannot authorize changed evidence.
