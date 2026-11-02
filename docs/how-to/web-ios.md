# Guide: cloud sessions (web and iOS)

**Goal:** run the flow in a Claude Code cloud session, started from the browser, your phone, Desktop or the terminal.
**Status:** not tested. This guide follows the official documentation for cloud sessions. In a cloud session with two repositories attached, the flow's authors observed that the project's hook never ran, as the documentation says for several repositories; the flow now refuses to start there (`hooks-check`).

Before you start, meet the [requirements](README.md#requirements) and [install the flow in your project](README.md#install-the-flow-in-a-project).

## What this environment needs

- A cloud session runs in an Anthropic virtual machine (Ubuntu 24.04, with Python 3, git and other tools preinstalled) on a clone of your GitHub repo. It keeps working when you close your laptop.
- It is available on Pro, Max and Team, counts against your plan's usage limits with no extra charge, and always uses your subscription.
- The official documentation says it loads the repo's `.claude/agents/` and `.claude/settings.json` (hooks and permissions) only when the session has one repository and is not a thread inside a Claude project. Attach this repository alone. If `hooks-check` exits 3, `/implement` stops before any agent; `/implement fallback` runs each agent as `claude -p`, which loads the hooks.
- A GitHub connection, either way:
  - **In the browser:** install the **Claude GitHub App** during the first setup at [claude.ai/code](https://claude.ai/code).
  - **From the terminal:** run `/web-setup`, which reuses your `gh` login.
- The branch with `.claude/` (and `architecture.md`, if it exists) pushed. The cloud clones what is on GitHub, not your local copy.

## 1. Open a session

Pick one:

- **Browser:** [claude.ai/code](https://claude.ai/code), then the repo and the branch.
- **iPhone:** the **Code** tab of the Claude app.
- **Desktop:** choose **Cloud** instead of **Local** when creating the session.
- **Terminal:**

  ```bash
  claude --cloud "/implement"
  ```

## 2. Design

```
/architect <your request>
```

The architect's interview suits a phone well: short questions with options. Design on the phone and, once you approve, build on Desktop. To continue a cloud session in your terminal: `claude --teleport`. Commit and push `architecture.md` before building.

## 3. Build

```
/implement
```

- **The cloud uses the native workflow**, as locally: workflows are available in cloud sessions and their progress is saved with the session. The fallback mode (`claude -p` processes) has not been tested inside the VM.
- Changes appear behind the `+N -M` indicator; open it to see the diff and comment on lines.

When it finishes you get the same report as in the [terminal guide](terminal.md#3-build):

- The report lists each package with one of four statuses: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT` or `BLOCKED`.
- It also lists the stop gate denials (`gate_denials`), the review and QA results, and the pending items: design questions, needs validation, concerns and fix limits. Each package can also report what it did not check (`not_checked`).
- Nothing is committed until you approve the proposed commits. The steps are in [the working cycle](README.md#the-working-cycle).

A run that passed `hooks-check` had its hook running; a stage `check` with `GUARDRAIL HOOK SAW NO FLOW AGENT` did not. Either way, check the diff yourself before you approve.

## 4. Review and deliver

- Create the pull request from the session once you approve.
- If a package ends `BLOCKED`, or `NEEDS_CONTEXT` a second time, the stage stops. Fix the cause (usually a gap in `architecture.md`, revisited with `/architect`) and resume from that wave with `/implement <wave>`, for example `/implement 2`.
- To run everything on your machine and follow it from your phone, start the session on Desktop or in the terminal and turn on **Remote Control**.

## Troubleshooting

| Symptom | Fix |
|---|---|
| The session does not see `.claude/` or `architecture.md` | That branch was not pushed. The cloud clones the remote |
| No repositories appear | Check the GitHub connection (the App installed on the repo, or `/web-setup`) |
| Usage limits run out | Cloud sessions share limits with the rest of your usage. Run fewer packages per wave, or wait for the reset |

For anything else, see the [common table](README.md#troubleshooting).

## References

- [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)
- [Cloud environments](https://code.claude.com/docs/en/cloud-environments)
- [Remote Control](https://code.claude.com/docs/en/remote-control)
