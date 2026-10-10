# Palm Beach County district source audit

Palm Beach County's separate 2024–25 source/cohort audit identifies **165 usable pure grade-school records for each of Math, ELA and Combined**. This phase audits identities, populations, individual income, native outcomes and missingness. It fits no district regression and publishes no comparison. Both `approved_for_source` and `approved_for_modeling` remain false, with status and scope `audit_pending`; independent numerical review and canonical/browser integration remain separate gates.

[scripts/audit_palm_beach.py](../scripts/audit_palm_beach.py) rebuilds and checks [data/source/palm-beach-district-audit.json](../data/source/palm-beach-district-audit.json). The artifact retains the full directory, original native worksheet rows and headers, exact cohort IDs, subject exclusions and bounded original membership evidence. Florida's existing statewide definition and every earlier comparison remain unchanged.

## Exact same-year roster and provenance

The authoritative baseline is the 2024–25 CCD school directory attached to **NCES LEA `1201500` / native LEA `FL-50`**. All 238 district records are retained: 234 operational (232 Open, two Added), three Closed and one Future. Each link preserves NCESSCH, native school code, original CSV row, status, school type, charter flag and complete offered-grade flags. Only the documented `FL-` prefix is removed from `FL-50-ssss` to join Florida's native `50-ssss` records. Names never establish identity.

All 230 native Fall Survey 2 profiles and 230 February Survey 3 income rows match exact operational roster keys. Native achievement has 201 rows: **199 campus rows and two provider-specific virtual rows**, all attached to operational keys. No outside-roster profile, income-only record or collocated assessment row is observed. Four operational records have no Fall profile: `50-3081`, `50-3931`, `50-7023` and `50-9063`. All four have mixed offerings; their directory identities and source gaps remain explicit without invented native grade, income or outcome records. CCD supplies no virtual-status field, so that field stays null; native provider/program metadata is retained separately.

Pinned official sources include the original [CCD directory ZIP](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip), [CCD school membership ZIP](https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip), [School Grades workbook](https://cdn.fldoe.org/file/18534/SchoolGrades25.xlsx), [February Final Survey 3 lunch workbook](https://cdn.fldoe.org/file/7584/2425LunchStatusFS2-3.xlsx), [Fall membership workbook](https://cdn.fldoe.org/file/7584/2425MembBySchoolByGrade.xlsx), [School Grades calculation guide](https://cdn.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf) and [Lunch Status definition](https://cdn.fldoe.org/core/fileparse.php/20744/urlt/2425-146025.pdf). Their URLs, paths and SHA-256 checksums remain attached, along with original worksheet/CSV row references.

The complete directory fingerprint is `ef081409121f1676b33a3329368f1ba58439618691ebb43b72a9a14cd8e449de`, with a separately pinned original column header. Native source notes retain lunch definitions and assessment/grade year and column headers; the first three original `2425 FS3_Schl` income-header rows are also retained. The entire frozen Florida extract is pinned to SHA-256 `523afad888444e875fc8d06486b20240896341d55b14d9484e8b935888f66daf`, plus its canonical-payload fingerprint. Replay rejects changed identities, years, raw values, suppression, headers or memberships instead of silently selecting a new cohort.

## Offered grades, enrolled grades and applicability

Operational offerings comprise **170 pure lower configurations, 26 pure high configurations and 38 mixed configurations**. Pure lower means complete reported flags, at least one offered PK–8 grade and no offered grade 9–13, ungraded or adult grade. Florida's separate native grade-school contract requires explicit zero in every Fall enrolled grade 9–12. Protected `*` denotes positive membership with an unavailable count, never zero. All 170 pure lower configurations have matching Fall profiles and satisfy that native contract; no native zero-high profile has mixed offerings in this district.

| Matched operational source/cohort set | Profiles | Subject applicability | Usable Math / ELA / Combined | Available individual income |
| --- | ---: | ---: | ---: | ---: |
| Native explicit-zero enrolled high-grade contract | 170 | 170 within source contract | 165 / 165 / 165 | 170 |
| Proposed pure lower directory | 170 | 168 | 165 / 165 / 165 | 170 |
| Proposed pure lower with offered grade 3–8 | 168 | 168 | 165 / 165 / 165 | 168 |
| Pure lower with positive/protected enrolled grade 3–8 | 168 | 168 | 165 / 165 / 165 | 168 |
| Primary-only offerings | 2 | 0 | 0 / 0 / 0 | 2 |
| Native enrolled-grade contract with mixed CCD offerings | 0 | 0 | 0 / 0 / 0 | 0 |

Native-summary applicability means membership in the explicit-zero high-grade contract and includes primary-only profiles; it does not assert tested-grade enrollment. Proposed applicability separately requires pure lower offerings including grade 3–8. Every one of the 168 applicable profiles has positive or protected enrolled tested-grade evidence. High and mixed assessment approval is not extended by this audit.

Primary `50-1931`, Lighthouse Elementary, offers PK–2 and retains individual income `88/564 = 15.603%`. Primary `50-3100`, Teen Parent Program – PK, offers PK/KG while Fall enrollment records PK 25 and KG zero; February income records zero individually eligible students among 32 enrolled. Both are CCD Regular/noncharter schools and remain nonapplicable for tested-grade outcomes. No school is relabeled by its name.

Three applicable profiles lack campus achievement: **`50-2791` The Learning Center**, CCD Special Education/charter with income `0/165 = 0%`; **`50-4100` Connections Education Center**, Special Education/charter with `48/92 = 52.174%`; and **`50-0040` Palm Beach Preparatory Charter Academy Middle School**, Added Alternative/charter with `25/34 = 73.529%`. Their source flags and missingness remain retained. Absence of usable outcomes, rather than a blanket type filter, determines these exclusions.

Among all 230 linked profiles, 39 have offered/enrolled differences, totaling 79 offered-but-explicit-zero grade cells. Forty profiles have 109 protected enrolled-grade cells. No positive or protected enrolled grade falls outside reported offers. These are configuration checks, not valid-score counts or weights for averaging proficiency.

## Original membership proof and planning reconciliation

The planning queue reports enrollment **189,634**, 168 potential ES schools and 26 potential HS schools. Exact-ID independent reconstruction from the original CCD school membership stream reproduces every planning ES/HS ID; the district Education Unit Total is retained in independent review at original row **677,810**. The planning ES set equals the 168 native source-applicable identities. This agreement does not make planning membership a model-selection rule: 165 eligible outcomes are established separately from native Florida income and achievement.

The source audit retains a bounded **58-row original total/grade subset for six exact schools**: all four missing-Fall mixed records and the two primary profiles, with the original CSV header, member, source URL/path/checksum and row references. All four missing-Fall totals are Reported zero; their retained grade counts are explicit Reported/Derived zero. Original total rows are 2,638,068 (`50-3081`), 2,640,234 (`50-3931`), 2,639,833 (`50-7023`) and 2,641,401 (`50-9063`). Their mixed offerings keep them outside pure planning cohorts, while their missing native profiles remain a separate source gap.

The primary totals are positive: **569 at row 2,625,085 (`50-1931`)** and **25 at row 2,630,569 (`50-3100`)**. They do not offer grades 3–8. CCD membership differs from February income enrollment (564 and 32, respectively); no membership value replaces native income enrollment, supplies a missing profile or creates a score denominator.

The bounded proof canonical fingerprint is `f921c39e3ccbe063b80ef69c3f5c0671ebc8d219edf305734ee9cd16cac3b1c8`; the original membership archive SHA-256 is `4a7f660c5fc5eaae488dd02fd43498f349fc828b227edd0970d5b6995ead4d4d`. The full original review retains 1,972 school total/grade rows and verifies all 234 totals as Reported. The adapter rejects missing, duplicate, foreign or wrong-scope planning IDs and changed discovery identity/enrollment metadata before conversion. No tested configuration is omitted from the planning ES set, and discovery data never approves high-school outcomes or selects native source eligibility.

## Native outcomes, individual income and missingness

Outcomes retain Florida's **2024–25 School Grades Mathematics Achievement and English Language Arts Achievement**, Level 3 or above under full-year enrollment and home-zoned attribution rules. Components include FAST, eligible FAA Performance Task and prescribed Math EOC results; FAA Datafolio is excluded. Native whole percentages remain published school totals. Grade percentages are not averaged. Combined is the equally weighted mean of eligible Math and ELA, not the percentage proficient in both.

The provider-specific `50-7001` Palm Beach Virtual Instruction Program rows remain separate: provider **302 at worksheet row 2,712** has Math 67 / ELA 81; provider **309 at row 2,713** has Math 38 / ELA 56. There is no campus achievement row. The school has individual income `9/89 = 10.112%`, but that campus income cannot support either provider's achievement population. Its CCD mixed configuration and positive/protected high-grade enrollment also remain outside the proposed pure source cohort. No provider rate is assigned to campus income, averaged across providers or converted into score counts.

Income uses same-year February Final Survey 3 individual eligibility: `(D/F free + 3/E reduced + C/R CEP direct certification) / enrolled PK–12 × 100`. CEP N is outside the numerator. USDA-adjusted funding counts and School Grades' published economic-disadvantage percentage are not substitutes. February enrollment and full-year/home-zoned achievement populations differ; CEP identification coverage and possible undercount remain proxy limitations.

All 170 pure profiles have available individual income. Across the full native roster, **mixed `50-3039` and `50-3091` have masked income count cells**, including code 4. Both percentage and survey enrollment remain unavailable. Masked code 4 cannot establish actual Provision 2 participation or a known nonzero count. All original protected/masked cells remain intact.

Seven native profiles have **zero recorded individual eligibility** with positive February enrollment and explicit zero numerator/code-4 cells. Only `50-2791` and `50-3100` are pure: the former lacks achievement and the latter is primary-only. Neither enters a usable model cohort, and no eligible school has zero recorded income. The recorded zeros remain 0%, rather than becoming missing or proving there are no low-income families.

Usable points comprise **141 noncharter and 24 charter schools**: **164 CCD Regular schools and one Career and Technical charter school**. The latter, **`50-3441` / NCESSCH `120150008242`, South Tech Preparatory Academy**, offers grades 6–8, satisfies the native zero-high contract and has published Math 67 / ELA 70, Combined 68.5, with individual income `350/528 = 66.288%`. It remains eligible; school-type labels are retained rather than used to invent a Regular-only filter. All campus charter flags agree with CCD.

Eligible income ranges from 11.196% to 93.103%, with 165 distinct ratios, mean 54.645% and sample standard deviation 22.878 percentage points. These are descriptive source statistics; no fit, leverage or influence statistic is calculated here. Every valid-score count and sampling variance stays null and sampling intervals are unavailable for entire prospective models. Enrollment, participation, published component floors, percent tested and studentization cannot manufacture valid-score denominators or supply enrollment adjustment.

## Rebuild, checks and remaining gates

Normal validation is offline from the committed audit and pinned Florida extract. Extraction reopens the original directory and income-header sources, verifies the membership ZIP checksum and reuses the committed fingerprinted membership subset; it does not restream the Deflate64 archive on every run. Bootstrap extraction accepts the separately retained original CSV subset using `--membership-evidence`. New source fingerprints require a fresh original-file audit.

```sh
.venv/bin/python scripts/audit_palm_beach.py --extract
.venv/bin/python scripts/audit_palm_beach.py
.venv/bin/python -m unittest discover -s tests -p test_palm_beach_audit.py -v
```

Nine focused tests pass in 2.912 seconds. Two producer extraction runs are byte-identical to the 1,523,978-byte committed audit, SHA-256 `67fc1f19d5f4355fff06187df5a5b6cc38f6b9a97e1cf3f1892290e0a1ad2c25`; offline replay and `git diff --check` also pass. These tests cover the complete roster/population sets, Career and Technical eligibility, primary/missing/mixed/provider flags, actual zero and masked income, protected enrollment, raw same-year income arithmetic, null denominators/intervals, offline retained headers, exact planning identities and original zero-versus-positive membership proof. Typed fingerprint corruption tests reject bool/numeric substitutions, altered years/IDs/counts/source rows, suppression, headers, provider attribution or cohort membership.

The root verification passed 53 targeted Python tests across this audit, Orange, Hillsborough, Broward, Miami-Dade, Florida and district planning. Two fresh extractions and their offline replays reproduce the frozen 1,523,978-byte artifact exactly, SHA-256 `67fc1f19d5f4355fff06187df5a5b6cc38f6b9a97e1cf3f1892290e0a1ad2c25`. Independent reviews compare all original directory and native worksheet records, all cohort/exclusion memberships and the original CCD membership reconstruction. Preservation checks retain the byte-identical canonical database, every prior source/model/provider/catalog JSON file and all 213 served files, including 211 regional files. The source README change only adds this audit's documentation. The catalog remains 51 canonical datasets, 54 ready regions, 39 released states and 11 state holds, with 71 latest assessment definitions and the unchanged 72/172 candidate queue.

The next gate is an independently reviewed numerical audit: separate same-year Math, ELA and Combined OLS fits, externally studentized residuals, a practical 30-school subject floor, rank and full/deleted-scale checks, and leverage/influence diagnostics without fit-driven selection. Canonical/static integration would subsequently require namespaced repeat imports, preservation of existing datasets, every-metric current/history comparison and browser verification. Source success alone leaves both approvals false and scope `audit_pending`.
