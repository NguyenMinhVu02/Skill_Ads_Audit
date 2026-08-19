#!/usr/bin/env python3
"""Resolve an audit input that may be a local file, a Google Sheet, or a Google Doc.

Partners keep the ADS SCRIPTS contract and the working checklist in Google
Drive, so the auditor accepts a share link directly. Everything is normalised to
a local CSV file before parsing; the rest of the pipeline never sees a URL.
"""

from __future__ import annotations

import csv
import re
import subprocess
import tempfile
from pathlib import Path

SHEET_ID = re.compile(r"docs\.google\.com/spreadsheets/d/(?:e/)?([a-zA-Z0-9_-]+)")
DOC_ID = re.compile(r"docs\.google\.com/document/d/(?:e/)?([a-zA-Z0-9_-]+)")
GID = re.compile(r"[#&?]gid=([0-9]+)")
# A checklist line exported from Docs: "App name: com.example" / "Package name\tcom.example"
DOC_PAIR = re.compile(r"^\s*(?P<key>[^:\t]{2,60}?)\s*(?::|\t|\s{3,})\s*(?P<value>.+?)\s*$")


class DocumentError(ValueError):
    """Raised when a supplied document cannot be fetched or understood."""


def is_url(value: str) -> bool:
    return value.strip().lower().startswith(("http://", "https://"))


def export_url(url: str) -> tuple[str, str]:
    """Return (download url, kind) where kind is 'csv' or 'txt'."""
    sheet = SHEET_ID.search(url)
    if sheet:
        gid_match = GID.search(url)
        gid = gid_match.group(1) if gid_match else "0"
        return f"https://docs.google.com/spreadsheets/d/{sheet.group(1)}/export?format=csv&gid={gid}", "csv"
    doc = DOC_ID.search(url)
    if doc:
        return f"https://docs.google.com/document/d/{doc.group(1)}/export?format=txt", "txt"
    return url, "csv"


def _download(url: str) -> bytes:
    command = [
        "curl", "--silent", "--show-error", "--location",
        "--max-time", "45", "--fail", url,
    ]
    try:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    except FileNotFoundError as error:
        raise DocumentError("curl is required to read a document link. Install curl or pass a local file.") from error
    except subprocess.TimeoutExpired as error:
        raise DocumentError(f"Timed out downloading {url}") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip() or f"curl exit {completed.returncode}"
        raise DocumentError(
            f"Could not download {url}: {detail}. "
            "Check that link sharing is set to anyone-with-the-link viewer."
        )
    return completed.stdout


def _looks_like_login_page(payload: bytes) -> bool:
    head = payload[:4096].lower()
    return b"<html" in head and (b"accounts.google.com" in head or b"sign in" in head)


def doc_text_to_csv(text: str) -> str:
    """Convert an exported Google Doc checklist into a two-column CSV.

    Only lines that read as `label <separator> value` are kept, which is how the
    working checklist is written. Prose and headings are dropped.
    """
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = DOC_PAIR.match(stripped)
        if not match:
            continue
        key = match.group("key").strip().strip("-•*").strip()
        value = match.group("value").strip()
        if key and value:
            rows.append((key, value))
    if not rows:
        raise DocumentError(
            "The Google Doc contains no `label: value` lines. "
            "Use a Google Sheet, or write the checklist as `App name: ...` lines."
        )
    buffer = ["Task Detail,Document"]
    for key, value in rows:
        buffer.append(",".join('"' + field.replace('"', '""') + '"' for field in (key, value)))
    return "\n".join(buffer) + "\n"


def resolve_document(value: str, label: str, cache_dir: Path | None = None) -> Path:
    """Return a local CSV path for `value`, downloading and converting if needed."""
    if not is_url(value):
        return Path(value).expanduser()
    url, kind = export_url(value)
    payload = _download(url)
    if _looks_like_login_page(payload):
        raise DocumentError(
            f"{label} link returned a Google sign-in page instead of the document. "
            "Set link sharing to anyone-with-the-link viewer, then rerun."
        )
    directory = cache_dir or Path(tempfile.mkdtemp(prefix="ads-audit-docs-"))
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{label}.csv"
    if kind == "txt":
        target.write_text(doc_text_to_csv(payload.decode("utf-8", errors="replace")), encoding="utf-8")
    else:
        target.write_bytes(payload)
    return target
