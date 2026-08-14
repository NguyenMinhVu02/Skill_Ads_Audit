# Flexible Sheet Parsing and Python Auto-Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make direct Python and npx audits accept safely recognizable partner CSV layouts without requiring fixed column names.

**Architecture:** Keep `parse_ads_script()` and `parse_working_file()` as public boundaries. Add deterministic alias mapping first, guarded content inference second, and explicit ambiguity errors last; add equivalent filename discovery to the Python entry point without changing explicit-path behavior.

**Tech Stack:** Python 3.10 standard library, Node.js 18, `unittest`, Node test runner, Markdown.

## Global Constraints

- Do not add third-party dependencies.
- Explicit CSV paths always override auto-discovery.
- Never silently select tied or low-confidence semantic columns.
- Do not change audit findings, webhook behavior, report schema, or release-only `ad_config.json` checking.
- Do not expose tokens or webhook credentials in diagnostics.

---

### Task 1: Python CSV auto-discovery and macOS path portability

**Files:**
- Modify: `scripts/run_audit.py`
- Modify: `tests/test_run_audit.py`

**Interfaces:**
- Produces: `discover_csv(project: Path, kind: str) -> Path`
- Produces: `resolve_csv_input(project: Path, supplied: str | None, kind: str) -> Path`
- Preserves: `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write failing Python CLI tests**

Add tests that call `run_audit.main()` without CSV flags, assert unique recursive discovery succeeds, assert explicit paths win, and assert zero/multiple candidates return a sanitized setup error. Change the webhook attachment assertion to compare canonical paths:

```python
self.assertEqual(
    post.call_args_list[0].kwargs["attachment_path"].resolve(),
    (output_dir / "ads-audit-summary.md").resolve(),
)
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_run_audit.AdsAuditTest.test_python_cli_auto_discovers_csv_inputs \
  tests.test_run_audit.AdsAuditTest.test_python_cli_rejects_ambiguous_csv_discovery
```

Expected: failure because argparse still requires both flags or discovery helpers do not exist.

- [ ] **Step 3: Implement optional flags and guarded discovery**

Normalize candidate filenames with `re.sub(r"[^a-z0-9]+", "", name.casefold())`, skip `.git`, `.gradle`, `.idea`, `.agents`, `.codex`, `build`, `out`, `node_modules`, and `ads-audit-output`, and require exactly one candidate for each omitted flag. Validate explicit files before parsing.

- [ ] **Step 4: Run focused and existing CLI tests**

Run:

```bash
python3 -m unittest tests.test_run_audit -v
node --test tests/test_cli.js
```

Expected: all CLI tests pass on canonical output paths.

### Task 2: Flexible working-file and ADS SCRIPTS column mapping

**Files:**
- Modify: `scripts/ads_audit_lib.py`
- Modify: `tests/test_run_audit.py`

**Interfaces:**
- Preserves: `parse_ads_script(path: str | Path) -> AuditContract`
- Preserves: `parse_working_file(path: str | Path) -> ProjectChecklist`
- Produces internal canonical working-key normalization and guarded missing-header inference.

- [ ] **Step 1: Write failing parser tests**

Add fixtures for:

```csv
Order,Content,Detail,PIC
1,App name,Partner Player,Alice
2,Package name,com.partner.player,Bob
```

Also add a reordered unknown-header working sheet whose data uniquely identifies key/value columns, an ADS sheet whose placement name/type/ID headers use new aliases, and an ambiguous sheet that must raise `ValueError` with detected headers.

- [ ] **Step 2: Run parser tests and verify RED**

Run the four new parser tests. Expected: `app_name`/`package_name` are missing or placement parsing raises the existing generic error.

- [ ] **Step 3: Add explicit aliases and working-key normalization**

Map normalized `Content`, `Task content`, `Item`, `Field`, `Key`, `Nội dung`, and `Hạng mục` to `Task Detail`. Map `Detail`, `Value`, `Data`, `Result`, `Chi tiết`, and `Giá trị` to `Document`. Canonicalize row labels such as app name, package name, Firebase, Adjust, Facebook, and TikTok before building `ProjectChecklist`.

- [ ] **Step 4: Add guarded content inference**

Infer a working key column only from recognized checklist labels and select a unique value column from populated matching rows. Infer ADS type from known formats, placement name from identifier-like keys, and ID from ad-unit-like values. If required semantics are missing or tied, raise an error containing delimiter, detected headers, and missing semantic fields.

- [ ] **Step 5: Run focused parser tests and full Python suite**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: all parsing and audit regression tests pass without secret values in output.

### Task 3: Skill and partner documentation

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `README.vi.md`

**Interfaces:**
- Documents the zero-flag Python invocation and safe three-stage parsing contract.

- [ ] **Step 1: Update skill instructions**

Document that the bundled Python runner auto-discovers omitted CSV inputs, aliases and content inference support varying sheets, and ambiguous layouts must stop rather than guess.

- [ ] **Step 2: Update English and Vietnamese READMEs**

Show both npx and Python commands without CSV flags, explain explicit overrides, list representative aliases including `Content / Detail`, and describe safe ambiguity errors.

- [ ] **Step 3: Check documentation consistency**

Run:

```bash
rg -n "required=True|Task Detail.*Document|Content|Detail|auto-discover" README.md README.vi.md SKILL.md scripts/run_audit.py
git diff --check
```

Expected: docs match implemented behavior and contain no whitespace errors.

### Task 4: Final verification and publication

**Files:**
- No additional source files.

**Interfaces:**
- Publishes the tested package from GitHub `main` for `npx` users.

- [ ] **Step 1: Run full verification**

```bash
python3 -m unittest discover -s tests -v
node --test tests/test_cli.js
python3 -m py_compile scripts/*.py
git diff --check
```

- [ ] **Step 2: Run real-project smoke tests**

Run direct Python and npx against a real Android partner project with omitted CSV flags and `--no-webhook`. Confirm both locate the same files and generate reports.

- [ ] **Step 3: Commit and push**

Commit source, tests, `SKILL.md`, and both READMEs. Push `main`, then verify the remote SHA with `git ls-remote origin refs/heads/main`.
