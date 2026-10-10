# Fairfax County source and cohort audit

Fairfax County Public Schools is a separately audited prospective **2024–25 grade-school comparison**, using the existing Virginia native source contract. This step establishes **152 usable schools for each Math, ELA and Combined subject**, from 162 exact native grade-school profiles. It does not fit district models, approve source/model release, import a canonical dataset or create a browser comparison. The source artifact retains `status: audit_pending`, `scope: audit_pending`, and both approval flags as false. Independent numerical diagnostics, canonical integration and browser verification remain required.

## Source evidence and exact identities

[`fairfax-district-audit.json`](../data/source/fairfax-district-audit.json) preserves the entire exact attached-district roster and source evidence:

- **223** original 2024–25 CCD directory records, all operational/Open, with all offered-grade flags, exact status/type/charter values, full source columns and original CSV row references.
- **1,689** original CCD school membership records: **199** school totals and **1,490** complete retained grade subtotals. The other 24 directory programs have no membership rows; absence is not zero.
- **965** original CCD lunch records, retained as supplemental evidence. They never replace the native Virginia individual economic-status measure.
- **195** exact native division-29 profiles from the complete **1,812-school** audited Virginia inventory. Each original HTML page is checksum-verified and reparsed; all retained raw year labels, grade tables, subgroup counts, Math/ELA chart values and performance categories match the complete committed extract.
- Five original definition/population HTML fragments per native school, with original source line references, covering SOL/VAAP scope, reading and mathematics grade/course populations, September 30 Fall Membership and individual economic status.
- All eight worksheets of the original CCD Final 2a notes workbook, including all 561 Data Notes rows, headers, membership/grade metadata, business rules and post-submission revisions. Workbook dates retain explicitly typed ISO values.

Every raw source has its official URL and SHA-256 checksum. The entire committed [`virginia.json`](../data/source/virginia.json) is pinned to SHA-256 `fff223450f4a03d1763e8704d7b2b95cd67fde27213e67582c457de24febfccc`; offline validation checks the complete statewide extract before replaying the district subset. The full retained original input fingerprint is `8be5fa3da5953fe1a9229e574a5ac67db7486e30ec73de80e365e26bcf75f7bd`.

The exact district is NCES LEA **5101260**, native **VA-029**. CCD `ST_SCHID` already contains the complete seven-digit native division/school key: for example, `VA-029-0290131` maps to `0290131`, whose same-profile native Division Number is `29` and School Number is `131`. Remove only the exact `VA-029-` prefix; do not prepend the division again, shorten the source code, match names or construct school URLs from names. All 195 native profiles cross-check to exact CCD identities; no native profile lies outside the complete attached roster. Names and current category descriptions remain display evidence and may postdate the results.

## Prospective populations and outside records

Population membership follows the existing [Virginia enrolled-grade contract](virginia-data.md), using the profile's exact **2024-2025** grade counts. Schools with positive native grade 3–8 membership and no positive high-school membership are grade schools; high-only and mixed grade 3–8/high-school spans are separate populations. Positive unsupported grade labels remain unclassified. Complete CCD offered flags and strict offered intersections are separate completeness diagnostics, never an extra population filter.

| Native same-year population | Profiles | Usable Math | Usable ELA | Usable Combined | Prospective release |
| --- | ---: | ---: | ---: | ---: | --- |
| Grade schools | 162 | 152 | 152 | 152 | Numerical and integration audits pending |
| High schools | 25 | 23 | 23 | 23 | Below 30-school floor; unreleased |
| Mixed-grade schools | 4 | 1 | 1 | 1 | Below 30-school floor; unreleased |
| Unclassified | 4 | 0 | 0 | 0 | No approved native population |
| CCD schools without native profiles | 28 | 0 | 0 | 0 | Native income/outcomes unavailable |

All 162 native grade schools independently match the strict complete CCD pure-grade offering intersection and the 162 planning grade-school IDs. That agreement is reported after reconstruction; the planning screen did not select income or outcomes. All 152 usable grade schools are observed as Regular School and noncharter. Type, current category, admissions labels and model fit are not selection rules. The complete roster retains 194 regular, 11 alternative, seven special-education and 11 career/technical schools, all noncharter. No authoritative admissions or virtual-status classification is supplied.

Three native profiles—Bailey's Elementary `0290550`, Fort Belvoir Elementary `0292224` and McNair Elementary `0292231`—are primary-only with no applicable grade 3–8 or high-school population; their published missing assessment arrays remain missing. Lake Braddock Secondary `0290090` has grades 7–12 plus explicitly published **Post Graduate: `1`** in 2024–25. That positive unsupported label keeps its native population unclassified, despite its mixed CCD offerings, reconciled native income and published Math **87%**/ELA **90%**. It is not relabeled Ungraded, silently truncated or included in the mixed cohort.

Every one of the **28** CCD-only identities is retained individually, with its exact source records and missing-native explanation. Four PK-only centers have **784** reported CCD pupils. The other 24 programs explicitly report `NOGRADES: Yes`, every offered-grade flag `No`, including `G_UG_OFFERED: No`, and have no original CCD membership rows. These records establish neither zero enrollment nor Ungraded enrollment. None offers grades 3–8, so the missing native records do not conceal a school in the complete prospective pure-grade population. They still receive no imputed native income, outcome or source approval.

## Native outcomes, income and count limitations

Outcomes are the exact profile's native **All Students** subject option **0** Mathematics or English Reading **Passed** percentages for 2024–25. The source Assessment tab includes **SOL and VAAP**. Passed includes proficient and advanced; their separately rounded category percentages are retained rather than summed to replace Passed. No grade/course percentages are averaged. Lower-grade mathematics totals can include secondary course tests; varying tested grade/course mixes remain a limitation. Combined is the equal mean of eligible Math and ELA pass percentages, not the fraction proficient in both.

[VDOE's April 17, 2025 standards update](https://content.govdelivery.com/accounts/VADOE/bulletins/3dc0d1d) identifies spring 2025 as the first SOL administration for the new 2023 mathematics and 2024 English standards. Older and later displayed profile years remain raw evidence but do not enter this proposed single-year snapshot. The full native definition and coverage notes are retained independently from supplemental CCD notes.

Economic disadvantage uses the native same-profile September 30 All Students and individually classified **Economically Disadvantaged** counts. The source definition includes meal eligibility, TANF, Medicaid eligibility, migrant status or homelessness; this is broader than FRPL alone and differs from portal CEP meal-service coverage and CCD direct certification. ED plus non-ED, every same-year grade subtotal and the grade-table total must reconcile exactly to All Students. Required counts and the displayed ED percentage must be unsuppressed. Native comma-formatted counts are parsed numerically while their exact original strings remain retained.

**15** native profiles fail the complete grade-count reconciliation contract: ten grade schools, two high schools and three mixed schools. Their masked/missing grade cells stay unavailable even when the other subtotals appear to imply zero. A suppressed ED count is never inferred from the non-ED complement. The 152 usable grade-school income percentages are distinct, ranging from **1.7013%** to **98.7037%**; this source audit computes descriptive coverage only, without regression diagnostics.

**128** native profiles have stale displayed ED percentages that differ from the independently reconciled count ratios. The model input proposal uses `100 × ED / All Students` only after complete native count reconciliation and retains the inconsistent display percentages. Native membership totals also differ from CCD: the 195 native profiles sum to **179,770**, while those same 195 CCD schools sum to **178,539**; 163 individual totals differ. All 199 reported CCD school totals sum to **179,323**, agreeing with the planning LEA total. These are source/timing/coverage diagnostics; CCD enrollment never repairs or replaces native income or grade membership.

The native profiles publish rounded pass percentages without verified exact valid-score denominators. Every prospective subject's valid-score count, sampling variance and interval remains unavailable. Enrollment, CCD counts, ED counts, portal CSV Record Count and participation are never denominator substitutes. This audit fits no models and creates no district results; future studentization cannot supply enrollment adjustment, shrinkage or missing intervals.

## Rebuild and verification

Ordinary offline replay requires only the committed audit and complete Virginia extract:

```sh
.venv/bin/python scripts/audit_fairfax.py
.venv/bin/python -m unittest discover -s tests -p 'test_fairfax_source.py' -v
```

Re-extract from the pinned original CCD archives, notes workbook and every saved native Fairfax profile:

```sh
.venv/bin/python scripts/audit_fairfax.py --extract
```

The script streams the original Deflate64 school membership archive with `unzip -p`. `--membership-evidence` optionally accepts a separately verified complete original district subset with original archive provenance, header and CSV row references; the resulting full input fingerprint must still match exactly. Default extraction always reopens the original membership archive. No planning count participates in native eligibility.

Validation rejects changed whole-state fingerprints, source URLs/checksums, exact identities/years, raw counts/flags, missing record deletions, row/header references, native definitions, population membership, floor/hold flags, manufactured valid-score counts and model payloads. The audit does not call canonical imports or statistical fitting. Preserve existing statewide and district comparisons while the later Fairfax numerical and integration steps are completed.

The completed source unit passed **49 targeted Python tests**, syntax/diff checks, **60 local documentation links** and two independent original-source reviews. One reviewer checked **106,323** typed original/derived fields; the other checked **66,953** source fields, **19,086** original native HTML fields and all **975** definition fragments. Their **53** additional scientific/provenance corruption probes were rejected. Two fresh full-original-archive rebuilds reproduce the exact **4,854,357-byte** committed artifact, SHA-256 `cf2fe4641d7b274fc46abff23b019bf044cd7404e484bddb408ac2eb8d145723`; offline replay also passes.

The canonical database and all nine tables are byte-identical to the pre-audit snapshot. All **221 served files / 219 regional files** and **160 existing code/test/UI files** remain unchanged; the only existing data-file change is a source README insertion. Catalog/assessment/provider/planning JSON and previous audits remain unchanged: **53 datasets / 56 ready regions / 39 states / 73 latest definitions**, **11 state holds**, and **70 first-tier / 172 second-tier district candidates**. This source-only step creates no district fits or browser behavior to validate. The next unit independently verifies the 152-school district Math/ELA/Combined full and deleted-school fits, leverage, income spread and sensitivity before canonical/browser integration. High/mixed and unclassified populations remain unreleased.
