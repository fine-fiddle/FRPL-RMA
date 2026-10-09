"""Validate the expansion ledger and audit the published CCD lunch archive.

Discovery is separate from modeling approval. This script never creates model
inputs, substitutes direct certification for FRPL, or changes the site catalog.
It uses only Python's standard library and preserves manually audited state
definitions when refreshing the CCD coverage counts.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/source/state-expansion.json"
GUIDE = ROOT / "docs/state-expansion.md"
CCD_ARCHIVE = ROOT / "data/raw/ccd_sch_033_2425_l_2a_073025.zip"
CCD_MEMBER = "ccd_sch_033_2425_l_2a_073025.csv"
CCD_URL = "https://nces.ed.gov/ccd/Data/zip/ccd_sch_033_2425_l_2a_073025.zip"

# USPS abbreviations and state FIPS from Census state.txt. DC and territories
# are deliberately not in the user's 50-state rollout.
OFFICIAL_STATES = {
    "AL": ("Alabama", "01"), "AK": ("Alaska", "02"),
    "AZ": ("Arizona", "04"), "AR": ("Arkansas", "05"),
    "CA": ("California", "06"), "CO": ("Colorado", "08"),
    "CT": ("Connecticut", "09"), "DE": ("Delaware", "10"),
    "FL": ("Florida", "12"), "GA": ("Georgia", "13"),
    "HI": ("Hawaii", "15"), "ID": ("Idaho", "16"),
    "IL": ("Illinois", "17"), "IN": ("Indiana", "18"),
    "IA": ("Iowa", "19"), "KS": ("Kansas", "20"),
    "KY": ("Kentucky", "21"), "LA": ("Louisiana", "22"),
    "ME": ("Maine", "23"), "MD": ("Maryland", "24"),
    "MA": ("Massachusetts", "25"), "MI": ("Michigan", "26"),
    "MN": ("Minnesota", "27"), "MS": ("Mississippi", "28"),
    "MO": ("Missouri", "29"), "MT": ("Montana", "30"),
    "NE": ("Nebraska", "31"), "NV": ("Nevada", "32"),
    "NH": ("New Hampshire", "33"), "NJ": ("New Jersey", "34"),
    "NM": ("New Mexico", "35"), "NY": ("New York", "36"),
    "NC": ("North Carolina", "37"), "ND": ("North Dakota", "38"),
    "OH": ("Ohio", "39"), "OK": ("Oklahoma", "40"),
    "OR": ("Oregon", "41"), "PA": ("Pennsylvania", "42"),
    "RI": ("Rhode Island", "44"), "SC": ("South Carolina", "45"),
    "SD": ("South Dakota", "46"), "TN": ("Tennessee", "47"),
    "TX": ("Texas", "48"), "UT": ("Utah", "49"),
    "VT": ("Vermont", "50"), "VA": ("Virginia", "51"),
    "WA": ("Washington", "53"), "WV": ("West Virginia", "54"),
    "WI": ("Wisconsin", "55"), "WY": ("Wyoming", "56"),
}


def load_registry(path: Path = LEDGER) -> dict:
    registry = json.loads(path.read_text())
    validate_registry(registry)
    return registry


def validate_registry(registry: dict) -> None:
    if registry.get("schema_version") != 1:
        raise ValueError("Unsupported expansion-ledger version")
    states = registry["states"]
    identifiers = [state["id"] for state in states]
    if len(identifiers) != 50 or set(identifiers) != set(OFFICIAL_STATES):
        raise ValueError("The ledger must contain all 50 states exactly once")
    statuses = {"statewide_ready", "partial_city", "implementation", "discovered", "audited_blocker"}
    for state in states:
        name, fips = OFFICIAL_STATES[state["id"]]
        if (state["name"], state["fips"], state["abbreviation"]) != (name, fips, state["id"]):
            raise ValueError(f"Invalid official identity: {state['id']}")
        if state["status"] not in statuses:
            raise ValueError(f"Unknown readiness status: {state['id']}")
        if state["status"] in {"statewide_ready", "partial_city"}:
            release = state.get("existing_release", {})
            if not release.get("source_extracts") or not release.get("scope"):
                raise ValueError(f"A ready release needs explicit scope and evidence: {state['id']}")
        if state['status'] == 'audited_blocker':
            evidence = state.get('blocker_evidence')
            if (not isinstance(evidence, dict) or not isinstance(evidence.get('summary'), str)
                    or not evidence['summary'].strip() or not evidence.get('guide')):
                raise ValueError(f'A blocked state needs concrete source evidence: {state["id"]}')
        candidate = state["candidate_snapshot"]
        if candidate["year"] != 2025 or candidate["school_year"] != "2024-25":
            raise ValueError(f"Mismatched candidate year: {state['id']}")
        if candidate["approved_for_modeling"]:
            raise ValueError("Discovery ledger cannot approve a new source for modeling")
        if not state["next_steps"]:
            raise ValueError(f"Missing actionable next step: {state['id']}")
        audit = state.get("ccd_lunch_audit")
        if audit:
            total = audit["schools"]
            for measure in ("frpl_total", "direct_certification"):
                values = audit[measure]
                if sum(values["flags"].values()) != total:
                    raise ValueError(f"Incomplete CCD totals: {state['id']} {measure}")
                if values["reported_numeric_schools"] > values["flags"].get("Reported", 0):
                    raise ValueError(f"Invalid reported CCD count: {state['id']} {measure}")
    if registry.get("browser_catalog") is not False:
        raise ValueError("This source ledger must not be represented as the browser catalog")


def reported_count(row: dict | None) -> int | None:
    if row is None or row["DMS_FLAG"] != "Reported":
        return None
    value = row["STUDENT_COUNT"]
    return int(value) if re.fullmatch(r"\d+", value) else None


def audit_ccd(registry: dict, archive: Path) -> dict:
    """Count published values without treating any value as approved income."""
    states = {state["id"]: state for state in registry["states"]}
    schools = defaultdict(dict)
    other = defaultdict(set)
    keys = set()
    record_count = 0
    match = re.fullmatch(r"ccd_sch_033_2425_l_([12]a)_073025.zip", archive.name)
    if not match:
        raise ValueError("Expected the official 2024–25 CCD lunch 1a or 2a archive")
    member = archive.with_suffix('.csv').name
    with zipfile.ZipFile(archive) as zf:
        with zf.open(member) as binary:
            reader = csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8-sig"))
            required = {"SCHOOL_YEAR", "ST", "FIPST", "NCESSCH", "DATA_GROUP",
                        "LUNCH_PROGRAM", "STUDENT_COUNT", "TOTAL_INDICATOR", "DMS_FLAG"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("CCD archive lacks required columns")
            for row in reader:
                record_count += 1
                if row["SCHOOL_YEAR"] != "2024-2025":
                    raise ValueError("CCD archive includes another school year")
                abbreviation, school_id = row["ST"], row["NCESSCH"]
                if not re.fullmatch(r"\d{12}", school_id):
                    raise ValueError(f"Invalid NCES school ID: {school_id!r}")
                key = (abbreviation, school_id, row["DATA_GROUP"],
                       row["LUNCH_PROGRAM"], row["TOTAL_INDICATOR"])
                if key in keys:
                    raise ValueError(f"Duplicate CCD observation: {key}")
                keys.add(key)
                if abbreviation not in states:
                    other[abbreviation].add(school_id)
                    continue
                if row["FIPST"] != states[abbreviation]["fips"]:
                    raise ValueError(f"State/FIPS mismatch: {abbreviation}")
                if not school_id.startswith(row["FIPST"]):
                    raise ValueError(f"State/NCES namespace mismatch: {school_id}")
                school = schools[abbreviation].setdefault(school_id, {})
                if row["TOTAL_INDICATOR"] == "Education Unit Total":
                    label = {"Direct Certification": "direct_certification",
                             "Free and Reduced-price Lunch Table": "frpl_total"}.get(row["DATA_GROUP"])
                else:
                    label = {"Free lunch qualified": "free",
                             "Reduced-price lunch qualified": "reduced",
                             "Missing": "missing_category"}.get(row["LUNCH_PROGRAM"])
                if label is None or label in school:
                    raise ValueError(f"Unexpected CCD category: {key}")
                school[label] = row
    for abbreviation, state in states.items():
        observations = schools[abbreviation]
        audit = {"schools": len(observations), "approved_as_income": False}
        for measure in ("frpl_total", "direct_certification", "free", "reduced", "missing_category"):
            flags = Counter()
            unavailable_tokens = Counter()
            numeric = []
            for school in observations.values():
                if measure not in school:
                    raise ValueError(f"Missing CCD measure: {abbreviation} {measure}")
                row = school[measure]
                flags[row["DMS_FLAG"]] += 1
                count = reported_count(row)
                if count is not None:
                    numeric.append(count)
                else:
                    unavailable_tokens[row["STUDENT_COUNT"]] += 1
            audit[measure] = {
                "flags": dict(sorted(flags.items())),
                "reported_numeric_schools": len(numeric),
                "reported_zero_schools": numeric.count(0),
                "reported_student_sum": sum(numeric),
                "unavailable_raw_count_tokens": dict(sorted(unavailable_tokens.items())),
            }
        both = equal = dc_over_frpl = dc_over_free = components_differ = 0
        for school in observations.values():
            frpl, direct, free, reduced, unknown = (reported_count(school[name]) for name in
                ("frpl_total", "direct_certification", "free", "reduced", "missing_category"))
            if frpl is not None and direct is not None:
                both += 1
                equal += frpl == direct
                dc_over_frpl += direct > frpl
            if direct is not None and free is not None:
                dc_over_free += direct > free
            if all(value is not None for value in (frpl, free, reduced, unknown)):
                components_differ += frpl != free + reduced + unknown
        audit["consistency_checks"] = {
            "both_measures_reported_schools": both,
            "frpl_equals_direct_certification_schools": equal,
            "direct_certification_exceeds_frpl_schools": dc_over_frpl,
            "direct_certification_exceeds_free_schools": dc_over_free,
            "frpl_different_from_reported_category_sum_schools": components_differ,
        }
        issues = []
        if not audit["frpl_total"]["reported_numeric_schools"]:
            issues.append("no_reported_frpl_totals")
        if not audit["direct_certification"]["reported_numeric_schools"]:
            issues.append("no_reported_direct_certification_totals")
        if all(audit[measure]["flags"].get("Suppressed", 0) == audit["schools"]
               for measure in ("frpl_total", "direct_certification")):
            issues.append("all_income_totals_suppressed")
        if both < min(audit[measure]["reported_numeric_schools"]
                      for measure in ("frpl_total", "direct_certification")):
            issues.append("different_measures_reported_for_different_schools")
        if dc_over_frpl or dc_over_free:
            issues.append("direct_certification_exceeds_reported_eligibility_count")
        if components_differ:
            issues.append("reported_frpl_total_and_components_do_not_reconcile")
        audit["issues"] = issues
        state["ccd_lunch_audit"] = audit
    registry["sources"]["ccd_lunch_2025"].update({
        "path": str(archive.resolve().relative_to(ROOT)) if archive.resolve().is_relative_to(ROOT) else str(archive.resolve()),
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "bytes": archive.stat().st_size, "member": member,
        "url": "https://nces.ed.gov/ccd/Data/zip/" + archive.name,
        "version": "Final " + match[1],
        "release": "2026-06" if match[1] == '2a' else "2025-12",
        "records": record_count, "schools_50_states": sum(len(rows) for rows in schools.values()),
        "other_jurisdictions_school_counts": {key: len(value) for key, value in sorted(other.items())},
        "audit_date": date.today().isoformat(), "approved_as_income": False,
    })
    validate_registry(registry)
    return registry


def render_guide(registry: dict) -> str:
    states = registry["states"]
    counts = Counter(state["status"] for state in states)
    source = registry["sources"]["ccd_lunch_2025"]
    audited = "schools_50_states" in source
    lines = [
        "# Expansion to all 50 states", "",
        "This is the source and implementation ledger for the expansion branch. It is separate from "
        "`data/manifest.json`: discovering a download never makes a state available in the site. "
        "The first milestone is a defensible, latest practical grade-school snapshot in every state. "
        "High-school comparisons and same-assessment histories follow separately.", "",
        "District comparisons follow the statewide basics. The [district comparison queue](district-comparisons.md) "
        "screens official district size and potential school cohorts, keeps existing CPS/NYC scopes separate, "
        "and requires a district source/model audit before adding any new comparison.", "",
        "Use one shared source contract, then integrate state adapters in small batches with their own "
        "coverage audits. A state becomes ready only after its actual inputs, same-year identity joins, "
        "definitions, model results and interface have been verified. Keep state populations separate. "
        "The existing Chicago, Illinois, NYC and Wisconsin releases are evidence for their stated scopes, "
        "not approval of new years or statewide New York.", "",
        f"Current ledger: {counts['statewide_ready']} verified statewide releases, "
        f"{counts['partial_city']} city-only release, {counts['implementation']} implementation in progress, "
        f"{counts['audited_blocker']} with an audited obstacle, and {counts['discovered']} states at source discovery. These counts describe implementation "
        "status, not whether every school or assessment is covered.", "",
        "## Shared sources and approval gates", "",
        "[EDC v3.1](https://www.eddatacenter.org/data) supplies a common assessment format with 2025 "
        "data across all 50 states. Its [methodology](https://www.eddatacenter.org/methodology) limits "
        "coverage to grades 3–8. High-school outcomes require other sources. The "
        "[technical documentation](https://www.eddatacenter.org/data_documentation/EDC_technical_documentation_v3.1.pdf) "
        "provides SEA source paths (Appendix B), identifiers (Tables 8–10), count substitutions (Table 21), "
        "and proficiency criteria (Appendix E). Portal links preserve initial discovery leads; "
        "state source guides and release records below document verified native routes and remaining issues.", "",
        "For each actual state-year extract:", "",
        "- Preserve source URLs, checksums, raw suppression/range values, assessment names/types, "
        "grade coverage, proficiency criteria and change flags.",
        "- Join an audited enrollment-based economic measure from the same school year through exact "
        "authoritative IDs. Assessment subgroup tested ratios cannot replace enrolled economic disadvantage.",
        "- Prefer an unsuppressed, correctly scoped published school total. Otherwise require complete "
        "grade coverage and verified valid-score weights. Do not average grade percentages or use ranges.",
        "- Verify denominators against source definitions. An integer in EDC's tested field is not enough: "
        "Kansas and North Dakota 2025 use CCD enrollment; Utah school counts also use enrollment. "
        "Exclude those proxies from aggregation weights and sampling intervals.",
        "- Split assessment populations, alternate-assessment aggregates, standards eras, school levels "
        "and years explicitly. Require intervals for every model member or omit them for the model.",
        "- Run each importer twice, regenerate affected exports, inspect coverage/exclusions and independently "
        "check models. Verify the state selector, filters, first search after reload, URL restoration and charts.",
        "",
        "The machine-readable ledger is [state-expansion.json](../data/source/state-expansion.json). "
        "Each candidate retains `approved_for_modeling: false`; approval belongs to an implemented, "
        "verified adapter with evidence. Unknown definitions and denominators stay unknown.", "",
        "## CCD lunch data discovery audit", "",
        f"The [official 2024–25 CCD lunch archive]({source['url']}) "
        f"is {source['version']}, with 93,870 school identities across its jurisdictions. "
        "Its [companion workbook](https://nces.ed.gov/ccd/xls/SY_2024-25_SCH_Lunch_Companion_2026-005d_2a.xlsx) "
        "identifies school totals, direct certification, category counts and raw `DMS_FLAG` values. "
        "The archive and documentation are retained under ignored `data/raw/`; checksums are in the ledger.", "",
        "[NCES guidance](https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data) "
        "explains that CEP schools can report every student as free-lunch eligible and states can report "
        "direct certification instead of FRPL. Thus reported availability is not a verified economic predictor. "
        "Do not silently substitute the two measures or approve a state from these counts.", "",
    ]
    if audited:
        no_frpl = [state["id"] for state in states if not state["ccd_lunch_audit"]["frpl_total"]["reported_numeric_schools"]]
        no_dc = [state["id"] for state in states if not state["ccd_lunch_audit"]["direct_certification"]["reported_numeric_schools"]]
        lines.extend([
            f"The audit covers {source['schools_50_states']:,} school identities in the 50 states. "
            f"No reported numeric FRPL totals: {', '.join(no_frpl)}. "
            f"No reported numeric direct-certification totals: {', '.join(no_dc)}.", "",
            "South Carolina and Pennsylvania school totals are suppressed in the current 2a release "
            "because NCES identified data-quality problems. Ohio and Nebraska "
            "report different measures for different schools; an unexamined fallback would change the "
            "predictor within one model. Suppression and missing/nonreported tokens are retained in "
            "the per-state audit and never become zero.", "",
        ])
    lines.extend([
        "Reproduce the counts after downloading the archive:", "", "```sh",
        ".venv/bin/python scripts/state_registry.py --audit-ccd data/raw/ccd_sch_033_2425_l_2a_073025.zip --render",
        ".venv/bin/python scripts/state_registry.py --check", "```", "",
        "## State-by-state work queue", "",
        "Names, USPS identifiers and FIPS codes use the [Census state reference](https://www2.census.gov/geo/docs/reference/state.txt). "
        "Every EDC link targets the 2024–25 assessment candidate. `FRPL` and `DC` below count only "
        "school-total records marked `Reported` with a nonnegative integer; percentages use the number "
        "of school identities in the CCD lunch file, not statewide assessment coverage. They are availability "
        "statistics and do not approve values for modeling.", "",
        "| State (ID / FIPS) | Implementation | Assessment source discovery | Income and denominator work | CCD reported FRPL / DC |",
        "| --- | --- | --- | --- | --- |",
    ])
    status_labels = {"statewide_ready": "Verified statewide release", "partial_city": "NYC only; statewide pending",
                     "implementation": "Implementation in progress", "discovered": "Discovery; not available",
                     "audited_blocker": "Audited obstacle; not available"}
    for state in states:
        candidate = state["candidate_snapshot"]
        links = [f"[EDC 2025]({candidate['edc_url']})"]
        for i, src in enumerate(candidate["sea_sources"]):
            if src.get("url"):
                links.append(f"[SEA{' ' + str(i + 1) if i else ''}]({src['url']})")
        if candidate["sea_via_data_request"]:
            links.append("SEA request documented by EDC")
        issues = state["method_notes"] or ["Audit actual cohort, tested denominator and thresholds."]
        income = state["candidate_snapshot"]["income_status"]
        issue_text = " ".join(issues)
        if state['status'] == 'audited_blocker' and state['blocker_evidence']['summary'] not in issue_text:
            issue_text += ' ' + state['blocker_evidence']['summary']
        if income == "verified_existing_adapter":
            issue_text += " State income already audited for the existing 2025 adapter."
        else:
            issue_text += " Audit same-year enrolled economic disadvantage."
        audit = state.get("ccd_lunch_audit")
        if audit:
            denominator = audit["schools"]
            values = [audit[measure]["reported_numeric_schools"] for measure in ("frpl_total", "direct_certification")]
            coverage = " / ".join(f"{n:,}/{denominator:,} ({100*n/denominator:.1f}%)" for n in values)
        else:
            coverage = "Not audited"
        lines.append(f"| {state['name']} ({state['id']} / {state['fips']}) | {status_labels[state['status']]} "
                     f"| {'; '.join(links)} | {issue_text} | {coverage} |")
    lines.extend([
        "", "## Existing releases and rollout boundaries", "",
        "- Illinois: preserve the 2024 IAR/SAT release and its Chicago models. The 2025 candidate "
        "uses different EDC proficiency criteria and requires a fresh standards and income audit.",
        "- Wisconsin: preserve the separate 2025 WSAS totals and Forward/ACT history. The existing "
        "DPI enrollment-based income definition is verified; the broad totals and general assessments "
        "remain different populations.",
        "- New York: preserve the separate NYC city release and its historical definitions. "
        "Native statewide comparisons use their own economic-definition, identity and cohort audit; "
        "city and statewide populations are not interchangeable.",
        *[f"- {state['name']}: {state['existing_release']['scope']} "
          f"See [{state['name']} source guide]({state['existing_release']['guide'].removeprefix('docs/')})."
          for state in states if state['status']=='statewide_ready' and state['id'] not in {'IL','WI'}],
        "- Audited access and methodological obstacles are recorded in [expansion-blockers.md](expansion-blockers.md).",
        "",
        "Next integration priorities should follow completed income audits and usable assessment totals, "
        "not state size. When a source cannot support a defensible snapshot, retain its explicit blocker "
        "and seek a better published total or a source request. DC, territories and BIE are outside this "
        "50-state milestone and remain visible only as extra jurisdictions in the raw-source audit.", "",
        "This guide's work-queue tables are rendered from the ledger by `scripts/state_registry.py --render`. "
        "Update state evidence in the JSON and rerender; refreshing CCD counts never changes release status "
        "or source approval.", "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-ccd", type=Path, metavar="ARCHIVE", help="Refresh discovery-only CCD counts")
    parser.add_argument("--render", action="store_true", help="Render the state work queue guide from the ledger")
    parser.add_argument("--check", action="store_true", help="Validate official identities and readiness evidence")
    args = parser.parse_args()
    registry = load_registry()
    if args.audit_ccd:
        audit_ccd(registry, args.audit_ccd)
        LEDGER.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n")
    if args.render:
        GUIDE.write_text(render_guide(registry))
    validate_registry(registry)
    print(f"Validated {len(registry['states'])} states; discovery records grant no modeling approval.")


if __name__ == "__main__":
    main()
