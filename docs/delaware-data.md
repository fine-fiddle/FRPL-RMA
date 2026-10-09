# Delaware 2024–25 native snapshot

Delaware uses separate regular Smarter Balanced grade-school and SAT high-school models. Native school totals supply actual proficiency and explicitly documented valid-score counts. The predictor is individual SNAP/TANF direct certification divided by same-year native end-of-year enrollment.

## Public data and definitions

The DDOE [assessment dataset](https://data.delaware.gov/Education/Student-Assessment-Performance/ms6b-mt82) and its [machine-readable field dictionary](https://data.delaware.gov/api/views/ms6b-mt82.json) explicitly define `tested` as completed assessments with valid scores, and `pctproficient` as proficient students divided by tested students. Select year 2025, school rather than district/state, and `All Students` in race, gender, grade, special population, geography and subgroup. Native `Smarter Balanced Summative Assessment` covers grades 3–8; `SAT School-Day (Spring)` covers grade 11. Alternate DeSSA, ACCESS, science/social studies and SAT essay are excluded. Use the native total, never a grade-percentage average.

The [enrollment dataset](https://data.delaware.gov/Education/Student-Enrollment/6i7v-xnmf) uses the ending-year convention and explicitly defines `students`, `eoyenrollment` and `pctofeoyenrollment`. Select year 2025 and the native whole-school `Low-Income` row with other dimensions `All Students`. Divide its independently published individual count by its own end-of-year denominator. The September `fallenrollment` field is a different collection and is never substituted.

DDOE's [low-income methodology](https://education.delaware.gov/community/funding-contracts/federal-and-state-programs/title-programs/low-income-measure-and-title-i-schools/) identifies TANF/SNAP direct certification as the general low-income measure since 2013–14. Medicaid is separately added for Consolidated Grant Application purposes. That broader grant measure, meal access and CEP claiming percentages are not substituted. The schoolwide enrolled predictor and tested population differ; results describe their association.

All native percentages must reconcile to independently published numeric counts within their two-decimal rounding precision. Missing and redacted fields remain unavailable. No protected percentage or count is reconstructed. Published valid-score counts support sampling intervals. If a future eligible member lacks a count, the shared pipeline omits intervals for its entire affected model while preserving approved native rates.

## Authoritative identity and source inconsistencies

Join the same-year [public education organization directory](https://data.delaware.gov/Education/Delaware-Public-Education-Organization-Directory/p3ez-si4g), income and assessment records on both exact native `districtcode` and `schoolcode`. Names never establish joins. The directory must identify a unique public reporting unit with a native historical grade span: maximum grade 3–8 supports grade schools; minimum at least 9 and maximum at least 11 supports high schools. Mixed, unknown and untested spans are excluded.

The native 2025 enrollment query contains 542 exact duplicate records. Full JSON equality is checked before collapsing copies; conflicting rows cause failure. The directory also reuses school codes across differing public campus records, names and grade spans. Those ambiguous units are excluded instead of choosing a name or assigning one aggregate income to multiple campuses. Administrative-office rows are excluded by their native organization type. The source extract retains the conflicting public rows and exclusions. This restricts coverage, including some charter reporting units.

Six models use externally studentized residuals, separately by assessment, level and subject. Combined is the equally weighted Math/ELA mean. UI filters do not refit models. This is one snapshot, without historical connections, admissions classification or audited map coordinates. See `data/delaware/audit.json` for coverage.

## Rebuild

Normal rebuilding uses the committed [source extract](../data/source/delaware.json):

```sh
.venv/bin/python scripts/prepare_delaware.py
.venv/bin/python scripts/export_catalog.py
```

To refresh the six public Socrata files and their field dictionaries:

```sh
.venv/bin/python scripts/prepare_delaware.py --download --extract
```

The adapter saves exact query URLs and SHA-256 hashes, raw suppression/status fields, source row indices and native directory evidence. It rejects a query that reaches its record limit rather than silently truncating it. Raw downloads and SQLite files remain ignored.

Tests cover valid-score definitions, exact native counts, independent end-of-year income, wrong-year/foreign-ID substitutions, cohort mixing, disclosure controls, duplicate conflicts, repeated imports and independent deleted-school calculations for all six models.
