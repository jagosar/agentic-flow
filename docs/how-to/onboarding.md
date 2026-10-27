# Onboarding: bring a repo into the flow, or bring it up to date

> Reviewed on 2026-10-27 with agentic-flow 1.1.0. Both examples are real repos: every output below comes from running the installer on a copy of them. Nothing was pushed to either repo.

Two situations, one command:

| Your repo | Example | Go to |
|---|---|---|
| Has never used the flow | [`jagosar/islet`](https://github.com/jagosar/islet), a GNOME Shell extension in TypeScript | [A. A repo without the flow](#a-a-repo-without-the-flow-islet) |
| Has an older version of the flow (from the template or the plugin) | `jagosar/finanzas-familiares`, a PWA created from the template, with 16 approved designs | [B. A repo with an older flow](#b-a-repo-with-an-older-flow-finanzas-familiares) |

You need `git`, `python3` 3.9+ and Claude Code. For GitLab repos, see [gitlab.md](gitlab.md).

**On Windows (native, not WSL):** the flow's hook, permissions and commands call `python3`, and the python.org installer
only ships `python.exe`. Copy it as `python3.exe` in the same folder (that folder must come before
`%LOCALAPPDATA%\Microsoft\WindowsApps` in `PATH`, or `python3` stays the Microsoft Store shortcut). `/architect` and
`/implement` (the native workflow) work; `run-pipeline` (one `claude -p` per agent) is not supported on Windows yet, and
neither are its tests: the suite's fake `claude` is a shebang script Windows cannot run. Run the suite with
`PYTHONUTF8=1` there, since many tests read and write files in the platform's default encoding.

## A. A repo without the flow: islet

### 1. Start from a clean branch

```bash
cd ~/islet
git switch -c chore/agentic-flow
```

The installer refuses to write over uncommitted changes in the files it manages, so commit or stash first.

### 2. Install

With the plugin, in a Claude Code session inside the repo: `/agentic-flow:init`. Without it, from a clone of agentic-flow:

```bash
python3 ~/agentic-flow/.claude/bin/agentic.py install ~/islet --dry-run   # what it would do
python3 ~/agentic-flow/.claude/bin/agentic.py install ~/islet
```

The real output on islet:

```
agentic-flow unknown -> 1.1.0 -> ~/islet
  new: 28
  settings.json: allow Bash(python3 .claude/bin/agentic.py:*), allow Workflow(agentic-implement), deny Bash(git reset --hard:*), deny Bash(git clean:*), deny Bash(rm -rf:*), hook PreToolUse, enableWorkflows
  .gitignore: .claude/state/, .agentic-result.json
  .claude/agentic.json: created with the defaults
  rules: common, typescript
RESULT: OK
```

- **28 new files** under `.claude/`: the agents, `/architect` and `/implement`, the workflow, `agentic.py` and the rules library.
- **`settings.json`** is created with the flow's permissions and guardrail hook. If you already had one, it is merged: nothing of yours is removed.
- **Rules:** the installer detected TypeScript (from `package.json` and `tsconfig.json`) and installed its rules next to the common ones.

### 3. Review and commit

```bash
git status --short          #  M .gitignore   ?? .claude/
git add .claude .gitignore
git commit -m "Add agentic-flow"
```

Commit before running the installer again: a second run over the uncommitted `.gitignore` stops with `install: nothing was written` and exit code 3. That guard is what makes every install undoable with git.

### 4. Open a new session

Close the session and open a new one in the repo, so Claude Code loads the commands, agents, hook and workflow. Trust the folder when asked (without it, the project's permissions do not apply). On Pro, enable **Dynamic workflows** in `/config`.

### 5. Your first feature

```
/architect Add a 15-minute preset to the focus timer, next to 25, 50 and 90
```

The architect explores the code first (the presets live in `src/core/focus.ts:11`), asks what it cannot deduce, and writes `architecture.md`. For a project like islet, the manifest at the end of it should look like this (this one passes `agentic.py validate` on the real repo):

```json
{
  "stack": ["typescript"],
  "allow_bash": ["Bash(npm run typecheck)", "Bash(npm run lint)", "Bash(npm test)", "Bash(npx vitest run:*)"],
  "acceptance": {"files": ["tests/core/acceptance/"], "command": "npx vitest run tests/core/acceptance"},
  "verify": {"types": "npm run typecheck", "lint": "npm run lint", "tests": "npm test"},
  "docs": {"files": ["README.md", "CHANGELOG.md"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/core/focus.ts", "tests/core/focus.test.ts"],
     "acs": ["AC-001"], "mirror": ["src/core/focus.ts:1-30", "tests/core/focus.test.ts:1-20"]}
  ]
}
```

Three choices worth checking in your own project:
- **Acceptance inside the test runner's reach.** islet's `vitest.config.ts` only includes `tests/core/**`, so the acceptance zone goes under it. A folder outside would never run.
- **Verify only what runs on your machine.** `npm run build` needs `glib-compile-schemas`, and the GJS and integration suites need GNOME and D-Bus. They stay in CI; the flow runs types, lint and unit tests.
- **Specific commands.** `validate` rejects open rules such as `Bash(npm:*)`.

Then `/implement`, follow it with `/workflows`, and approve the commit at the end. See [terminal.md](terminal.md) for the run itself.

## B. A repo with an older flow: finanzas-familiares

This repo was created from the template in an early version of the flow. It has no install record, still carries the flow's own tests, adds a command of its own (`categorizar.md`), and has a live `architecture.md` and 16 archived designs.

### 1. Clean branch, then preview

```bash
cd ~/finanzas-familiares
git switch -c chore/update-agentic-flow
python3 ~/agentic-flow/.claude/bin/agentic.py install . --dry-run
```

### 2. Upgrade

```bash
python3 ~/agentic-flow/.claude/bin/agentic.py install .
```

Or update the plugin (`claude plugin update agentic-flow@agentic-flow`), restart the session and run `/agentic-flow:init`. The real output:

```
agentic-flow unknown -> 1.1.0 -> ~/finanzas-familiares
  new: 10
  updated: 16
  unchanged: 14
  settings.json: unchanged
  rules: common, python, typescript
upgrade notes:
  - Agents answer with the launcher's JSON schema; the text STATUS: format is gone. …
  - The commands … were removed: update scripts or CI that call them.
  - Plans need '#### WP-NN' and '- AC-NNN ·' headings to give each agent only its slice (briefs); …
  - install now updates the flow's own tests and CI copied from the template when they are intact, …
validate: OK
RESULT: OK
```

What happened:
- **`unknown -> 1.1.0`:** there was no install record. The installer still recognised every flow file as intact, because each matched a version the flow once published, so it **updated 16** without `--force` and **kept none**.
- **10 new files:** the pieces added since that version (`brief.py`, `pipeline.py`, `upgrade.py`, the test-auditor, the spec) and the parts of the flow's test suite the repo lacked, so its CI keeps passing.
- **Untouched:** the project's own command, `settings.json` (it already had everything), `architecture.md` and `docs/architecture/`.
- **`validate: OK`:** the current plan still validates with the new version.

If you had edited a flow file, it would be listed under `modified by you (left alone)`, with the new version in `.claude/state/upgrade/`. Compare them with `diff -ru .claude/state/upgrade/.claude .claude` and merge by hand.

### 3. Read the notes, run the tests, commit

- **Notes.** The upgrade notes are what may affect you: here, no scripts called the removed commands. Older plans keep working; new ones get the briefs.
- **Tests.** `python3 -m unittest discover -s .claude/bin -p "test_*.py"` runs the flow's own suite: 170 tests on this repo.
- **Commit:** `git add -A && git commit -m "Update agentic-flow to 1.1.0"`, then open a pull request.

## When something goes wrong

| Symptom | Fix |
|---|---|
| `install: nothing was written` (exit 3) | A flow file has uncommitted changes, or a run is in progress. Commit or stash (or `--allow-dirty`), or `python3 .claude/bin/agentic.py stop` |
| `not a git repository` | The flow needs git: `git init` and commit first |
| Files under `modified by you` that you never touched | Line endings (`core.autocrlf`) or a formatter changed them. Compare with `.claude/state/upgrade/` and use `--force` if nothing is yours |
| `validate: FAILED: …` after upgrading | The current plan predates a rule of the new version. Ask `/architect` to revise it |
| The flow's tests fail on your own commands or agents | Fixed in 1.1.0: the flow's tests accept a project's extra commands and agents |

More on updates: [plugin.md › Update](plugin.md#update).
