# Fairfax County source and cohort audit

Fairfax County Public Schools is a separately audited prospective **2024–25 grade-school comparison**, using the existing Virginia native source contract. This step establishes **152 usable schools for each Math, ELA and Combined subject**, from 162 exact native grade-school profiles. It does not fit district models, approve source/model release, import a canonical dataset or create a browser comparison. The source artifact retains `status: audit_pending`, `scope: audit_pending`, and both approval flags as false. Independent numerical diagnostics, canonical integration and browser verification remain required.

## Source evidence and exact identities

[`fairfax-district-audit.json`](../data/source/fairfax-district-audit.json) preserves the entire exact attached-district roster and source evidence:

- **223** original 2024–25 CCD directory records, all operational/Open, with all offered-grade flags, exact status/type/charter values, full source columns and original CSV row references.
- **1,689** original CCD school membership records: **199** school totals and **1,490** complete retained grade subtotals. The other 24 directory programs have no membership rows; absence is not zero.
- **965** original CCD lunch records, retained as supplemental evidence. They never replace the native Virginia individual economic-status measure.
- **195** exact native division-29 profiles from the complete **1,812-school** audited Virginia inventory. Each original HTML page is checksum-verified and reparsed; all retained raw year labels, grade tables, subgroup counts, Math/ELA chart values and performance categories match the complete committed extract.
- Five original definition/population HTML fragments per native school, with original source line references, covering SOL/VAAP scope, reading and mathematics grade/course populations, September 30 Fall Membership and individual economic status.
- All eight worksheets of the original CCD Final 2a notes workbook, including all 561 Data Notes rows, headers, membership/grade metadata, business rules and post-submission revisions. Workbook dates retain explicitly typed ISO values.

Every raw source has its official URL and SHA-256 checksum. The entire committed [`virginia.json`](../data/source/virginia.json) is pinned to SHA-256 `fff223450f4a03d1763e8704d7b2b95cd67fde27213e67582c457de24febfccc`; offline validation checks the complete statewide extract before replaying the district subset. The full retained original input fingerprint is `8be5fa3da5953fe1a9229e574a5ac67db7486e30ec73de80e365e26bcf75f7bd`.

The exact district is NCES LEA **5101260**, native **VA-029**. CCD `ST_SCHID` already contains the complete seven-digit native division/school key: for example, `VA-029-0290131` maps to `0290131`, whose same-profile native Division Number is `29` and School Number is `131`. Remove only the exact `VA-029-` prefix; do not prepend the division again, shorten the source code, match names or construct school URLs from names. All 195 native profiles cross-check to exact CCD identities; no native profile lies outside the complete attached roster. Names and current category descriptions remain display evidence and may postdate the results.

## Prospective populations and outside records

Population membership follows the existing [Virginia enrolled-grade contract](virginia-data.md), using the profile's exact **2024-2025** grade counts. Schools with positive native grade 3–8 membership and no positive high-school membership are grade schools; high-only and mixed grade 3–8/high-school spans are separate populations. Positive unsupported grade labels remain unclassified. Complete CCD offered flags and strict offered intersections are separate completeness diagnostics, never an extra population filter.

| Native same-year population | Profiles | Usable Math | Usable ELA | Usable Combined | Prospective release |
| --- | ---: | ---: | ---: | ---: | --- |
| Grade schools | 162 | 152 | 152 | 152 | Numerical and integration audits pending |
| High schools | 25 | 23 | 23 | 23 | Below 30-school floor; unreleased |
| Mixed-grade schools | 4 | 1 | 1 | 1 | Below 30-school floor; unreleased |
| Unclassified | 4 | 0 | 0 | 0 | No approved native population |
| CCD schools without native profiles | 28 | 0 | 0 | 0 | Native income/outcomes unavailable |

All 162 native grade schools independently match the strict complete CCD pure-grade offering intersection and the 162 planning grade-school IDs. That agreement is reported after reconstruction; the planning screen did not select income or outcomes. All 152 usable grade schools are observed as Regular School and noncharter. Type, current category, admissions labels and model fit are not selection rules. The complete roster retains 194 regular, 11 alternative, seven special-education and 11 career/technical schools, all noncharter. No authoritative admissions or virtual-status classification is supplied.

Three native profiles—Bailey's Elementary `0290550`, Fort Belvoir Elementary `0292224` and McNair Elementary `0292231`—are primary-only with no applicable grade 3–8 or high-school population; their published missing assessment arrays remain missing. Lake Braddock Secondary `0290090` has grades 7–12 plus explicitly published **Post Graduate: `1`** in 2024–25. That positive unsupported label keeps its native population unclassified, despite its mixed CCD offerings, reconciled native income and published Math **87%**/ELA **90%**. It is not relabeled Ungraded, silently truncated or included in the mixed cohort.

Every one of the **28** CCD-only identities is retained individually, with its exact source records and missing-native explanation. Four PK-only centers have **784** reported CCD pupils. The other 24 programs explicitly report `NOGRADES: Yes`, every offered-grade flag `No`, including `G_UG_OFFERED: No`, and have no original CCD membership rows. These records establish neither zero enrollment nor Ungraded enrollment. None offers grades 3–8, so the missing native records do not conceal a school in the complete prospective pure-grade population. They still receive no imputed native income, outcome or source approval.

## Native outcomes, income and count limitations

Outcomes are the exact profile's native **All Students** subject option **0** Mathematics or English Reading **Passed** percentages for 2024–25. The source Assessment tab includes **SOL and VAAP**. Passed includes proficient and advanced; their separately rounded category percentages are retained rather than summed to replace Passed. No grade/course percentages are averaged. Lower-grade mathematics totals can include secondary course tests; varying tested grade/course mixes remain a limitation. Combined is the equal mean of eligible Math and ELA pass percentages, not the fraction proficient in both.

[VDOE's April 17, 2025 standards update](https://content.govdelivery.com/accounts/VADOE/bulletins/3dc0d1d) identifies spring 2025 as the first SOL administration for the new 2023 mathematics and 2024 English standards. Older and later displayed profile years remain raw evidence but do not enter this proposed single-year snapshot. The full native definition and coverage notes are retained independently from supplemental CCD notes.

Economic disadvantage uses the native same-profile September 30 All Students and individually classified **Economically Disadvantaged** counts. The source definition includes meal eligibility, TANF, Medicaid eligibility, migrant status or homelessness; this is broader than FRPL alone and differs from portal CEP meal-service coverage and CCD direct certification. ED plus non-ED, every same-year grade subtotal and the grade-table total must reconcile exactly to All Students. Required counts and the displayed ED percentage must be unsuppressed. Native comma-formatted counts are parsed numerically while their exact original strings remain retained.

**15** native profiles fail the complete grade-count reconciliation contract: ten grade schools, two high schools and three mixed schools. Their masked/missing grade cells stay unavailable even when the other subtotals appear to imply zero. A suppressed ED count is never inferred from the non-ED complement. The 152 usable grade-school income percentages are distinct, ranging from **1.7013%** to **98.7037%**; this source audit computes descriptive coverage only, without regression diagnostics.

**128** native profiles have stale displayed ED percentages that differ from the independently reconciled count ratios. The model input proposal uses `100 × ED / All Students` only after complete native count reconciliation and retains the inconsistent display percentages. Native membership totals also differ from CCD: the 195 native profiles sum to **179,770**, while those same 195 CCD schools sum to **178,539**; 163 individual totals differ. All 199 reported CCD school totals sum to **179,323**, agreeing with the planning LEA total. These are source/timing/coverage diagnostics; CCD enrollment never repairs or replaces native income or grade membership.

The native profiles publish rounded pass percentages without verified exact valid-score denominators. Every prospective subject's valid-score count, sampling variance and interval remains unavailable. Enrollment, CCD counts, ED counts, portal CSV Record Count and participation are never denominator substitutes. This audit fits no models and creates no district results; future studentization cannot supply enrollment adjustment, shrinkage or missing intervals.

## Rebuild and verification

Ordinary offline replay requires only the committed audit and complete Virginia extract:

```sh
.venv/bin/python scripts/audit_fairfax.py
.venv/bin/python -m unittest discover -s tests -p 'test_fairfax_source.py' -v
```

Re-extract from the pinned original CCD archives, notes workbook and every saved native Fairfax profile:

```sh
.venv/bin/python scripts/audit_fairfax.py --extract
```

The script streams the original Deflate64 school membership archive with `unzip -p`. `--membership-evidence` optionally accepts a separately verified complete original district subset with original archive provenance, header and CSV row references; the resulting full input fingerprint must still match exactly. Default extraction always reopens the original membership archive. No planning count participates in native eligibility.

Validation rejects changed whole-state fingerprints, source URLs/checksums, exact identities/years, raw counts/flags, missing record deletions, row/header references, native definitions, population membership, floor/hold flags, manufactured valid-score counts and model payloads. The audit does not call canonical imports or statistical fitting. Preserve existing statewide and district comparisons while the later Fairfax numerical and integration steps are completed.

The completed source unit passed **49 targeted Python tests**, syntax/diff checks, **60 local documentation links** and two independent original-source reviews. One reviewer checked **106,323** typed original/derived fields; the other checked **66,953** source fields, **19,086** original native HTML fields and all **975** definition fragments. Their **53** additional scientific/provenance corruption probes were rejected. Two fresh full-original-archive rebuilds reproduce the exact **4,854,357-byte** committed artifact, SHA-256 `cf2fe4641d7b274fc46abff23b019bf044cd7404e484bddb408ac2eb8d145723`; offline replay also passes.

The canonical database and all nine tables are byte-identical to the pre-audit snapshot. All **221 served files / 219 regional files** and **160 existing code/test/UI files** remain unchanged; the only existing data-file change is a source README insertion. Catalog/assessment/provider/planning JSON and previous audits remain unchanged: **53 datasets / 56 ready regions / 39 states / 73 latest definitions**, **11 state holds**, and **70 first-tier / 172 second-tier district candidates**. This source-only step creates no district fits or browser behavior to validate. The next unit independently verifies the 152-school district Math/ELA/Combined full and deleted-school fits, leverage, income spread and sensitivity before canonical/browser integration. High/mixed and unclassified populations remain unreleased.

## Independent numerical audit · completed phase, integration pending

The [numerical audit](../data/source/fairfax-model-audit.json), rebuilt by [audit_fairfax_models.py](../scripts/audit_fairfax_models.py), now verifies three separate district models from the immutable source audit above. It retains `scope: numerical_audit_only`, `status: numerically_verified_pending_integration` and both approval flags as false. The historical source audit, extractor and tests stay unchanged; this numerical step supplies evidence for a later canonical/static adapter and browser checks.

Each 2024–25 Math, ELA and Combined model retains all **152** source-eligible native grade schools from the complete **162-profile** grade population. The ten unavailable native incomes remain explicit exclusions. Complete evidence preserves all 223 operational CCD records, 195 native profiles, original definition fragments and whole-state source fingerprint. High/mixed populations remain below the floor at 23/1 usable schools; three primary-only profiles, Lake Braddock's positive Post Graduate count and all 28 missing native profiles remain outside this grade-school cohort. Neither the coincident planning/CCD offering set, observed Regular/noncharter composition, current categories nor influence diagnostics select membership.

Income is the exact reconciled native September 30 individual economic-status percentage for the same year. It is broader than FRPL and never replaced by stale displayed percentages, CCD direct certification, CEP meal coverage or earlier-year observations. Outcomes are direct native All Students schoolwide SOL/VAAP Passed percentages, using the existing `SOL/VAAP 2025 standards · grade-school totals` assessment name. No individual-grade/course rates are averaged. Combined is the equal Math/ELA mean with its own residual scale and externally studentized values; it is not the mean of subject studentized residuals. Spring 2025 SOL standards changes remain explicit, and no earlier profile year enters these models.

| Subject | Schools | Intercept | Slope | R² | Maximum Cook distance | Largest deleted-line shift |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Math | 152 | 95.021410 | −0.439943 | 0.855474 | 0.119340 | 0.447468 pp |
| ELA | 152 | 95.340481 | −0.475574 | 0.862162 | 0.078611 | 0.380240 pp |
| Combined | 152 | 95.180945 | −0.457758 | 0.871487 | 0.100536 | 0.399247 pp |

Slopes measure proficiency percentage points per percentage point of native individual economic status. Schools receive equal fitting weight. Income spans **1.7013–98.7037%**, with **152** distinct values, mean **44.7763%**, population standard deviation **31.1444** and sample standard deviation **31.2473** percentage points. The full and every deleted design have rank two; every residual scale is finite and positive, and every deleted slope remains negative. The 30-school, rank and numerical-scale guards pass with no hard holds. Predictions remain unclipped; diagnostics do not establish causal school effectiveness.

Every eligible school is explicitly omitted and refitted once per subject: **456 deleted-school fits**, each with **151** training schools and **149** residual degrees of freedom. Full residual scale uses **150** degrees of freedom. The held-out external residual uses the deleted scale and prediction factor `1+h_deleted`, independently agreeing with the full-residual/leverage studentization formula. In-build centered OLS independently checks coefficients, exact native actuals, predictions, residuals, R² and leverage. Coefficient/prediction discrepancies are below `8.6e−14`, studentization discrepancies below `1.6e−14`, and deleted-SSE identity discrepancies below `2.8e−12`.

The deleted-line shift is the greatest absolute prediction change between full and deleted fits over the observed income range, including both endpoints. The largest shift is **0.447468 proficiency points**. It describes sensitivity of the fitted line, not an uncertainty interval or school-performance adjustment. Maximum leverage is **0.02630391**, below the descriptive `2p/N=4/152` threshold. Math/ELA/Combined have **0/0/0** leverage flags, **13/14/12** Cook-distance flags and **8/11/11** `|external t|>2` flags. Riverside Elementary (`0291820`) has the largest Cook distance and absolute external residual in Math/Combined; Forest Edge Elementary (`0290070`) does in ELA. All remain included. Maximum absolute external residuals are **3.553984 / 3.017310 / 3.240432** for Math/ELA/Combined.

All 152 native Math and ELA pass rates are published whole percentages. Adding the separately published Advanced and Proficient categories differs from direct Passed in **39 Math** and **37 ELA** records; one further Math record (`0291640`) has an incomplete category pair despite an available direct Passed rate. These original category values remain retained, while the model uses direct Passed. No category sum replaces a published rate or reconstructs a suppressed category.

Rounded schoolwide percentages, combined SOL/VAAP coverage, varying tested grade/course mixes, differences between Fall Membership and the assessed population, and the broader native economic-status measure remain limitations. Studentization supplies no enrollment adjustment or shrinkage. There is no verified valid-score denominator: all counts, sampling variances and interval endpoints stay null for every member and each entire model. A zero variance vector passed to the shared fitter is solely an internal point-estimate sentinel; no zero sampling variance or generated endpoint is published.

Rebuild and offline replay use only committed, pinned source evidence. They do not reopen original archives or alter canonical/browser data:

```sh
.venv/bin/python scripts/audit_fairfax_models.py
.venv/bin/python scripts/audit_fairfax_models.py --check
.venv/bin/python -m unittest discover -s tests -p 'test_fairfax_models.py' -v
```

Typed raw values, source URLs/checksums/rows, identities, years, cohort membership, exact native outcomes and absent uncertainty compare exactly. Only computed metrics permit `2e−10` absolute or relative replay tolerance; independent in-build checks use `2e−9` absolute limits. Nonfinite results, numeric/boolean substitution, model-set drift, altered raw records, inferred counts or endpoints and material numerical changes are rejected. Canonical/browser integration remains the next gate; no ready comparison or new assessment-provider binding is created, and high/mixed/unclassified populations remain unreleased.

Delivery validation passes **66 targeted Python tests**: ten new numerical tests, nineteen immutable source tests, eight native Virginia tests, eight shared-model tests, seven CCD tests, six district-planning tests and eight reference Gwinnett numerical tests. Two independent original-source reviews verify every one of the **456** deleted-school results: a scalar oracle checks **6,012** computed values, and a NumPy oracle checks **6,132**, alongside **147,638** typed source/input fields, **19,086** original HTML fields and **975** definition fragments. Their **70** additional scientific/provenance corruption checks reject. Direct fitter calls require exact frozen native inputs and the complete eligible membership before numerical work, preventing altered values or diagnostic exclusions from silently changing the models.

Two fresh offline builds reproduce exactly **8,405,900 bytes**, SHA-256 `d95fe3f778d0daca09a877f70f87ca746fb8fa049532923e8341990ea007fda3`. Offline replay, syntax/diff checks and **65** local documentation links pass. The historical guide prefix, source audit, source extractor/tests and every earlier JSON artifact remain unchanged. The only existing data-file change is a source README insertion. The canonical database/all nine tables, all **221 served / 219 regional files** and **162 existing code/test/UI files** remain unchanged. Catalog, guide and queue totals remain **53 datasets / 56 ready regions / 39 states / 73 latest definitions / 11 state holds / 70 first-tier and 172 second-tier candidates**. This numerical-only step releases no browser comparison. A separately validated canonical/static adapter, repeat-import/export preservation and HTTP browser checks are next; #3, Detroit #15 and incomplete state holds remain open.
