# Clark County: district source and cohort audit

This audit reconciles Clark County School District's exact 2024–25 CCD roster (`LEAID=3200060`, `ST_LEAID=NV-02`) with same-year individual-school direct certification, enrollment and native Nevada SBAC grades 3–8 outcomes. It establishes reproducible source/cohort evidence only. District source and modeling approval remain **false**; no regression, canonical import or browser comparison is released by this unit. Planning's 306,038 district enrollment and potential 296 ES / 10 HS schools are discovery evidence, not approved model populations.

## Exact identity and retained sources

The [committed audit](../data/source/clark-county-district-audit.json) retains all 380 directory records, including one Future school, and links the 379 operational schools (378 Open, one New). Membership, lunch and assessment join through authoritative 12-digit `NCESSCH` and the same year. EDC's native district/school codes are cross-checked against `NV-02-sssss` using fixed two-/five-digit padding after the NCES join. Names never establish identity: EDC retains older names for the renamed FuturEdge campuses while the IDs agree.

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

The 286 usable schools are all CCD Regular: 283 noncharter and three attached-LEA charters (`320006000670`, `320006000717`, `320006000756`). Alternative, special-education and career/technical directory flags remain retained; absence of eligible points in those types follows source coverage, not a blanket type exclusion or a fit decision. The 289 source profiles retain Miley's unavailable special-education outcomes. Eligible income spans 9.758–86.774%, with 286 distinct values, mean 52.611% and sample standard deviation 16.175 percentage points; these describe the cohort, without assessing numerical model stability.

EDC's G38 rows report 614 `SchVirtual=No`, four `Yes`, and two `Supplemental virtual` observations across subject rows. Odyssey K–5 (`320006000488`, supplemental virtual) and NV Learning Academy ES (`320006000949`, virtual) lack usable DC income. NV Learning Academy JSHS (`320006000845`, virtual) has mixed offerings. These source exclusions remain distinct from virtual metadata; virtual labels do not add a new exclusion policy, and CCD virtual status remains null.

The retained Nevada Final 2a `CCD-0007` note says some districts classified directly certified students as reduced-price rather than free lunch. Its 18 listed schools are outside Clark County. This remains a Nevada definition/reporting caveat; the audit does not infer a Clark-specific allocation failure or substitute other meal categories.

## Replay and next gates

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

The next unit must review/freeze the district population and independently fit separate same-year Math, ELA and Combined models with externally studentized residuals, a 30-school floor and deletion/influence diagnostics. Canonical import, preservation/repeatability, separate district metadata, static exports and browser checks are later release gates. No source audit count or statewide residual approves or replaces those checks; results remain associations rather than causal school effectiveness or overall quality.
