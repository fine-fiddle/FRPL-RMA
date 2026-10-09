# Missouri 2024–25 source audit

The released comparison contains **regular MAP grade schools only**. It has 1,511 verified native grade-school profiles and three independent 2025 subject models: 620 math, 580 ELA and 469 Combined schools. CEP buildings, suppressed proficiency components, incomplete grade coverage, high schools and mixed schools do not enter these models. This is a substantially restricted population, not complete Missouri coverage.

## Native identity and income

The [DESE MCDS public portal](https://apps.dese.mo.gov/MCDS/home.aspx?categoryid=2&view=2), Students tab, publishes **Free and Reduced Priced Lunch Percentage by Building 2009–10 to 2025–26**. Use its **2024–2025** worksheet, whose percentage header is `2025 F&RL Percentage`. Its notes define the percentage as eligible January State FTE divided by January Membership, submitted in the February Core Data cycle. Building records exclude students educated elsewhere, including the stated desegregation and K–8 district exceptions.

The same workbook explicitly identifies CEP participating buildings and states that **all students in those buildings are reported as free lunch**. All 513 flagged records are unsuitable for individual income comparisons. Among released grade-school profiles, 362 are excluded on this basis; missing or invalid native income excludes two more. The 2024–25 file has 2,224 income building records in total.

Outside CEP, the source reports individual January FRL eligibility. Its numerator is fractional instructional-time FTE, and its membership denominator can also be fractional. The adapter preserves the **published percentage**, rather than converting these values to headcounts or reconstructing a count from a rounded percentage. It retains both native quantities and the CEP flag. Displayed enrollment comes from the separate same-year native fall enrollment file; it is not the January denominator or the tested denominator. For example, Kirksville Senior High has January FRL FTE 278.9, membership 759.77 and published fraction 0.367. The raw ratio differs slightly from that rounded source percentage.

School identity is the native six-digit county-district code plus four-digit building code. The 2025 **Supporting Building Report** supplies explicit beginning and ending grade offers. Only these metadata are used: its accountability MPI, status points and performance designations are not proficiency. **Building Enrollment**, year 2025, corroborates native grade scope and supplies fall enrollment. District-total building code zero is not a school. Names never establish a join.

## Valid-score aggregation and suppression

The [native public Performance Level Report](https://apps.dese.mo.gov/MCDS/Reports/SSRS_Print.aspx?Reportid=e7546486-3e0e-437f-902b-767f33fb0fc3) supports 2025, district, school, math/ELA, Category **Total**, Type **Total**, and individual tested grades. The `All Grades/Subjects` option yielded an empty native export for the audited districts, so the adapter does not assume a schoolwide percentage exists.

The official **2024 MAP Data Download Supporting Documentation** defines `REPORTABLE` as students receiving a MAP score, and Proficient and Advanced percentages relative to reportable students. No-score students include exempt, cheating and invalid-attempt records. Accountable enrollment and participant counts are distinct fields. The **2025–2026** documentation independently retains these definitions. These score definitions establish valid aggregation weights; neither enrollment nor a 95% accountability assignment substitutes for a score.

The [EDC 2025 Missouri regular MAP extract](https://www.eddatacenter.org/api/data/3.1?state=MO&year=2025) contains native school IDs, exact reportable counts and grade achievement counts. Its source documentation identifies MCDS as Missouri's school source. On October 9, 2026, 26 native public school/subject/grade rows from Academie Lafayette and Academy for Integrated Arts were exported through the public report's normal CSV control. All **130** reportable and performance-count/suppression cells agree with EDC. The committed extract retains these native audit rows and their source-file checksums.

The adapter calculates each subject as:

`100 × sum(Proficient + Advanced) / sum(reportable valid scores)`

Every grade in the school's native offered tested-grade range must appear once, and both proficiency components and its score denominator must be unsuppressed. This is count weighting, not averaging grade percentages. Native `*`, missingness and incomplete grade coverage remain unavailable.

EDC sometimes supplies a numeric combined proficient count even when both native proficiency components are suppressed. For Academy for Integrated Arts, third-grade ELA has 31 reportable, 18 Below Basic, 7 Basic and suppressed Proficient and Advanced; EDC also provides a combined value of 6. **The adapter ignores that combined value.** Without affirmative publication provenance, it cannot recover suppression by subtraction or by using a combined third-party column. This conservative restriction accounts for much of the lost coverage. Lower-level suppression does not prevent use when Proficient, Advanced and the independently reported score denominator are all published; when all four levels are numeric their sum must reconcile exactly.

The model excludes native offers reaching grades 9–12, EOC results and MAP alternate populations. It requires complete regular MAP grades 3–8 within each grade school's native range. Suppressed enrollment outside an explicitly unoffered grade does not become zero; the native offered grade range establishes that scope. Positive high-grade enrollment independently excludes a profile. There is no audited Missouri high-school model or location layer.

## Rebuild and verification

Raw files are ignored. Retrieve the workbooks using the exact file links recorded in `scripts/prepare_missouri.py`; export the two public assessment comparison files with the documented report controls. The adapter's `--extract` command reads these files and the EDC CSV without downloading or bypassing login. Public MCDS access follows **View Public Applications**; secure MAP raw downloads are not accessed.

```sh
.venv/bin/python scripts/prepare_missouri.py --extract
.venv/bin/python scripts/prepare_missouri.py
.venv/bin/python -m unittest discover -s tests -p test_missouri.py -v
```

Default rebuilds use committed `data/source/missouri.json`. SQLite is canonical, and the adapter emits schools, history, coverage and the catalog descriptor with `prepare_script`. It fits separate math, ELA and Combined models using externally studentized residuals; Combined is the equally weighted subject mean. All eligible subject models have verified score counts and sampling intervals. The tests independently verify studentization, count weighting, suppression, complete grade coverage, native identity, CEP exclusions and repeatable imports. State thresholds are not a common national scale, and these associations do not establish causal school effectiveness.
