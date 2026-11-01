# Architecture: the README and the guides, rewritten for 2.2
Type: change · Size: standard

## 1. Goal
The README and the ten guides in `docs/how-to/` grew by accretion: each release added a sentence, a row or a count, so the README mixes mechanism, install and status, the hub guide is 311 lines, the five environment guides repeat each other with different wording, and the test counts rot on every pull request. This change rewrites them for a reader who decides in two minutes (what it is, what you get, what it costs you, proof) and then installs; keeps one file per environment, each with the same skeleton; removes every hard-coded count and version; and brings the content to 2.2.0 (the stop gate, the four implementer statuses, needs validation, `not_checked`, concerns, the callers, the bench with its mutation score). No code, prompt or test of the flow changes.

## 2. Scope
### Included
- `README.md`: new order and voice.
- `docs/how-to/README.md` (the hub): index, shared requirements and install, the working cycle, reference tables, troubleshooting, testing the flow.
- The five environment guides (`terminal.md`, `desktop.md`, `vscode.md`, `jetbrains.md`, `web-ios.md`): one skeleton.
- The five task guides (`onboarding.md`, `plugin.md`, `gitlab.md`, `ci-github-actions.md`, `bench.md`): refreshed to 2.2.0; the CI guide written so `docs-check` passes.
- Acceptance tests in `acceptance/test_docs.py`, deterministic over the Markdown.
### Excluded (non-goals)
- `docs/how-it-works.md` (the technical reference, the doc-updater's zone here), `docs/architecture/`, `docs/roadmap/`, the assets and their generators.
- Any change to code, agents, commands, rules, CI workflows or the plugin.
- Translations.
- New screenshots or animations: the existing six screens and `flow.gif` are reused where they fit, never described as showing what they do not.

## 3. Stack
Markdown, English. Checks in Python 3.9+ `unittest`, no dependency: the acceptance tests read the files and run `agentic.py docs-check`.
- Lint: `python3 .claude/bin/agentic.py docs-check` (links, anchors and paths, but only inside the manifest's `docs.files`, here `docs/how-it-works.md` and `docs/roadmap/`: `agentic.py:1112-1116`; the eleven rewritten files are checked by the acceptance tests with the same rules)
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"` (the flow's whole suite, which includes the documentation drift tests of `test_definitions.py`: cited commands exist, internal links and anchors resolve, Mermaid blocks are well formed, no personal paths)
- Acceptance: `python3 -m unittest discover -s acceptance -p test_docs.py`

## 4. Repository structure
```
README.md                             WP-01
docs/how-to/README.md                 WP-02  the hub
docs/how-to/terminal.md               WP-03
docs/how-to/desktop.md                WP-03
docs/how-to/vscode.md                 WP-03
docs/how-to/jetbrains.md              WP-03
docs/how-to/web-ios.md                WP-03
docs/how-to/onboarding.md             WP-04
docs/how-to/plugin.md                 WP-04
docs/how-to/gitlab.md                 WP-04
docs/how-to/ci-github-actions.md      WP-04
docs/how-to/bench.md                  WP-04
acceptance/test_docs.py               AT
qa/                                   QA
docs/how-it-works.md, docs/roadmap/   docs (doc-updater; expected to change nothing)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The README today: order and content | `README.md:1-128` (headings `:2,11,21,53,72,95,99,116,122`: title, How it works, Quick start, What's inside, Guardrails, Language rules, Status, Documentation, Credits) | Section 6 fixes the new order; the tables of `:55-68` (pieces) and `:74-91` (guardrails) are kept, updated, and moved |
| The hub today | `docs/how-to/README.md:1-312` (headings `:7,22,39,48,56,92,102,142,158,170,180,191,208,245,280,302`) | Section 6 fixes the new order; the troubleshooting table `:249-274` and the script reference `:210-240` are kept and completed |
| The environment guides today | `terminal.md:1-152`, `desktop.md:1-73`, `vscode.md:1-61`, `jetbrains.md:1-67`, `web-ios.md:1-68`: each opens with `**Goal:**` and `**Status:**` lines, then numbered sections, `## Troubleshooting`, `## References` | The skeleton of section 6 generalises what `desktop.md:1-15` already does (Goal, Status, the "Before you start" line, `## What this environment needs`) |
| The task guides today | `onboarding.md:1-153` (two worked examples A/B), `plugin.md:1-132`, `gitlab.md:1-99`, `ci-github-actions.md:1-116` (`:25` cites `.github/workflows/agentic-qa.yml`, a file the reader creates: `docs-check` flags it), `bench.md:1-90` | Kept as task guides; the CI guide names the file as `agentic-qa.yml` in `.github/workflows/` (two separate code spans, no path with a slash that does not exist) |
| The source of truth for every 2.2.0 term | `docs/how-it-works.md:336-363` (glossary: Callers, Finding, Needs validation, `not_checked`, Stop gate, Implementer statuses, Fix attempt, Brief, Ledger…), `:163-190` (lifecycle and the statuses), `:191-224` (the hook, the stop gate), `:226-250` (permission matrix) | The guides paraphrase the glossary and link to it; they do not restate numbers it does not hold |
| What `/implement` presents | `.claude/commands/implement.md:55-66` (status, test audit, WPs, verification, review, QA, fixes, docs, pending by type: design, needs validation, concern, fix limit; `not_checked`; `gate_denials`) | The hub's "Read the report" step lists these items in that order |
| The bench as documented today | `docs/how-to/bench.md:6-31` (what it measures, the fixtures table with five rows including `roster`), `:64-66` (read `RESULTS.md`, the `Mutation` column), `:84-90` (commit results) | Kept; the fixtures table and the column description are the reference |
| The upgrade notes per version | `.claude/bin/upgrade.py:50-78` (`NOTES["2.2.0"]`, `["2.1.0"]`, `["2.0.0"]`) | What changed per release, for the plugin guide's "Update" section, without quoting version numbers in the hub or the README |
| The subcommands the docs may cite | `agentic.py:4-45` (the usage docstring) and `test_definitions.py:409-417` (`test_cited_commands_exist`: any `` `agentic.py <cmd>` `` or `python3 .claude/bin/agentic.py <cmd>` must be a real subcommand) | `callers` exists since 2.2.0 and belongs in the script reference |
| Link and anchor checks | `test_definitions.py:419-433` (`test_internal_links`: relative links must exist, `#fragments` must match a heading slug: lower case, punctuation removed, spaces to `-`), `agentic.py:1119-1120` (`LINK_RE`, `PATH_RE`: a backticked token with a slash is a path that must exist) | Section 6 lists the headings every file must expose, so cross-links resolve; a path in backticks must exist in the repo |
| Mermaid and personal paths | `test_definitions.py:435-450` | No new Mermaid in the guides (diagrams live in `how-it-works.md`); no `/home/<user>` or `C:\Users` paths |
| What CI runs | `.github/workflows/agentic-flow-ci.yml:53-59` (`node test_workflow.mjs`, the `.claude/bin` suite, `bench/`, `bench/acceptance`) | `acceptance/test_docs.py` is not in CI (CI is outside every zone); section 11 |
| Assets | `docs/assets/flow.gif`, `docs/assets/screens/{fix,hook,install,ledger,report,validate}.png`, with their alt texts in `README.md:8` and `how-it-works.md` | Reuse by relative path; keep the alt texts accurate to the image |

**What must NOT change:** anything outside the files of section 4; the ECC credit (`README.md:122-128`) stays; the `<!-- agentic-flow-template -->` marker on `README.md:1` stays (the template's `reset-readme` workflow in `.github/workflows/` looks for it; nothing in `agentic.py` does); the worked examples of `onboarding.md` (islet, finanzas-familiares) stay as examples.

## 5. Data model
Not applicable: the deliverables are Markdown files. The acceptance tests read them as text.

## 6. Contracts between modules
The contract between files is their **headings**: other files link to them, and the acceptance tests check them. Exact text, in this order, H2 unless noted.

`README.md` (WP-01), at most 150 lines, no hard-coded test counts or flow versions:
```
<!-- agentic-flow-template -->          (line 1, kept)
# agentic-flow                          (line 2)
<one-paragraph pitch, then the flow.gif with its alt text>
## What you get
## What it costs you                    (the two approvals, the models, the plan it needs, usage on your subscription)
## Proof                                (real runs, the bench with a link to bench/RESULTS.md and the measurement guide; no figures copied)
## Quick start                          (template and plugin, then /architect and /implement; the requirements in one line with a link to the hub)
## What's inside                        (the pieces table, 12 rows as today, with the reviewer row mentioning the callers)
## Guardrails                           (the table as today, 16 rows including the stop gate, plus one row "A report says DONE_WITH_CONCERNS or NEEDS_CONTEXT": 17 rows)
## Documentation                        (How it works, the guides hub, the measurement guide, the roadmap, the decision archive)
## Credits                              (kept verbatim)
```
"What you get" names, each in one line with a link to the glossary entry in `docs/how-it-works.md#8-glossary`: tests first, parallel packages, the stop gate, the four implementer statuses, review with callers and an adversarial verifier, needs validation and `not_checked`, living documentation, the bench with the mutation score.

`docs/how-to/README.md` (WP-02), at most 260 lines:
```
# Guides: building with agentic-flow
<the "Reviewed on" blockquote, with the Claude Code version it was checked against>
## Pick your environment               (the table: Environment, Guide, Best for, Status; ten rows as today)
## Requirements                        (### Windows kept as H3)
## Install the flow in a project
## The working cycle                   (six numbered steps; step 5 "Read the report" lists what /implement presents, including concerns, needs validation, not_checked, gate_denials; ### Two ways to run as H3 at its end)
## Good practice                       (kept from today, :158-168)
## Language rules                      (kept from today, :170-178)
## Follow and stop the work
## Configuration
## Script reference                    (every command of the current block plus `callers`)
## Troubleshooting                     (the table as today, with the three 2.1 rows kept)
## Testing the flow itself             (the four commands; what the suites cover; no counts)
## Official references
```
"The flow in one minute" (the pieces table and "Why this order") moves to the README's "What you get" and to `how-it-works.md`, which already has the matrix; the hub links to both instead of repeating. The README's "Language rules" section (`README.md:95-97`) becomes one sentence inside "What's inside" with a link to the hub's `Language rules`.

Environment guides (WP-03): `terminal.md`, `desktop.md`, `vscode.md`, `jetbrains.md`, `web-ios.md`, each at most 160 lines:
```
# Guide: <environment>
**Goal:** <one sentence>
**Status:** <tested | partly tested | not tested>, <what was tested, honestly, as today>
Before you start, meet the requirements and install the flow in your project.   (two links into the hub: `README.md` with the anchors `requirements` and `install-the-flow-in-a-project`)
## What this environment needs
## 1. Open a session                   (install and start, in that environment)
## 2. Design                           (/architect, the model gate, approve, commit)
## 3. Build                            (/implement, following the run, reading the report: statuses, gate denials, pending items)
## 4. Review and deliver               (commit gate; when a stage stops: BLOCKED, NEEDS_CONTEXT twice, resume with /implement <wave>)
## Troubleshooting                     (environment-specific rows only; the last line links to README.md#troubleshooting)
## References
```
`terminal.md` keeps, after step 4, `## 5. Without the launcher: stage by stage` and `## 6. On a remote server`; its numbered sections are therefore 1 to 6.

Task guides (WP-04), each at most 160 lines; headings free, but:
- `onboarding.md` keeps `## A. ...` and `## B. ...` and `## When something goes wrong`; the fenced blocks that quote real installer output stay unchanged and labelled with the date and flow version they came from (that output was run; nothing newer was); one sentence of prose after them says what a newer upgrade adds to the `settings.json:` line (the hook matcher and timeout, `agentic.py:1297-1306`), without quoting output that was not run.
- `plugin.md` keeps `## Install`, `## Update`, `## Troubleshooting`; "Update" says what `init` refreshes and that edited files are kept with the new version in `.claude/state/upgrade/`, and points to the upgrade notes `init` prints rather than listing versions.
- `gitlab.md` keeps `## A.`, `## B.`, the CI section and `## Where Claude Code runs`.
- `ci-github-actions.md` keeps `## What you need`, `## The workflow`, `## What you get`, `## Before you rely on it`, `## References`; the file to create is written as `agentic-qa.yml` in `.github/workflows/` (two code spans), never as one path.
- `bench.md` keeps `## What it measures`, `## The fixtures`, `## Run it locally`, `## Run it from GitHub Actions`, `## Read RESULTS.md` (heading text exactly: `` ## Read `RESULTS.md` ``), `## Add a fixture`, `## Commit results by hand`; "What it measures" describes the mutation score (what is mutated, the two suites, the baseline rule, the ceiling) and "Read RESULTS.md" the `Mutation` column.

Shared rules (all WPs): every `agentic.py` command cited exists (`test_definitions.py:409`); every relative link and `#anchor` resolves; a backticked path passes the path rule of `docs_check` (`agentic.py:1125-1151`): outside fenced blocks, a backticked token with a slash whose first segment is a top-level directory of the repo not in `SKIP_DIRS` (`agentic.py:111`; `.claude` is in it) must exist; no digit-count of tests (`N tests`, `N scenarios`); no flow version string: the regex `(?<!Claude Code )(?<!claude-code@)\b[12]\.\d+\.\d+\b` must not match (a Claude Code version is allowed only right after `Claude Code ` or `claude-code@`; Python versions have two components and never match; the regex deliberately ignores versions above 2.x and a `v` prefix, which the docs do not use). Lines to reword today: the hub's `:94` and `:272` ("1.1.1": say "an old flow" / "a flow before Windows support"), `gitlab.md:3`, `onboarding.md:3,130,141,149,151`, `plugin.md:90,93` (describe the upgrade path without version numbers, or move real command output into a fenced block). No em-dashes; one idea per sentence.

## 7. Conventions
- English, present tense, second person for the reader ("you approve"), third for the agents ("the reviewer reads"). Short sentences. No marketing adjectives ("powerful", "seamless").
- The reader first: what they get and what it costs before how it works; how it works before how to install.
- Honest status lines: "not tested" stays "not tested" unless a real run is cited.
- Headings are the contract: the exact texts of section 6; anchors in links follow GitHub's slug rules (`test_definitions.py:419-433`).
- Numbers: none that rot (test counts, versions, costs). The bench results live in `bench/RESULTS.md`; the docs link, they do not copy.
- Commands in fenced blocks, one per block when the reader is meant to run them one by one (as today).
- Forbidden: inventing a tested status, a feature or a command; Mermaid in the guides; absolute personal paths; describing a screenshot as showing something it does not.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · The README speaks to the reader who decides first
  - Scenario: the rewritten `README.md`.
  - Action: read its H2 headings and content.
  - Expected: line 1 is `<!-- agentic-flow-template -->` and line 2 `# agentic-flow`; the H2 headings are exactly, in order, `What you get`, `What it costs you`, `Proof`, `Quick start`, `What's inside`, `Guardrails`, `Documentation`, `Credits`; no fenced code block appears before the `## Quick start` heading; the file has at most 150 lines; it contains the strings `stop gate`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `needs validation`, `not_checked`, `callers`, `mutation`; it links to `bench/RESULTS.md`, `docs/how-it-works.md`, `docs/how-to/README.md` and `docs/how-to/bench.md`; the Credits section still names ECC with its MIT line.
  - Must not: contain a test count (regex `\b\d+ (Python |workflow |bench |QA )?(tests|scenarios)\b`) or a flow version (regex `(?<!Claude Code )(?<!claude-code@)\b[12]\.\d+\.\d+\b`: a Claude Code version after `Claude Code ` or `claude-code@` is allowed); lose the `flow.gif` image.
  - Check: `acceptance/test_docs.py::ReadmeTests::test_ac_001_readme_order_and_terms`
  - WP: WP-01
- AC-002 · The hub is an index plus the shared reference
  - Scenario: the rewritten `docs/how-to/README.md`.
  - Action: read its headings, tables and code blocks.
  - Expected: the H2 headings are exactly, in order, `Pick your environment`, `Requirements`, `Install the flow in a project`, `The working cycle`, `Good practice`, `Language rules`, `Follow and stop the work`, `Configuration`, `Script reference`, `Troubleshooting`, `Testing the flow itself`, `Official references`; an H3 `Windows` under Requirements and an H3 `Two ways to run` under The working cycle; the environment table has ten data rows whose Guide column links to the ten guide files; the script reference block contains `agentic.py callers`, `agentic.py run-pipeline`, `agentic.py validate`, `agentic.py status`, `agentic.py stop`, `agentic.py install`; "The working cycle" contains `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `needs validation`, `not_checked`, `gate_denials`; the troubleshooting table keeps rows containing the plain substrings `the report says DONE but the acceptance tests`, `about its acceptance tests` and `twice`; at most 260 lines.
  - Must not: contain a test count or a flow version (the regexes of AC-001); repeat the pieces table (no row starting with `| Architect |`).
  - Check: `acceptance/test_docs.py::HubTests::test_ac_002_hub_order_tables_and_terms`
  - WP: WP-02
- AC-003 · The five environment guides share one skeleton
  - Scenario: the rewritten `terminal.md`, `desktop.md`, `vscode.md`, `jetbrains.md`, `web-ios.md`.
  - Action: read each.
  - Expected: each starts with `# Guide: `, has a `**Goal:**` line and a `**Status:**` line within its first 6 lines, a "Before you start" line with two links into the hub, one to the `requirements` anchor and one to the `install-the-flow-in-a-project` anchor of the hub's `README.md`, and the H2 headings `What this environment needs`, `1. Open a session`, `2. Design`, `3. Build`, `4. Review and deliver`, `Troubleshooting`, `References` in that order (with `5. Without the launcher: stage by stage` and `6. On a remote server` between `4.` and `Troubleshooting` in `terminal.md` only); section `3. Build` contains `/implement` and at least one of `DONE_WITH_CONCERNS` or `gate`; section `4. Review and deliver` contains `/implement <wave>`; each file has at most 160 lines; the Troubleshooting section ends with a link to `README.md#troubleshooting`.
  - Must not: contain a Mermaid block; a test count or a flow version; a status line that says `tested` for `vscode.md`, `jetbrains.md`, `web-ios.md` unless it also says `not` before it (those three are not tested today, `docs/how-to/README.md:13-15`; the check is case-insensitive: `Not tested` counts).
  - Check: `acceptance/test_docs.py::EnvironmentGuideTests::test_ac_003_same_skeleton`
  - WP: WP-03
- AC-004 · The task guides are current and docs-check passes
  - Scenario: the rewritten `onboarding.md`, `plugin.md`, `gitlab.md`, `ci-github-actions.md`, `bench.md`.
  - Action: read each; apply the path rule of `docs_check` (`agentic.py:1125-1151`): outside fenced blocks, a backticked token with a slash whose first segment is a top-level directory of the repo not in `SKIP_DIRS` (`agentic.py:111`; `.claude` is in it) must exist to the five files.
  - Expected: no such path of the five files is missing from the repo (today `ci-github-actions.md:25` cites `.github/workflows/agentic-qa.yml`, which does not exist); `bench.md` contains `Mutation`, `mutation score`, `roster`, `selftest`, a row for each of the five fixtures (`tempconv`, `inventory`, `vault`, `tally`, `roster`) and the headings of section 6; `ci-github-actions.md` contains `agentic-qa.yml` and does not contain `.github/workflows/agentic-qa.yml`; `plugin.md` contains `.claude/state/upgrade/` and `/agentic-flow:init`; `onboarding.md` keeps `## A.`, `## B.` and `## When something goes wrong`; `gitlab.md` keeps `## Where Claude Code runs`; each file has at most 160 lines.
  - Must not: a test count or a flow version in any of the five (the AC-001 regexes), except inside fenced code blocks that show real command output in `onboarding.md` and `plugin.md`.
  - Check: `acceptance/test_docs.py::TaskGuideTests::test_ac_004_current_and_paths_exist`
  - WP: WP-04
- AC-005 · Every link, anchor and cited command in the eleven files resolves
  - Scenario: all eleven files as rewritten.
  - Action: one `subTest` per file: for each relative link, check the target exists and the `#fragment` matches a heading slug (the rule of `test_definitions.py:419-433`); for each `` `agentic.py <cmd>` `` or `python3 .claude/bin/agentic.py <cmd>`, check `<cmd>` is a subcommand of `agentic.py` (the rule of `:409-417`, with `agentic_subcommands()` imported from `test_definitions`); apply the path rule of `docs_check` (`agentic.py:1125-1151`): outside fenced blocks, a backticked token with a slash whose first segment is a top-level directory of the repo not in `SKIP_DIRS` (`agentic.py:111`; `.claude` is in it) must exist (import `PATH_RE` and `SKIP_DIRS` from `agentic.py` and copy the filter, so `.claude/state/...`, `jagosar/islet`, `dist/` and tokens inside fenced blocks are not flagged).
  - Expected: zero broken links, zero missing anchors, zero unknown commands, zero missing paths; every one of the ten guides is linked from the hub's environment table, and the hub is linked from the README's Documentation section.
  - Must not: rely on `test_definitions.py` or `docs-check` running (this test re-implements the three rules over the eleven files only, with a `subTest` per file so one broken file names itself).
  - Check: `acceptance/test_docs.py::LinkTests::test_ac_005_links_anchors_and_commands`
  - WP: WP-01, WP-02, WP-03, WP-04

### Work packages
#### WP-01 · The README
- Wave 1.
- Files: `README.md`.
- Implements the README contract of section 6. Consumes the hub's and the guides' headings by signature (links to `docs/how-to/README.md#requirements`, `#install-the-flow-in-a-project`, `#troubleshooting`, `docs/how-to/bench.md`, `docs/how-it-works.md#8-glossary`).
- ACs: AC-001, AC-005.
- Patterns to mirror: `README.md:1-9` (marker, title, pitch, the gif with its alt text), `:55-68` and `:74-91` (the two tables: keep their shape, update the reviewer and gate rows), `:122-128` (Credits, verbatim), `docs/how-it-works.md:336-363` (the glossary wording for every term named in "What you get").
- Gotchas: line 1 must stay the template marker (the installer and the template detect it); the Status bullets of `README.md:101-112` are real runs and move under "Proof" with their wording, without the sentence of test counts (`:110`) and without the "Not confirmed" paragraphs' version-specific items turned into claims; "What it costs you" says the agents run on the reader's subscription and that `/architect` uses Opus and the rest Sonnet, with the Haiku gatekeeper; the Proof section links `bench/RESULTS.md` and says what the bench measures, not the figures.
- WP validation: `python3 -m unittest discover -s acceptance -p test_docs.py -k Readme` and `-k Link`.

#### WP-02 · The hub
- Wave 1.
- Files: `docs/how-to/README.md`.
- Implements the hub contract of section 6. Consumes the guides' file names (section 4) and the headings the README links to.
- ACs: AC-002, AC-005.
- Patterns to mirror: `docs/how-to/README.md:7-20` (the environment table, keep the ten rows and the honest Status column), `:56-100` (Requirements with the Windows H3), `:102-140` (Install), `:142-156` (the cycle: keep the six steps, expand step 5 with the items `implement.md:55-66` presents), `:191-206` (Configuration), `:208-243` (Script reference, add `callers` with a one-line comment), `:245-276` (Troubleshooting, keep every row), `:280-299` (Testing, drop the counts sentence), `:302-312` (references).
- Gotchas: the pieces table and "Why this order" leave the hub (they live in the README and `how-it-works.md`): link, do not repeat; the "Reviewed on" blockquote names the Claude Code version it was checked against and that is allowed by the version regex because it follows `Claude Code ` (section 6) but must be a version actually run: keep the current `2.1.302` and the date it names (the agents cannot run `claude --version`); the anchors `#requirements`, `#install-the-flow-in-a-project`, `#troubleshooting`, `#windows` are linked from every guide and from the README: the heading texts of section 6 produce exactly those slugs.
- WP validation: `python3 -m unittest discover -s acceptance -p test_docs.py -k Hub` and `-k Link`.

#### WP-03 · The five environment guides
- Wave 1.
- Files: `docs/how-to/terminal.md`, `docs/how-to/desktop.md`, `docs/how-to/vscode.md`, `docs/how-to/jetbrains.md`, `docs/how-to/web-ios.md`.
- Implements the environment skeleton of section 6. Consumes the hub's anchors by signature.
- ACs: AC-003, AC-005.
- Patterns to mirror: `desktop.md:1-15` (Goal, Status, the "Before you start" line, "What this environment needs"), `terminal.md:34-80` (Design and Build steps with the model gate and `/workflows`), `terminal.md:81-131` (stage by stage, fixing by hand, remote server: kept as sections 5 and 6), `web-ios.md:8-14` (what a cloud session is: becomes "What this environment needs" content), each guide's current Troubleshooting and References sections.
- Gotchas: the status lines are honest and come from the hub table (`README.md:9-20` of the hub): terminal tested, desktop partly tested, the other three not tested; step 3 explains what the report shows in that environment (the four statuses, gate denials, pending items, `not_checked`) with a link to the hub's cycle; step 4 covers the commit gate and resuming with `/implement <wave>` after `BLOCKED` or a second `NEEDS_CONTEXT`; `web-ios.md` must say that cloud sessions load `.claude/settings.json` hooks per the official docs but that this was not verified by the flow's authors (the 0004 run in a cloud session saw no hook fire: `docs/architecture/0004-bench-quality.md` section 11 and `0005` section 11); the permission-mode advice of `desktop.md:17-23` stays.
- WP validation: `python3 -m unittest discover -s acceptance -p test_docs.py -k EnvironmentGuide` and `-k Link`.

#### WP-04 · The five task guides
- Wave 1.
- Files: `docs/how-to/onboarding.md`, `docs/how-to/plugin.md`, `docs/how-to/gitlab.md`, `docs/how-to/ci-github-actions.md`, `docs/how-to/bench.md`.
- Implements the task-guide rules of section 6. Consumes the hub's anchors by signature.
- ACs: AC-004, AC-005.
- Patterns to mirror: `bench.md:6-31` and `:64-90` (keep and tighten), `ci-github-actions.md:20-30` (the file to create, reworded as two code spans), `plugin.md:65-94` (Update), `onboarding.md:93-141` (the upgrade example: keep the quoted output as it was run, labelled; describe newer upgrades in prose, `agentic.py:1297-1306` is the output format).
- Gotchas: `docs-check` treats any backticked token with a slash as a path (`agentic.py:1120`): write files the reader creates as a name plus a folder in separate spans; the bench guide's numbers (fixture test counts, costs) are not written: `bench/RESULTS.md` holds them; `onboarding.md` and `plugin.md` may show command output with versions and counts inside fenced blocks only (the acceptance test strips fenced blocks before applying the version and count regexes to those two files); `onboarding.md:140` ("170 tests") is outside a block today and must move or go.
- WP validation: `python3 -m unittest discover -s acceptance -p test_docs.py -k TaskGuide` and `-k Link`.

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)"],
  "acceptance": {"files": ["acceptance/"], "command": "python3 -m unittest discover -s acceptance -p test_docs.py"},
  "verify": {"lint": "python3 .claude/bin/agentic.py docs-check", "tests": "python3 -m unittest discover -s .claude/bin -p test_*.py"},
  "docs": {"files": ["docs/how-it-works.md", "docs/roadmap/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["README.md"],
     "acs": ["AC-001", "AC-005"], "mirror": ["README.md:1-9", "README.md:55-68", "README.md:74-91", "README.md:122-128", "docs/how-it-works.md:336-363"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["docs/how-to/README.md"],
     "acs": ["AC-002", "AC-005"], "mirror": ["docs/how-to/README.md:7-20", "docs/how-to/README.md:142-156", "docs/how-to/README.md:208-243", ".claude/commands/implement.md:55-66"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": ["docs/how-to/terminal.md", "docs/how-to/desktop.md", "docs/how-to/vscode.md", "docs/how-to/jetbrains.md", "docs/how-to/web-ios.md"],
     "acs": ["AC-003", "AC-005"], "mirror": ["docs/how-to/desktop.md:1-15", "docs/how-to/terminal.md:34-80", "docs/how-to/terminal.md:81-131", "docs/how-to/web-ios.md:8-14"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": ["docs/how-to/onboarding.md", "docs/how-to/plugin.md", "docs/how-to/gitlab.md", "docs/how-to/ci-github-actions.md", "docs/how-to/bench.md"],
     "acs": ["AC-004", "AC-005"], "mirror": ["docs/how-to/bench.md:6-31", "docs/how-to/ci-github-actions.md:20-30", "docs/how-to/plugin.md:65-94", "docs/how-to/onboarding.md:93-141"]}
  ]
}
```

## 9. Test strategy
- Unit: none (Markdown). Each WP runs its own slice of the acceptance tests (its class and `LinkTests`) before `DONE`.
- Acceptance: `acceptance/test_docs.py`, AC-001…AC-005, written first and red (today the README's headings are in another order, the hub has `The flow in one minute`, the guides differ, `ci-github-actions.md` breaks `docs-check`, and the counts are present). The tests read files and parse headings with a regex; AC-005 imports `agentic_subcommands` from `.claude/bin/test_definitions.py` (add `.claude/bin` to `sys.path`) and re-implements the link and anchor rule over the eleven files.
- QA: exploratory reading for contradictions between files (a status that differs between the hub table and the guide; a command shown with options the script does not accept; a step order that differs between environments without reason); and the drift tests of `test_definitions.py` over the whole repo.
- After merging: nothing to release (docs only); with the default `docs` zone of a later plan, `docs-check` goes green for the first time since the CI guide was written.

## 10. Decisions
- **D1 · The README speaks to the reader who decides (user's choice):** what you get, what it costs, proof, then install. Discarded: quick start first.
- **D2 · One file per environment, same skeleton (user's choice):** the five guides keep their files and gain one structure, so a reader switching environments finds the same steps. Discarded: one surfaces guide (the per-IDE gotchas would get lost) and by-task only.
- **D3 · No hard-coded counts or versions (user's choice):** they were stale twice this week; an acceptance test forbids them in the README and the hub, and in the guides outside fenced output. The bench's figures stay in `bench/RESULTS.md`, linked.
- **D4 · Headings are the contract:** four packages write eleven files in one wave; the only thing that crosses between them is the links, and links need anchors. Section 6 fixes the heading texts, so each package can link to the others before they exist.
- **D5 · Acceptance tests in `acceptance/`, outside `.claude/`:** this plan can run through `/implement` (nothing it owns is protected). The drift tests in `test_definitions.py` keep covering the whole repo in CI; `acceptance/test_docs.py` is a stricter, per-file check for this change, not added to CI (CI is outside every zone; section 11).
- **D6 · The CI guide stops citing a path that does not exist:** the path rule (`PATH_RE`) has flagged `ci-github-actions.md:25` since it was written; naming the file and the folder in two spans fixes it. `docs-check` itself only scans the manifest's `docs.files`, so the acceptance tests apply the same rule to the eleven files; running `docs-check` from a test would also write a stage line to the ledger (`agentic.py:1153`), which is why they do not call it.
- **D7 · `docs/how-it-works.md` is not rewritten:** it is the technical reference, recently updated per release, and the glossary is the source of truth the guides link to.
- **D8 · The pieces table lives once, in the README:** the hub's copy goes; the hub links to the README and to the permission matrix.

## 11. Risks and open questions
- **Implementers writing prose:** Sonnet implementers may drift to marketing voice or invent a tested status. The skeleton, the honest-status rule and the acceptance regexes bound the structure; voice is checked by the reviewer and QA (section 7), not by a test.
- **Over-constrained headings:** the exact heading texts make cross-links safe but limit wording; a better heading means changing section 6 and the test, which is intended.
- **`acceptance/test_docs.py` is not in CI:** adding it means editing `.github/workflows/agentic-flow-ci.yml`, outside every zone; a one-line follow-up by hand after merging.
- **Cloud-session hooks:** the guides may only say what was observed (`web-ios.md` says hooks were not verified in a cloud session by the flow's authors), not what the official docs promise.
- **Line caps:** 150 (README), 260 (hub), 160 (guides) were chosen from today's sizes (128, 311, 61 to 153) to force tightening; `onboarding.md` at 153 lines and `terminal.md` at 152 have little room and may need cutting.
