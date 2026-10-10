# Hillsborough County district source audit

Hillsborough County's separate 2024–25 source audit identifies **219 usable pure grade-school records for each of Math, ELA and Combined**. This phase audits identities, populations, income, outcomes and exclusions. It fits no district regression and publishes no district comparison. Both `approved_for_source` and `approved_for_modeling` remain false, with status and scope `audit_pending`; independent numerical review and canonical/browser integration remain separate gates.

[scripts/audit_hillsborough.py](../scripts/audit_hillsborough.py) rebuilds and checks [data/source/hillsborough-district-audit.json](../data/source/hillsborough-district-audit.json). The artifact retains the full district directory, original native worksheet rows and headers, exact cohort IDs and subject-specific missingness. Florida's existing statewide population and source definition remain unchanged.

## Exact same-year roster and provenance

The authoritative baseline is the 2024–25 CCD school directory attached to **NCES LEA `1200870` / native LEA `FL-29`**. All 309 district records are retained: 293 operational (292 Open, one Added), 13 Closed and three Future. Every link keeps its NCESSCH, native state code, original CSV row, status, school type, charter flag and offered-grade flags. Only the documented `FL-` prefix is removed from `FL-29-ssss` to join Florida's `29-ssss` registry. School names never establish identity.

Florida has 291 native Fall Survey 2 grade profiles: 289 match the exact operational roster, and two remain outside it. `29-6608`, Village of Excellence, matches a CCD Closed record and has a protected native grade-2 count. `29-7006` has no exact attached-LEA directory key and has a protected grade-10 count. Neither has February income or campus achievement, and neither enters an operational cohort. Four operational records have no Fall profile: `29-3525`, `29-6529`, `29-6531` and `29-7001`. Their directory identities and exclusions remain explicit rather than acquiring inferred grade scope.

There are 289 February income rows and 260 native assessment rows. All assessment rows are campus rows matching the operational roster; no provider-specific or collocated row is observed. There are no income-only rows. The directory has no virtual-status field, so CCD virtual status remains null; a school name cannot establish virtual status or justify an exclusion. Native school/program flags remain retained separately.

Pinned sources include the original [CCD directory ZIP](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip), [CCD school membership ZIP](https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip), [School Grades workbook](https://cdn.fldoe.org/file/18534/SchoolGrades25.xlsx), [Final Survey 3 lunch workbook](https://cdn.fldoe.org/file/7584/2425LunchStatusFS2-3.xlsx), [Fall membership workbook](https://cdn.fldoe.org/file/7584/2425MembBySchoolByGrade.xlsx), [School Grades calculation guide](https://cdn.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf) and [Lunch Status definition](https://cdn.fldoe.org/core/fileparse.php/20744/urlt/2425-146025.pdf). Their URLs, local paths and SHA-256 values are retained. Native source rows are original worksheet/CSV row references, not positions in a filtered audit.

The complete district directory and its column header are fingerprinted. Florida source notes retain the lunch definitions and assessment/grade year and column headers; the first three original `2425 FS3_Schl` income header rows are retained separately. The entire committed Florida extract is pinned to SHA-256 `523afad888444e875fc8d06486b20240896341d55b14d9484e8b935888f66daf`, with an additional canonical-payload fingerprint. Replay rejects changed identities, years, source cells, suppression, headers or membership rather than silently deriving a new population.

## Offered grades, enrolled grades and applicability

The 293 operational CCD records comprise **224 pure lower offered configurations, 34 pure high configurations and 35 mixed configurations**. Pure lower means complete reported flags, at least one offered PK–8 grade and no offered grade 9–13, ungraded or adult grade. Florida's native grade-school contract instead requires explicit zero in every Fall enrolled grade 9–12. A protected `*` denotes positive membership with an unavailable count and never becomes zero. The two definitions are preserved independently.

Of the 224 pure lower directory records, 222 have Fall profiles. The two missing profiles, `29-6529` and `29-6531`, offer PK only. Thus the full directory inventory has four primary-only schools, while the matched source directory has two. Every one of the 220 offered-tested pure lower configurations has a matching Fall profile and satisfies the native explicit-zero high-grade contract.

| Matched operational source/cohort set | Profiles | Subject applicability | Usable Math / ELA / Combined | Available individual income |
| --- | ---: | ---: | ---: | ---: |
| Native explicit-zero enrolled high-grade contract | 223 | 223 within source contract | 219 / 219 / 219 | 223 |
| Proposed matched pure lower directory | 222 | 220 | 219 / 219 / 219 | 222 |
| Proposed pure lower with offered grade 3–8 | 220 | 220 | 219 / 219 / 219 | 220 |
| Pure lower with positive/protected enrolled grade 3–8 | 219 | 219 | 219 / 219 / 219 | 219 |
| Matched pure lower with primary-only offerings | 2 | 0 | 0 / 0 / 0 | 2 |
| Native enrolled-grade contract with mixed CCD offerings | 1 | 1 within source contract | 0 / 0 / 0 | 1 |

“Applicability” in the native summary means membership in the explicit-zero high-grade source contract; it does not assert that all 223 schools enroll a tested grade. Proposed district applicability separately requires verified pure lower offerings including grade 3–8 and the native contract. The full 224-school CCD inventory, missing-Fall records and matched source sets each retain their exact IDs.

The matched primary-only schools `29-5372` and `29-5375` are CCD Special Education/noncharter schools. They retain available February income and unavailable outcomes, with primary-only nonapplicability taking precedence for the proposed cohort. `29-7817`, Big Bend Academy of Math and Science, offers KG–8 but has explicit zero Fall enrollment in every tested grade 3–8 and no campus achievement row. It stays offered-applicable and unavailable; it is not relabeled primary-only. The mixed-offering Alternative/noncharter `29-4324`, The Spring, satisfies the native zero-high contract and has individual income `12/20 = 60%`, but no campus achievement. Its mixed configuration remains outside the pure district proposal. Florida high and mixed assessment populations are not extended by this audit.

Among the 289 linked profiles, 29 have offered/enrolled differences, comprising 101 offered-but-explicit-zero grade cells. Thirty-three linked profiles have 142 protected enrolled-grade cells. Across all 291 native profiles, including the two outside records, the protected counts are 35 profiles and 144 cells. No positive or protected enrolled grade in an operational linked profile falls outside a reported offering. These are configuration checks, not valid-score denominators or weights for averaging proficiency.

## The planning discrepancy

The planning queue reports district enrollment 220,360, 218 potential ES schools and 34 potential HS schools. These are discovery evidence. Exact-ID reconciliation finds two additional source-applicable and usable Regular charter schools: **`29-7791` / NCESSCH `120087008438`** and **`29-7805` / NCESSCH `120087008556`**. No planning ES school lies outside the proposed source set.

A bounded original CCD membership read retains all 19 Education Unit Total and grade-subtotal rows for these two schools, together with the original CSV header, member name and archive fingerprint. Their total rows are **2,485,085 and 2,485,702**, respectively. Both totals and every retained grade subtotal have blank `STUDENT_COUNT` and `DMS_FLAG=Suppressed`. This explains their omission from the discovery screen's reported-positive-membership criterion. Suppression does not mean zero. Their independent Florida Fall, individual income and achievement records remain valid, so neither is removed from the proposed source cohort.

The bounded evidence has canonical fingerprint `d9bf79b3407bcfdce6102ddf97e09d6a1a18aa81aa20749e419c42af4a459375`; the original membership archive SHA-256 is `4a7f660c5fc5eaae488dd02fd43498f349fc828b227edd0970d5b6995ead4d4d`. Membership evidence documents discovery exclusions only. It is not a proficiency denominator or a model-selection filter. The extractor also rejects duplicate, foreign, missing or wrong-scope planning IDs and changed discovery identity/enrollment metadata before converting IDs.

## Native outcomes, individual income and missingness

Outcomes retain Florida's **2024–25 School Grades Mathematics Achievement and English Language Arts Achievement**, Level 3 or above under the full-year enrollment and home-zoned attribution rules. The native components include FAST, eligible FAA Performance Task and prescribed Math EOC results. They are published whole percentages rather than reconstructed grade averages. All 260 retained campus rows have published Math and ELA components, but publication supplies no verified valid-score denominator. A component publication floor of ten eligible students and percent tested cannot reveal the missing count. Combined is the equally weighted mean of usable Math and ELA, not the percentage proficient in both.

Income uses same-year February Final Survey 3 individual eligibility: `(D/F free + 3/E reduced + C/R CEP direct certification) / enrolled PK–12 × 100`. CEP N is outside the numerator. USDA-adjusted funding counts and School Grades' published economic-disadvantage percentage are not substitutes. The February income and full-year/home-zoned assessment populations differ; CEP identification coverage and possible undercount remain limitations of this proxy.

All 222 matched pure lower profiles have available individual income. Across the full native registry, `29-7004` has masked income count cells, including Provision 2 code 4; this exclusion cannot establish actual Provision 2 participation. The two outside profiles lack income rows. No verified zero individual-income ratio is observed, although reported zero component cells remain preserved and a verified zero would remain zero. Protected, masked and absent values remain unavailable rather than becoming zero.

All 219 usable proposed points are CCD Regular schools: **184 noncharter and 35 charter**. Charter and school-type flags are retained without anticipated-fit exclusions; all campus charter flags agree with CCD. The eligible income range is 0.767–98.895%, with 219 distinct values, mean 61.482% and sample standard deviation 25.843 percentage points. These are descriptive source statistics; no regression or influence statistic is calculated here.

Every subject's valid-score count and sampling variance remains null, and sampling intervals are unavailable for each entire proposed model. Enrollment, participation, published floors and studentization cannot manufacture score counts or supply enrollment adjustment.

## Rebuild, validation and remaining gates

Normal validation is offline from the committed audit and pinned Florida extract. Extraction opens the original directory and income-header sources, verifies the membership ZIP checksum, and reuses the committed fingerprinted membership subset; it does not restream every original membership cell on each run. Bootstrap extraction accepts the separately retained subset produced by an original CSV stream via `--membership-evidence`. A source change requires a fresh source audit and new reviewed fingerprints.

```sh
.venv/bin/python scripts/audit_hillsborough.py --extract
.venv/bin/python scripts/audit_hillsborough.py
.venv/bin/python -m unittest discover -s tests -p test_hillsborough_district.py -v
```

Nine focused tests pass. They cover the complete directory and separate matched populations, primary/mixed and offered/enrolled distinctions, unavailable and true-zero semantics, protected/program exclusions, native income arithmetic, null score counts/intervals, offline headers, original suppressed membership proof, strict planning identities and typed source corruption. Canonical fingerprints distinguish numeric zero from false metadata and reject count/source-row type changes.

The frozen source artifact is 1,894,806 bytes, SHA-256 `33a01a1cc919e7357319b9deba0f17dd2b891a6af8b0456253cd4588da659a40`. Extraction in one environment must reproduce identical bytes. No canonical database import, served JSON, catalog/provider definition, coordinates, boundaries or admissions population is part of this unit.

The completed unit passed all 35 targeted Hillsborough, Broward, Florida, Miami-Dade source and district-planning tests: nine new tests and 26 existing tests, in 11.571 seconds. Two extraction runs produced bytes identical to the committed audit. Two independent reviews verified the original CCD directory, native workbook rows/headers and exact cohort memberships; the bounded membership proof retains separately streamed original CSV rows. The canonical database and all 205 existing served JSON/GeoJSON files retain their previous checksums. The only changed prior file under `data/` is added source-README documentation. Catalog counts remain 49 canonical datasets, 52 ready regions across 39 states, 11 source holds and 69 latest assessment definitions. The district queue retains 74 first-tier and 172 second-tier candidates.

The next gate is an independently verified numerical audit: separate same-year Math, ELA and Combined district fits, externally studentized residuals, a practical 30-school subject floor, full/deleted scale and rank checks, and explicit leverage/influence diagnostics without fit-driven membership changes. Canonical/static integration would then require repeat imports, preservation of existing datasets, every-metric export comparison and browser verification. Source success alone leaves both approval flags false and scope `audit_pending`.
