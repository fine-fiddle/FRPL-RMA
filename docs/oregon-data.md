# Oregon 2024–25 snapshot

Oregon uses the state's published school assessment totals and its same-year individual Students Experiencing Poverty (SEP) enrollment measure. Grade schools and pure high schools have separate models; mixed schools and incompatible histories are excluded. Every model is point-only, with no sampling intervals or manufactured tested counts.

## Official sources and joins

The [Assessment Group Reports index](https://www.oregon.gov/ode/educator-resources/assessment/Pages/Assessment-Group-Reports.aspx) links the 2024–25 school-level, all-grades, all-student-group [Math workbook](https://www.oregon.gov/ode/educator-resources/assessment/Documents/TestResults2425/pagr_schools_math_all_2425.xlsx) and [ELA workbook](https://www.oregon.gov/ode/educator-resources/assessment/Documents/TestResults2425/pagr_schools_ela_all_2425.xlsx). Select `Academic Year=2024-2025`, `Student Group=Total Population (All Students)` and `Grade Level=All Grades`. Use the native `Percent Proficient` field directly. No individual grades or rounded performance levels are combined.

The [spring enrollment workbook](https://www.oregon.gov/ode/reports-and-data/students/Documents/spring_student_enrollment_20242025.xlsx), `Schools` sheet and `Report Year=20242025`, supplies `Total Number of Students`, `Students Experiencing Poverty`, and `Percentage Students Experiencing Poverty`. The notes identify the first school day in May snapshot. SEP flags indicate individual SNAP/TANF, foster care, homelessness or migrant services; this measure replaced Economically Disadvantaged in 2023–24. Preserve the published rounded percentage and actual source count independently.

The [2025 school metadata download](https://www.ode.state.or.us/data/ReportCard/Media/DownloadFile?schlYr=26&fldr=stateData&flNm=AAGmediaSchoolsAggregate) and [codebook](https://www.ode.state.or.us/data/ReportCard/Media/DataDoc/2025) provide native grade spans and county. Media school-year ID 26 denotes 2024–25, confirmed by its native year selector and document-list response. Join all three sources on the exact native `School ID` and require agreement on `District ID`. Names never establish identity. Only the metadata grade span is used; its accountability proficiency rates are excluded.

## Assessment population and caveats

The [June 2025 assessment inclusion rules](https://www.oregon.gov/ode/schools-and-districts/reportcards/reportcards/Documents/asmtinclusionrules2425.pdf), printed pages 4–8 and 14, define AGR performance separately from participation: resolved valid scores of students enrolled May 1, including qualifying partial tests and Oregon Extended alternate assessments, with beginning EL, invalid tests and nonattempts excluded. AGR does not use the full-academic-year restriction or the 95% denominator adjustment applied to At-A-Glance/Accountability Details. High-school resolved totals cover current grade 11 students and may credit prior-year passing high-school scores.

The workbook's `Number of Participants` differs from the performance population; some rows have more participants than students in the four performance levels. It is retained raw but never used as tested. All sampling intervals remain unavailable.

The current manual explicitly includes students assigned from district special-education programs under SB 923, superseding the workbook's stale exclusion sentence. The manual also retains conflicting older dates in some general EL paragraphs; the extraction uses its explicit A/B beginning-EL exclusion and 2024–25 AGR calculation table. The media codebook retains a 2023 date in its enrollment row; the predictor instead uses the spring workbook's explicit year and notes. These source inconsistencies are preserved in metadata.

Native grade spans determine cohorts: maximum grade 3–8 with no grade above 8 supports grade schools; minimum grade at least 9 and maximum at least 11 supports high schools. K–2-only, mixed and unknown spans are excluded. Suppression markers such as `*`, `--`, `< 5.0%` and `> 95.0%` remain unavailable; actual numeric boundary values are preserved.

## Rebuild and coverage

Ignored official downloads live in `data/raw/or-*`. The reproducible [source extract](../data/source/oregon.json) retains complete selected native rows, exclusion reasons, checksums, definitions, and primary URLs. Rebuild with:

```sh
.venv/bin/python scripts/prepare_oregon.py
```

Use `--extract` only with the audited official files present. `--database PATH` permits isolated review before canonical integration. Coverage is generated in [coverage.json](../data/oregon/coverage.json): the initial extract contains 870 grade-school and 198 high-school profiles; Combined models include 865 and 161 respectively. Missing/suppressed income excludes schools, while suppressed subjects remain unavailable without reconstructing a rate. A second import replaces only this dataset, preserving other states.
