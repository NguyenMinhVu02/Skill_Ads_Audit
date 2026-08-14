# Flexible ADS SCRIPTS CSV Design

## Goal

Allow each partner's `ADS SCRIPTS.csv` to use its own column order, delimiter, Vietnamese/English labels, and optional preamble rows without requiring manual spreadsheet edits.

## Design

The parser will read a CSV as a table, detect comma/semicolon/tab delimiters, and locate the first row containing recognizable placement fields. Header matching will normalize case, whitespace, punctuation, and Vietnamese diacritics. Supported aliases will cover placement ID, placement name, ad type, and description.

When no ID header is present, the parser will inspect unnamed columns and select a unique column whose values look like ad-unit identifiers (for example, values containing `/` or known ad-network prefixes). A serial-number column will not qualify. If no safe ID column can be selected, setup will fail with the detected headers and a concrete mapping instruction rather than silently dropping every row.

Existing named headers remain authoritative, so current files with a blank serial-number column and a separately named `ID` column keep their behavior. Working-file parsing will use the same delimiter/header-row detection while retaining its existing `Task Detail` and `Document` semantics.

## Error handling

The parser will report the source file, detected delimiter, detected headers, and required semantic fields when it cannot map a placement table. It will never claim a placement exists based only on a row number or description.

## Verification

Tests will cover the existing format, semicolon-delimited aliases, preamble rows, and the reported format where the ad-unit ID column is unnamed. The full Python and Node test suites must remain green.
