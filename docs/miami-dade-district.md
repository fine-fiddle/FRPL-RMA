# Miami-Dade source and cohort audit

Miami-Dade has a reproducible **source/cohort audit only** for 2024–25. The audit retains exact school identities, source records, missing outcomes and grade-configuration differences. It does not fit district models, import observations, create browser data or approve a comparison. `approved_for_modeling` remains `false` in [the saved audit](../data/source/miami-dade-district-audit.json).

The proposed later grade-school population contains **357 usable schools for each of Math, ELA and Combined**, selected independently of Florida statewide residuals. High-school and mixed assessment populations remain outside the existing [Florida source approval](florida-data.md). Counts and income spread establish source readiness for the next numerical audit; they do not establish numerical stability or school effectiveness.

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

The 357 usable proposed schools have income from **0.968% to 98.844%**, with **357 distinct values**, mean **56.505%** and sample standard deviation **18.651 percentage points**. These are descriptive source summaries; no regression, leverage or influence calculation occurs here.

Math and ELA use the native full-year-attributed School Grades achievement components under the existing Florida inclusion rules, including eligible FAA Performance Task and Math EOCs. The outcome, Fall grade registry and February income describe different prescribed populations; same-year exact identity does not make those populations identical. The source supplies whole-percent achievement rates, while enrollment, percent tested, school letter grade, published economic percentage and historical grade fields remain raw audit evidence only.

Eight offered-applicable pure lower schools lack both native achievement components: `13-4070`, `13-6057`, `13-6099`, `13-0402`, `13-0403`, `13-4328`, `13-5119`, `13-5219`. All eight are CCD charters: five regular, two alternative and one special education. The five primary-only profiles also lack outcomes. Alternative and special-education schools remain in the baseline directory; their absence from eligible points follows missing native outcomes, rather than a decision to discard their performance. All 357 usable schools are CCD regular schools: **261 noncharter and 96 charter**. This composition limits what a later comparison describes.

All 469 district campus achievement rows match operational roster identities and their charter flags agree with CCD. No district native row uses the collocated rule. The additional provider-specific virtual row `13-7001`, provider `302`, workbook row `1032`, is retained separately and remains excluded because school income cannot establish provider-specific income. The CCD directory has **no virtual-status field**; its absence is not a finding that a school is nonvirtual. Native provider, collocation, charter, Title I, alternative/ESE, school type, School Grade 2025, percent-tested and economic fields are retained for review without using them as substitute outcome or income measures.

**No valid-score denominators are available.** Every subject record has `valid_scores: null`, and sampling intervals are unavailable for each entire future model. Florida's ten-student publication condition does not identify a denominator, and none is inferred from enrollment or participation. Combined requires eligible Math and ELA and is their equally weighted proficiency mean, not the proportion proficient in both.

## Reproduction and next gates

```sh
# Extract with the pinned CCD ZIP and official income workbook already downloaded.
.venv/bin/python scripts/audit_miami_dade.py --extract

# Offline replay: committed audit plus committed Florida extract only.
.venv/bin/python scripts/audit_miami_dade.py
.venv/bin/python -m unittest discover -s tests -p test_miami_dade_district.py -v
```

Two extraction runs produce byte-identical output. Seven tests cover exact cohort identities, native versus offered scope, primary-only and enrolled-grade differences, missing profiles and provider variants, protected membership, income/achievement exclusions, model-wide absent denominators, offline replay and source/derived-output corruption. Together with five existing Florida and six district-planning tests, all 18 targeted checks passed. All 253 prior source/site JSON and GeoJSON files and the canonical database retained identical SHA-256 values. Existing Florida/state outputs, district planning and browser files are not modified by this audit.

The next concrete unit is a separate numerical audit of the proposed pure grade-school Math, ELA and Combined populations, with an explicit frozen population policy, the existing 30-school subject floor, independent same-year district OLS, externally studentized residuals and independent full-fit/leave-one-out checks. All sampling intervals must remain unavailable. Income rank, deletion scale, leverage, influence and coverage need honest diagnostics; none has been checked here. Statewide residuals cannot be reused or refitted by a UI filter. High/mixed source approval remains separate work. A later release also requires canonical import repeatability, exported per-school numerical equivalence, complete directory/exclusion metadata, distinct district discovery and browser checks. No coordinates, boundaries, admissions claim, causal effectiveness claim or deployment is supplied.
