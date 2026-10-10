# Wake County source and cohort audit

Wake County Schools has a prospective **2024–25 grade-school comparison** with **159 usable Math, 160 ELA and 159 Combined records**. The [source audit](../data/source/wake-district-audit.json) reconstructs the original records before checking agreement with the existing North Carolina extract. Its scope is `source_cohort_audit_only`, status is `audit_pending`, and both approval flags remain false. Independent numerical validation and canonical/browser integration are still required.

## Exact identities and original evidence

The attached district is NCES LEA **3704720**, native **NC-920**, DPI public school unit **920**. A complete native CCD school ID such as `NC-920-314` maps to DPI school code `920314` and its exact same-year NCES school ID. Names never establish membership. The native district aggregate `920LEA` remains outside every school cohort.

The artifact preserves official URLs, SHA-256 checksums, source headers and original row references for:

- All **202** original CCD school directory records: **198 operational schools** and **four future schools**. Exact status, school type, charter fields and every offered-grade flag remain available.
- Original individual school membership totals and complete grade subtotals, plus the original CCD LEA directory and membership total. These are scope and discovery evidence, never assessment denominators.
- All **5,792** native All Students performance rows for Wake schools and its district aggregate, across every published assessment type, subject and grade. Only exact regular grade-school Math/ELA rows can supply the proposed outcomes.
- All **199** original **APR 2025** income rows for PSU 920, including the district aggregate. Raw percentages, enrollment, other meal-service measures, cell types and suppression remain retained.
- Full original performance codebook, EDS collection and 2024–25 accountability technical-guide text, plus the original official EDS definition webpage. The codebook embedded in the performance archive is independently checksum-verified.

The complete existing `north-carolina.json` is also pinned and replayed. Its previously released statewide comparison remains unchanged. The planning queue is checked only after reconstructing the original exact district and school records; planning membership does not approve a model or replace native sources.

## Prospective population and exclusions

Grade schools require complete, reported CCD PK–8 offerings, reconciled lower-grade enrollment, explicit Reported/Derived zero outside-grade records, no high/adult offerings and compatible native lower-grade spans. All 198 original Not Specified records retain their literal zero and Derived flag; missing or suppressed records never become zero. There must be applicable grades 3–8. The exact native assessment and April income records must match those school identities and the same year.

| Population or availability | Schools | Math | ELA | Combined |
| --- | ---: | ---: | ---: | ---: |
| Complete operational CCD grade-school configurations | 162 | 159 | 160 | 159 |
| Same-year native profiles with usable April income | 160 | 159 | 160 | 159 |
| Outside grade-school scope | 36 | Unreleased | Unreleased | Unreleased |
| Future CCD schools | 4 | Unreleased | Unreleased | Unreleased |

The two income exclusions are **Apex Friendship Elementary**, `920314` / NCES `370472003624`, and **White Oak Elementary**, `920614` / `370472003377`. Each publishes April EDS **`<5`**, which remains unavailable. Their published outcomes never repair income. White Oak also has Math **`>95`**. **Mills Park Middle**, `920502` / `370472003205`, has usable income and ELA but Math **`>95`**; it remains among the 160 profiles with unavailable Math and Combined. Exact numeric boundary values, when actually published, are distinct from these masks.

The 36 operational schools outside this prospective population comprise **29 standard high-school configurations, four high-only early colleges offering grade 13, and three mixed configurations**. The grade-13 records explain why the discovery screen lists only 29 potential high schools. Mixed schools include Longview and the two grades 6–13 leadership academies. The leadership academies publish regular GS rows, but those rows do not admit mixed schools into a pure grade-school comparison. Longview, `920324` / `370472002254`, has CCD and April income records but no school performance rows in the original archive; absence is not zero. Four future schools remain individually retained. No charter or primary-only school occurs in the exact operational roster.

All 198 reported school grade totals reconcile to their own school membership totals. Their fall total is **163,176**, while the original LEA total is **163,325**: the **149-pupil discrepancy** remains explicit. April school income denominators sum to the published district April total **164,495**; **192** individual April totals differ from fall membership. These sources have different reporting populations and timing. Neither snapshot repairs the other or supplies a tested count.

## Assessment, income and unavailable counts

Outcomes select only native **`subgroup=ALL`, `type=RG`, `grade=GS`, `subject=MA/RD`** and the direct published **`pct_glp`**. The codebook defines GLP as Level 3 and above; CCR is a different threshold. GS covers grades 3–8, including grade-8 NC Math 1 EOC in mathematics. Grade/course percentages, other composites, alternate assessments and EOC-only rows are never averaged or substituted. Combined requires both usable Math and ELA percentages and is their equal mean, not proficiency in both subjects.

The original codebook includes tests completed in 2024–25, including 2024 summer school. It labels the alternate type `EXT1`, while the data use `X1`; regular selection uses only literal `RG`. Its standalone Math 1 note says grades 9–12, whereas its code definitions include 9–13. Those original discrepancies remain explicit and do not alter the selected regular GS rows. [DPI's technical guide](https://www.dpi.nc.gov/dpischoolgradetechnicalguidedraft2024-25/open) distinguishes ordinary test-result reporting from School Performance Grades and long-term goals with federal 95% denominator adjustments. Accountability-adjusted outcomes never replace these published test results.

Income uses the exact same-year April published individual **`pct_eds`**, with its separately retained economic enrollment **`den`**. [DPI's EDS definition](https://www.dpi.nc.gov/data-reports/economically-disadvantaged) includes individual direct certification, categorical eligibility and locally established financial need. It is broader than FRPL alone and covers enrolled pupils rather than only assessed students. CEP meal-service coverage, adjusted reimbursement, `pct_nslp`, tested EDS subgroups and fall CCD counts never replace it. No low-income count is inferred from a rounded percentage. The cached definition page's older CEP reimbursement-threshold discussion is not used to determine individual economic status.

Native `num_tested` fields remain raw evidence with **unverified valid-score scope**. Verified scored counts, sampling variances and interval endpoints remain unavailable for every subject; the ten-valid-scored floor is **uncertified**. Neither published rates nor privacy suppression rules certify that denominator. Future point-only numerical work must preserve these limitations, use separate district models and retain all source-eligible members without diagnostic-based exclusions. Studentization cannot supply enrollment adjustment, shrinkage or missing sampling intervals.

## Rebuild and remaining work

Offline validation replays the frozen original input contract and complete pinned statewide extract without fitting or importing:

```sh
.venv/bin/python scripts/audit_wake.py
.venv/bin/python -m unittest discover -s tests -p 'test_wake_audit.py' -v
```

Re-extract from all pinned original archives, workbook, PDFs and HTML:

```sh
.venv/bin/python scripts/audit_wake.py --extract
```

The extractor streams the original CCD membership archives with `unzip -p`. Typed raw values, headers, rows, definitions, exact identities, years, membership, exclusions and approval flags must replay exactly. Missingness, foreign identities, altered source fingerprints, inferred counts, manufactured uncertainty and model payloads are rejected.

The completed unit passes **41 targeted Python tests**, including 14 new Wake tests, plus syntax/diff checks and local documentation-link validation. Two independent original-source reviews verify every one of the **7,715 retained original rows**, including 129,433 raw cells, all 202 school decisions and 606 subject decisions. Their **346 mutation rejections** include 38 semantic cases with the raw fingerprint guard deliberately bypassed; **48 boundary/policy checks** also pass. Two full original-source CLI extractions retain the same frozen input fingerprint and reproduce the exact **4,369,154-byte** artifact after final-policy replay, SHA-256 `6416cc99800e45e1b1f405bf62e065e12faec35924155640732827ed90b7b3b2`. Offline replay also passes. The first CLI read began before final policy wording was frozen, so its original raw inputs were replayed under the final policy before byte comparison; the second CLI read uses the final script directly.

The canonical database remains byte-identical, including all nine tables. All **229 served files**, existing source extracts, catalog, assessment/provider bindings and planning JSON remain unchanged; the source README gains only this audit's documentation. This phase adds no district fits or browser behavior.

The next unit verifies independent Math, ELA and Combined district fits, income spread, leverage and every deleted-school residual. Canonical/static integration and HTTP browser checks follow only after those gates pass. Wake remains a candidate; the **68 first-tier / 172 second-tier** queue, existing comparisons, assessment/provider bindings and all unresolved source holds remain unchanged. High/mixed assessment populations, admissions classifications, geometry and provider roles remain unaudited.
