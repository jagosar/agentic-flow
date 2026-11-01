# Guide: JetBrains IDEs (IntelliJ IDEA, PyCharm, WebStorm, GoLand, PhpStorm, Android Studio)

**Goal:** use the flow from a JetBrains IDE, with diffs in the IDE's viewer.
**Status:** not tested. The plugin runs the same CLI, so the flow should behave as in the [terminal](terminal.md).

Before you start, meet the [requirements](README.md#requirements) and [install the flow in your project](README.md#install-the-flow-in-a-project).

## What this environment needs

- **The CLI installed.** The plugin does not bundle its own copy, so it is mandatory.
- The **Claude Code [Beta]** plugin from the JetBrains Marketplace.
- In your interactive session, Manual mode for edits. The official documentation warns that, in JetBrains IDEs, `acceptEdits` mode can modify IDE configuration files that the IDE executes. The flow's agents use `acceptEdits`, but the hook only lets them write their own package's files, so they cannot touch `.idea/` or anything outside the manifest.

## 1. Open a session

1. Install the CLI:

   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   ```

2. Go to `Settings → Plugins → Marketplace`, search for **Claude Code [Beta]**, install it and restart the IDE.
3. Use `Ctrl+Esc` (`Cmd+Esc` on a Mac) or the Claude Code button. Or run `claude` in the integrated terminal, at the project root. From an external terminal, connect to the IDE with `/ide`.
4. Make diffs open in the IDE: run `/config` and set **Diff tool** to `auto`.

## 2. Design

```
/architect <your request>
```

- Before writing `architecture.md`, the architect tells you which model it is running on. If it is not Opus, pause, switch the model and reply `continue`.
- Read `architecture.md`, approve it, then commit it from the **Commit** window (`Alt+0`).

## 3. Build

```
/implement
```

- Follow it with `/workflows`. Changes are written straight to disk.
- Review them in the **Commit** window (`Alt+0`) or in **Git → Local Changes**.

When it finishes you get the same report as in the [terminal guide](terminal.md#3-build):

- The report lists each package with one of four statuses: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT` or `BLOCKED`.
- It also lists the stop gate denials (`gate_denials`), the review and QA results, and the pending items: design questions, needs validation, concerns and fix limits. Each package can also report what it did not check (`not_checked`).
- Nothing is committed until you approve the proposed commits. The steps are in [the working cycle](README.md#the-working-cycle).

## 4. Review and deliver

- The QA report is in the `/implement` summary and in `.claude/state/runs/workflow-result.json`.
- Commit and push from the IDE, or ask the session. The flow's agents cannot commit or push.
- If a package ends `BLOCKED`, or `NEEDS_CONTEXT` a second time, the stage stops. Fix the cause (usually a gap in `architecture.md`, revisited with `/architect`) and resume from that wave with `/implement <wave>`, for example `/implement 2`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Cannot launch Claude Code" or "command not found" | Check `claude --version`. If the IDE cannot find it, set the full path in `Settings → Tools → Claude Code [Beta] → Claude command` |
| macOS: works in the terminal, not from the IDE | An IDE launched from the Dock may not inherit your shell's `PATH`. Set the full path in **Claude command** |
| Windows with WSL | In **Claude command**, use `wsl -d Ubuntu -- bash -lic "claude"`, with your distribution |
| "No available IDEs detected" on WSL2 | Follow the WSL section of the official guide (a firewall rule, or mirrored networking) |
| `Esc` does not interrupt | In `Settings → Tools → Terminal`, untick "Move focus to the editor with Escape" |

For anything else, see the [common table](README.md#troubleshooting).

## References

- [Claude Code in JetBrains IDEs](https://code.claude.com/docs/en/jetbrains)
