# Florida 2024–25 grade schools

This release compares native School Grades achievement components with same-year
individual lunch eligibility. Florida's economic-disadvantage column and federal
funding lunch percentage can include USDA multipliers, so neither is used as income.

## Primary sources

| Raw file | Official download |
| --- | --- |
| `fl_assessment_2025.xlsx` | [2025 School Grades, September 8 release](https://cdn.fldoe.org/file/18534/SchoolGrades25.xlsx) |
| `fl_income_2025.xlsx` | [2024–25 final Survey 2/3 Lunch Status](https://cdn.fldoe.org/file/7584/2425LunchStatusFS2-3.xlsx) |
| `fl_grades_2025.xlsx` | [2024–25 final Survey 2 grade membership](https://cdn.fldoe.org/file/7584/2425MembBySchoolByGrade.xlsx) |
| `fl_lunch_definition_2025.pdf` | [2024–25 Lunch Status element 146025](https://cdn.fldoe.org/core/fileparse.php/20744/urlt/2425-146025.pdf) |
| `fl_guide_2025.pdf` | [2024–25 School Grades calculation guide, September 2025](https://cdn.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf) |

The files are linked by the official
[School Grades archive](https://www.fldoe.org/accountability/accountability-reporting/school-grades/archives.stml)
and [data publications archive](https://cdn.fldoe.org/accountability/data-sys/edu-info-accountability-services/pk-12-public-school-data-pubs-reports/archive.stml).
The public `cdn.fldoe.org` links download directly. URLs, SHA-256 checksums,
retrieval date, original rows and workbook notes are committed in the compact
extract. The downloads remain ignored raw files.

## Individual income without the funding multiplier

Use `2425 FS3_Schl`, Final Survey 3 (February 2025), and its raw counts:
free-eligible D/F + reduced-eligible 3/E + CEP direct-certified C/R, divided by
the same row's enrollment denominator. PK–12 enrollment is included. These are
mutually exclusive Lunch Status codes; do not add the already adjusted federal
funding numerator or multiply C/R by 1.6.

For example, `01-0031` reports 213 individually identified CEP students out of 514,
or 41.44%. Its funding count is 340 and the native School Grades economic column is
66.1%; those are different quantities. The model uses 213/514.

At CEP schools, C/R identifies direct certification or extension to household
members. N identifies children who receive meals through CEP but are not
individually identified eligible; N is outside the numerator. The direct-certified
categories include SNAP/TANF, Medicaid eligibility, and specified categorical
groups. This is individual reported FRPL/direct-certification eligibility, with
different identification methods at CEP and application-based schools. CEP income
survey coverage is incomplete; reporting coverage and undercount are unknown.

Provision 2 code 4 identifies enrollment at a Provision 2 school, regardless of
individual income. Nonzero or masked code 4 makes income unavailable. Fellsmere
Elementary (`31-0101`, 616 code 4 students) is therefore retained as a profile with
an income exclusion, rather than classified 100% economically disadvantaged. The
source masks all count fields for very small groups; none is reconstructed from
other totals or demographics. Missing February records are not backfilled from
October or another year.

## Native achievement population

Use the whole-percent `English Language Arts Achievement` and `Mathematics
Achievement` components in the 2025 School Grades file. Their denominators are
valid scores under Florida's prescribed achievement rules, with numerator Level 3
or above. These are not learning gains, overall points, letter grades, or the
percent-tested measure. No valid-score count is published in this workbook, so
all sampling intervals are unavailable; enrollment and participation are not
substitute denominators.

The [same-year guide](https://cdn.fldoe.org/file/18534/SchoolGradesCalcGuide25.pdf),
printed pages7–14, specifies full-year-enrollment and home-zoned attribution rules.
It includes eligible FAA Performance Task results and excludes FAA Datafolio.
ELA uses FAST PM3 grades 3–10; mathematics uses FAST PM3 grades 3–8 and
B.E.S.T./Access Algebra 1/Geometry EOCs. The retained grade-school cohort has no
enrolled grades 9–12 in fall Survey 2. Students testing above enrolled grade and
prescribed home-zoned students can also contribute. ELLs enter achievement after
two years in US schools; medical/extraordinary testing exemptions are excluded.
Components need at least 10 eligible students. Suppressed/unavailable components
remain missing, with no grade-level reconstruction.

Collocated schools can share an aggregate achievement calculation spanning
different school IDs (guide page8). Every row with the collocated rule used is
unavailable for school-level models; no repeated site aggregate is assigned to
one school's income. Ten provider-specific virtual rows also lack provider-level
income and are excluded. This avoids joining multiple virtual providers to an
aggregate campus income. Other source-required home-zoned attribution remains
part of the native outcome definition and is disclosed in methodology.

Income describes February enrolled children; achievement describes Florida's
full-year and attributed population. They match on school ID and school year,
without claiming identical student membership. Exact raw eligibility ratios and
native rounded achievement percentages are preserved. These state thresholds
are not a common national scale.

## Identity, scope and coverage

The authoritative district two-digit plus school four-digit ID preserves leading
zeros, for example `01-0031`. Names are never used to infer a match. Fall Survey 2
grade membership requires explicit zero in each grade 9–12; protected positive
counts shown as asterisks are never treated as zero. Twelve February income
school IDs have no fall grade-registry row and are excluded with raw records
retained. One native achievement ID (`26-0018`, Hendry Success Academy) similarly
lacks a fall grade-registry row. Changes within the year remain explicit gaps.

| Coverage | Count |
| --- | ---: |
| Fall enrolled school records | 4,009 |
| Grade-school profiles | 2,885 |
| High/mixed/protected high-grade profiles outside cohort | 1,124 |
| Eligible Math / ELA / Combined members | 2,742 / 2,742 / 2,742 |
| Grade-school code 4 unavailable/masked income | 19 |
| Grade-school February income absent | 2 |
| Provider-specific virtual assessment rows excluded | 10 |

The 19 code 4 unavailable/masked cases include 18 small-group records with all
income counts suppressed and one published Provision 2 school. Exclusion categories
overlap. All 143 profiles without Combined retain explanations. Coordinates are
unavailable because no authoritative coordinate crosswalk has been imported;
location missingness does not affect list/chart coverage or model membership.

The [Miami-Dade district comparison](miami-dade-district.md) retains exact 2024–25 CCD
LEA `1200390` / native `FL-13` school membership. It separates this statewide
enrolled-grade contract from pure offered-grade district membership,
including schools with no enrolled high grades but high-grade offerings in CCD.
The separate district directory retains 370 pure lower profiles, with 357 usable
schools in each independently audited Math, ELA and Combined model. Missing
outcomes and primary-only profiles retain their exclusions; valid-score counts
and sampling intervals remain unavailable. Historical source and numerical audits
stay immutable and unapproved; the separate normalized district release supplies
integration evidence. Florida's statewide results remain unchanged. High-school
and mixed district assessment scope require further audit.

Separate Math, ELA and Combined models use externally studentized residuals.
Combined is the equally weighted mean of subject proficiency, not proficiency in
both tests. UI filters do not refit. One year only, with no fabricated history.
The associations do not estimate causal effectiveness or overall school quality.

## Rebuild

```sh
.venv/bin/python scripts/prepare_florida.py --download
.venv/bin/python scripts/prepare_florida.py
.venv/bin/python -m unittest discover -s tests -p test_florida.py -v
```

`--download` saves official sources, extracts and imports. `--extract` reuses the
local raw files. Default preparation rebuilds offline from the committed source
through `state_snapshot.py`, replacing only `fl-schoolgrades-2025`. The descriptor
declares its checked-in preparation script; catalog readiness checks canonical
models and exports.
