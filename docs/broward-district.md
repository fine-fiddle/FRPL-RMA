# Broward County district comparison

Broward County has a separate 2024–25 pure grade-school comparison under Florida, with **249 retained profiles and independent 241-school Math, ELA and Combined models**. The separately validated normalized adapter supplies canonical and browser readiness. Both immutable historical audits retain false source/model approval flags: the source artifact keeps scope `audit_pending`, and the numerical artifact keeps `numerically_verified_pending_integration`. Their completed evidence is pinned by the release adapter rather than rewritten. Statewide Florida and Miami-Dade retain their separate populations and fits.

The audit is [data/source/broward-district-audit.json](../data/source/broward-district-audit.json), rebuilt and checked by [scripts/audit_broward.py](../scripts/audit_broward.py). It retains all original district directory records, native worksheet rows and source references needed to repeat the cohort calculation.

## Exact same-year identities and source evidence

The baseline is the official 2024–25 CCD school directory attached to **NCES LEA `1200180` / native LEA `FL-06`**. All 327 directory records remain retained: 325 operational (323 Open, two Added) and two Closed. Each link keeps its NCESSCH, raw CCD state code, original CSV row and complete grade/status/type/charter flags. Only the documented `FL-` prefix is removed from `FL-06-ssss` to join Florida's native `06-ssss`; school names never establish identity. The two Closed records, `06-6051` and `06-6017`, remain explicit outside the operational baseline.

Florida's committed native extract has 324 Broward Fall Survey 2 grade profiles, all matching the exact operational roster, and 292 assessment rows (291 campus rows and one provider-specific row). There are no native Fall profiles or assessment rows outside the operational roster. Operational `06-0007`, Broward County Acceleration Academies, has no Fall grade profile. Its February income-only row 235 remains linked to the exact CCD operational Alternative/noncharter record: enrollment 31, individual eligible count 10, ratio `100 × 10 / 31`. Missing Fall scope excludes it from proposed grade-school populations; its income is available rather than zero or missing.

Pinned provenance includes the original [CCD directory ZIP](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip), [School Grades workbook](https://cdn.fldoe.org/file/18534/SchoolGrades25.xlsx), [Final Survey 3 lunch workbook](https://cdn.fldoe.org/file/7584/2425LunchStatusFS2-3.xlsx), [Fall membership workbook](https://cdn.fldoe.org/file/7584/2425MembBySchoolByGrade.xlsx), [School Grades calculation guide](https://cdn.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf) and [Lunch Status definition](https://cdn.fldoe.org/core/fileparse.php/20744/urlt/2425-146025.pdf). Each source has its URL, local path and SHA-256 in the audit. The full directory subset and CSV header have independent fingerprints. Retained Florida source notes contain assessment/grade column and year headers; the first three `2425 FS3_Schl` income header rows close the compact extract's income-header gap. Native row numbers are original worksheet references, not positions in the filtered audit.

The whole committed Florida extract is pinned to SHA-256 `523afad888444e875fc8d06486b20240896341d55b14d9484e8b935888f66daf`; its complete canonical payload is also fingerprinted. Default validation needs that extract and this audit, without reopening raw ZIP/workbook downloads. Source fingerprints reject altered identities, years, grade flags, missingness, suppression and raw count cells rather than silently accepting a newly derived population.

## Offered grades and enrolled-grade scope

Operational CCD offerings comprise 249 pure lower-grade schools, 45 pure high schools and 31 mixed schools. Pure lower means complete reported offered flags, at least one PK–8 grade, and no offered grade 9–13, ungraded or adult grade. Florida's existing source contract instead requires explicit zero in **every enrolled grade 9–12** in the same-year Fall Survey 2 registry. A protected `*` is positive membership with an unavailable count; it never becomes zero. Offered grades and actual enrolled grades remain different evidence.

| Source/cohort set | Profiles | Subject applicability | Usable Math / ELA / Combined | Available individual income |
| --- | ---: | ---: | ---: | ---: |
| Native explicit-zero enrolled high-grade contract | 252 | 252 within source contract | 244 / 244 / 244 | 251 |
| Proposed pure lower-grade directory | 249 | 243 | 241 / 241 / 241 | 248 |
| Proposed pure lower with offered grade 3–8 | 243 | 243 | 241 / 241 / 241 | 243 |
| Pure lower with positive/protected enrolled grade 3–8 | 242 | 242 | 241 / 241 / 241 | 242 |
| Pure lower with primary-only offerings | 6 | 0 | 0 / 0 / 0 | 5 |
| Native enrolled-grade contract with mixed CCD offerings | 3 | 3 within source contract | 3 / 3 / 3 | 3 |

“Applicability” in the native source-contract summary identifies membership in the explicit-zero high-grade contract; it does not assert that all 252 schools enroll a tested grade. Proposed district subject applicability separately requires pure lower offerings including grade 3–8 and the native zero-high contract. Neither definition uses the planning queue to select model members.

The six primary-only profiles are `06-5511`, `06-5521`, `06-5541`, `06-5561`, `06-5581` and `06-5641`. All are CCD Regular/noncharter schools offering PK only; names do not establish special-education classification. They remain nonapplicable with their native income and outcome exclusions retained. `06-5017`, the Added Avant Garde Academy Foundation K8, offers KG–8 but has explicit zero enrolled grades 3–8, positive KG–2 and no campus achievement row. It stays offered-applicable and unavailable, separately from primary-only schools.

The three native usable mixed-offering charter profiles are `06-5038`, `06-5355` and `06-5381`. Their enrolled high grades are explicit zero, so they belong to the existing Florida native source contract; their CCD mixed offerings exclude them from this proposed pure district cohort. They are never silently relabeled pure schools. High and mixed assessment populations have no Florida district approval in this phase.

Across 324 linked profiles, 44 have an offered-versus-enrolled difference, with 136 offered-but-explicit-zero grade cells. Forty-seven profiles have 96 protected enrolled-grade cells. No positive or protected enrolled grade falls outside a reported offering. These counts describe grade configuration evidence; they are not valid-score denominators or weights for averaging proficiency rates.

The planning queue's 243 potential ES and 45 potential HS schools and enrollment 243,553 are discovery evidence. Its exact 243 ES IDs reconcile to the independently derived offered-applicable source set, with both difference lists empty. The extractor rejects duplicate, foreign, missing or wrong-scope planning IDs and changed discovery identity/enrollment metadata before conversion. Planning eligibility and enrollment do not approve a model or extend high-school assessment scope.

## Native outcomes, income and exclusions

Outcomes retain Florida's **2024–25 School Grades Mathematics Achievement and English Language Arts Achievement** components, Level 3 or above under full-year enrollment and home-zoned attribution rules. They include eligible FAA Performance Task and prescribed Math EOC results; they are not a FAST-only grade-average reconstruction. Native rates are published whole percentages; the component publication floor of ten eligible students does not reveal a valid-score denominator. Combined is the equally weighted mean of usable Math and ELA rates, not the share proficient in both.

Income uses same-year February Final Survey 3 raw individual eligibility: `(D/F free + 3/E reduced + C/R CEP direct certification) / enrolled PK–12 × 100`. CEP N is outside the numerator. USDA-adjusted federal funding counts and the School Grades published economic-disadvantage percentage are not substitutes. The February income population and full-year/home-zoned assessment population differ; CEP identification coverage and possible undercount remain limitations of this proxy.

All 243 offered-applicable profiles have available individual income. Their two unavailable campus outcomes are `06-5017` and `06-7001`. Broward Virtual Instruction Program `06-7001` has only provider 302 assessment row 492, whose raw ELA 86 and Math 62 remain retained separately. Its school-level income is `2 / 86`, not the funding-adjusted `3 / 86`; it cannot be matched to provider-specific achievement. Thus no campus outcome is imported. The directory has no virtual-status field, so CCD virtual status stays null; the native provider identifier is retained as source metadata rather than inferred away.

Primary-only `06-5561`, UCP Early Beginnings, has masked `*` income count cells, including Provision 2 code 4. Its income exclusion expresses nonzero **or masked** code 4 and cannot establish actual Provision 2 participation. Primary-only `06-5541` and `06-5581` have verified zero individual eligibility and retain income zero. Missing/ protected values remain unavailable, separately from these true zeros. The original source reason is retained even when a primary-only applicability exclusion takes precedence for the proposed cohort.

All 241 usable proposed points are CCD Regular schools: 176 noncharter and 65 charter. The 249 pure lower profiles include 183 noncharter and 66 charter schools. The audit retains all attached-LEA charter/type/program flags; no charter or school type is removed based on anticipated fit. All campus charter flags agree with CCD. No native Broward collocated row is observed, but the native collocation exclusion remains enforced. Alternative/high/mixed and unmatched records retain their source exclusions and cannot gain eligibility from a name, available income or a provider rate.

The proposed Combined income range is 0.274–100%, with 238 distinct ratios, mean 52.273% and sample standard deviation 21.041 percentage points. These are descriptive source diagnostics; the separate numerical phase below contains model diagnostics. Every subject's valid-score count and sampling variance is null. Sampling intervals remain unavailable modelwide; enrollment, percent tested and publication floors never manufacture score counts.

## Replay and remaining gates

With the pinned raw downloads available, extraction rebuilds the audit. Normal validation is offline:

```sh
.venv/bin/python scripts/audit_broward.py --extract
.venv/bin/python scripts/audit_broward.py
.venv/bin/python -m unittest discover -s tests -p test_broward_district.py -v
```

Two extraction runs must produce identical bytes. Eight focused tests cover exact source/population memberships, primary/mixed distinctions, provider and income-only records, native income arithmetic, true zero/protected/masked/suppressed values, point-only counts, offline headers, strict planning identities and typed corruption replay. Canonical fingerprints distinguish numeric zero from false metadata.

The completed source unit passed all 26 targeted Broward, Florida, Miami-Dade source and district-planning tests. Repeated extraction produced byte-identical 2,048,820-byte artifacts, SHA-256 `11e79d74cac96af228be063a9756c59aabc877cfa99217fe0b7ddc9352b9f5e1`. Two independent reviews verified the full original CCD roster and native workbook rows, headers, source hashes and exact memberships. The canonical database's SHA-256 stayed unchanged, as did all 201 existing served JSON/GeoJSON files; the only changed prior file under `data/` is this audit's added source-README documentation. No district dataset or global assessment-guide definition was added.

The source phase's numerical gate is completed separately below, followed by the normalized adapter's canonical/static integration. Coordinates, boundaries and admissions populations have not been audited. The historical source/cohort artifact leaves both approval flags false and itself publishes no district comparison.

## Separate district numerical audit

[scripts/audit_broward_models.py](../scripts/audit_broward_models.py) rebuilds [data/source/broward-model-audit.json](../data/source/broward-model-audit.json) offline from the immutable source audit pinned above. The numerical artifact freezes the 325 operational IDs, 249 pure lower profiles, 243 offered-applicable IDs and the exact 241 eligible IDs for each subject. It retains all eight pure-profile exclusions, the three usable native mixed-offering charters outside the district cohort, operational records outside pure lower scope, income-only `06-0007`, provider `06-7001` and nonoperational records. Neither regression quality nor influence flags alter membership.

The three independent ES models use the same 241 source-eligible schools: 176 noncharter and 65 charter Regular schools. Every input retains its full native school ID, NCESSCH, CCD directory raw row, offered/enrolled flags and protected values, native income and achievement raw rows, year and source references. Math and ELA use native achievement components. Combined takes their exact equally weighted mean and receives its own regression and deleted residual scales. The audit does not reuse any statewide prediction or studentized residual.

| Subject | Schools | Intercept | Slope per income percentage point | R² | Maximum Cook's distance | Largest deleted-fit prediction shift, points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Math | 241 | 83.884134 | −0.327206 | 0.250379 | 0.135371 | 0.993586 |
| ELA | 241 | 81.899105 | −0.377025 | 0.337252 | 0.163379 | 1.018977 |
| Combined | 241 | 82.891619 | −0.352115 | 0.311468 | 0.162390 | 1.006281 |

The 30-school floor, rank-two design, finite input/returned metrics and full/deleted residual scales pass with no hard holds. The raw design condition number is 151.175; centering income gives 20.997, expressed in the native percentage-point units rather than a universal pass threshold. Income population SD is 20.997 points (the source table's sample SD is 21.041). The maximum leverage is 0.029597, at `06-5111`, Imagine Weston. Thirty members exceed the conventional `2p/n = 4/241` leverage reference in every model. Math/ELA/Combined have 8/10/8 Cook's-distance flags above `4/n` and 12/11/10 externally studentized residual flags with absolute value above two. These are descriptive review flags, not school-quality labels or exclusion rules.

`06-5407`, Everest Charter School, has the largest Cook's distance and absolute externally studentized residual in each model: maximum absolute statistics 3.275630 Math, 3.615473 ELA and 3.603919 Combined. All deleted-fit slopes remain negative. The prediction shifts in the table are the largest change between each full and deleted line over the observed income range, not just the held-out school's change. These shifts, native whole-percent rounding, CEP identification coverage and the different February/full-year populations remain visible limitations. Results describe associations, not causal school effectiveness.

For each model, an independent centered full fit verifies coefficients, actual proficiency, predictions, residuals, R² and closed-form leverage. Every school also receives an explicit leave-one-out fit: **723 deleted fits**, each with `n−3 = 238` residual degrees of freedom. Its held-out residual is divided by deleted residual scale times `sqrt(1 + h_deleted)`, and compared with the shared fitter's externally studentized statistic. Deleted SSE and held-out prediction identities are also verified. All maximum absolute verification errors are below `1.5e−11`, including the SSE identity; the prediction/residual errors are below `8.6e−14` and studentization errors below `1.2e−14` in this environment. The audit's independent absolute verification tolerance is `2e−9` across these reported checks.

Every published count, sampling variance and interval endpoint remains null for all 723 results. A zero variance vector is used solely as the shared fitter's internal point-estimate sentinel; generated endpoints are immediately cleared. It is not a zero-uncertainty claim. Residual standard error uses `sqrt(SSE/(n−2))`; studentization uses each deleted scale. Neither residual scale supplies missing binomial sampling variance or enrollment adjustment.

```sh
.venv/bin/python scripts/audit_broward_models.py
.venv/bin/python scripts/audit_broward_models.py --check
.venv/bin/python -m unittest discover -s tests -p test_broward_models.py -v
```

Rebuilds in one environment must produce identical bytes. Replay permits an absolute **or** relative tolerance of `2e−10` for computed numerical metrics; identities, actual native outcomes, raw cells, source fingerprints, policy, membership, count types and absent intervals compare exactly. Typed canonical fingerprints reject numeric zero substituted for false approval or raw count metadata. Eight focused numerical tests cover full/deleted manual calculations, separate Combined fitting, missing uncertainty, floor/rank/full/deleted-scale failures, nonfinite or incorrect returned fits, exact source/population/type drift and limited computed-float portability. Source/model approval remains false pending independent review and separate canonical/browser integration; numerical success alone does not grant release readiness.

The numerical unit passed 51 targeted Broward model/source, Florida, district-planning, Miami-Dade/Clark model and shared-statistics tests. Repeated generation produced byte-identical 5,270,470-byte audits, SHA-256 `882067b31bae9fa2f524ff458b55479b8953f52f819a6a87eedb70242b54233d`. Two independent reviews reconstructed the raw eligibility and all 723 full/deleted result records, including leverage, Cook's distance and deletion metrics. The immutable source audit, canonical database and all 201 existing served JSON/GeoJSON files retain their previous SHA-256 values. The only changed prior file under `data/` is source-README documentation. Numerical review is complete; the next unit is separate canonical/static integration with repeat imports and browser verification. This audit's false approval flags and pending-integration status remain unchanged.

## Separate canonical and static integration

[scripts/prepare_broward.py](../scripts/prepare_broward.py) validates the separately reviewed [data/source/broward.json](../data/source/broward.json) against both immutable audits before importing canonical dataset `fl-broward-2025`. The normalized extract is 2,531,730 bytes, SHA-256 `0379bc7b1949fe574465b8d6fa65d068b864e9ee79fd301540c31cf789109399`; two generation runs produce identical bytes. It retains all 249 pure lower profiles, six primary-only profiles and both unavailable campus-outcome profiles. Coverage retains all 327 original CCD rows, 325 operational links, complete native records, the income-only `06-0007` row and provider-specific `06-7001` achievement, together with all wider native cohort/exclusion evidence.

The adapter has its own ready release status; neither historical audit is rewritten. All 249 profile/history identities, source rows, same-year economic observations, raw cells and exclusions are validated exactly. Computed coefficients and externally studentized metrics use the numerical audit's tight tolerance; native outcomes, population/count types and interval absence remain exact. Scope, source-definition or count changes fail before import. Export validation rejects extra subjects, altered histories or model summaries, renamed statewide descriptors, changed coverage, reconstructed denominators and fabricated geometry.

The dataset adds 249 schools and economic observations, 498 native Math/ELA observations, one income definition, one exact native assessment definition, ten provenance records, three district model runs and 723 results. Dataset/source/definition namespaces keep Florida's overlapping native school IDs separate from statewide and Miami-Dade records. The source-bound assessment definition is `fl-broward-2025:2025:Florida School Grades FAST + FAA + Math EOC · grade schools:ES`; native grades, standard and source URL match Florida's approved assessment contract exactly, while the regression population remains Broward's separately audited selection. Counts, sampling variances and interval endpoints stay unavailable modelwide.

Independent reconstruction verified every normalized profile, all eight excluded pure profiles, all 723 canonical/browser results and all current/history metadata against original source cells and independently fitted full/deleted models. The largest prediction difference is below `1.1e−13` and the largest studentization difference below `1.1e−14`. Every Broward prediction differs from the corresponding statewide Florida prediction, and all three district slopes differ from Miami-Dade's. No statewide residual is reused.

Two incremental imports preserve every pre-existing row in all nine canonical tables and produce identical Broward rows and four static exports. Foreign-key checks are empty and SQLite integrity is `ok`. All 199 existing regional JSON/GeoJSON files remain byte-identical. Removing only the new Broward records from the global manifest and assessment guide restores their prior content exactly; map geometry and assessment-provider evidence are unchanged. The catalog now has 49 canonical datasets and 52 ready regions across the same 39 states, with 11 source holds unchanged. The guide adds one separate Broward link/definition, for 69 latest definitions; provider and relative-target fields remain unverified. The district queue changes only Broward's exact LEA scope to existing, leaving 74 first-tier and 172 second-tier candidates.

```sh
.venv/bin/python scripts/prepare_broward.py --extract-only  # regenerate normalized evidence offline
.venv/bin/python scripts/prepare_broward.py                # incremental import and four exports
.venv/bin/python scripts/export_catalog.py
.venv/bin/python scripts/export_assessment_guide.py
.venv/bin/python -m unittest discover -s tests -p test_broward.py -v
```

Integration passed all 377 Python tests and all 20 JavaScript tests, including eight focused adapter tests for same-state overlapping IDs, repeated imports, protected/true-zero distinctions, native provenance and scientific corruption. Two independent reviews checked source/metric equivalence and preservation. Repeated catalog/guide exports are identical. Browser verification covered initial Combined/selected defaults, the first search after a reload for an eligible school beyond the 75-row list page, all three subject models, all-filtered scope without refitting, shared selections/focus/query, explicit empty selection, invalid filters and foreign IDs. High-school selection is disabled, unaudited program classifications remain Unclassified, and absent geometry has a searchable-list fallback. One 2025 history point, the accessible table and current/history chart labels explicitly report unavailable sampling intervals. The separate guide link navigates to Broward; its Florida statewide and Miami-Dade links remain distinct. A visually inspected 390-pixel viewport has no horizontal overflow, and browser warning/error lists are empty.

Only the expansion branch has been pushed. This integration does not merge into `master` or deploy GitHub Pages. High-school/mixed assessments, admissions populations and geometry remain unaudited; the parent district issue and all outstanding source holds remain open.
