<!-- agentic-flow-template -->
# agentic-flow

A small team of Claude Code agents that turns an idea into tested code.
Opus designs. Sonnet builds, in parallel. You make the two decisions that matter: you approve the design and you approve the commit.

<p align="center">
  <img src="docs/assets/flow.gif" width="800" alt="The flow in eight scenes. Opus writes architecture.md (contracts, acceptance criteria, work packages) and a second Opus reviews it before you approve it. A separate agent writes the acceptance tests, which fail because no code exists yet. Implementers build the work packages in parallel, and the hook blocks a write outside a package's files. Build, types, lint, tests and acceptance are verified against a baseline. A reviewer, an adversarial verifier and QA find a defect; its owner fixes it in one cycle. The documentation is brought up to date. Ready: you approve the commit.">
</p>

## What you get

- **Tests first.** A separate agent turns every acceptance criterion into a test before any code exists, and nobody else may edit it ([wave 0](docs/how-it-works.md#8-glossary)).
- **Parallel packages.** One implementer per work package, each writing only its own files ([work package](docs/how-it-works.md#8-glossary)).
- **The stop gate.** A package cannot report done while its acceptance command fails ([stop gate](docs/how-it-works.md#8-glossary)).
- **Four implementer statuses.** `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT` and `BLOCKED` say what happened instead of hiding it ([statuses](docs/how-it-works.md#8-glossary)).
- **Review with callers.** The reviewer sees the callers outside the diff, and an adversarial verifier tries to refute each serious finding ([callers](docs/how-it-works.md#8-glossary)).
- **Needs validation and `not_checked`.** Claims the code cannot settle, and what each agent skipped, reach you as a list ([needs validation](docs/how-it-works.md#8-glossary)).
- **Living documentation.** With the code accepted, the code map is regenerated and the docs are updated and checked ([living documentation](docs/how-it-works.md#8-glossary)).
- **A bench with a mutation score.** It measures whether the tests catch a deliberate defect ([bench](docs/how-to/bench.md)).

## What it costs you

- **Two approvals.** The design, before any code, and the commit, at the end.
- **Models.** `/architect` uses Opus, the other agents use Sonnet, and a Haiku gatekeeper runs the deterministic steps.
- **A plan.** Pro, Max, Team or Enterprise, with Dynamic workflows enabled.
- **Your subscription.** The agents use your usage allowance, not the API: API keys are removed from their environment.

## Proof

Tested end to end with real agents:
- **A new project:** acceptance tests red first, two parallel waves, verification, review and QA.
- **An existing codebase:** the plan cited exact `file:line` references, the new criteria passed and the existing ones stayed green.
- **A full cycle with an injected defect:** the reviewer and QA found it independently, the verifier upheld it, its package fixed it in one cycle, and the doc-updater brought README and CHANGELOG in line with the real CLI.
- **A badly written acceptance test:** the implementer could not touch it, did not cheat, and reported the cause. The flow stopped and resumed from the same wave once the test was fixed.
- **The plugin:** `/agentic-flow:init` installed the flow in a TypeScript repo in a real session.

The bench runs the flow on fixed projects and records oracle results, fix cycles, cost and the mutation score. The figures are in [bench/RESULTS.md](bench/RESULTS.md); [the measurement guide](docs/how-to/bench.md) explains how to read and reproduce them.

Not confirmed with real agents: the interactive interview in the UI, installing the plugin from the marketplace, the VS Code, JetBrains, cloud and GitHub Actions setups, and the briefs and the usage telemetry. Some parts are covered only by simulated agents.

## Quick start

**New project**, from the template:

```bash
gh repo create my-project --template jagosar/agentic-flow --private --clone
```

**Existing project**, with the plugin. In a Claude Code session inside the repo:

```
/plugin install agentic-flow --marketplace jagosar/agentic-flow
```

```
/agentic-flow:init
```

Then open `claude` in the project, accept the trust prompt, and:

```
/architect A URL shortener with a CLI and JSON storage
```

```
/implement
```

Requirements in one line: a Pro, Max, Team or Enterprise plan, Dynamic workflows, `python3` 3.9+, `git`, an up-to-date Claude Code, and macOS, Linux, WSL 2 or Windows with Git for Windows. See the [requirements](docs/how-to/README.md#requirements), the [install steps](docs/how-to/README.md#install-the-flow-in-a-project) and [troubleshooting](docs/how-to/README.md#troubleshooting).

## What's inside

| Piece | Model | Role |
|---|---|---|
| `/architect` | latest Opus | Classifies the request, researches, interviews and writes `architecture.md` |
| `plan-reviewer` | latest Opus | Reviews the plan in a clean context before you approve it |
| `/implement` | latest Sonnet | Validates, launches the workflow and holds the commit gate |
| `agentic-implement` | script | The native workflow: tests first, waves, verification, review, QA, fixes, docs |
| `test-author` | latest Sonnet | Writes the acceptance tests from the criteria, before the code |
| `implementer` | latest Sonnet | Builds one work package, in parallel with the rest of its wave |
| `test-auditor` | latest Sonnet | Read-only; checks the acceptance tests would not pass against an empty implementation |
| `reviewer` · `verifier` | latest Sonnet | Read-only review; the reviewer also checks the callers of every changed symbol, the verifier tries to refute every serious finding |
| `qa` | latest Sonnet | Exploratory testing beyond the acceptance criteria |
| `doc-updater` | latest Sonnet | Updates README, CHANGELOG and guides, only inside its zone |
| `gatekeeper` | latest Haiku | Runs the deterministic steps of `agentic.py` for the workflow, several per call |
| `agentic.py` | script | The guardrail hook, the deterministic steps, the ledger and the installer |
| `/red-green-proof` | your session | A bug fix you can trust: a test red before the fix, green after it, and red again when the fix is reverted |

Models are set by alias (`opus`, `sonnet`, and `haiku` for the gatekeeper only), which always resolve to the newest version your Claude Code knows. `validate` fails if anyone pins another model. Language rules for ten language families are installed by `rules-sync` for the languages `agentic.py stack` detects; see [Language rules](docs/how-to/README.md#language-rules).

## Guardrails

| Risk | Protection |
|---|---|
| An agent writes files that are not its own | A `PreToolUse` hook checks every write against the manifest. Reviewers write nothing |
| A change breaks code the diff does not touch | The reviewer receives the callers of every changed public symbol, outside the diff, and must check each one |
| An implementer passes by weakening the test | The tests are written by another agent, before the code, and are locked. Red first, green after |
| Relaxing a linter or skipping a test | Editing existing quality config is blocked; so are unconditional `skip`, `xfail` and `only` |
| Secrets in code | Writes containing credential patterns are blocked |
| Bypassing git hooks | `--no-verify`, `commit -n` and `core.hooksPath` are blocked for everyone |
| Git writes, new dependencies, nested sessions | Blocked inside every agent of the flow |
| Writes that dodge the hook | Each stage compares file fingerprints before and after |
| Breaking what already worked | A baseline before any change: a regression blocks, a pre-existing failure is reported |
| False positives from review | An independent verifier must refute a finding with confidence to dismiss it |
| Endless fix loops | At most two fix cycles per package; then you decide |
| A package that says DONE with its acceptance tests red | The stop gate runs the acceptance command before the report is accepted and refuses it, with the failing lines, twice at most |
| Documentation that invents things | The doc-updater must verify each claim; `docs-check` validates links and paths; the code map is generated without a model; claimed edits are compared with the files that actually changed |
| Prompt injection from the repo | Every agent treats repository content as data, not instructions |
| A failure in the guardrail itself | The hook fails closed inside an agent. Where Claude Code does not load it at all, `hooks-check` stops the run before the first agent, and a stage whose files changed with no hook call from a flow agent ends in REVIEW |
| Usage billed to the API by mistake | Agents run on your subscription; API keys are removed from their environment |
| A report says `DONE_WITH_CONCERNS` or `NEEDS_CONTEXT` | A concern becomes a pending item the reviewer may confirm as a finding; `NEEDS_CONTEXT` gets one more call with the whole plan, then a blocker you resolve |

The full decision diagram is in [How it works](docs/how-it-works.md#4-guardrails-the-hooks-decision).

## Documentation

- [How it works](docs/how-it-works.md): the flow, the lifecycle of a package, the hook, the permission matrix and the glossary.
- [Guides](docs/how-to/README.md): requirements, install, the working cycle and one guide per environment.
- [The measurement guide](docs/how-to/bench.md): run the bench and read its results.
- [Roadmap](docs/roadmap/repo-review-2026-11.md): ideas taken from ten other skill repos, ordered by what to build first.
- [Decision archive](docs/architecture/): the plans of earlier changes.

## Credits

agentic-flow is released under the [MIT licence](LICENSE).

Several ideas are adapted from [ECC](https://github.com/affaan-m/ECC) (MIT, © 2026 Affaan Mustafa):
- the independent judge and ceremony scaled to the size of the change;
- confidence-filtered review and phased verification;
- config protection, the `--no-verify` block and the prompt-injection defence;
- the language rules and the documentation agent with its code map.

The `red-green-proof` skill is by RooAGI (MIT, © 2026 RooAGI), from [claude-skills](https://github.com/alirezarezvani/claude-skills) (MIT, © 2025 Alireza Rezvani).
