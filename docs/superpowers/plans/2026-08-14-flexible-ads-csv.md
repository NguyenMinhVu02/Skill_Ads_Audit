# Flexible ADS SCRIPTS CSV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the audit accept partner-specific ADS SCRIPTS CSV layouts without manual header renaming.

**Architecture:** Replace the fixed `csv.DictReader` path with a small table reader that detects delimiter and header row, canonicalizes semantic aliases, and safely infers an unnamed ID column from ad-unit-like values. Keep `parse_ads_script` and `parse_working_file` as the public boundaries.

**Tech Stack:** Python standard library (`csv`, `unicodedata`, `re`), `unittest`, Markdown documentation.

## Global Constraints

- No third-party Python dependencies.
- Existing named `ID`, `Name`, and `Ads type` files must keep parsing unchanged.
- Do not infer a placement from a row number alone.
- Reports and webhook payloads must not expose credentials.

### Task 1: Add failing parser tests

**Files:**
- Modify: `tests/test_run_audit.py`

- [ ] Add tests for a semicolon-delimited file with Vietnamese/English aliases and a preamble row.
- [ ] Add a test for the reported layout with unnamed serial and ad-unit-ID columns; assert the real ad-unit ID column is selected.
- [ ] Run the focused tests and confirm they fail because the current fixed parser cannot map these layouts.

### Task 2: Implement flexible CSV table mapping

**Files:**
- Modify: `scripts/ads_audit_lib.py`

- [ ] Add delimiter detection and header-row detection using the standard library.
- [ ] Normalize headers and map aliases for ID, name, ad type, description, Task Detail, and Document.
- [ ] Infer an unnamed ID column only when values are consistently ad-unit-like and the candidate is unambiguous.
- [ ] Update setup errors to include detected headers and the missing semantic fields.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Document partner-facing behavior

**Files:**
- Modify: `README.md`
- Modify: `README.vi.md`

- [ ] Explain that column order, delimiter, language, and preamble rows can differ.
- [ ] Explain the safe fallback for an unnamed ID column and the explicit error when mapping remains ambiguous.

### Task 4: Verify and publish

**Files:**
- No source changes.

- [ ] Run the full Python test suite.
- [ ] Run the Node CLI tests and syntax checks.
- [ ] Copy the verified changes into the SSH-authenticated release clone, commit, push, and verify the remote SHA.
