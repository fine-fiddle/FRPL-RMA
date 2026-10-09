# Miami-Dade district comparison

Miami-Dade has reproducible **source/cohort and numerical audits plus a validated canonical/static adapter** for 2024–25. The immutable [source audit](../data/source/miami-dade-district-audit.json) retains exact school identities, source records, missing outcomes and grade-configuration differences. The [numerical audit](../data/source/miami-dade-model-audit.json) independently fits and verifies three district grade-school models from that population. Both historical audits retain `approved_for_modeling: false`. Readiness belongs to the separate [normalized release](../data/source/miami-dade.json), which freezes policy/IDs and produces [district browser data](../data/miami-dade/schools.json) only after source, numerical and integration validation.

The audited pure grade-school population contains **357 usable schools for each of Math, ELA and Combined**, selected independently of Florida statewide residuals. All three fits pass independent full-fit and explicit leave-one-out verification without numerical holds. High-school and mixed assessment populations remain outside the existing [Florida source approval](florida-data.md). Numerical verification does not establish school effectiveness. Adapter imports and exports have passed repeatability, preservation and every-metric checks in isolated and full canonical databases; global registration and interactive browser checks also passed.

## Exact roster and native sources

[The adapter](../scripts/audit_miami_dade.py) reads the pinned official [2024–25 CCD school directory](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip). It retains all **544** records attached to NCES LEA **1200390**, native LEA **FL-13**, including the **530 operational** schools and **14 nonoperational** records (11 closed, three future). Operational statuses are Open 525, Added three, New one and Reopened one. No name matching is used: exact `FL-13-ssss` CCD `ST_SCHID` maps to Florida native school ID `13-ssss` by removing only the documented `FL-` prefix. Each full CCD raw row retains `NCESSCH`, `source_row`, status, school type, charter flag and every offered-grade flag.

The existing committed [Florida compact extract](../data/source/florida.json) supplies the same-year native records and the existing adapter supplies the identity, income and outcome validators. The new audit retains all **522** district-13 Fall Survey 2 profiles and **470** native achievement rows, including the provider variant. It links **521** profiles to exact operational CCD schools. Nine operational roster schools lack a Fall Survey 2 profile: `13-7013`, `13-7023`, `13-7834`, `13-8005`, `13-8017`, `13-8139`, `13-8901`, `13-8911`, `13-9733`. Their missing income and outcomes are unavailable, never zero. Native profile `13-7006` (Graduation Alliance) has no exact operational roster match and is retained outside the baseline. Its name cannot reconcile it to closed CCD school `13-7831` or another identity.

Native inputs are the [School Grades 2025 workbook](https://cdn.fldoe.org/file/18534/SchoolGrades25.xlsx), [Final Survey 3 individual Lunch Status workbook](https://cdn.fldoe.org/file/7584/2425LunchStatusFS2-3.xlsx), [Fall Survey 2 enrollment by school and grade workbook](https://cdn.fldoe.org/file/7584/2425MembBySchoolByGrade.xlsx), [2025 achievement calculation guide](https://cdn.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf) and [2024–25 Lunch Status definitions](https://cdn.fldoe.org/core/fileparse.php/20744/urlt/2425-146025.pdf). The artifact records each source URL, local path and SHA-256; every native profile and assessment retains complete raw values and workbook row references. Grade and assessment worksheet headers and lunch methodology notes are preserved from the Florida extract. The new audit additionally retains the income worksheet's first three rows, with worksheet name `2425 FS3_Schl`, exact row references, the Final Survey 3 year and the unadjusted D/F, 3/E, 4 and C/R field definitions. Those headers were read from the checksum-verified official income workbook; they were not present in the earlier compact extract.

Key integrity pins are:

| Input | SHA-256 |
| --- | --- |
| Full CCD directory ZIP | `39326da788aa322353d20ceaf8ad4baed26272502cd05b066cf6c594988b21ab` |
| Complete retained 544 CCD records, canonical JSON | `bb6c9571e6cf73aeac9174e3b76f2bfcd611c642c07f541911bc017b1b41dba2` |
| Committed Florida extract bytes | `523afad888444e875fc8d06486b20240896341d55b14d9484e8b935888f66daf` |
| Complete Florida native payload, canonical JSON | `f08640b8501e323cfc9298057500c4087e543bacdfda5fa4a6edb8a49778cfb8` |
| Retained income worksheet headers, canonical JSON | `69ae27b3692c211ba0da156585105a87d5dcf47c9b6c4e160061b0f8abb88209` |

Canonical fingerprints use UTF-8 JSON with sorted object keys, compact separators and unchanged array ordering. Wrong years, changed identities or source fingerprints, omitted roster records, altered suppression cells and changed derived memberships fail replay. Normal validation requires the committed audit and pinned Florida extract; it does not require raw downloads.

## Offered grades and enrolled grades are separate

The complete reported CCD offerings classify the 530 operational schools as **370 pure lower**, **87 pure high** and **73 mixed**. A pure lower configuration offers one or more PK–8 grades, offers no grades 9–12, 13, ungraded or adult education, and has complete `Yes`/`No` flags with `IGOFFERED=As reported`. The five pure lower schools without an offered grade 3–8 are retained separately as primary-only/nonapplicable. Nonoperational schools' unavailable grade flags do not establish a cohort.

Florida's existing grade-school contract instead requires **explicit zero enrollment in every Fall Survey 2 grade 9–12**. A protected positive count (`*`) stays protected and excludes that school from this contract when it occurs in a high grade. Zero, positive, protected positive and unavailable native cells are stored separately. This native contract retains **380** exact operational profiles: all 370 CCD pure lower schools plus ten CCD mixed-offered schools. The audit preserves both memberships rather than relabeling the 380 profiles as pure CCD grade schools.

| Source/cohort view | Profiles | Applicable under that view | Usable Math | Usable ELA | Usable Combined |
| --- | ---: | ---: | ---: | ---: | ---: |
| Existing native explicit-zero high-grade contract | 380 | 380 source-contract profiles | 361 | 361 | 361 |
| Proposed pure lower directory | 370 | 365 offered grades 3–8 | 357 | 357 | 357 |
| Proposed pure offered tested-grade subset | 365 | 365 | 357 | 357 | 357 |
| Pure lower with positive/protected enrolled grades 3–8 | 361 | 361 | 357 | 357 | 357 |
| Pure lower primary offerings only | 5 | 0 | 0 | 0 | 0 |
| Native grade-school contract with mixed CCD offerings | 10 | 10 native profiles | 4 | 4 | 4 |

Each saved cohort specifies its `applicable_basis`. Native-contract summaries use `applicable` to count source-contract profiles, including primary-only records; that field does not claim assessed or tested-grade applicability. Proposed district summaries instead count verified offered-grade applicability. The explicit offered and enrolled grade fields remain the evidence for interpreting both.

The proposed population intersects exact operational CCD membership, verified pure lower offerings, at least one offered grade 3–8 and Florida's explicit-zero enrolled high-grade rule. The [planning queue](district-comparisons.md) reports 365 potential ES and 81 potential HS schools using additional CCD membership-reporting screens. The independently derived ES identities happen to agree with those 365 planning IDs; planning enrollment reconciliation is not used as a model filter. The 81 HS planning records do not approve Florida high-school outcomes.

The five primary-only IDs are `13-2531`, `13-8016`, `13-9013`, `13-0331` and `13-0351`. Four additional schools offer a tested grade in CCD while reporting explicit Fall zeros in every grade 3–8: `13-0402`, `13-4328`, `13-5119`, `13-5219`. They remain offered-applicable with unavailable achievement; this explains 365 offered-applicable versus 361 enrolled-tested-evidence profiles without changing the 357 usable population. Offered grades cannot be converted into students or valid-score counts.

Across 521 exact matched profiles, **72 schools have 205 offered-but-explicit-zero enrolled grade cells**, and **46 schools have 151 protected enrolled grade cells**. No positive or protected enrolled grade falls outside CCD's reported offerings. The other 449 profiles have matching offered and positive/protected enrollment evidence sets. The audit retains each grade-level difference, including protected cells; it never reconstructs masked counts or claims that offered and enrolled populations are identical.

The four usable native profiles with mixed offerings are `13-0441`, `13-2332`, `13-3034` and `13-6047`. They remain usable under the original native source contract but are excluded from the proposed pure district cohort. The other six mixed-offered native grade-school profiles lack achievement components. The 141 matched profiles outside the native explicit-zero high-grade contract retain raw assessment references without approving high/mixed models.

## Income, achievement and population limits

All 370 matched pure lower schools have available same-year individual Lunch Status income. The numerator is raw D/F free eligibility + 3/E reduced eligibility + C/R CEP direct certification; the denominator is the same Final Survey 3 enrollment. Provision 2 code 4 nonzero or masked counts make income unavailable. USDA multipliers, the School Grades published economic percentage, another year's income and school names are never substitutes. CEP direct certification does not measure complete household income eligibility, and its undercount is unknown.

The 357 usable pure schools have income from **0.968% to 98.844%**, with **357 distinct values**, mean **56.505%** and sample standard deviation **18.651 percentage points**. These source summaries are descriptive; the separate numerical audit below calculates district fits and influence without altering the population.

Math and ELA use the native full-year-attributed School Grades achievement components under the existing Florida inclusion rules, including eligible FAA Performance Task and Math EOCs. The outcome, Fall grade registry and February income describe different prescribed populations; same-year exact identity does not make those populations identical. The source supplies whole-percent achievement rates, while enrollment, percent tested, school letter grade, published economic percentage and historical grade fields remain raw audit evidence only.

Eight offered-applicable pure lower schools lack both native achievement components: `13-4070`, `13-6057`, `13-6099`, `13-0402`, `13-0403`, `13-4328`, `13-5119`, `13-5219`. All eight are CCD charters: five regular, two alternative and one special education. The five primary-only profiles also lack outcomes. Alternative and special-education schools remain in the baseline directory; their absence from eligible points follows missing native outcomes, rather than a decision to discard their performance. All 357 usable schools are CCD regular schools: **261 noncharter and 96 charter**. This composition limits what a later comparison describes.

All 469 district campus achievement rows match operational roster identities and their charter flags agree with CCD. No district native row uses the collocated rule. The additional provider-specific virtual row `13-7001`, provider `302`, workbook row `1032`, is retained separately and remains excluded because school income cannot establish provider-specific income. The CCD directory has **no virtual-status field**; its absence is not a finding that a school is nonvirtual. Native provider, collocation, charter, Title I, alternative/ESE, school type, School Grade 2025, percent-tested and economic fields are retained for review without using them as substitute outcome or income measures.

**No valid-score denominators are available.** Every subject record has `valid_scores: null`, and sampling intervals are unavailable for each entire audited model. Florida's ten-student publication condition does not identify a denominator, and none is inferred from enrollment or participation. Combined requires eligible Math and ELA and is their equally weighted proficiency mean, not the proportion proficient in both.

## Independent district numerical audit

[The numerical adapter](../scripts/audit_miami_dade_models.py) pins the historical source audit bytes to SHA-256 `6faee4cbed0c37bade8bf8eb04ffa65b32c772141028b898080d9c86e5fb2b78` and replays that audit against the pinned Florida extract before fitting. It records the exact 530 operational IDs, 370 pure lower directory IDs, 365 offered-applicable IDs, five primary-only IDs, ten native grade-school profiles with mixed offerings, and each subject's exact eligible IDs. Policy and population fingerprints cover that selection. Full per-school income, grade and native achievement inputs, source row references, charter/type flags and all 13 pure-directory exclusions remain auditable. Missing alternative/ESE outcomes and the four usable mixed-offered native schools remain outside eligible pure models for the source reasons above; no residual or influence value selects membership.

Three separate 2025 ES models use the existing `fit_model` OLS/external-studentization implementation. The minimum is 30 eligible schools per subject; each model has 357. Combined is fitted independently to the exact mean of Math and ELA rates, and its studentized residuals are not averaged subject residuals. These native Florida definitions remain full-year/home-zoned School Grades achievement, including applicable FAST, FAA and Math EOC components; they are not a FAST-only or identically enrolled student cohort.

| Subject | Schools | Income slope | R² | Maximum absolute external t | Maximum Cook's distance | Largest deleted-fit prediction shift, points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Math | 357 | −0.415517 | 0.270939 | 3.188900 | 0.030564 | 0.408544 |
| ELA | 357 | −0.500611 | 0.358027 | 3.199436 | 0.038207 | 0.450708 |
| Combined | 357 | −0.458064 | 0.333506 | 3.285360 | 0.035869 | 0.421847 |

Income slopes are proficiency percentage points per income percentage point. Prediction shifts are the maximum absolute change of the fitted line over the entire observed income range after deleting one school. Every deleted slope remains negative, but association and residuals cannot establish causal effectiveness, admissions chances or overall school quality. Whole-percent achievement rounding, the CEP eligibility proxy, missing alternative/ESE outcomes and the different prescribed income/achievement populations remain limitations.

All full and deleted designs have rank two, and every deleted residual scale is finite and positive. The common maximum leverage is **0.027709**. The uncentered income-design condition number is **190.104** and the centered condition number is **18.624**; these are reported diagnostics, not invented release thresholds. The population income standard deviation is 18.624 points, distinct from the source table's sample standard deviation of 18.651. Conventional review flags use leverage > `2p/N` (p=2), Cook's distance > `4/N` and absolute external t > 2. They flag 41 leverage cases in each model, 14/21/13 Cook cases and 17/17/16 external-t cases for Math/ELA/Combined. These flags and the saved top-ten Cook records are descriptive review aids; no flagged school is removed or assigned a quality label. Residual standard error is explicitly `sqrt(SSE/(N−2))`.

Independent centered least squares checks the returned coefficients, native actual values, predictions, residuals and R². Centered closed-form leverage is checked separately. Every one of the **1,071 explicit deleted fits** recomputes its own training-income center, SSE and `N−3` residual scale, and verifies external t using held-out prediction and variance factor `1+h_deleted`. Coefficient/prediction discrepancies are at most 2.5e−13; studentization discrepancies at most 2.4e−14; deleted-SSE identity discrepancies at most 2.2e−11. All are below the independent absolute verification tolerance of 2e−9.

The shared fitter accepts an internal zero variance vector only as its point-estimate computational sentinel. The adapter removes all resulting interval endpoints and exposes **null score counts, null sampling variances and null low/high bounds for every member**, with model-wide interval availability false. No zero variance is published as measured uncertainty. The independent verifier explicitly requires interval absence; it does not manufacture or validate unavailable sampling intervals. OLS studentization still does not adjust for enrollment or provide shrinkage.

Saved replay accepts computed floats within absolute **or** relative tolerance `2e−10` (`max(abs_tol, rel_tol × abs(expected))`) for portability across numerical runtimes. Identity, year, raw source evidence, cohort membership, native rates, counts and absent interval fields compare exactly. Repeated generation on this environment is byte-identical. The historical numerical audit's top-level and per-model status remains `numerically_verified_pending_integration`, with false approval flags and no import/catalog in that artifact. It is immutable evidence for the separate ready adapter below.

## Canonical and static integration

[The district adapter](../scripts/prepare_miami_dade.py) uses dataset **`fl-miami-dade-2025`**, region/geography **`miami-dade`**, state **FL**, name **Miami-Dade County** and explicit **`statewide: false`**. It pins the completed numerical audit SHA-256 `b327ccd70365bbf91ab14c8bfd5828ead73d807db453efc2fd66e79bdc50f9e1` and the source audit pin above, replays both and rejects numerical holds. The new normalized extract and [district descriptor](../data/miami-dade/catalog.json) carry `release_status`/status `ready`; the historical audit files and their false flags are unchanged.

The normalized release stores all 370 exact pure lower profiles, full income and grade raw values, CCD identities/offered flags, protected cells, native assessment flags and raw components/row references. Its checksummed selection contains the final population policy, all directory IDs and independently audited subject IDs. Coverage retains all 530 operational roster decisions, 14 nonoperational records, nine unmatched operational profiles, the outside-roster native record and provider-specific virtual evidence. All five primary-only and eight missing-achievement schools remain in lists/history with unavailable outcomes and source exclusions. Missing Combined explanations translate the source's internal subject names to visible Math/ELA labels without changing applicability or eligibility.

Native Florida assessment name, year, ES level, grades, standard and source URL are copied **exactly** from the existing statewide definition; the cohort sets `allow_point_only: true`. Canonical source, income-definition, assessment-definition and model IDs are separately namespaced under `fl-miami-dade-2025`, so the same `13-ssss` school identities can appear in statewide and district datasets without replacing either comparison. The district has 370 school/income records, 740 native subject observations, three model runs and 1,071 model-result rows. Counts and interval endpoints remain absent in both canonical and browser results; internal variance sentinels are removed from published metrics.

Eight integration tests verify the complete 370/365/357 population, source exclusions and every current/history metric against the pinned numerical audit. They cover names, district labels, income/enrollment history, exact three-model summaries, native definition metadata, null tested counts/intervals, no coordinates or inferred admissions programs, strict corrupt-source/output rejection and immutable historical hashes. Import and full preparation twice are identical in isolated databases, preserve same-state/same-native-ID sentinel rows across every canonical table and pass foreign-key checks. Independent review also imported the actual statewide Florida release into an isolated database and verified that all its rows across nine canonical tables remain unchanged after two district preparations, even though all 370 district IDs overlap. No default database or global catalog is modified by these adapter tests.

The district adapter was also run twice against the established full canonical store. Both runs produced identical district rows and all four exports. Every preexisting row across all nine canonical tables retained its exact count and hash; foreign-key and integrity checks passed. The catalog now contains 47 datasets and 50 ready regions across the same 39 released states, preserving all 49 previous regions. Removing only the Miami-Dade additions reproduces the previous manifest and assessment guide exactly. The guide now has 67 released definitions. All old source and served JSON/GeoJSON files are unchanged except the global manifest, assessment guide and the district queue's exact Miami-Dade scope field; native planning evidence and both historical audits remain unchanged.

All **328 Python tests and 20 JavaScript tests** passed. Browser checks verified the district selector, 370-profile directory with 357 modeled points, disabled high-school selection, all three subject fits, the first search after loading for a school beyond page one, annual actual/predicted/residual values, selected and explicitly empty shared URLs, unavailable coordinates and the separate assessment-guide links. The browser-discovered empty-comparison interval legend is now hidden, and history/residual accessibility descriptions explicitly identify unavailable intervals when no displayed point has them. Chicago's available-interval descriptions remain correct. No application warnings or errors were observed; a fresh guide tab made the repository's existing missing-favicon request.

## Reproduction and next gates

```sh
# Extract with the pinned CCD ZIP and official income workbook already downloaded.
.venv/bin/python scripts/audit_miami_dade.py --extract

# Offline replay: committed audit plus committed Florida extract only.
.venv/bin/python scripts/audit_miami_dade.py
.venv/bin/python -m unittest discover -s tests -p test_miami_dade_district.py -v

# Numerical generation and saved replay use committed inputs, with no raw downloads.
.venv/bin/python scripts/audit_miami_dade_models.py
.venv/bin/python scripts/audit_miami_dade_models.py --check
.venv/bin/python -m unittest discover -s tests -p test_miami_dade_models.py -v

# Overlay this district on an established canonical store; preserves other datasets.
# The optional --database path supports a separately initialized isolated store.
.venv/bin/python scripts/prepare_miami_dade.py --extract --database data/build/schools.sqlite
.venv/bin/python scripts/prepare_miami_dade.py --database data/build/schools.sqlite
.venv/bin/python -m unittest discover -s tests -p test_miami_dade.py -v
```

The source audit's two extraction runs produced byte-identical output. Seven source tests cover exact cohort identities, native versus offered scope, primary-only and enrolled-grade differences, missing profiles and provider variants, protected membership, income/achievement exclusions, model-wide absent denominators, offline replay and source/derived-output corruption. The source unit passed 18 targeted source/planning checks and preserved SHA-256 values for all 253 prior source/site JSON and GeoJSON files and the canonical database. The new numerical unit adds eight tests covering manual deleted studentization and Cook's distance, exact Combined means and separate scale, internal point-only sentinel/absent intervals, floor/rank/full/deleted-scale failures, incorrect returned fit values, source/population/count drift and portable numerical replay.

The grade-school source, numerical and canonical/browser integration gates are complete on the expansion branch. High/mixed source approval remains separate work, and the large-district parent stays open for the remaining queue and Detroit cohort hold. All district sampling intervals remain unavailable; statewide residuals are not reused or refitted by a UI filter. No coordinates, boundaries, admissions claim or causal effectiveness claim is supplied. Pushing this branch does not deploy GitHub Pages from `master`.
