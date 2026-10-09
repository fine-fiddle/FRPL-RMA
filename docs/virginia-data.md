# Virginia published school totals

Virginia uses native VDOE School Quality Profiles for **2024–25** schoolwide All Students Mathematics and English Reading pass rates, with the same year's September 30 individual economic-status counts. Ordinary grade-school and high-school models appear in one region; schools with both grade 3–8 and grade 9–12 enrollment have a separate mixed-grade region and separate regressions.

## Official sources and identity

- [School Quality Profiles](https://schoolquality.virginia.gov/) publish authoritative **Division Number** and **School Number** on each school page, native year-labelled subject-area pass-rate arrays, performance tables, grade enrollment tables, and economic-status subgroup counts.
- [The official download page](https://schoolquality.virginia.gov/download-data) supplies published assessment CSVs. An exact-school request worked, but the all-school assessment request failed with HTTP 500 or returned “No data avaialble.” The all-school enrollment CSV contains names rather than authoritative school identifiers, so it was not joined by name.
- [Data definitions](https://schoolquality.virginia.gov/glossary) and the native profile explanations describe September 30 Fall Membership and individual economic status.
- [VDOE's April 17, 2025 assessment update](https://content.govdelivery.com/accounts/VADOE/bulletins/3dc0d1d) identifies spring 2025 as the first administration measuring the new **2023 mathematics** and **2024 English** standards. Older displayed profile years are excluded from this snapshot.

The public search JavaScript exposes the native school-search endpoint:

```text
https://schoolquality.virginia.gov/wp-admin/admin-ajax.php?action=doe_rc_ajax&get=namesearch&searchval=&searchtype=school&pagenum=1&highschool=&middleschool=&elementaryschool=&combinedschool=&accreditation=&career=&special=&alternative=&charter=
```

Its school records include the official school URLs, total results and page count. The extraction traverses the complete 182-page, 1,812-school inventory and retrieves each supplied URL. School and division records in the search response are distinguished by native `search_type`. No URL is constructed from a school name. The source extract preserves each school's native division and school number; its internal school key pads these numeric codes to three and four digits respectively. Both assessment and economic status come from that same native profile, so no identity inference or name join is needed.

The current inventory can omit schools that closed before it was published. Names and category descriptions may postdate the 2024–25 results. Models use same-year grade membership rather than current category text. Raw HTML pages, native search responses and diagnostic CSV exports are retained under ignored `data/raw/virginia/`. The committed extract includes every profile source URL and SHA-256 checksum, selected native data rows, all retained raw year labels and the complete inventory request list.

## Outcome and populations

The native whole-subject **Passed** percentage includes proficient and advanced levels. VDOE explicitly states that the Assessment tab includes **SOL and VAAP** results. This is a published schoolwide assessment total, not a SOL-only rate, the `Proficient` category alone, or an accountability/accreditation measure.

The extractor selects native subject option `0`: Mathematics or English Reading, subgroup `5`: All Students. It verifies the school chart values against the corresponding native All Students **Passed** table columns and checks that their year labels agree. The selected school year is exactly `2024-2025`. The parser supports both the native indexed-array and keyed-object chart representations. A missing table row is allowed only when all native school chart values are missing.

No grade-level or course-level percentages are averaged. Grade-school totals may include end-of-course mathematics taken in lower grades; high-school totals combine applicable course tests. Participation and varying grade/course composition remain limitations. Schools are partitioned using native 2024–25 grade counts: grade 3–8 membership without high-school membership, high-school membership without grade 3–8 membership, or both in the separate mixed-grade population. A suppressed positive-grade count keeps the grade in the classification but makes income count reconciliation unavailable. Unknown/ungraded membership and schools without an applicable same-year grade span are excluded from these comparison populations.

Native profiles publish rounded integer pass percentages. They do not supply a verified exact valid-score denominator. The CSV's `Record Count` was not established as that denominator and is not used. All assessment tested counts and all sampling intervals are therefore unavailable. Externally studentized residuals are computed from the published rates; studentization does not provide enrollment adjustment or shrinkage. Combined is the equally weighted mean of math and ELA pass rates.

## Income and the portal denominator issue

The native Fall Membership **Economically Disadvantaged** subgroup describes individual status if a student is eligible for free/reduced-price meals, receives TANF, is eligible for Medicaid, or is migrant or experiencing homelessness. It is broader than FRPL alone. The separate portal meal-eligibility series explicitly treats every student in CEP divisions as meal eligible and is excluded.

Income is `100 × ED count / All Students count` for the same school's September 30, 2024 enrollment. Both individual counts must be published. Every grade subtotal, the native grade-table total, and ED plus non-ED must reconcile exactly to the native All Students count before a count ratio is used. A missing or suppressed ED count is never inferred from the non-ED complement. Missingness and suppression remain unavailable, including when a percentage is masked despite a visible count. Exact published zero eligibility is retained.

The portal has an auditable display issue: some subgroup percentages use a different denominator from the native enrollment counts, even producing All Students percentages above 100. For example, A. Henderson Elementary has native 2024–25 enrollment **818**, ED **227**, and non-ED **591**, with grade subtotals summing to **818**, but displays ED **27.819%** and All Students **100.245%**. The model uses the verified count ratio, **27.7506%**, and retains the inconsistent raw display percentages. `audit.json` records the number of affected profiles and examples. If the native counts do not reconcile, income is unavailable rather than repaired.

## Rebuild and verification

Offline rebuild uses the committed extract:

```sh
.venv/bin/python scripts/prepare_virginia.py
.venv/bin/python scripts/export_catalog.py
```

To repeat extraction, first download the exact inventory request pages and each school URL listed in their native response. Save the inventory URL map as `data/raw/virginia/inventory.json`, request list as `inventory-urls.json`, and downloaded school URL-to-file map as `profile-files.json`. Then run:

```sh
.venv/bin/python scripts/prepare_virginia.py --extract
.venv/bin/python -m unittest discover -s tests -p 'test_virginia.py' -v
```

The importer replaces only the Virginia dataset and is repeatable. Tests independently verify studentized residuals for every cohort, exact native pass-rate selection, strict mixed-grade separation, same-year IDs, suppression, income reconciliation, display denominator discrepancies, missing intervals, and repeated imports preserving unrelated datasets. No map coordinates or admissions classifications are supplied by this extract; the descriptor accurately leaves boundaries unavailable.
