# Flexible Sheet Parsing and Python Auto-Discovery Design

## Goal

Allow both the Python CLI and the npx wrapper to audit partner CSV exports whose header names, column order, delimiter, and preamble rows vary, while refusing ambiguous mappings that could compare the wrong advertising IDs or app metadata.

## Scope

The change covers three verified gaps:

1. Make the webhook attachment-path test portable across macOS `/var` and `/private/var` aliases.
2. Give `scripts/run_audit.py` the same CSV auto-discovery behavior as the npx wrapper.
3. Extend both ADS SCRIPTS and working-file parsing with explicit aliases and guarded content-based inference.

Audit rules, webhook credentials, report schema, static findings, and release-only `ad_config.json` ID checking remain unchanged.

## CSV discovery

The Python CLI accepts `--ads-script` and `--working-file` as optional arguments. For each omitted argument, it recursively searches the project while skipping generated and hidden build directories. It selects exactly one matching CSV based on normalized filename markers:

- ADS contract: filename contains `ADS SCRIPTS` after punctuation and spacing normalization.
- Working contract: filename contains `working` or `work file` after normalization.

An explicitly supplied path always wins. Zero matches or multiple matches stop setup with a message that names the missing flag and lists candidates when applicable. Python and Node use the same discovery contract.

## Flexible header mapping

Parsing follows three ordered stages.

### 1. Explicit semantic aliases

Header normalization removes case, whitespace, punctuation, underscores, and Vietnamese diacritics. Existing aliases remain valid. Working-file aliases additionally include:

- `Content`, `Task content`, `Item`, `Field`, `Key`, and Vietnamese equivalents as the checklist-key column (`Task Detail`).
- `Detail`, `Value`, `Data`, `Result`, and Vietnamese equivalents as the checklist-value column (`Document`).

ADS SCRIPTS aliases cover placement name, ad type, ad-unit ID, and description without depending on column order.

### 2. Content-based inference

If required working-file headers are still unknown, the parser scores columns from their data:

- A key-column candidate contains recognized checklist labels such as `App name`, `Package name`, `Firebase`, `Adjust token`, Facebook fields, or TikTok fields.
- A value-column candidate contains populated cells on the same recognized rows and differs from the key column.
- The unique highest-confidence key/value pair is accepted.

For ADS SCRIPTS, existing ad-unit-ID inference remains guarded by recognizable ID shapes. Placement-name and ad-type columns may be inferred only when a unique pair consistently contains identifier-like placement keys and known ad formats.

### 3. Ambiguity stop

The parser never selects the first non-empty column merely because parsing failed. If required semantics are missing, tied, or below the confidence threshold, setup stops and reports the delimiter, detected headers, missing semantics, and candidate columns. This prevents a flexible parser from silently auditing the wrong contract.

## Data extraction

Column order and unrelated columns such as `Order`, `PIC`, owner, status, or notes do not matter. Preamble/export rows before the real header are allowed. Empty rows are ignored. Existing exact formats remain backward compatible and take precedence over inference.

## macOS path portability

Production code may canonicalize output paths. Tests compare canonical paths, so `/var/...` and `/private/var/...` are treated as the same target on macOS. Webhook attachment behavior is otherwise unchanged.

## Error handling

- Missing explicit files produce a sanitized input error.
- Auto-discovery with zero or multiple candidates produces an actionable setup error.
- Ambiguous sheet layouts fail before auditing and never produce false PASS findings.
- Error messages may include filenames and column headers but never token or webhook values.

## Verification

Automated tests cover:

- Python auto-discovery with one CSV of each kind.
- Explicit paths overriding discovery.
- Zero and multiple candidate failures.
- macOS-style symlinked output paths.
- `Order, Content, Detail, PIC` working sheets.
- Renamed and reordered working columns inferred from known checklist labels.
- Flexible ADS SCRIPTS aliases and safely inferred placement columns.
- Ambiguous layouts stopping with diagnostic headers.
- Existing Python and Node regression suites.

A final npx smoke test runs against a real partner project without sending a webhook.
