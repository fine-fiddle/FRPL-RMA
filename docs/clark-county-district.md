# Clark County district comparison

Clark County has source/cohort and numerical audits plus a separate canonical/static adapter for 2024–25. The source phase reconciles its exact CCD roster (`LEAID=3200060`, `ST_LEAID=NV-02`) with same-year individual-school direct certification, enrollment and native Nevada SBAC grades 3–8 outcomes. Both immutable audits retain district source and modeling approval **false**; neither historical record grants a browser release. The separately validated [normalized release](../data/source/clark-county.json) produces the [district comparison](../data/clark-county/schools.json) from 289 native source profiles and three independent 286-school models. Planning's 306,038 district enrollment and potential 296 ES / 10 HS schools remain discovery evidence, not approved model populations.

## Exact identity and retained sources

The [committed source audit](../data/source/clark-county-district-audit.json) retains all 380 directory records, including one Future school, and links the 379 operational schools (378 Open, one New). Membership, lunch and assessment join through authoritative 12-digit `NCESSCH` and the same year. EDC's native district/school codes are cross-checked against `NV-02-sssss` using fixed two-/five-digit padding after the NCES join. Names never establish identity: EDC retains older names for the renamed FuturEdge campuses while the IDs agree.

The [extractor/replay validator](../scripts/audit_clark_county.py) pins each raw file's URL, path, byte size and SHA-256; the complete retained inputs additionally have canonical JSON SHA-256 `1881df8584fa5a514217b7983e005dfd8777617b90e20b93f92a3aa052dcee86`. Source inputs include original CSV headers and record row references:

| Source | Retained Clark evidence |
|---|---:|
| [CCD directory Final 1a](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip) | 380 full directory records |
| [CCD membership Final 1a](https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip) | 3,371 full total/grade records from 49,009 district rows; 379 totals and grade maps |
| [CCD school lunch Final 2a](https://nces.ed.gov/ccd/Data/zip/ccd_sch_033_2425_l_2a_073025.zip) | 1,785 full category rows; 357 Direct Certification school totals |
| [EDC Nevada v3.1](https://www.eddatacenter.org/api/data/3.1?state=NV&year=2025) | 2,468 full school All Students Math/ELA rows across individual grades and G38; 310 native G38 subject pairs |

Full-CSV assessment row numbers and the prior statewide compact-extract ordinal are both retained with their distinct bases. No retained native membership, lunch or assessment record falls outside the operational roster. Individual grade rows remain audit evidence and never substitute for a native G38 total or an aggregation weight. The extract also pins the EDC codebook/technical documentation, NCES definitions and SEA lunch notes through the immutable [state snapshot](../data/source/ccd-state-snapshots.json). Its Nevada contract is validated without importing or fitting; prior statewide approval is historical evidence and does not approve district models.

## Offered grades and Nevada's enrollment exception

Every operational Clark school reports `G_UG_OFFERED=Yes`. The descriptive graded-offer buckets are 302 lower, 55 high and 22 mixed, **all also offering ungraded programs**; they are not strictly pure offered-grade schools. There is no virtual-status field in this CCD directory.

The existing [Nevada source contract](ccd-state-data.md) resolves ungraded offerings with explicit reported-zero ungraded membership, complete reported lower-grade subtotals reconciled to school total enrollment, and zero outside-lower enrollment with reported/derived flags. It also requires unadjusted complete Yes/No offers, highest grade 01–08, and no offered grades 9–13 or adult education. Missing or protected counts never mean zero. This district audit preserves that definition, rather than silently adopting the planning screen's cohort or treating UG as absent.

| Distinct set | Schools | Offered grade 3–8 applicable | Usable Math / ELA / Combined |
|---|---:|---:|---:|
| Native reconciled lower-grade configurations | 299 | 298 | 286 / 286 / 286 |
| Native configurations with a tested-grade offer | 298 | 298 | 286 / 286 / 286 |
| Positive-membership tested candidates (planning cross-check) | 296 | 296 | 286 / 286 / 286 |
| Native configurations with usable DC income | 291 | 290 | 286 / 286 / 286 |
| Native G38 pairs with eligible configuration and income; exact historical source profiles | 289 | 289 | 286 / 286 / 286 |

Mitchell Andrew ES (`320006000012`, PK–2) is a native lower-grade configuration with usable income (125 DC / 356 members), but no applicable tested-grade offer or G38 row. Three other primary sites (`320006000740`, `320006000797`, `320006000814`) have highest offered grade KG and are outside the existing native grade-school approval. They remain explicit directory records.

Lundy Earl B ES (`320006000080`) and Juvenile Detention 3–5 ES (`320006000807`) retain native tested-grade configurations but zero total enrollment and unavailable income/outcomes. Removing these two from 298 applicable offerings yields planning's 296; a zero total does not become a valid denominator. Variety ES (`320006000619`, special education) has usable income (22 / 28) and an applicable offer, but no native G38 pair. Thus 295 of the 299 configurations have G38 pairs, with 15 additional pairs at mixed schools remaining outside the approved lower-grade population. No high-school or ACT assessment rows are available in this source path; the potential 10 HS sites remain discovery only.

## Income, outcomes and missingness

Income is reported nonnegative same-year CCD Direct Certification `Education Unit Total` divided by reported positive membership `Education Unit Total`, including pre-K. This is a benefits/status proxy, distinct from household-income FRPL eligibility or universal free meals. There is no claiming multiplier, free-lunch/FRPL fallback, tested-subgroup ratio or backfill. All categories are retained raw, but only Direct Certification supplies the numerator. Among 299 configurations, income is unavailable at two zero-enrollment sites, five schools with absent DC, and Goodsprings ES (`320006000037`) with suppressed blank DC. Absence, suppression and zero remain separate.

Published exact `ProficientOrAbove_percent` supplies point rates only for SBAC Regular school/All Students/All Students `G38`, `Levels 3-4`, school year 2024–25 and EDC `V3.1`. The [EDC documentation](https://www.eddatacenter.org/data_documentation/EDC_technical_documentation_v3.1.pdf) describes SEA-native grades 3–8 totals. Nevada's source-level assessment business rules and valid-score denominators have not been independently verified here. An offered grade is not proof that every student/grade contributes to the published aggregate. EDC may construct achievement-level counts; raw tested, proficient, participation and level cells remain unused evidence. Every subject's verified valid-score count and sampling variance remain null; every future district model must omit sampling intervals modelwide unless independently verified denominators are obtained for every eligible member.

The 289 historical source profiles include Blue Diamond (`320006000010`), Reid Harry (`320006000099`) and Miley Achievement (`320006000607`, special education), each with both published subject rates `*`. All remain profiles with explicit exclusions, yielding 286 usable points per subject. Combined requires both exact eligible subject rates and is their equally weighted mean, not the percentage proficient in both. No suppressed or ranged value is reconstructed from counts or individual-grade rates.

The 286 usable schools are all CCD Regular: 283 noncharter and three attached-LEA charters (`320006000670`, `320006000717`, `320006000756`). Alternative, special-education and career/technical directory flags remain retained; absence of eligible points in those types follows source coverage, not a blanket type exclusion or a fit decision. The 289 source profiles retain Miley's unavailable special-education outcomes. Eligible income spans 9.758–86.774%, with 286 distinct values, mean 52.611% and sample standard deviation 16.175 percentage points; the source phase reports these as descriptive cohort evidence, with numerical checks documented below.

EDC's G38 rows report 614 `SchVirtual=No`, four `Yes`, and two `Supplemental virtual` observations across subject rows. Odyssey K–5 (`320006000488`, supplemental virtual) and NV Learning Academy ES (`320006000949`, virtual) lack usable DC income. NV Learning Academy JSHS (`320006000845`, virtual) has mixed offerings. These source exclusions remain distinct from virtual metadata; virtual labels do not add a new exclusion policy, and CCD virtual status remains null.

The retained Nevada Final 2a `CCD-0007` note says some districts classified directly certified students as reduced-price rather than free lunch. Its 18 listed schools are outside Clark County. This remains a Nevada definition/reporting caveat; the audit does not infer a Clark-specific allocation failure or substitute other meal categories.

## Source replay

Ordinary validation requires only this committed audit plus the pinned state snapshot, without raw downloads, membership caches or workbook access:

```sh
.venv/bin/python scripts/audit_clark_county.py
.venv/bin/python -m unittest discover -s tests -p 'test_clark_county_district.py' -v
```

Explicit extraction reads pinned downloaded archives and the EDC CSV, streams the official Deflate64 membership archive, and never alters the ignored membership cache:

```sh
.venv/bin/python scripts/audit_clark_county.py --extract
```

The validator rejects changed raw identities, years, native source fingerprints, headers/row references, grade counts, suppression, exclusions, cohort memberships or fabricated denominators/intervals. Tests also exercise the reported-zero-UG/reconciliation rule independently, primary/zero-income missingness, exact renamed-school identity, and offline replay. Repeated extraction must produce identical bytes.

## Numerical phase: independently verified

The [numerical audit](../data/source/clark-county-model-audit.json) and [offline replay script](../scripts/audit_clark_county_models.py) pin the immutable source audit SHA-256 `7cac2c5521f7a5995956b5b190df616e68f61ac756aed5ca09d2228449269823`. They freeze exact school IDs and policy for all 379 operational schools, 299 native lower-grade configurations, 298 applicable offerings, 296 positive-membership tested candidates and 289 historical source profiles. Each subject independently selects its 286 eligible source members; the three current sets agree. All 13 excluded native configurations, all 80 operational records outside the native configuration, raw source rows, charter/type/virtual metadata and exclusion reasons remain auditable. Neither influence flags nor fit quality remove schools.

Three same-year district OLS models fit eligible native Math, ELA and Combined proficiency against the individual-school CCD DC percentage. They use externally studentized residuals and never reuse statewide predictions or residuals. Combined is fitted independently to its exact equally weighted subject mean; its residual scale and studentized result are not the average of subject studentized results.

| Subject | N | Intercept | Slope per income percentage point | R² | Maximum Cook distance | Largest deleted-line prediction shift |
|---|---:|---:|---:|---:|---:|---:|
| Math | 286 | 79.075899 | −0.837813 | 0.654063 | 0.042083 | 0.463161 pp |
| ELA | 286 | 89.220615 | −0.874864 | 0.777741 | 0.075513 | 0.492056 pp |
| Combined | 286 | 84.148257 | −0.856338 | 0.736944 | 0.045568 | 0.404694 pp |

The deleted-line shift is the largest absolute difference between the full-fit line and each deleted-school line over the observed income range, including its endpoints. Income design rank is two; the condition number is 187.630 with an uncentered intercept and 16.146 when income is centered. Maximum leverage is 0.028125 in all three models. Full and every deleted residual scale are finite and positive, and every deleted slope remains negative. Each model passes the 30-school floor, rank and residual/deletion-scale guards; there are no numerical hard holds. Finite precision guards reject unresolved scales rather than manufacturing a variance floor.

Conventional review flags use leverage `h>2p/N=4/286`, Cook distance `D>4/N` and `|external t|>2`. There are 20 leverage flags in each model, 9/7/8 Cook flags and 13/12/9 external-residual flags for Math/ELA/Combined. These are descriptive review signals, not causal evidence, school-quality labels, automatic exclusions or newly invented release thresholds. Published-rate rounding, the benefits-based income proxy, differing enrollment/assessment populations, unverified SEA business rules and absent verified valid-score denominators remain limitations.

The script independently verifies centered full-fit coefficients, every actual/predicted/residual value and R², plus closed-form centered leverage. It explicitly refits every deletion—858 fits across three subjects—using deleted-school SSE with `N−3=283` degrees of freedom and the held-out prediction factor `1+h_deleted`. This check agrees with the shared `fit_model` externally studentized results; the largest full-fit coefficient/prediction discrepancy is below `1.9e−13`, studentization below `2.9e−14`, and the deleted-SSE algebraic identity below `7.3e−12`.

Every model input/result has null valid-score counts and null sampling variances; every low/high endpoint is null and interval availability is false for the entire model. The shared helper receives a zero vector solely as its point-estimate computational sentinel; zero sampling variance and generated interval endpoints are never exposed. Raw EDC tested/proficient counts remain retained unverified evidence. Numerical success does not verify denominators or remove source limitations.

```sh
.venv/bin/python scripts/audit_clark_county_models.py
.venv/bin/python scripts/audit_clark_county_models.py --check
.venv/bin/python -m unittest discover -s tests -p 'test_clark_county_models.py' -v
```

Rebuild and saved-audit replay are offline; two rebuilds produce identical bytes on this environment. Replay allows `2e−10` absolute **or** relative tolerance for computed floating-point metrics, while IDs, year, exact input/source values, policy, population, counts and interval absence compare exactly. Tests cover manual deleted-school studentization/Cook calculations, Combined's separate fit, point-only missingness, source/population/count/metric drift, the 30-school floor, rank/full/deleted-scale failures and incorrect shared-fit results.

Both immutable audits remain source/numerical evidence with approval false and their historical pending-integration status. Release belongs to the separately validated adapter below. No audit count, conventional influence flag or statewide residual approves or replaces integration checks; results describe associations rather than causal school effectiveness or overall quality.

## Canonical and static integration

The [district adapter](../scripts/prepare_clark_county.py) uses dataset **`nv-clark-county-2025`**, region/geography **`clark-county`**, state **NV**, name **Clark County** and explicit **`statewide: false`**. It pins numerical audit SHA-256 `44304bb83de3bb9656490bfcc933685fa5e29782460fa474d4a94fbd2e0332c5` and the source audit pin above, replays both and rejects unresolved population or numerical holds. The [normalized extract](../data/source/clark-county.json) and [district descriptor](../data/clark-county/catalog.json) carry `release_status`/status `ready`; both historical audits remain unchanged with false approval flags.

The normalized release retains all 289 historical native source profiles, including the three suppressed-outcome profiles. Raw directory, membership/grade, direct-certification and native assessment values remain auditable by exact NCES/native IDs and source-row references. Coverage also retains the full 379 operational roster, 299 native lower-grade configurations, 298 applicable offerings, 296 positive-membership planning candidates, 13 configuration exclusions and 80 operational records outside native configuration. Neither a missing income/outcome record nor an excluded offered configuration is silently counted as a modeled point.

The native Nevada assessment name, year, ES level, grades, published standard and source URL match the existing statewide definition exactly, including its original state-definition wording. The district model scope explicitly identifies the independent district population. Canonical source, income-definition, assessment-definition and model IDs use the separate dataset namespace; the same 12-digit NCES IDs can appear in statewide and district datasets without replacing either population. Each subject is fitted separately to its exact frozen membership. Combined uses the equally weighted native subject mean and its own external studentization.

The canonical district has 289 school/income records, 578 native subject observations, three model runs and 858 model-result rows. All verified valid-score counts and interval endpoints remain null; raw EDC counts retain their unverified status. Browser metrics do not expose the shared numerical helper's internal variance sentinel. No coordinates, boundaries or admissions classifications are invented. Only the 2024–25 history point is supplied, and no high-school or mixed assessment series is approved.

The assessment guide gives the district its own Nevada link and explicitly binds its exact definition to the already audited 2024–25 Smarter Balanced consortium developer evidence. Legal ownership, delivery contracts and relative target ambition remain unverified. District and statewide assessment-family colors do not make their predictions or residuals interchangeable.

Eight integration tests verify exact source/raw inputs, profile and model populations, immutable audit hashes, all current/history metrics, counts and interval absence, native definitions and strict typed corruption rejection. Isolated repeated preparations preserve the actual statewide Nevada release and same-ID sentinel rows. The adapter also ran twice against the established full canonical store: district rows and all four exports are identical, all preexisting row counts and hashes across nine tables are unchanged, foreign-key checks are empty and SQLite integrity is `ok`. Independent centered OLS and explicit deleted-school checks agree with all 858 canonical and browser results, with maximum prediction error below `1.9e−13` and studentization below `2.5e−14`. Every district prediction differs from its corresponding statewide prediction.

The catalog now has 48 datasets and 51 ready regions across the same 39 released states; all 50 prior regions are preserved. The guide has 68 latest released definitions and nine explicit consortium developer bindings. Removing only Clark additions reproduces the prior manifest and guide content exactly. All 195 old regional browser files remain byte-identical. Of 268 previously tracked data files, 263 are unchanged; the five intended changes are the manifest, assessment guide, exact Clark planning-scope field, provider evidence extension and source README. All eight previous provider bindings and all three evidence sources remain unchanged. The planning queue now has 75 first-tier and 172 second-tier remaining candidates; native planning counts do not change.

All **352 Python tests and 20 JavaScript tests** pass. Browser checks verify the district selector, 289-profile/286-point directory, unavailable high-school option, all three separate fits, the first search after reload for a school at alphabetic index 112 beyond the initial 75 controls, selected and explicitly empty URL restoration, invalid-filter safety, single-year history/table values and the separate assessment-guide link. A 390-pixel viewport has no horizontal overflow. Current/history accessibility descriptions identify unavailable intervals, and no map coordinates are fabricated. All application assets load successfully; the guide retains its existing unrelated missing-favicon request.

Browser inspection found that the comparison legend's flex rule overrode the hidden attribute when no schools were selected. The targeted `.chart-footnote[hidden]` rule now removes the empty legend from layout and the stylesheet query version is bumped. Selected Clark points keep their visible unavailable-interval explanation; Chicago's available-interval legend, history bars and accessibility text remain correct. This display correction changes no modeled data.

```sh
# Rebuild normalized inputs from the two committed immutable audits, then import.
.venv/bin/python scripts/prepare_clark_county.py --extract
.venv/bin/python scripts/prepare_clark_county.py
.venv/bin/python scripts/export_catalog.py
.venv/bin/python scripts/export_assessment_guide.py
.venv/bin/python -m unittest discover -s tests -p 'test_clark_county.py' -v
```

The adapter rebuilds offline against the existing populated canonical store. Avoid a Chicago-only database rebuild when updating this district. The full rebuild uses `prepare_states.py`, which discovers this checked-in adapter through its district descriptor. State source holds, issue #3's remaining district work and Detroit's separate cohort hold stay open. Clark's high/mixed scope, native SEA denominator business rules and source-specific limitations remain future evidence gates.
