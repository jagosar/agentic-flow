# Guide: Visual Studio Code (and Cursor)

**Goal:** use the flow from the official Claude Code extension, reviewing changes in the editor.
**Status:** not tested. This guide follows the extension's official documentation; the flow uses the same `.claude/` files as the CLI.

Before you start, meet the [requirements](README.md#requirements) and [install the flow in your project](README.md#install-the-flow-in-a-project).

## What this environment needs

- VS Code 1.94 or later. It also works in Cursor.
- The **Claude Code** extension by Anthropic (`anthropic.claude-code`).
- **Dynamic workflows enabled** (on Pro, in `/config`).
- **Optionally, the CLI installed separately**, for the fallback mode. The extension bundles a CLI for its panel, but does not put it on the `PATH`.

## 1. Open a session

1. Open Extensions (`Ctrl+Shift+X`, or `Cmd+Shift+X` on a Mac), search for **Claude Code** and click **Install**.
2. Open the panel with the **Spark** icon: in the editor toolbar (with a file open), in the Activity Bar, or from **✻ Claude Code** in the status bar.
3. Click **Sign in** and authorise in the browser with your plan's account. No API key needed.
4. Use `File → Open Folder` on the repo root, where `.claude/` lives. Typing `/` in the panel should show `/architect` and `/implement`.

## 2. Design

```
/architect Add PDF export to invoices
```

- No need to choose a model: each command sets its own. Click the model name under the input box to see the session's.
- The permission mode indicator under the input box works as in Desktop. Start with a mode that asks you.
- Before writing `architecture.md`, the architect tells you which model it is running on. If it is not Opus, pause, switch the model and reply `continue`.
- Read `architecture.md` in the editor, approve it, then commit it from Source Control.

## 3. Build

```
/implement
```

- **Workflow:** follow it with `/workflows`, or from the agent counter, which opens the **agent map** with each agent, its state and its transcript.
- **Changes** are written straight to disk. Review them in **Source Control** (`Ctrl+Shift+G`).

When it finishes you get the same report as in the [terminal guide](terminal.md#3-build):

- The report lists each package with one of four statuses: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT` or `BLOCKED`.
- It also lists the stop gate denials (`gate_denials`), the review and QA results, and the pending items: design questions, needs validation, concerns and fix limits. Each package can also report what it did not check (`not_checked`).
- Nothing is committed until you approve the proposed commits. The steps are in [the working cycle](README.md#the-working-cycle).

## 4. Review and deliver

- **Source Control** lists every file touched: code, the acceptance tests (wave 0), the QA tests and the documentation. The QA report is in the `/implement` summary and in `.claude/state/runs/workflow-result.json`.
- Commit and push from Source Control, or ask the session. The flow's agents cannot commit or push.
- If a package ends `BLOCKED`, or `NEEDS_CONTEXT` a second time, the stage stops. Fix the cause (usually a gap in `architecture.md`, revisited with `/architect`) and resume from that wave with `/implement <wave>`, for example `/implement 2`.
- You can also open the integrated terminal (`` Ctrl+` ``) and follow [terminal.md](terminal.md). When started from there, `claude` connects to the editor to show diffs.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/implement` uses the fallback mode | Enable **Dynamic workflows** in `/config` and launch again |
| The flow's commands do not appear | Open the repo's root folder, not a subfolder |
| The architect's questions arrive as text instead of options | Answer in the chat: the architect accepts free-text answers |

For anything else, see the [common table](README.md#troubleshooting).

## References

- [Claude Code in VS Code](https://code.claude.com/docs/en/vs-code)
