# Orange County district source audit

Orange County's separate 2024–25 source/cohort audit identifies **200 usable pure grade-school records for each of Math, ELA and Combined**. This unit audits exact identities, populations, individual income, outcomes and missingness. It fits no district model and publishes no comparison. Both `approved_for_source` and `approved_for_modeling` remain false, with status and scope `audit_pending`; independent numerical review and canonical/browser integration are separate gates.

[scripts/audit_orange.py](../scripts/audit_orange.py) rebuilds and checks [data/source/orange-district-audit.json](../data/source/orange-district-audit.json). The artifact retains the complete district directory, original native worksheet rows and headers, exact cohort memberships and subject exclusions. Florida's existing statewide population and source definition remain unchanged.

## Exact same-year roster and provenance

The authoritative baseline is the 2024–25 CCD school directory attached to **NCES LEA `1201440` / native LEA `FL-48`**. All 282 records are retained: 275 operational (271 Open, one Added, one New and two Reopened), five Closed and two Future. Links preserve NCESSCH, native state codes, original CSV row references, status, school type, charter flags and offered-grade flags. Only the documented `FL-` prefix is removed from `FL-48-ssss` to join native Florida `48-ssss` records. Names never establish identity.

All 268 native Fall Survey 2 profiles and 268 February income rows match exact operational roster keys. All 234 native achievement rows are campus rows matching those keys. No provider-specific, income-only or outside-roster native row is observed. Seven operational schools have no Fall profile: `48-1131`, `48-1581`, `48-5783`, `48-0113`, `48-7023`, `48-1961` and `48-0772`. Their directory configuration and source exclusions remain explicit; no native income, grade profile or outcome is invented. The directory has no virtual-status field, so CCD virtual status stays null. Native program flags remain separate evidence.

Pinned sources include the original [CCD directory ZIP](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip), [CCD school membership ZIP](https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip), [School Grades workbook](https://cdn.fldoe.org/file/18534/SchoolGrades25.xlsx), [Final Survey 3 lunch workbook](https://cdn.fldoe.org/file/7584/2425LunchStatusFS2-3.xlsx), [Fall membership workbook](https://cdn.fldoe.org/file/7584/2425MembBySchoolByGrade.xlsx), [School Grades calculation guide](https://cdn.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf) and [Lunch Status definition](https://cdn.fldoe.org/core/fileparse.php/20744/urlt/2425-146025.pdf). URLs, local paths, SHA-256 values and original worksheet/CSV rows are retained.

The complete district directory fingerprint is `e9c7b14e25ab8d82fee29e1dea88951653e074669ef2ce7653519695f6226a48`. Its original column header is separately pinned. Native source notes retain lunch definitions and assessment/grade year and column headers; the first three original `2425 FS3_Schl` income-header rows are retained separately. The full Florida extract is pinned to SHA-256 `523afad888444e875fc8d06486b20240896341d55b14d9484e8b935888f66daf`, plus its canonical-payload fingerprint. Replay rejects changed identities, years, headers, suppression, raw cells or membership.

## Offered grades, enrolled grades and applicability

Operational CCD offerings comprise **209 pure lower configurations, 34 pure high configurations and 32 mixed configurations**. Pure lower means complete reported flags, at least one PK–8 offering and no offered grade 9–13, ungraded or adult grade. Florida's native grade-school contract instead requires explicit zero in every Fall enrolled grade 9–12. A protected `*` denotes positive membership with an unavailable count and never means zero.

The full 209-school pure lower inventory contains **207 offered-tested configurations** and two PK-only records. Of these, 208 have Fall profiles: 206 offered-applicable profiles and the two primary-only profiles. The remaining pure record, **`48-1961` / NCESSCH `120144009033`**, offers grades 6–8 but has no Fall profile. It remains an unavailable tested configuration; it is not relabeled primary-only.

| Matched operational source/cohort set | Profiles | Subject applicability | Usable Math / ELA / Combined | Available individual income |
| --- | ---: | ---: | ---: | ---: |
| Native explicit-zero enrolled high-grade contract | 209 | 209 within source contract | 201 / 201 / 201 | 209 |
| Proposed matched pure lower directory | 208 | 206 | 200 / 200 / 200 | 208 |
| Proposed pure lower with offered grade 3–8 | 206 | 206 | 200 / 200 / 200 | 206 |
| Pure lower with positive/protected enrolled grade 3–8 | 206 | 206 | 200 / 200 / 200 | 206 |
| Matched primary-only offerings | 2 | 0 | 0 / 0 / 0 | 2 |
| Native enrolled-grade contract with mixed CCD offerings | 1 | 1 within source contract | 1 / 1 / 1 | 1 |

Native “applicability” means membership in the explicit-zero high-grade source contract, including primary-only profiles. It does not assert tested-grade enrollment. Proposed district applicability additionally requires verified pure lower offerings including grade 3–8. All matched offered-applicable profiles have positive or protected enrolled tested-grade evidence.

The two PK-only records retain available income but nonapplicable outcomes: `48-0090`, UCP East Charter, is CCD Special Education/charter, while `48-1881`, Washington Shores Primary Learning Center, is CCD Regular/noncharter. Native mixed **`48-0283`, Pinecrest Collegiate Academy**, offers grades 6–12, has enrolled high-grade zeros, published Math/ELA 92/92 and individual income `5/14 = 35.714%`. It is usable within the native contract but excluded from the pure district proposal. High and mixed assessment approval is not extended.

Among all 268 linked profiles, 22 have offered/enrolled differences, totaling 61 offered-but-explicit-zero grade cells. Forty-one profiles have 110 protected enrolled-grade cells. No positive or protected enrolled grade falls outside reported offers. These are configuration checks, not score denominators or proficiency-aggregation weights.

## Planning reconciliation and original membership proof

The planning queue reports enrollment **205,853**, 206 potential ES schools and 31 potential HS schools. Its 206 ES identities exactly equal the matched source-applicable set; this agreement does not make planning a model-selection rule. The full directory tested-offer inventory has one additional ES configuration, `48-1961`. The high-offered inventory has three additional records, `48-1131`, `48-1581` and `48-5783`; all three are Career and Technical schools without Fall profiles.

A bounded original CCD membership stream retains **61 Education Unit Total and grade-subtotal rows for nine exact schools**: all seven missing-Fall records and both primary-only records. Original headers, member name, archive fingerprint and CSV row references remain attached. Every missing-Fall total is Reported zero, and every retained grade count for those seven missing-Fall schools is explicit zero with Reported or Derived status. Original total row references are 2,581,336 (`1131`), 2,581,550 (`1581`), 2,581,633 (`5783`), 2,588,586 (`0113`), 2,597,208 (`7023`), 2,602,537 (`1961`) and 2,602,664 (`0772`). The two primary totals are positive: 120 at row 2,592,980 (`0090`) and 82 at row 2,602,705 (`1881`), but neither offers grade 3–8. These original values explain discovery omissions; reported zero CCD membership never supplies a native Fall profile or an income rate of zero.

The retained subset canonical fingerprint is `c010f94b96171b829d9f30c9c57fdf3561905a1e0f8f7c08dcc4610ab76eeb85`; the original membership archive SHA-256 is `4a7f660c5fc5eaae488dd02fd43498f349fc828b227edd0970d5b6995ead4d4d`. Original-file independent reconstruction also verifies every planning ES/HS ID and the district enrollment total. The adapter rejects duplicate, foreign, missing or wrong-scope planning IDs and altered identity/enrollment metadata before converting IDs. Membership is discovery evidence only, never an outcome denominator or native eligibility filter.

## Native outcomes, individual income and missingness

Outcomes retain Florida's **2024–25 School Grades Mathematics Achievement and English Language Arts Achievement**, Level 3 or above under full-year enrollment and home-zoned attribution rules. Native components include FAST, eligible FAA Performance Task and prescribed Math EOC results. FAA Datafolio does not supply these rates. Published whole percentages remain native school totals; grade rates are not averaged. Combined is the equally weighted mean of eligible Math and ELA, not the percentage proficient in both.

Two original rows, **`48-0042` BETA and `48-0065` UCP Downtown Charter**, retain collocation group `480042480065` and shared published aggregate Math 17 / ELA 20. Those outcomes cannot be assigned to either campus's individual income, so both remain unavailable under native collocation rules. Downtown is an offered-applicable pure Alternative/charter school and remains excluded. The other five applicable pure records without campus achievement are `48-0055`, `48-0070`, `48-0068`, `48-0184` and `48-0163`. Raw rates, identities, program flags and exact reasons remain preserved rather than dropping records.

Income uses same-year February Final Survey 3 individual eligibility: `(D/F free + 3/E reduced + C/R CEP direct certification) / enrolled PK–12 × 100`. CEP N is outside the numerator. USDA-adjusted funding counts and School Grades' published economic-disadvantage percentage are not substitutes. February enrollment and full-year/home-zoned assessment populations differ; CEP identification coverage and possible undercount remain proxy limitations.

All 268 profiles have available individual income; no masked or absent income row is observed. **Seven records have zero recorded individual eligibility**, with positive enrollment and explicit zero component/code-4 cells. Three are in the pure cohort: `48-0055`, `48-0056` and `48-0061`. Lake Eola Charter (`0056`, enrollment 183) and Hope Charter (`0061`, enrollment 414) are eligible and retain income **0%**. `0055` has no campus achievement and remains unavailable. Zero recorded eligibility does not establish that a school has no low-income families. Masked, protected and absent values would remain unavailable under the preserved native validators.

All 200 usable proposed points are CCD Regular schools: **182 noncharter and 18 charter**. Charter and type flags are retained without anticipated-fit exclusions; campus charter flags agree with CCD. Eligible income ranges from 0% to 99.533%, with 198 distinct ratios, mean 48.290% and sample standard deviation 22.342 percentage points. These are descriptive source statistics; no fit or influence statistic is calculated here.

Verified valid-score counts and sampling variances are null for every subject, with model-wide sampling intervals unavailable. The native publication floor and percent tested cannot identify valid-score denominators. Enrollment, participation and studentization do not provide substitute counts, enrollment adjustment or shrinkage.

## Rebuild, checks and remaining gates

Default validation is offline from the committed audit and pinned Florida extract. Extraction reopens the original directory and income-header sources, verifies the membership ZIP checksum and reuses the committed fingerprinted membership subset; it does not restream the Deflate64 membership archive each time. Bootstrap extraction accepts a separately retained original CSV stream subset using `--membership-evidence`. Source changes require fresh raw investigation and reviewed fingerprints.

```sh
.venv/bin/python scripts/audit_orange.py --extract
.venv/bin/python scripts/audit_orange.py
.venv/bin/python -m unittest discover -s tests -p test_orange_audit.py -v
```

Nine focused tests pass. Two producer extraction runs reproduced the committed artifact byte-for-byte: 1,748,206 bytes, SHA-256 `671c14166fd5110bd569b26b2997d8bc73264e0156393d757516324e57c726f3`. Offline replay and `git diff --check` also pass. The focused tests cover the complete roster and population sets, unmatched tested offerings, primary/mixed distinctions, real zero income, collocated aggregate exclusion, protected/masked versus missing values, exact same-year income arithmetic, null counts/intervals, offline retained headers, original zero-membership proof, strict planning identities and typed source corruption. Canonical fingerprints distinguish numeric zero from false metadata and reject source-row/count type changes.

The completed source unit passes all 44 targeted Orange, Hillsborough, Broward, Miami-Dade, Florida and district-planning tests in 13.846 seconds. Two additional root extraction runs reproduce identical bytes and replay successfully. Two independent reviews verify original directory/native rows, exact cohort membership and the bounded membership proof; 20 additional scientific/provenance corruption checks reject invalid changes. The original membership stream independently reconstructs all 275 operational totals, 2,001 grade subtotals and the exact discovery ES/HS lists.

The canonical database remains byte-identical at SHA-256 `e9b44eba7b91e2eb80bd6b4c2e2ef49995a67518a371c186736e890c12f163d7`, with unchanged counts across all nine tables. All 209 earlier served JSON/GeoJSON files, including 207 regional files, remain byte-identical. Of 287 prior tracked data files, 286 are unchanged; the sole change is added source-README documentation. Catalog/provider/geometry/planning evidence remains unchanged: 50 canonical datasets, 53 ready regions across 39 states, 11 source holds, 70 latest assessment definitions and 73/172 district candidates. Parent #3, Detroit #15 and unresolved state source holds remain open.

The next gate is an independently reviewed numerical audit: separate same-year Math, ELA and Combined OLS fits, externally studentized residuals, a 30-school subject floor, rank and full/deleted-scale checks, and explicit leverage/influence diagnostics without fit-driven membership changes. Canonical/static integration would then require repeat imports, preservation of existing datasets, every-metric current/history export comparison and browser verification. Source success alone leaves both approvals false and scope `audit_pending`.
