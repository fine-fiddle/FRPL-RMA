# Broward source and cohort audit

Broward has a reproducible 2024–25 source/cohort audit, with **source and modeling approval both false** and scope `audit_pending`. This phase establishes exact identities, population differences, native outcomes and income missingness. It does not fit regressions, import a district dataset or release a browser comparison. The existing Florida comparison and its grade-school assessment approval remain unchanged.

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

The proposed Combined income range is 0.274–100%, with 238 distinct ratios, mean 52.273% and sample standard deviation 21.041 percentage points. These are descriptive source diagnostics; no leverage, residual or regression has been calculated. Every subject's valid-score count and sampling variance is null. Sampling intervals remain unavailable for the entire future model; enrollment, percent tested and publication floors never manufacture score counts.

## Replay and remaining gates

With the pinned raw downloads available, extraction rebuilds the audit. Normal validation is offline:

```sh
.venv/bin/python scripts/audit_broward.py --extract
.venv/bin/python scripts/audit_broward.py
.venv/bin/python -m unittest discover -s tests -p test_broward_district.py -v
```

Two extraction runs must produce identical bytes. Eight focused tests cover exact source/population memberships, primary/mixed distinctions, provider and income-only records, native income arithmetic, true zero/protected/masked/suppressed values, point-only counts, offline headers, strict planning identities and typed corruption replay. Canonical fingerprints distinguish numeric zero from false metadata.

The completed source unit passed all 26 targeted Broward, Florida, Miami-Dade source and district-planning tests. Repeated extraction produced byte-identical 2,048,820-byte artifacts, SHA-256 `11e79d74cac96af228be063a9756c59aabc877cfa99217fe0b7ddc9352b9f5e1`. Two independent reviews verified the full original CCD roster and native workbook rows, headers, source hashes and exact memberships. The canonical database's SHA-256 stayed unchanged, as did all 201 existing served JSON/GeoJSON files; the only changed prior file under `data/` is this audit's added source-README documentation. No district dataset or global assessment-guide definition was added.

Before release, the proposed exact population requires a frozen independently reviewed numerical audit with separate same-year Math, ELA and Combined fits, a practical 30-school floor, rank/scale checks, every-school deleted-fit verification and influence diagnostics without fit-driven exclusions. Canonical import/repeatability, source-definition namespace, historical comparison, global catalog and browser validation remain subsequent gates. Coordinates, boundaries and admissions populations have not been audited. This source/cohort phase leaves both approval flags false and publishes no district comparison.
