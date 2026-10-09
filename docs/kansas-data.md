# Kansas native 2024–25 snapshot

Kansas uses a native, published school-total route with separate grade-school and high-school models. The initial snapshot contains 895 pure grade schools and 163 pure high schools, with Math, ELA and Combined available for all 1,058 profiles. Mixed schools and ambiguous grade configurations are excluded. These are point-only models; every tested count and sampling interval is unavailable. History is unavailable because the general assessment was refreshed with new scale scores and cut scores in 2025.

## Assessment scope and calculation

The official [Kansas Building Report Card performance page](https://ksreportcard.ksde.gov/assessment_results.aspx?org_no=State&rptType=3) links the [2024–25 full assessment workbook](https://ksreportcard.ksde.gov/2024_2025_Assessment_Full_File.xlsx). Its live year-selection script sets that file for program year 2025. The workbook includes both 2024 and 2025 sheets; use only `2025`, with `Student Subgroup = All Students`, `Grade = All Grades`, `Subject = Math` or `ELA`, and exact public-district organization/building codes.

The native reporting population includes general KAP and DLM alternate assessments. This is established independently of EDC's `Regular` label by the [official September 9, 2025 board meeting recording](https://www.youtube.com/live/gWQrChUA9Mg?t=6097), linked from the [official board archive](https://www.ksde.gov/state-board/meeting-information/board-meeting-resources). At 1:41:37, the KSDE assessment presenter explains that KSDE adds DLM results when KU general-assessment data return; at 1:41:53, the presenter explains combining the two; at 1:42:01, the presenter explicitly says the public report card includes alternate-assessment students. The [official minutes](https://www.ksde.gov/docs/default-source/state-board/september-9-and-10-2025-kansas-state-board-of-education-minutes-with-time-stamps.pdf?sfvrsn=7db47387_2), page 5, identify the KSDE/KU presenters and the performance-level report-card release. A dated capture of the recording's automatic captions is checksummed in source provenance; the primary recording remains the scope evidence.

The report-card help defines Level 3 as proficient and Level 4 as advanced. The [2025 KAP technical manual](https://ksassessments.org/sites/default/files/documents/technical-manuals/KAP_Technical_Manual_2025.pdf), printed page 46, also defines proficiency as Levels 3 and 4. The adapter adds the independently published, unsuppressed `Pct. Level 3` and `Pct. Level 4` from each native school-total row. This sum retains the two source categories' rounding; it is not a grade-level average. If either category is suppressed or unavailable, proficiency is unavailable. Complementary categories, tested-subgroup counts and enrollment never repair a masked category.

The native combined population includes alternate academic achievement standards. It is labeled KAP + DLM, rather than regular KAP. Pure grade schools assess grades 3–8; pure high schools use the native high-school total. Math and ELA use separate state/cohort models. Combined is the equal mean of the two published proficient-category sums.

The workbook supplies percentages and `Pct. Not Tested`, without verified valid-score denominators. All selected native 2025 public school-total rows have published `Pct. Not Tested = 0`; this does not establish a valid-score count. EDC's Kansas counts can use CCD enrollment proxies, and none are used. The model population never receives inferred counts or intervals.

## Same-year individual economic measure

The official [demographic page](https://ksreportcard.ksde.gov/demographics.aspx?org_no=State&rptType=3) explicitly says demographic information includes all enrolled students. Its public, year-parameterized service is `https://ksreportcard.ksde.gov/services/dataService.svc/getDemoChart` with:

```text
orgNo=D0101&bldgNo=0111&progYear=2025&demoType=3&rptType=1
```

This is enrolled-school `Econ. Disadvantaged`, with a complementary `Non-Econ. Disadvantaged` percentage. It is not the economically disadvantaged tested subgroup. The adapter captures the exact request URL, school code, year and unmodified response. Missing responses stay unavailable. Published percentages are used directly; no eligible count is reconstructed.

The dated [2024–25 KIDS Collection System File Specifications v1.15](https://kidsweb.ksde.gov/LinkClick.aspx?fileticket=Bjstg5HkxZ0%3d&tabid=92&portalid=0&mid=484) provide the individual reporting rules:

- Page 8 identifies the September 20, 2024 ENRL population and explicitly says that collection feeds KSDE K–12 and Building Report Card reports.
- Page 35, D34, requires each student's NSLP and/or at-risk eligibility from an application, direct certification, or the KSDE Household Economic Survey. Codes 1/2 represent individually eligible reduced/free status from applications or direct certification, including qualifying Medicaid; codes 3/4 represent individual reduced/free status from household surveys.
- CEP schools use direct-certification codes 1/2 for individually certified students and survey codes 3/4 for other individually eligible students. Universal meal service does not establish individual economic eligibility.

The FY25 Enrollment Handbook, printed page 38, reinforces individual qualification at CEP/Provision II schools. It permits the standard first-30-operating-day carryover for prior approved meal applications/direct certification, while Household Economic Surveys cannot carry over into 2024–25. The native measure retains those administrative eligibility rules. It is an economic-status proxy, not family income itself or a meal-claiming multiplier.

Displayed enrollment comes separately from reported same-year CCD membership. The exact denominator behind the rounded demographic percentage is not reconstructed or equated to CCD membership. `low_income` remains null.

## Exact identities and regression populations

The native workbook's `Org. No.` and `Bldg. No.` are strings, preserving leading zeros. Same-year CCD `ST_SCHID = KS-D0101-0111` authoritatively supplies the same organization/building codes and the NCES school ID. No school is joined by name. Native public district codes beginning `D` define this initial cohort; private and state-school organization namespaces are outside this adapter.

The 2024–25 CCD directory and membership files establish grade scope. Directory grade offers must be reported and complete, and observed grade membership must reconcile to total enrollment. Pure grade schools have tested grades 3–8 and no high-grade offers/enrollment; pure high schools have grade 10, no grade-school offers/enrollment and no adult or grade-13 offer. Unknown, adjusted and mixed configurations are excluded.

Among 1,253 native public-district assessment units, 194 are excluded for mixed, untested, adjusted or unknown grade configuration and one for unavailable native enrolled income or membership. All excluded raw rows and reasons remain in the committed extract. No complete statewide coverage or compatible history is claimed.

## Rebuild and verification

The committed `data/source/kansas.json` supports offline rebuilds with `scripts/prepare_kansas.py`; its descriptor declares the same preparation script for the full state dispatcher. Large native sources and API captures remain under ignored `data/raw/` with their URLs and SHA-256 checksums preserved.

```sh
.venv/bin/python scripts/prepare_kansas.py --database data/build/education.sqlite
```

Raw refresh requires the official workbook, KIDS specification, FY25 handbook, scope recording captions/minutes and same-year CCD directory/membership archives. The downloader captures only exact native/CCD candidate schools; the extractor performs all joins and validations:

```sh
.venv/bin/python scripts/prepare_kansas.py --download-income --extract --database data/build/kansas-audit.sqlite
.venv/bin/python -m unittest discover -s tests -p test_kansas.py -v
```

Initial validation uses an isolated SQLite database. Tests independently reproduce deleted-school externally studentized residuals in both cohorts, verify Combined, reject wrong-year/ID/population substitutions, preserve category suppression, prohibit inferred eligibility/tested counts and check repeatable imports without disturbing another dataset. A second export must be byte-identical.
