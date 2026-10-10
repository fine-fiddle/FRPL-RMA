# Gwinnett County source and cohort audit

Gwinnett County has a reproducible **source/cohort audit only** for 2024–25. It reconciles exact CCD district `LEAID=1302550`, native `ST_LEAID=GA-667`, with same-year individual-school direct certification and native Georgia Milestones EOG grades 3–8 outcomes. The [committed audit](../data/source/gwinnett-district-audit.json) retains status and scope `audit_pending`, `approved_for_source: false` and `approved_for_modeling: false`. Its 111 usable schools per subject exceed the prospective 30-school floor; independent district fits, numerical diagnostics, canonical integration and browser checks remain separate gates. No district comparison, high-school assessment model or mixed-school model is released by this unit.

## Exact roster and original source evidence

The [extractor and offline validator](../scripts/audit_gwinnett.py) retain all 141 original district directory records. All are operational: 140 Open and one New. No nonoperational record or native record outside the exact operational roster occurs in these pinned sources. There are 139 CCD Regular and two Alternative schools, with 140 noncharter and one charter. These classifications remain raw evidence; school names, type labels and planning counts never establish identities or select model members.

School joins require authoritative 12-digit NCES IDs and the same academic year. Georgia EDC's native `StateAssignedSchID` already includes the district prefix, such as `667-1005`; the cross-check is exactly `GA-` plus that value against CCD `ST_SCHID=GA-667-1005`. It is not a numeric school-code padding rule. Alcova Elementary (`130255003395`) demonstrates this join. Renamed display labels do not alter identity.

Every raw file has a retained official URL, local path, byte size and SHA-256. Every retained CSV record includes its original row number, header and complete raw fields. Native assessment records also retain the separate statewide compact-extract ordinal, whose first data record is ordinal 1; the full CSV's first data row is 2.

| Pinned original source | Retained district evidence |
|---|---:|
| [CCD directory Final 1a](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip) | 141 complete school records |
| [CCD membership Final 1a](https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip) | 1,099 school-total/grade records: 141 totals and 958 grade subtotals |
| [CCD lunch Final 2a](https://nces.ed.gov/ccd/Data/zip/ccd_sch_033_2425_l_2a_073025.zip) | 705 complete category records, including 141 Direct Certification school totals |
| [EDC Georgia v3.1](https://www.eddatacenter.org/api/data/3.1?state=GA&year=2025) | 942 School/All Students Math/ELA records; 234 G38 rows at 117 schools |
| [CCD Final 2a notes and metadata](https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx) | Original Georgia rows, worksheet names, headers and source-row references |
| [EDC v3.1 codebook](https://www.eddatacenter.org/data_codebooks/EDC_codebook_v3.1.xlsx) | Complete original worksheet cells and row references |

The membership subset preserves every exact district Education Unit Total and Subtotal 4 – By Grade row from the original archive. The 958 grade rows comprise 817 Reported and 141 Derived zeros for **Not Specified**, whose race and sex cells also say Not Specified. They are not offered Ungraded records. All 141 school totals are Reported and positive and sum to the reported district enrollment of 182,518. The planning record retains its original LEA total at CSV row 711258 and directory row 4210. Race/sex subgroup rows do not become school totals or tested denominators; the audit does not claim a count of every discarded district CSV row.

## Offered and enrolled population

Original offerings divide into 111 pure lower-grade, 24 pure high-school and six mixed schools. No operational school offers Ungraded, Grade 13 or Adult Education. Every lower-grade school offers at least one grade 3–8, and every lower-grade enrolled subtotal is reported and reconciles to its school membership. No positive enrolled grade lies outside reported offerings.

The inherited Georgia native contract requires complete unadjusted Yes/No offerings, highest grade 01–08, no offered grades 9–13/adult, complete reported lower-grade membership, reconciled school totals and explicit Reported/Derived zero outside-lower subtotals. Its conditional reported-zero Ungraded exception is retained in the validator, but **no Gwinnett school uses that exception**. Missing, suppressed or unknown grade evidence cannot establish zero. Offered grades and enrolled subtotals remain separate evidence; neither identifies the children with valid assessment scores.

| Independently reconstructed set | Schools | Applicable Math / ELA / Combined | Usable Math / ELA / Combined |
|---|---:|---:|---:|
| Native lower-grade configurations | 111 | 111 / 111 / 111 | 111 / 111 / 111 |
| Native configurations with a grade 3–8 offer | 111 | 111 / 111 / 111 | 111 / 111 / 111 |
| Positive-membership tested candidates | 111 | 111 / 111 / 111 | 111 / 111 / 111 |
| Native configurations with usable DC income | 111 | 111 / 111 / 111 | 111 / 111 / 111 |
| Native G38 pairs plus configuration and income; historical state profiles | 111 | 111 / 111 / 111 | 111 / 111 / 111 |
| Primary-only native configurations | 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Mixed offerings with native G38 pairs | 6 | 0 / 0 / 0 | 0 / 0 / 0 |

The 111 source-eligible schools are 110 noncharter and one attached-LEA charter, New Life Academy of Excellence (`130255003991`, `GA-667-1020`). All 111 happen to be CCD Regular schools. This observed composition is not a Regular-only policy; both Alternative records and all other roster flags remain retained. CCD has no virtual-status field, so its virtual status remains null. EDC separately reports `SchVirtual=No` on all 234 G38 subject rows; those metadata do not create a new exclusion.

Planning's 111 ES and 24 HS IDs are reconstructed independently from the original directory and total/grade records. Its ES set exactly equals source eligibility in this release, with no missing or additional IDs. This agreement is a discovery reconciliation, not an income/outcome filter or an approval. The 24 high-school configurations have no native G38 observations, and no high-school assessment is inferred from their size or offerings.

## Income proxy, state notes and roster mismatch

Income is reported nonnegative school-level CCD Direct Certification Education Unit Total divided by reported positive same-year school membership Education Unit Total, multiplied by 100. This is a **benefits/status eligibility proxy**, distinct from full household-income FRPL eligibility, all economic disadvantage or universal free meals. There is no CEP multiplier, free/reduced-lunch fallback, tested-subgroup ratio, enrollment weighting or prior-year income. All lunch categories remain raw, while only Direct Certification supplies the numerator.

All 141 district DC totals are Reported and positive. No zero, suppressed, missing or absent DC value is observed in this roster, but the rules preserve those distinctions: a reported numerator zero is valid zero recorded eligibility; absence or suppression remains unavailable. For example, Walnut Grove (`130255000046`) uses 137 DC / 819 same-year members, with original lunch row 115753 and membership row 2910686. The 111 eligible schools span 2.093–38.552%, with 111 distinct values, mean 20.493% and sample standard deviation 8.414 percentage points. These are descriptive source checks, with no regression or influence calculation in this phase.

The original Final 2a **Data Notes row 129, CCD-0060**, says Georgia added Medicaid-income eligibility in 2024 alongside SNAP/TANF and foster-child records. It documents an eligibility-era change associated with increased CEP participation; it does not authorize a multiplier, full-FRPL interpretation, previous-year backfill or an assertion of complete benefits coverage. **CCD Membership Metadata row 14** identifies state-funded programs and PK enrollment in outside programs. Consequently, the fall membership income denominator need not equal the tested G38 children.

**Data Notes row 133, DGO-0033**, names historical NCES `130255002906` in a reportable-program extension note spanning districts. That ID is absent from the entire pinned Final 1a directory and is explicitly retained in `later_release_note_roster_gaps`. This later Final 2a context does not add a current school, assign it a current type or justify a name-based join. The historical statewide snapshot's empty 033-filtered lunch-note subset is retained for replay, alongside the newly retained broader original Georgia notes; it does not imply Georgia has no relevant metadata caveats.

## Native proficiency and unavailable denominators

Only exact native School / All Students / All Students **Georgia Milestones EOG Regular G38**, Levels 3–4, school year 2024–25 and EDC V3.1 rates may enter the source cohort. The original G38 codebook row 44 identifies the SEA grades 3–8 aggregate. Exact published `ProficientOrAbove_percent` is converted from a proportion to percentage points. Individual G03–G08 rows remain evidence and never supply averaged or reconstructed school totals.

The [Georgia source](https://goews.georgia.gov/dashboards-data-report-card/downloadable-data) and [EDC technical documentation](https://www.eddatacenter.org/data_documentation/EDC_technical_documentation_v3.1.pdf) support the native aggregate provenance. This audit does not independently verify Georgia's assessment business rules or every valid-score denominator. EDC permits derivations within achievement-level data and tested-count fallbacks. Raw tested/proficient counts, participation and achievement-level cells therefore remain unverified evidence. No enrollment or participation proxy supplies a valid-score denominator, aggregation weight or sampling variance. Every verified subject count and sampling variance remains null, and intervals remain unavailable; any future point-only model must omit intervals modelwide.

Six mixed schools have G38 pairs but remain outside the proposed lower-grade population. Their observed zero rates remain **published zero proficiency**, distinct from missing or suppressed outcomes. International Transition Center (`130255004257`) publishes zero in both subjects. Devereux Ackerman Academy – Gwinnett (`130255004683`) publishes Math zero and ELA 25%, with tested cells `*`; neither the zeros nor the protected counts change its mixed-school scope. Combined requires both eligible native subject rates and is their equally weighted mean, not the fraction proficient in both. No grade-specific, mixed-school, EOC or alternate population is synthesized.

## Rebuild, replay and remaining gates

The audit pins the full committed statewide extract SHA-256 `3b6e55bba0055c582eb14a461697c64131a36e4cd555bca94965e5f77cac91fc` and Georgia snapshot canonical SHA-256 `46d47899274835d484be76ac9b13515afb96474c54b5a676c4c43539df289a67`. Complete retained raw records, headers, definitions, row references and exact discovery evidence have canonical SHA-256 `5f6e99cede2abfc989372132f8b3a58327eaa68a104d443d7855479a258f0242`. Raw workbook date cells use explicitly typed ISO values; ordinary counts, flags, text, missing cells and suppression markers preserve their original types.

Ordinary validation uses only the committed audit and pinned state extract, without raw downloads, workbook reads or an ignored membership cache:

```sh
.venv/bin/python scripts/audit_gwinnett.py
.venv/bin/python -m unittest discover -s tests -p 'test_gwinnett_audit.py' -v
```

Explicit extraction reopens every pinned original input, streams the complete original Deflate64 membership archive and rereads the full Georgia CSV and original definition workbooks. It does not reuse the saved audit's membership rows or modify the statewide membership cache:

```sh
.venv/bin/python scripts/audit_gwinnett.py --extract
```

An optional `--membership-evidence PATH` accepts a separately verified original district subset for bootstrap development; its provenance and all retained contents must match the same pinned contract. The two completed default `--extract` runs used the original archive path, and each exactly reproduces the committed **3,420,619 bytes**, SHA-256 **`d2b6c919d45a6116246368619afbac3ca782aec7dcf4f12109bad288c051cd50`**. Logs and independent output copies are retained under ignored `data/build/gwinnett-district-audit/producer-repeat-{one,two}` paths.

Nine focused tests pass, covering exact roster/discovery identities, offered/enrolled reconciliation, income-zero/absence/suppression separation, Georgia native prefixed IDs and assessment population, published mixed zero rates, charter retention, unknown denominators, original definition rows and roster mismatch, raw-disabled offline replay and typed adverse drift. The validator rejects changed source fingerprints, source cells, row numbers, years, IDs, headers, suppression, policy, cohorts, source/count booleans versus numbers, fabricated sampling evidence or unexpected model fields. The source audit fits no regressions and writes no canonical or browser data. Independent district numerical verification and separately validated integration remain pending; issue #3 and the candidate's discovery scope remain open.

Delivery validation passes 29 targeted Python tests, including the nine new source tests and the existing CCD, district-planning and Clark source checks. Two independent original-source reviews agree on all 141 school links, exact subject memberships and 132,557 typed fields; 30 scientific and 18 provenance corruption probes reject invalid changes. Both fresh original-archive extractions and offline replays agree. The canonical database and all nine tables, all 217 served files and all 215 regional files remain unchanged; the source README only gains this audit's paragraph. Existing catalog, provider and queue evidence remain unchanged: 52 datasets, 55 ready regions across 39 states, 72 latest assessment definitions, 11 state holds and 71/172 remaining district candidates. This source-only audit leaves Gwinnett in the queue.

## Independent numerical audit — completed phase, integration pending

The preceding source section records the completed historical source checkpoint. A separate [numerical audit](../data/source/gwinnett-model-audit.json), built by [audit_gwinnett_models.py](../scripts/audit_gwinnett_models.py), now verifies district fits from that immutable source audit, SHA-256 `d2b6c919d45a6116246368619afbac3ca782aec7dcf4f12109bad288c051cd50` (3,420,619 bytes). The source JSON, extractor and source tests remain unchanged. This numerical artifact retains **`approved_for_source: false`**, **`approved_for_modeling: false`** and status **`numerically_verified_pending_integration`**. It grants no canonical import or browser release.

Membership freezes the 141 operational identities and every original directory, membership, lunch, native assessment and definition record. The same 111 source-eligible lower-grade schools enter separate Math, ELA and Combined district OLS models: 110 noncharter plus New Life Academy of Excellence charter (`130255003991`). All are observed CCD Regular schools; no type, income-extreme or fit flag selects membership. The 24 high-school and six mixed configurations, including published mixed zero rates and protected raw counts, remain outside the district model population with their complete source evidence. The later-note ID `130255002906` remains absent from the pinned directory and never becomes a model member. Planning's coincident 111 ES set supplies no eligibility rule.

Each model uses same-year individual-school Direct Certification percentages and exact published native Georgia Milestones EOG Regular G38 Levels 3–4 proficiency. Combined is the equally weighted Math/ELA mean with its own fitted residual scale and externally studentized residuals; it is not the mean of the two subject studentized values. No statewide residuals, grade-averaged rates or enrollment weights are reused.

| Subject | Schools | Intercept | Slope | R² | Maximum Cook distance | Largest deleted-line shift |
|---|---:|---:|---:|---:|---:|---:|
| Math | 111 | 86.342926 | −1.759363 | 0.717496 | 0.147220 | 1.129694 pp |
| ELA | 111 | 78.476245 | −1.690211 | 0.701283 | 0.102537 | 0.942074 pp |
| Combined | 111 | 82.409586 | −1.724787 | 0.721298 | 0.131246 | 1.035884 pp |

Slopes express proficiency percentage points per percentage point of the **Direct Certification benefits proxy**. They are not slopes for full FRPL eligibility. Income spans 2.093–38.552%, with 111 distinct values, mean 20.493%, population standard deviation 8.376 and sample standard deviation 8.414 percentage points. The intercept/income design has rank two; its condition number is 58.617 in raw percentage units and 8.376 with centered income. Full residual standard error is `sqrt(SSE/(N−2))` with 109 degrees of freedom. Full and every deleted residual scale are finite and positive; all deleted slopes stay negative. The 30-school floor, full/deleted rank and numerical-scale guards pass with no hard holds. Numerical precision guards reject unresolved scales rather than inventing a variance floor.

Every eligible school is explicitly omitted and refitted once per subject, giving **333 separate deleted-school fits**, each with 110 training members and `N−3=108` residual degrees of freedom. The held-out externally studentized value uses the deleted fit's scale and prediction factor `1+h_deleted`. Independent centered full OLS verifies coefficients, native actuals, predictions, residuals and R²; centered closed-form leverage and explicit deletion predictions verify the shared fitter's studentization. Largest stored coefficient/prediction discrepancies are below `2.5e−13`, external-studentization discrepancies below `2.7e−14`, and the deleted-SSE identity error below `3.7e−12`.

The deleted-line shift is the largest absolute change between a full-fit and deleted-fit prediction over the observed income range, including its endpoints. It measures sensitivity of the fitted line, not an uncertainty interval or a performance correction. Maximum leverage is 0.052483 at Level Creek Elementary (`130255003397`). Rosebud Elementary (`130255003785`) has the largest Cook distance and largest absolute external residual in all three subjects; it remains included. Maximum absolute external residuals are 3.229483 / 2.656546 / 3.033398 for Math/ELA/Combined. New Life's retained Combined external residual is approximately −0.100.

Conventional descriptive review flags use `h>2p/N=4/111`, `Cook D>4/111` and `|external t|>2`. Each subject has nine leverage flags; Math/ELA/Combined have 5/7/6 Cook flags and 3/5/4 external-residual flags. They never remove a school, supply a school-quality label or turn an association into causal effectiveness. The Georgia eligibility-era change, benefits-proxy coverage, PK/outside-program membership, differing income and assessment populations, published-rate rounding and unverified native assessment business rules remain source limitations.

All verified score counts, display counts and sampling variances remain null for every input/result. Both interval endpoints are null and interval availability is false for each entire model. The shared fitter receives a zero variance vector solely as its internal point-estimate sentinel; no zero sampling variance is published. Raw EDC tested/proficient counts remain unverified, including mixed-school `*` cells. Studentization does not supply enrollment adjustment, shrinkage or valid-score denominator verification.

Rebuild and replay require only the frozen committed source audit and pinned state extract. They do not reopen original archives, read an ignored membership cache or change canonical/site data:

```sh
.venv/bin/python scripts/audit_gwinnett_models.py
.venv/bin/python scripts/audit_gwinnett_models.py --check
.venv/bin/python -m unittest discover -s tests -p 'test_gwinnett_models.py' -v
```

Eight focused numerical tests pass. They cover exact populations and complete source retention, manual deleted-school studentization/Cook/range-shift calculations, Combined's independent residual scale, null uncertainty and the internal sentinel, the 30-school/rank/full/deleted-scale gates, wrong or nonfinite shared-fit outputs, source/type/row/count drift, and narrow computed-float replay. Source metadata, raw values, actual outcomes, memberships and interval absence compare exactly with typed canonical fingerprints. Only computed metrics allow `2e−10` absolute **or** relative tolerance; independent in-build verification uses `2e−9` absolute error limits. NaN, infinity, boolean/numeric substitution and material drift reject.

The numerical audit remains evidence pending a separately validated canonical/static adapter and browser checks. No ready catalog, normalized release or new assessment-provider claim is created, and high/mixed assessment scope and valid-score denominator verification remain unapproved.

Delivery validation passes 46 targeted Python tests: eight new numerical checks, nine immutable source checks, eight shared-model checks, seven CCD checks, six district-planning checks and eight reference Clark numerical checks. Two independent reviews reconstruct the original-source inputs and verify all 333 deleted-school results. Two offline rebuilds reproduce exactly 7,207,706 bytes with SHA-256 `8589af1edb602efec119f90d796498342e74d6f74b90e3405aef5801649c4dee`; saved replay, Python syntax, 57 relative documentation links and diff checks pass. The source audit and historical guide prefix, all 152 existing scripts/tests, the canonical database and all nine tables, all 217 served files and all 215 regional files remain unchanged. Catalog, assessment-guide, source-hold and queue totals remain 52 datasets, 55 ready regions across 39 states, 72 latest definitions, 11 state holds and 71/172 remaining district candidates. Issue #3, Detroit #15 and incomplete source holds remain open.
