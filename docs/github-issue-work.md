# GitHub issue work

Work continues on `expansion/all-states` in [robot-assisted-projects/FRPL-RMA](https://github.com/robot-assisted-projects/FRPL-RMA). The branch is separate from the GitHub Pages publishing branch, `master`.

- [#1 — What test is used, and to what standard](https://github.com/robot-assisted-projects/FRPL-RMA/issues/1): the [assessment guide](../assessments.html) implements the geographic map, state/test/population filters, latest released definitions, source links and region navigation. Eight 2025 California/Delaware/Nevada/Washington definitions, including two explicit Los Angeles bindings, now have an audited Smarter Balanced consortium developer role, separate from ownership and delivery contracts. Remaining provider roles and comparable cut-score ambition remain evidence work; this issue is not complete. [Source notes](assessment-guide.md). [Published progress](https://github.com/robot-assisted-projects/FRPL-RMA/issues/1#issuecomment-6089003981).
- [#2 — Expand to covering all 50 states](https://github.com/robot-assisted-projects/FRPL-RMA/issues/2): the [source ledger](state-expansion.md) records 39 ready states and 11 outstanding holds. The New Hampshire work verifies an exact income-to-directory crosswalk while preserving its assessment-ID hold. [New Hampshire audit](new-hampshire-data.md). [Published progress](https://github.com/robot-assisted-projects/FRPL-RMA/issues/2#issuecomment-6089004463).
- [#3 — Large District Breakouts](https://github.com/robot-assisted-projects/FRPL-RMA/issues/3): the [district queue](district-comparisons.md) supplies 77 first-tier and 172 second-tier remaining candidates and their implementation gates. Los Angeles Unified now has its own California region, exact official roster membership, same-year native joins, separate pure-level models and numerical checks. The [Los Angeles guide](los-angeles-district.md) records its source, model and integration evidence and limitations. The [Miami-Dade source audit](miami-dade-district.md) separately reconciles exact district membership and offered-versus-enrolled grade scope; district fits and release validation remain pending. [#15 — Detroit cohort hold](https://github.com/robot-assisted-projects/FRPL-RMA/issues/15) records insufficient Math and Combined coverage separately for M-STEP and PSAT. [Published progress](https://github.com/robot-assisted-projects/FRPL-RMA/issues/3#issuecomment-6089004978).

The organization app installation was verified on 2026-10-09, and publishing through the user-authorized `robotic-assistants` account succeeded. All twelve new blocker issues, both parent checklists and all three progress comments were read back from GitHub and verified.

The [blocker publication record](../data/source/expansion-issue-drafts.json) retains one source-grounded issue per unreleased state, its missing evidence, acceptance criteria, branch guide link and verified publication number:

| State | Blocker issue |
| --- | --- |
| Connecticut | [#4](https://github.com/robot-assisted-projects/FRPL-RMA/issues/4) |
| Kentucky | [#5](https://github.com/robot-assisted-projects/FRPL-RMA/issues/5) |
| Nebraska | [#6](https://github.com/robot-assisted-projects/FRPL-RMA/issues/6) |
| New Hampshire | [#7](https://github.com/robot-assisted-projects/FRPL-RMA/issues/7) |
| North Dakota | [#8](https://github.com/robot-assisted-projects/FRPL-RMA/issues/8) |
| Ohio | [#9](https://github.com/robot-assisted-projects/FRPL-RMA/issues/9) |
| South Dakota | [#10](https://github.com/robot-assisted-projects/FRPL-RMA/issues/10) |
| Utah | [#11](https://github.com/robot-assisted-projects/FRPL-RMA/issues/11) |
| Vermont | [#12](https://github.com/robot-assisted-projects/FRPL-RMA/issues/12) |
| West Virginia | [#13](https://github.com/robot-assisted-projects/FRPL-RMA/issues/13) |
| Wyoming | [#14](https://github.com/robot-assisted-projects/FRPL-RMA/issues/14) |

These issues are linked in the parent bodies and refer back to #2 or #3. **Native GitHub sub-issue attachment remains pending:** the available connector actions expose issue creation, updates and comments, but no parent/child attachment mutation. The linked checklists do not represent native sub-issue relationships.

On future runs, inspect the recorded issues and current parent content before publishing to avoid duplicates or overwriting newer edits. Attach these existing issues when a supported native action becomes available; do not recreate them. Keep #1, #2 and #3 open until their full acceptance criteria are met. Do not close a state source hold because the investigation or a numerical experiment was completed.

The scheduled follow-up checks issue activity every 15 minutes in this conversation. Its ignored local checkpoint, `data/build/github-issue-monitor.json`, retains successfully read issue bodies, states and comments together with unfinished actionable work. The monitor ignores its own comments as new triggers, preserves prior checkpoints after access/read failures, and continues unblocked work on the authorized branch. It reports meaningful changes or decisions while leaving unchanged source holds quiet.
