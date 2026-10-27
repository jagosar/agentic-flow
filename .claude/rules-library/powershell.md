---
paths:
  - "**/*.ps1"
  - "**/*.psm1"
  - "**/*.psd1"
---
<!-- Written for agentic-flow from a real run on a Windows PowerShell 5.1 + Pester 3.4 repo (2026-10-27). -->
# PowerShell

Extends the [common rules](common.md).

## Style

- Advanced functions: `[CmdletBinding()]`, an approved verb (`Get-Verb`) and a project prefix in the noun
  (`Get-XmmStatus`), comment-based help with at least `.SYNOPSIS`.
- Know the target before writing: Windows PowerShell 5.1 (`powershell.exe`) and PowerShell 7 (`pwsh`) differ. No
  `??`, `?:`, `&&`/`||` or `-Parallel` in code that must run on 5.1.
- A validator returns exactly one value: no stray `Write-Output` or unassigned expressions, which add items to the
  pipeline. `Write-Host` is for human output only.
- Keep each file's encoding and line endings. Windows PowerShell 5.1 reads a `.ps1` without a BOM as ANSI, so a file
  with non-ASCII text keeps its UTF-8 BOM.
- Literals in single quotes; double quotes only to interpolate.

## Errors

- `-ErrorAction Stop` (or `$ErrorActionPreference = 'Stop'`) where a failure must stop; a non-terminating error is
  otherwise ignored.
- `try`/`catch` of the specific exception type, not a bare `catch`, except at the entry point.
- Native executables do not throw: check `$LASTEXITCODE` after each one.

## Tests

- Mirror the Pester version the repo uses, and check it (`Get-Module Pester -ListAvailable`). Windows PowerShell 5.1
  ships Pester 3.4: `Should Be`, `Should Throw`, no `Should -Be`, no `-TestCases`, no `BeforeAll` or `Mock` from v5.
  Pester 5 syntax does not run on 3.4, and the reverse does not run on 5.
- Exit codes: `-EnableExit` exists on Pester 3 and 4; Pester 5 uses `-CI`. Without one of them, a failing run exits 0.
- One `Describe` per function, `It` names that describe the behaviour. `$TestDrive` for files, never the real profile
  or a system path.
- Regex in .NET: `\d` matches Unicode digits (use `[0-9]`), and `$` matches before a final newline (use `\A...\z` to
  validate a whole value). `-match` is case-insensitive; `-cmatch` is not.

## Security

- Never `Invoke-Expression` or `Start-Process` with a command line built from external input. Validate first
  (an allow-list) or pass arguments as separate elements.
- A value interpolated into a remote command (`ssh`, `adb shell`) is validated or quoted for that shell first.
- Secrets from the environment or `Get-Credential`, never as literals; no `ConvertTo-SecureString -AsPlainText` with
  a literal.
- Do not put `-ExecutionPolicy Bypass` in the manifest's commands. Ask the user to set
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once: agents must not change it, and Claude Code's auto mode
  may deny a command that weakens it. A run blocked by the policy is not a red test: `acceptance` reports it as an
  error.

## Common commands

| `verify` phase | Typical command |
|---|---|
| build | none (interpreted); a parse check if needed, e.g. a script calling `[System.Management.Automation.Language.Parser]::ParseFile` |
| types | none |
| lint | `powershell -NoProfile -Command Invoke-ScriptAnalyzer -Path . -Recurse -EnableExit` (PSScriptAnalyzer 1.18+) |
| tests | `powershell -NoProfile -NonInteractive -Command Invoke-Pester -Path ./tests -EnableExit` (Pester 3/4) or `pwsh -NoProfile -Command Invoke-Pester -Path ./tests -CI` (Pester 5) |
