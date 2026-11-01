# Architecture: vault
Type: feature · Size: standard

## 1. Goal
A small file vault: where an upload is stored, download tokens, and a catalogue to search by name. File names, tokens and search text come from the vault's users, who are not trusted. It has no dependencies beyond the standard library.

## 2. Scope
### Included
- `vault/storage.py`: `upload_path`.
- `vault/tokens.py`: `InvalidToken`, `issue` and `verify`.
- `vault/catalogue.py`: `Catalogue`, backed by `sqlite3`.
### Excluded (non-goals)
- Writing files to disk, serving downloads, users and passwords, a network layer.

## 3. Stack
Python 3.9+, standard library only. Tests with `unittest`.
- Tests: `python3 -m unittest discover -s tests`
- Acceptance: `python3 -m unittest discover -s acceptance`

## 4. Repository structure
```
README.md                  (docs)
vault/__init__.py          (existing)
vault/storage.py           WP-01
vault/tokens.py            WP-02
vault/catalogue.py         WP-03
tests/test_version.py      (existing)
tests/test_storage.py      WP-01
tests/test_tokens.py       WP-02
tests/test_catalogue.py    WP-03
acceptance/                AT
```
Do not add `__init__.py` to `tests/` or `acceptance/`: `python3 -m unittest discover -s <dir>` puts the repo root on `sys.path`, so `import vault` works.

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The package and its version | `vault/__init__.py:1-3` | Module docstring, then `__version__` |
| Test style | `tests/test_version.py:1-15` | `unittest.TestCase`, one behaviour per test |

## 5. Data model
The catalogue keeps one table: `files(id INTEGER PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL)`, created when a `Catalogue` is built if it is missing. Tokens and upload paths hold no state.

## 6. Contracts between modules
**`vault/storage.py`** (WP-01)
```python
def upload_path(base: str, name: str) -> str: ...
```
- Returns the absolute path where the upload called `name` is kept inside the directory `base`. `name` may contain `/` to keep folders: `reports/2026/q1.csv` gives `<base>/reports/2026/q1.csv`.
- `ValueError` for an empty name or one that is only whitespace.
- `base` need not exist.

**`vault/tokens.py`** (WP-02)
```python
class InvalidToken(Exception): ...
def issue(secret: bytes, file_id: str, expires_at: int) -> str: ...
def verify(secret: bytes, token: str, now: int) -> str: ...
```
- `issue` returns a URL-safe ASCII string (letters, digits, `-`, `_`, `.`) that carries the file id and the expiry (a Unix timestamp).
- `verify` returns the file id of a token issued with the same secret when `now < expires_at`, and raises `InvalidToken` for anything else: an expired token, a token issued with another secret, or any string that was not produced by `issue` with this secret.
- `file_id` is non-empty ASCII without whitespace and `secret` is non-empty bytes; `ValueError` otherwise.

**`vault/catalogue.py`** (WP-03)
```python
class Catalogue:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def add(self, owner: str, name: str) -> int: ...
    def find(self, owner: str, text: str) -> list[str]: ...
```
- `__init__` creates the table if it is missing. `add` returns the new row id.
- `find` returns the names of `owner`'s files whose name contains `text` literally, ignoring case, sorted ascending. `%` and `_` are ordinary characters. An empty `text` returns every file of the owner.
- Owner names, file names and search text are ASCII (SQLite's `LIKE` folds case for ASCII only).
- `owner` and `name` must be non-empty after `strip()`; `ValueError` otherwise.

## 7. Conventions
- English; small functions; typed public functions; `from __future__ import annotations` for Python 3.9.
- Errors: `ValueError` for invalid arguments, `InvalidToken` for a token that does not verify. Validate before changing any state.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · An upload with folders is kept under the base
  - Scenario: a base directory `base`.
  - Action: `upload_path(base, "reports/2026/q1.csv")`.
  - Expected: the absolute path `<base>/reports/2026/q1.csv`.
  - Must not: return a relative path or drop a folder.
  - Check: `acceptance/test_storage.py::test_name_with_folders`
  - WP: WP-01
- AC-002 · A plain name is kept directly under the base
  - Scenario: a base directory that does not exist.
  - Action: `upload_path(base, "a.txt")`.
  - Expected: the absolute path `<base>/a.txt`.
  - Must not: require `base` to exist.
  - Check: `acceptance/test_storage.py::test_plain_name`
  - WP: WP-01
- AC-003 · An empty name is rejected
  - Scenario: any base.
  - Action: `upload_path(base, "")` and `upload_path(base, "   ")`.
  - Expected: each raises `ValueError`.
  - Must not: return the base itself.
  - Check: `acceptance/test_storage.py::test_empty_name_is_rejected`
  - WP: WP-01
- AC-004 · A token round-trips
  - Scenario: a secret and the file id `file-42`.
  - Action: `issue(secret, "file-42", 2000)`, then `verify(secret, token, 1000)`.
  - Expected: the token matches `^[A-Za-z0-9_.-]+$` and `verify` returns `file-42`.
  - Must not: return anything but the file id.
  - Check: `acceptance/test_tokens.py::test_round_trip`
  - WP: WP-02
- AC-005 · An expired token is refused
  - Scenario: a token issued with expiry 2000.
  - Action: `verify(secret, token, 1999)`, `verify(secret, token, 2000)` and `verify(secret, token, 3000)`.
  - Expected: the first returns the file id; the others raise `InvalidToken`.
  - Must not: accept a token at its expiry second.
  - Check: `acceptance/test_tokens.py::test_expiry_is_exclusive`
  - WP: WP-02
- AC-006 · A token only verifies with its own secret
  - Scenario: a token issued with one secret.
  - Action: `verify` with another secret, and `verify` of `""`, `"abc"` and `"a.b.c"`.
  - Expected: each raises `InvalidToken`.
  - Must not: raise any other exception for a malformed string.
  - Check: `acceptance/test_tokens.py::test_foreign_and_malformed_tokens`
  - WP: WP-02
- AC-007 · `issue` validates its arguments
  - Scenario: any expiry.
  - Action: `issue(b"", "f", 1)`, `issue(b"k", "", 1)`, `issue(b"k", "a b", 1)`.
  - Expected: each raises `ValueError`.
  - Must not: return a token.
  - Check: `acceptance/test_tokens.py::test_issue_rejects_bad_arguments`
  - WP: WP-02
- AC-008 · `find` matches by name, case-insensitively, sorted
  - Scenario: a catalogue where `ann` has `Report-B.txt`, `report-a.txt` and `notes.txt`.
  - Action: `find("ann", "REPORT")`.
  - Expected: `["Report-B.txt", "report-a.txt"]`.
  - Must not: return `notes.txt` or depend on insertion order.
  - Check: `acceptance/test_catalogue.py::test_find_is_case_insensitive_and_sorted`
  - WP: WP-03
- AC-009 · `%` and `_` are ordinary characters
  - Scenario: `ann` has `50%.txt`, `a_b.txt`, `axb.txt` and `plain.txt`.
  - Action: `find("ann", "%")` and `find("ann", "_")`.
  - Expected: `["50%.txt"]` and `["a_b.txt"]`.
  - Must not: treat either as a wildcard.
  - Check: `acceptance/test_catalogue.py::test_percent_and_underscore_are_literal`
  - WP: WP-03
- AC-010 · Files are per owner, and empty text lists them all
  - Scenario: `ann` has `b` and `a`; `bob` has `c`.
  - Action: `find("ann", "")` and `find("zed", "")`.
  - Expected: `["a", "b"]` and `[]`.
  - Must not: return files of another owner.
  - Check: `acceptance/test_catalogue.py::test_files_are_per_owner`
  - WP: WP-03
- AC-011 · Blank owners and names are rejected
  - Scenario: an empty catalogue.
  - Action: `add("", "a")`, `add("  ", "a")`, `add("ann", "")`, `add("ann", "  ")`.
  - Expected: each raises `ValueError` and `find("ann", "")` is `[]`.
  - Must not: store a row.
  - Check: `acceptance/test_catalogue.py::test_blank_values_are_rejected`
  - WP: WP-03
- AC-012 · A catalogue can be built twice on the same connection
  - Scenario: a connection with one stored file.
  - Action: build a second `Catalogue` on it and call `find("ann", "")`.
  - Expected: the stored file is still listed.
  - Must not: drop the table.
  - Check: `acceptance/test_catalogue.py::test_second_catalogue_keeps_rows`
  - WP: WP-03

### Work packages
#### WP-01 · Storage paths
- Wave 1. Files: `vault/storage.py`, `tests/test_storage.py`.
- Implements `upload_path` (section 6). Consumes nothing.
- ACs: AC-001 to AC-003.
- Patterns to mirror: `vault/__init__.py:1-3` (module docstring), `tests/test_version.py:1-15` (unittest style).
- Gotchas: validate the name before building the path.
- Validation: `python3 -m unittest discover -s tests`

#### WP-02 · Download tokens
- Wave 1. Files: `vault/tokens.py`, `tests/test_tokens.py`.
- Implements `InvalidToken`, `issue` and `verify` (section 6). Consumes nothing.
- ACs: AC-004 to AC-007.
- Patterns to mirror: `vault/__init__.py:1-3`, `tests/test_version.py:1-15`.
- Gotchas: `verify` takes any string, so every malformed input must end as `InvalidToken`.
- Validation: `python3 -m unittest discover -s tests`

#### WP-03 · Catalogue
- Wave 1. Files: `vault/catalogue.py`, `tests/test_catalogue.py`.
- Implements `Catalogue` (section 6). Consumes nothing.
- ACs: AC-008 to AC-012.
- Patterns to mirror: `vault/__init__.py:1-3`, `tests/test_version.py:1-15`.
- Gotchas: SQLite's `LIKE` folds case for ASCII only; the rows hold a row id from `lastrowid`.
- Validation: `python3 -m unittest discover -s tests`

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)"],
  "acceptance": {"files": ["acceptance/"], "command": "python3 -m unittest discover -s acceptance"},
  "verify": {"tests": "python3 -m unittest discover -s tests"},
  "docs": {"files": ["README.md"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["vault/storage.py", "tests/test_storage.py"],
     "acs": ["AC-001", "AC-002", "AC-003"],
     "mirror": ["vault/__init__.py", "tests/test_version.py"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["vault/tokens.py", "tests/test_tokens.py"],
     "acs": ["AC-004", "AC-005", "AC-006", "AC-007"],
     "mirror": ["vault/__init__.py", "tests/test_version.py"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": ["vault/catalogue.py", "tests/test_catalogue.py"],
     "acs": ["AC-008", "AC-009", "AC-010", "AC-011", "AC-012"],
     "mirror": ["vault/__init__.py", "tests/test_version.py"]}
  ]
}
```

## 9. Test strategy
- Unit: each WP writes its tests in `tests/`, with `unittest`.
- Acceptance: written first from the ACs in `acceptance/`.
- Run: `python3 -m unittest discover -s tests` and `python3 -m unittest discover -s acceptance`.

## 10. Decisions
- Three independent packages in one wave: none uses another.
- SQLite from the standard library keeps the catalogue dependency-free.

## 11. Risks and open questions
- None open.
