# Hawaii 2024–25 data

Hawaii’s comparison uses the official state **Key Performance Indicator (KPI)** school proficiency release, joined to individual same-year CCD direct certification. It includes general Smarter Balanced, Hawaiian-language KĀʻEO and HSA alternate assessments. These have different achievement standards. This release provides grade-school comparisons only.

## Native assessed-student measure

The [ARCH report archive](https://arch.k12.hi.us/reports/strivehi-performance), with school year 2024–2025 selected, links the [December 2, 2025 updated workbook](https://doe-arch-prod-reports-repository-565393024988.s3.us-west-2.amazonaws.com/strivehi-performance/2025/2024-25KPIMasterDataFileUpdate20251202.xls) and [dated 2025 KPI Technical Guide](https://doe-arch-prod-reports-repository-565393024988.s3.us-west-2.amazonaws.com/strivehi-performance/2025/KPI_Technical_Guide_2025.pdf). The adapter uses `KPI School Data 2025`, `Year=2025`, `Subgroup Description=All Students`, and the native LA and Math Proficiency columns. Native whole-number school totals are retained without grade averaging.

Guide pages 3–4 explicitly define proficiency as proficient **Full School Year students receiving a valid test score / FSY students receiving a valid test score**. FSY requires enrollment at the same school on the official fall count, last Wednesday in January and spring participation count. The [Commission FSY guide](https://drive.google.com/file/d/1HYPfNsUangI3zF27NFB6vU-CqCefs9Cb/view) explains these dates and why state-level DOE 1-year results include some students who changed schools.

This state KPI measure differs from older federal ESSA achievement reporting, which can assign nonparticipants nonproficient results under a 95% rule or pool small populations across years. Those federal measures are not imported. The current KPI guide page 8 and workbook advisory suppress n-sizes below 11; `--` and blank remain unavailable. The workbook has no tested denominators, so all three models have point estimates without sampling intervals. No counts are inferred from rounded rates or privacy thresholds.

## Individual economic predictor and identity

[CCD 2024–25 Final 2a lunch](https://nces.ed.gov/ccd/Data/zip/ccd_sch_033_2425_l_2a_073025.zip) supplies individually reported school-total direct certification. Its numerator is divided by positive, reported same-year Final 1a membership, including pre-K where enrolled. This benefits-based proxy excludes application-only income eligibility. It is distinct from full FRPL, universal meal access or a CEP claiming multiplier. The dates can differ within the academic year; membership is the fall snapshot. [NCES explains these distinctions](https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data).

Native three-digit `School ID` matches the unique school-number component of the historical CCD `HI-001-area-school` state identifier. Every native school has an exact unique match. A duplicate match fails; names never establish identity. Native Elementary/Middle/Elementary-Middle type, complete unadjusted historical grade offers and reconciled reported grade membership establish the grade-school population. Any high-school offers or nonzero ungraded enrollment of unresolved grade scope are excluded. Most native high-school profiles have ungraded enrollment, so high and mixed comparisons require their own scope audit.

The source has 296 native All Students profiles, 225 verified grade-school profiles and 224 eligible schools in each Math, ELA and Combined model. Seventy-one profiles are outside this verified scope; one retained grade school has suppressed outcomes. Coordinates are unavailable. Coverage and exclusions are exported to `data/hawaii/coverage.json`.

## Rebuild

The committed `data/source/hawaii.json` preserves native rows, workbook advisory, exact CCD identities, income flags, enrollment/grade records, source row references, URLs and SHA-256 checksums. It rebuilds offline:

```sh
.venv/bin/python scripts/prepare_hawaii.py
```

To refresh the official workbook/guide after downloading the same-year CCD archives:

```sh
.venv/bin/python scripts/prepare_hawaii.py --download --extract
```

Imports replace only this dataset. Independent deleted-school regressions verify externally studentized residuals. Combined is the equally weighted Math/ELA mean, UI filters never refit, and these state models are not a national proficiency scale or a causal effectiveness measure.
