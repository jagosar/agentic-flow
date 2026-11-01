# Guide: repos hosted on GitLab

> Reviewed on 2026-10-27. The installer only needs a local git repo, so it behaves exactly as in [onboarding.md](onboarding.md), whose outputs are real. What is specific to GitLab (the CI job and merge requests) has **not** been run on GitLab yet.

The flow lives in your repo (`.claude/`), so where the repo is hosted does not matter to it. Two things change on GitLab:
- **There is no "Use this template" across hosts.** Start from your own project and install the flow into it.
- **The template's GitHub files are inert.** `.github/workflows/*` do nothing on GitLab. If you want the flow's tests in CI, add the GitLab job below.

The flow itself still comes from GitHub: the plugin's marketplace is `jagosar/agentic-flow`, which is private, so the machine where you install needs read access to it (`gh auth login` and `gh auth setup-git`, or an SSH key on GitHub).

## A. A GitLab project without the flow

```bash
git clone git@gitlab.com:<group>/<project>.git && cd <project>
git switch -c chore/agentic-flow
```

Install, either way:
- With the plugin: open a Claude Code session in the repo and run `/agentic-flow:init`.
- From a clone of agentic-flow: `python3 ~/agentic-flow/.claude/bin/agentic.py install . --dry-run`, then without `--dry-run`.

The output is the same as islet's in [onboarding.md › A](onboarding.md#a-a-repo-without-the-flow-islet): the new files under `.claude/`, the merged `settings.json`, two lines in `.gitignore`, and your languages' rules.

Then commit, push and open a merge request:

```bash
git add .claude .gitignore
git commit -m "Add agentic-flow"
git push -u origin chore/agentic-flow
glab mr create --source-branch chore/agentic-flow --target-branch main --title "Add agentic-flow" --fill
```

Open a new Claude Code session, trust the folder, and start with `/architect <what you want to build>`.

A brand-new GitLab project: create it empty, clone it and follow the same steps. The installer only needs a git repo; commit right after installing, so the next upgrade can be undone with git.

## B. A GitLab project with an older flow

Typical case: a repo copied from the GitHub template and moved to GitLab, so it has no install record and carries the template's GitHub files.

```bash
cd <project>
git switch -c chore/update-agentic-flow
python3 ~/agentic-flow/.claude/bin/agentic.py install . --dry-run
python3 ~/agentic-flow/.claude/bin/agentic.py install .
```

Or `claude plugin update agentic-flow@agentic-flow`, restart, and `/agentic-flow:init`. What to expect is in [onboarding.md › B](onboarding.md#b-a-repo-with-an-older-flow-finanzas-familiares):
- intact flow files are updated even without a record;
- the files you edited are kept, with the new version in `.claude/state/upgrade/`;
- the upgrade notes say what may affect you.

On GitLab, two more things:
- **`.github/workflows/agentic-flow-ci.yml` and `reset-readme.yml`.** If the copy brought them, the installer updates them when they are intact, but GitLab never runs them. Delete them in the same merge request if you prefer; the installer never adds them back.
- **The flow's tests.** They are updated together with `agentic.py`. Run them before pushing: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`.

Then `git commit`, `git push -u origin chore/update-agentic-flow` and `glab mr create … --fill`.

## The flow's tests in GitLab CI (optional, not yet run on GitLab)

The template runs the flow's own tests on GitHub Actions. The GitLab equivalent, in `.gitlab-ci.yml`:

```yaml
agentic-flow:
  image: python:3.12
  variables:
    GIT_DEPTH: "20"
  rules:
    - changes: [".claude/**/*"]
  script:
    - python3 -m unittest discover -s .claude/bin -p "test_*.py"
```

- **Image.** The official `python` image includes `git`, which the tests use. `node` is optional: without it, the workflow scenarios are skipped.
- **Scope.** The job only runs when something under `.claude/` changes.
- **Not included.** Running the agents themselves in CI (`agentic.py run-pipeline` with an API key) is described for GitHub in [ci-github-actions.md](ci-github-actions.md). On GitLab it needs the same pieces: the `claude` CLI, `ANTHROPIC_API_KEY` as a masked variable, and `"auth": "inherit"` in `.claude/agentic.json`. It has not been tried.

## Several GitLab repos at once

The installer works per repo. To update many, loop over them:

```bash
for p in group/app-a group/app-b; do
  dir=$(mktemp -d)
  git clone -q git@gitlab.com:$p.git "$dir" && cd "$dir" || continue
  git switch -c chore/update-agentic-flow
  python3 ~/agentic-flow/.claude/bin/agentic.py install . && git add -A && git commit -qm "Update agentic-flow" \
    && git push -q -u origin chore/update-agentic-flow \
    && glab mr create --source-branch chore/update-agentic-flow --target-branch main --title "Update agentic-flow" --fill
  cd - >/dev/null
done
```

- **Nothing is overwritten.** A repo with uncommitted flow files or a run in progress makes the installer exit 3, and that repo is skipped.
- **Read every merge request before merging.** It lists what was updated, kept and removed.

## Where Claude Code runs

The CLI, Desktop and IDE extensions work on any local clone, wherever it is hosted. The cloud sessions of Claude Code on the web clone repositories from GitHub; check the current documentation before relying on them with GitLab.
