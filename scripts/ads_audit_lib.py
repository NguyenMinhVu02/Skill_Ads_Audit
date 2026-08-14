"""Read-only static checks for Infinity Android ads integrations."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any, Iterable


SECRET_LABELS = {"Adjust token", "Facebook Client token", "Tiktok token"}
SKIP_DIRS = {".git", ".gradle", "build", ".idea", ".worktrees", "out"}
SOURCE_SUFFIXES = {".kt", ".java"}

_HEADER_ALIASES = {
    "id": {
        "id",
        "adid",
        "adunit",
        "adunitid",
        "adunitidentifier",
        "placementid",
        "placementidentifier",
        "maad",
        "maid",
    },
    "name": {
        "name",
        "adname",
        "placement",
        "placementname",
        "slot",
        "slotname",
        "ten",
        "tenvitri",
    },
    "Ads type": {
        "adstype",
        "adtype",
        "adformat",
        "format",
        "type",
        "loaiquangcao",
        "loaiads",
    },
    "Mô tả": {"mota", "description", "desc", "des", "note", "ghichu"},
    "Task Detail": {"taskdetail", "congviec", "chitietcongviec"},
    "Document": {"document", "doc", "link", "tailieu"},
}

_KIND_HEADER_ALIASES = {
    "ads": {
        "id": {"unitcode", "adcode", "adsid", "adunitcode", "macode", "madonvi"},
        "name": {"adskey", "adkey", "configkey", "placementkey", "adplacement", "keyquangcao"},
        "Ads type": {"adcategory", "adscategory", "category", "loaiformat"},
        "Mô tả": {"notes", "details", "content", "noidung"},
    },
    "working": {
        "Task Detail": {
            "content",
            "taskcontent",
            "item",
            "field",
            "key",
            "noidung",
            "hangmuc",
            "truongthongtin",
        },
        "Document": {
            "detail",
            "details",
            "value",
            "data",
            "result",
            "chitiet",
            "giatri",
            "dulieu",
        },
    },
}

_WORKING_KEY_ALIASES = {
    "App name": {"appname", "applicationname", "applicationtitle", "apptitle", "tenapp", "tenungdung"},
    "Package name": {
        "packagename",
        "package",
        "packageid",
        "applicationid",
        "bundleid",
        "bundleidentifier",
        "tenpackage",
    },
    "Firebase": {"firebase", "firebaseproject", "firebaseurl", "projectfirebase", "duanfirebase"},
    "Adjust token": {"adjusttoken", "adjustapptoken"},
    "Facebook App ID": {"facebookappid", "fbappid"},
    "Facebook Client token": {"facebookclienttoken", "fbclienttoken"},
    "Tiktok token": {"tiktoktoken", "tiktokapptoken"},
}

_KNOWN_AD_TYPES = {
    "app",
    "appopen",
    "banner",
    "collapsiblebanner",
    "inter",
    "interstitial",
    "mrec",
    "native",
    "open",
    "reward",
    "rewarded",
    "rewardedinterstitial",
}


@dataclass(frozen=True)
class Placement:
    name: str
    ad_type: str
    ad_unit_id: str
    description: str
    row: int


@dataclass(frozen=True)
class AuditContract:
    placements: dict[str, Placement]
    admob_app_id: str | None
    source: str


@dataclass(frozen=True)
class ProjectChecklist:
    app_name: str | None
    package_name: str | None
    firebase_project: str | None
    required_values: dict[str, str]
    source: str


@dataclass
class Finding:
    rule_id: str
    category: str
    status: str
    expected: str
    observed: str
    recommendation: str
    location: str | None = None

    @classmethod
    def pass_(cls, rule_id: str, category: str, expected: str, observed: str, location: str | None = None) -> "Finding":
        return cls(rule_id, category, "PASS", expected, observed, "No action required.", location)

    @classmethod
    def fail(cls, rule_id: str, category: str, expected: str, observed: str, recommendation: str, location: str | None = None) -> "Finding":
        return cls(rule_id, category, "FAIL", expected, observed, recommendation, location)

    @classmethod
    def needs_mapping(cls, rule_id: str, expected: str, observed: str, recommendation: str, location: str | None = None) -> "Finding":
        return cls(rule_id, "placement_flow", "NEEDS_MAPPING", expected, observed, recommendation, location)

    @classmethod
    def needs_runtime(cls, rule_id: str, expected: str, observed: str, recommendation: str, location: str | None = None) -> "Finding":
        return cls(rule_id, "runtime", "NEEDS_RUNTIME_PROOF", expected, observed, recommendation, location)


@dataclass
class AuditReport:
    project_root: str
    contract: AuditContract
    checklist: ProjectChecklist
    findings: list[Finding] = field(default_factory=list)

    def finding(self, rule_id: str) -> Finding:
        return next(finding for finding in self.findings if finding.rule_id == rule_id)

    def counts(self) -> dict[str, int]:
        return dict(Counter(finding.status.lower() for finding in self.findings))

    def readiness(self) -> str:
        return "BLOCKED" if any(finding.status == "FAIL" for finding in self.findings) else "REVIEW_REQUIRED"


def _value(row: dict[str, str], *names: str) -> str:
    normalized = {str(key).strip().lower(): str(value or "").strip() for key, value in row.items()}
    for name in names:
        result = normalized.get(name.strip().lower(), "")
        if result:
            return result
    return ""


def _normalize_header(value: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    without_marks = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "", without_marks.casefold())


def _detect_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:80])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {delimiter: sample.count(delimiter) for delimiter in (",", ";", "\t", "|")}
        return max(counts, key=counts.get) if any(counts.values()) else ","


def _read_table(path: Path) -> tuple[str, list[list[str]]]:
    text = path.read_text(encoding="utf-8-sig")
    delimiter = _detect_delimiter(text)
    return delimiter, list(csv.reader(io.StringIO(text), delimiter=delimiter))


def _semantic_header(value: str | None, kind: str | None = None) -> str | None:
    normalized = _normalize_header(value)
    if kind:
        for semantic, aliases in _KIND_HEADER_ALIASES[kind].items():
            if normalized in aliases:
                return semantic
    for semantic, aliases in _HEADER_ALIASES.items():
        if normalized in aliases:
            return semantic
    return None


def _canonical_working_key(value: str | None) -> str | None:
    normalized = _normalize_header(value)
    for canonical, aliases in _WORKING_KEY_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def _looks_like_ad_unit_id(value: str) -> bool:
    value = value.strip()
    lowered = value.casefold()
    if not value or any(character.isspace() for character in value):
        return False
    if "/" in value or re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{27,}", lowered):
        return True
    return lowered.startswith(("ca-app-", "admob", "pub-", "g-"))


def _infer_id_column(headers: list[str], data_rows: list[list[str]]) -> int | None:
    if any(_semantic_header(header, "ads") == "id" for header in headers):
        return None

    candidates: list[tuple[float, int]] = []
    for column_index, header in enumerate(headers):
        if _semantic_header(header, "ads") is not None:
            continue
        values = [row[column_index].strip() for row in data_rows if column_index < len(row) and row[column_index].strip()]
        if not values:
            continue
        id_like_ratio = sum(_looks_like_ad_unit_id(value) for value in values) / len(values)
        if id_like_ratio < 0.6:
            continue
        unique_ratio = len(set(values)) / len(values)
        score = (id_like_ratio * 10) + unique_ratio
        candidates.append((score, column_index))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 1:
        return None
    return candidates[0][1]


def _unique_best_column(scores: list[tuple[float, int]], minimum: float) -> int | None:
    eligible = [(score, index) for score, index in scores if score >= minimum]
    if not eligible:
        return None
    eligible.sort(reverse=True)
    if len(eligible) > 1 and abs(eligible[0][0] - eligible[1][0]) < 0.001:
        return None
    return eligible[0][1]


def _working_value_score(key: str, value: str) -> float:
    value = value.strip()
    if not value:
        return 0
    score = 1.0
    if key == "Package name" and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*){1,}", value):
        score += 5
    elif key == "Firebase" and ("firebase" in value.casefold() or "/project/" in value):
        score += 5
    elif key == "App name" and not _looks_like_ad_unit_id(value) and "://" not in value:
        score += 1
    elif key in SECRET_LABELS | {"Facebook App ID"} and len(value) >= 6:
        score += 1
    return score


def _infer_working_columns(canonical: list[str], data_rows: list[list[str]]) -> None:
    key_index = canonical.index("Task Detail") if "Task Detail" in canonical else None
    if key_index is None:
        key_scores = []
        for index in range(len(canonical)):
            count = sum(
                _canonical_working_key(row[index]) is not None
                for row in data_rows
                if index < len(row) and row[index].strip()
            )
            key_scores.append((float(count), index))
        key_index = _unique_best_column(key_scores, minimum=2)
        if key_index is not None:
            canonical[key_index] = "Task Detail"

    if key_index is None or "Document" in canonical:
        return
    value_scores: list[tuple[float, int]] = []
    for index in range(len(canonical)):
        if index == key_index or canonical[index] in {"Task Detail", "Document"}:
            continue
        score = 0.0
        for row in data_rows:
            if key_index >= len(row) or index >= len(row):
                continue
            key = _canonical_working_key(row[key_index])
            if key:
                score += _working_value_score(key, row[index])
        value_scores.append((score, index))
    value_index = _unique_best_column(value_scores, minimum=2)
    if value_index is not None:
        canonical[value_index] = "Document"


def _looks_like_ad_type(value: str) -> bool:
    return _normalize_header(value) in _KNOWN_AD_TYPES


def _looks_like_placement_name(value: str) -> bool:
    value = value.strip()
    if value.upper() == "APP ID":
        return True
    lowered = value.casefold()
    return bool(re.fullmatch(r"[a-z][a-z0-9_.-]+", lowered)) and (
        "_" in lowered or lowered.startswith(("banner", "inter", "native", "open", "reward"))
    )


def _infer_ads_column(canonical: list[str], data_rows: list[list[str]], semantic: str, predicate: Any) -> None:
    if semantic in canonical:
        return
    scores: list[tuple[float, int]] = []
    for index in range(len(canonical)):
        if canonical[index] in {"id", "name", "Ads type", "Mô tả"}:
            continue
        values = [row[index].strip() for row in data_rows if index < len(row) and row[index].strip()]
        if not values:
            continue
        ratio = sum(bool(predicate(value)) for value in values) / len(values)
        scores.append((ratio, index))
    inferred = _unique_best_column(scores, minimum=0.6)
    if inferred is not None:
        canonical[inferred] = semantic


def _canonical_headers(headers: list[str], data_rows: list[list[str]], kind: str) -> list[str]:
    canonical: list[str] = []
    for index, header in enumerate(headers):
        semantic = _semantic_header(header, kind)
        if semantic is not None:
            canonical.append(semantic if semantic not in canonical else f"{semantic}_{index}")
        else:
            normalized = _normalize_header(header)
            canonical.append(normalized or f"column_{index}")

    if kind == "ads":
        inferred_index = _infer_id_column(headers, data_rows)
        if inferred_index is not None:
            canonical[inferred_index] = "id"
        _infer_ads_column(canonical, data_rows, "Ads type", _looks_like_ad_type)
        _infer_ads_column(canonical, data_rows, "name", _looks_like_placement_name)
    else:
        _infer_working_columns(canonical, data_rows)
    return canonical


def _required_headers(kind: str) -> tuple[str, ...]:
    return ("name", "Ads type", "id") if kind == "ads" else ("Task Detail", "Document")


def _find_header_mapping(rows: list[list[str]], kind: str) -> tuple[int, list[str]] | None:
    required = _required_headers(kind)
    for index, row in enumerate(rows[:50]):
        semantics = {_semantic_header(value, kind) for value in row}
        if all(field in semantics for field in required):
            return index, _canonical_headers(row, rows[index + 1 :], kind)
    for index, row in enumerate(rows[:50]):
        if sum(bool(value.strip()) for value in row) < 2:
            continue
        canonical = _canonical_headers(row, rows[index + 1 :], kind)
        if all(field in canonical for field in required):
            return index, canonical
    return None


def _rows(path: Path, kind: str) -> Iterable[tuple[int, dict[str, str]]]:
    delimiter, rows = _read_table(path)
    if not rows:
        return
    mapping = _find_header_mapping(rows, kind)
    if mapping is None:
        nonempty = [row for row in rows[:50] if any(value.strip() for value in row)]
        headers = max(nonempty, key=lambda row: sum(bool(value.strip()) for value in row), default=[])
        displayed = ", ".join(header.strip() or "<unnamed>" for header in headers) or "<none>"
        required = ", ".join(_required_headers(kind))
        raise ValueError(
            f"Could not map required {kind} CSV columns in {path}. "
            f"Detected delimiter {delimiter!r} and headers: {displayed}. Required semantics: {required}."
        )
    header_index, canonical = mapping
    data_rows = rows[header_index + 1 :]
    for row_number, values in enumerate(data_rows, start=header_index + 2):
        if not any(value.strip() for value in values):
            continue
        padded = values + [""] * max(0, len(canonical) - len(values))
        yield row_number, {header: padded[index] for index, header in enumerate(canonical)}


def _layout_hint(path: Path, kind: str) -> str:
    try:
        delimiter, rows = _read_table(path)
        mapping = _find_header_mapping(rows, kind)
        header_index = mapping[0] if mapping else 0
        headers = rows[header_index] if rows and header_index < len(rows) else []
        displayed = ", ".join(header.strip() or "<unnamed>" for header in headers)
        return f" Detected delimiter {delimiter!r} and headers: {displayed or '<none>'}."
    except (OSError, UnicodeError, csv.Error):
        return " Could not inspect the CSV layout."


def parse_ads_script(path: str | Path) -> AuditContract:
    path = Path(path)
    placements: dict[str, Placement] = {}
    app_id: str | None = None
    for row_number, row in _rows(path, "ads"):
        name = _value(row, "Name")
        identifier = _value(row, "ID")
        if name.upper() == "APP ID":
            app_id = identifier or None
        elif name and identifier and _value(row, "Ads type"):
            placements[name] = Placement(name, _value(row, "Ads type"), identifier, _value(row, "Mô tả", "Des", "Description"), row_number)
    if not placements:
        raise ValueError(
            f"No placement rows found in ADS Script: {path}. "
            "Expected recognizable columns for Name, Ads type, and an ad-unit ID; "
            "the file may use an unsupported layout or have no populated placement rows."
            f"{_layout_hint(path, 'ads')}"
        )
    return AuditContract(placements=placements, admob_app_id=app_id, source=str(path))


def parse_working_file(path: str | Path) -> ProjectChecklist:
    path = Path(path)
    values: dict[str, str] = {}
    for _, row in _rows(path, "working"):
        key = _value(row, "Task Detail")
        value = _value(row, "Document")
        if key and value:
            values[_canonical_working_key(key) or key] = value
    return ProjectChecklist(
        app_name=values.get("App name"),
        package_name=values.get("Package name"),
        firebase_project=_firebase_project(values.get("Firebase", "")),
        required_values={key: value for key, value in values.items() if key in SECRET_LABELS or key == "Facebook App ID"},
        source=str(path),
    )


def _firebase_project(value: str) -> str | None:
    match = re.search(r"/project/([^/?]+)", value)
    return match.group(1) if match else None


def redact_value(value: str | None) -> str:
    if not value:
        return "<missing>"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"<redacted:sha256:{digest}>"


def _files(root: Path, suffixes: set[str] | None = None) -> list[Path]:
    return [
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file() and not any(part in SKIP_DIRS for part in candidate.relative_to(root).parts) and (suffixes is None or candidate.suffix in suffixes)
    ]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _line_ref(root: Path, path: Path, token: str) -> str | None:
    for number, line in enumerate(_read(path).splitlines(), start=1):
        if token in line:
            return f"{path.relative_to(root)}:{number}"
    return str(path.relative_to(root))


def _location(root: Path, path: Path | None, token: str | None = None) -> str | None:
    if path is None:
        return None
    return _line_ref(root, path, token) if token else str(path.relative_to(root))


def _missing_tokens(text: str, tokens: Iterable[str]) -> list[str]:
    return [token for token in tokens if token not in text]


def _tokens_in_order(text: str, tokens: Iterable[str]) -> bool:
    offset = -1
    for token in tokens:
        found = text.find(token, offset + 1)
        if found < 0:
            return False
        offset = found
    return True


def _check_tokens(
    report: AuditReport,
    root: Path,
    rule_id: str,
    category: str,
    expected: str,
    text: str,
    tokens: Iterable[str],
    recommendation: str,
    path: Path | None = None,
) -> None:
    tokens = list(tokens)
    missing = _missing_tokens(text, tokens)
    if missing:
        report.findings.append(Finding.fail(rule_id, category, expected, f"missing: {', '.join(missing)}", recommendation, _location(root, path)))
    else:
        report.findings.append(Finding.pass_(rule_id, category, expected, "found", _location(root, path, tokens[0] if tokens else None)))


def _check_ordered_tokens(
    report: AuditReport,
    root: Path,
    rule_id: str,
    category: str,
    expected: str,
    text: str,
    tokens: Iterable[str],
    recommendation: str,
    path: Path | None = None,
) -> None:
    tokens = list(tokens)
    missing = _missing_tokens(text, tokens)
    if missing:
        report.findings.append(Finding.fail(rule_id, category, expected, f"missing: {', '.join(missing)}", recommendation, _location(root, path)))
    elif not _tokens_in_order(text, tokens):
        report.findings.append(Finding.fail(rule_id, category, expected, "tokens found but not in required order", recommendation, _location(root, path, tokens[0])))
    else:
        report.findings.append(Finding.pass_(rule_id, category, expected, "found in required order", _location(root, path, tokens[0])))


def _combined_text(paths: Iterable[Path]) -> str:
    return "\n".join(_read(path) for path in paths)


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1) if match else None


def _config_data(path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(_read(path))
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict) and isinstance(parsed.get("ads"), dict):
        return parsed["ads"]
    return parsed if isinstance(parsed, dict) else None


def _check_equal(report: AuditReport, rule_id: str, category: str, expected: str | None, observed: str | None, recommendation: str, location: str | None = None, redact: bool = False) -> None:
    display_expected = redact_value(expected) if redact else (expected or "<not supplied>")
    display_observed = redact_value(observed) if redact else (observed or "<missing>")
    if expected and observed == expected:
        report.findings.append(Finding.pass_(rule_id, category, display_expected, display_observed, location))
    else:
        report.findings.append(Finding.fail(rule_id, category, display_expected, display_observed, recommendation, location))


def _check_config(report: AuditReport, root: Path, contract: AuditContract, config_name: str, label: str) -> None:
    candidates = [path for path in _files(root, {".json"}) if path.name == config_name]
    if not candidates:
        for placement in contract.placements.values():
            report.findings.append(Finding.fail(f"AD_CONFIG_{label}:{placement.name}", "ad_config", placement.ad_unit_id, "config file missing", f"Add `{config_name}` with `{placement.name}` and its contract ad unit ID."))
        return
    config_path = candidates[0]
    config = _config_data(config_path)
    if config is None:
        report.findings.append(Finding.fail(f"AD_CONFIG_{label}:FILE", "ad_config", "valid JSON", "invalid JSON", f"Fix JSON syntax in `{config_path.name}`.", str(config_path.relative_to(root))))
        return
    for placement in contract.placements.values():
        observed = config.get(placement.name)
        rule_id = f"AD_CONFIG_{label}:{placement.name}"
        if not isinstance(observed, dict):
            report.findings.append(Finding.fail(rule_id, "ad_config", placement.ad_unit_id, "key missing", f"Add `{placement.name}` using the ID from ADS Script row {placement.row}.", str(config_path.relative_to(root))))
            continue
        actual_id = str(observed.get("id", ""))
        location = _line_ref(root, config_path, f'"{placement.name}"')
        _check_equal(report, rule_id, "ad_config", placement.ad_unit_id, actual_id, f"Set `{placement.name}.id` to the exact ADS Script ID.", location)
        if "isEnable" not in observed:
            report.findings.append(Finding.fail(f"AD_CONFIG_{label}:ENABLE:{placement.name}", "ad_config", "isEnable field", "field missing", "Add explicit `isEnable` to this placement.", location))


def _load_overrides(path: Path | None) -> dict[str, dict[str, str]]:
    """Parse the narrow, dependency-free YAML shape supplied by the template."""
    if path is None or not path.is_file():
        return {}
    placements: dict[str, dict[str, str]] = {}
    current: str | None = None
    for raw_line in _read(path).splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        placement_match = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", raw_line)
        field_match = re.match(r"^    ([A-Za-z_]+):\s*(.*?)\s*$", raw_line)
        if placement_match:
            current = placement_match.group(1)
            placements[current] = {}
        elif field_match and current:
            placements[current][field_match.group(1)] = field_match.group(2).strip("\"'")
    return placements


def _check_flow(report: AuditReport, root: Path, contract: AuditContract, source_paths: list[Path], overrides: dict[str, dict[str, str]]) -> None:
    source = _combined_text(source_paths)
    known = {
        "inter_splash": ("SplashActivity", "loadSplashInterstitialAds"),
        "native_language_1": ("SplashActivity", "loadNativeLanguage"),
        "native_language_2": ("SplashActivity", "loadNativeLanguage"),
        "native_onboarding_1_1": ("LanguageActivity", "loadNativeOnboarding1"),
        "native_onboarding_2_1": ("LanguageActivity", "loadNativeOnboarding1"),
        "native_onboarding_1_4": ("OnBoardingActivity", "loadNativeOnboarding4"),
        "native_onboarding_2_4": ("OnBoardingActivity", "loadNativeOnboarding4"),
        "inter_onboarding": ("OnBoardingActivity", "showInterOnboarding"),
        "inter_welcome_back": ("AppLifecycleObserver", "getShouldDisplayInterWelcomeBack"),
        "native_home": ("MainActivity", "loadNativeHome"),
        "banner_home": ("MainActivity", "banner_home"),
    }
    for placement in contract.placements.values():
        rule_id = f"PLACEMENT_FLOW:{placement.name}"
        mapping = known.get(placement.name)
        override = overrides.get(placement.name)
        if override and override.get("class") and (override.get("show_call") or override.get("load_call")):
            mapping = (override["class"], override.get("show_call") or override["load_call"])
        if mapping is None:
            report.findings.append(Finding.needs_mapping(rule_id, placement.description or "project-specific placement", "no approved class/event mapping", f"Add `{placement.name}` to `ads-audit-overrides.yaml` with class and required call/event evidence."))
            continue
        class_name, call = mapping
        class_files = [path for path in source_paths if path.name == f"{class_name}.kt" or path.name == f"{class_name}.java"]
        matching = next((path for path in class_files if call in _read(path)), None)
        if matching:
            report.findings.append(Finding.pass_(rule_id, "placement_flow", f"{class_name} calls {call}", f"found {call}", _line_ref(root, matching, call)))
        elif class_files:
            report.findings.append(Finding.fail(rule_id, "placement_flow", f"{class_name} calls {call}", "call not found", f"Implement this placement through `AdsManager` at the configured lifecycle/event point.", str(class_files[0].relative_to(root))))
        else:
            report.findings.append(Finding.fail(rule_id, "placement_flow", f"{class_name} calls {call}", "screen class not found", "Add an approved override mapping if the partner uses another class name; otherwise restore the required screen flow."))
        if placement.ad_type.lower().strip() == "interstitial" and placement.name != "inter_welcome_back":
            report.findings.append(Finding.needs_runtime(f"RUNTIME:{placement.name}", "show only at the configured user transition", "static source cannot prove every runtime event", f"Run the placement test case for `{placement.name}` and attach video/log proof."))


def _source_by_class(source_paths: list[Path], class_name: str) -> Path | None:
    return next((path for path in source_paths if path.name in {f"{class_name}.kt", f"{class_name}.java"}), None)


PRIMARY_SCREEN_TOKENS = ("splash", "language", "onboarding", "home", "welcome")


def _simple_class_name(value: str) -> str:
    return value.rsplit(".", 1)[-1]


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _primary_screen_for_fragment(class_name: str) -> str | None:
    simple_name = _simple_class_name(class_name)
    normalized = _normalized_name(simple_name)
    if not normalized.endswith("fragment"):
        return None
    return next((token for token in PRIMARY_SCREEN_TOKENS if token in normalized), None)


def _check_primary_screen_activities(
    report: AuditReport,
    root: Path,
    manifests: list[Path],
    source_paths: list[Path],
    navigation_paths: list[Path],
) -> None:
    """Reject a single-Activity primary ad journey implemented as screen fragments."""
    fragments: dict[str, tuple[str, str | None]] = {}
    for path in source_paths:
        screen = _primary_screen_for_fragment(path.stem)
        if screen:
            fragments[_simple_class_name(path.stem)] = (screen, str(path.relative_to(root)))
    for path in navigation_paths:
        for class_name in re.findall(r'(?:android:)?name\s*=\s*["\']([^"\']+Fragment)["\']', _read(path)):
            screen = _primary_screen_for_fragment(class_name)
            if screen:
                fragments[_simple_class_name(class_name)] = (screen, str(path.relative_to(root)))

    activity_names: set[str] = set()
    for path in manifests:
        for class_name in re.findall(r'<activity\b[^>]*(?:android:)?name\s*=\s*["\']([^"\']+)["\']', _read(path)):
            activity_names.add(_simple_class_name(class_name))

    if not fragments:
        report.findings.append(Finding.pass_(
            "ARCH_PRIMARY_SCREENS_ACTIVITY",
            "architecture",
            "primary ads-journey screens use separate Activities",
            "no primary-screen Fragment navigation found",
        ))
        return

    missing: list[tuple[str, str | None]] = []
    for fragment_name, (screen, location) in fragments.items():
        has_matching_activity = any(
            _normalized_name(activity_name).endswith("activity") and screen in _normalized_name(activity_name)
            for activity_name in activity_names
        )
        if not has_matching_activity:
            missing.append((fragment_name, location))

    observed = ", ".join(name for name, _ in missing) if missing else ", ".join(fragments)
    locations = sorted({location for _, location in missing if location})
    if missing:
        report.findings.append(Finding.fail(
            "ARCH_PRIMARY_SCREENS_ACTIVITY",
            "architecture",
            "separate Activity classes for Splash, Language, Onboarding, Home, and Welcome primary screens",
            f"single-Activity/Fragment screen flow detected: {observed}",
            "Move the listed primary screens from Fragment navigation to separate Activities following the Infinity base flow.",
            "; ".join(locations) or None,
        ))
    else:
        report.findings.append(Finding.pass_(
            "ARCH_PRIMARY_SCREENS_ACTIVITY",
            "architecture",
            "primary ads-journey screens use separate Activities",
            f"matching Activity declarations found for: {observed}",
        ))


def _check_inter_welcome_back(report: AuditReport, root: Path, contract: AuditContract, source_paths: list[Path], manager_text: str, global_text: str, overrides: dict[str, dict[str, str]]) -> None:
    if "inter_welcome_back" not in contract.placements:
        return
    override = overrides.get("inter_welcome_back", {})
    observer_class = override.get("observer_class", "AppLifecycleObserver")
    welcome_class = override.get("welcome_class", "WelcomeActivity")
    observer_path = _source_by_class(source_paths, observer_class)
    welcome_path = _source_by_class(source_paths, welcome_class)
    observer_text = _read(observer_path) if observer_path else ""
    welcome_text = _read(welcome_path) if welcome_path else ""
    observer_tokens = (
        "ResumeAdsEntryRule.shouldShowWelcomeOnResume",
        "getShouldDisplayInterWelcomeBack",
        "startWelcomeActivity",
    )
    missing_observer = [token for token in observer_tokens if token not in observer_text]
    observer_location = str(observer_path.relative_to(root)) if observer_path else None
    if missing_observer:
        report.findings.append(Finding.fail("FLOW_INTER_WELCOME_BACK_OBSERVER", "placement_flow", "resume observer checks Welcome rule, UA gate, then routes to Welcome", f"missing: {', '.join(missing_observer)}", "Implement the resume chain: `ResumeAdsEntryRule.shouldShowWelcomeOnResume()` + `getShouldDisplayInterWelcomeBack(config.enableUaCheck)` + route to WelcomeActivity.", observer_location))
    else:
        report.findings.append(Finding.pass_("FLOW_INTER_WELCOME_BACK_OBSERVER", "placement_flow", "resume observer checks Welcome rule, UA gate, then routes to Welcome", "found", _line_ref(root, observer_path, "getShouldDisplayInterWelcomeBack")))
    welcome_tokens = ("AdsManager.loadInterWelcome", "AdsManager.showInterWelcome")
    missing_welcome = [token for token in welcome_tokens if token not in welcome_text]
    welcome_location = str(welcome_path.relative_to(root)) if welcome_path else None
    if missing_welcome:
        report.findings.append(Finding.fail("FLOW_INTER_WELCOME_BACK_LOAD_SHOW", "placement_flow", "Welcome screen loads and shows the Welcome interstitial through AdsManager", f"missing: {', '.join(missing_welcome)}", "Load `inter_welcome_back` when Welcome starts and show it only from the configured Welcome CTA; finish/continue in the close/fail callback.", welcome_location))
    else:
        report.findings.append(Finding.pass_("FLOW_INTER_WELCOME_BACK_LOAD_SHOW", "placement_flow", "Welcome screen loads and shows the Welcome interstitial through AdsManager", "found", _line_ref(root, welcome_path, "AdsManager.loadInterWelcome")))
    required_manager_tokens = ("fun loadInterWelcome", "fun showInterWelcome", ".isEnable", "AppPurchase.getInstance().isPurchased")
    missing_manager = [token for token in required_manager_tokens if token not in manager_text]
    if missing_manager:
        report.findings.append(Finding.fail("FLOW_INTER_WELCOME_BACK_MANAGER", "placement_flow", "AdsManager load/show applies config enable and purchase gates", f"missing: {', '.join(missing_manager)}", "Implement the Welcome interstitial inside AdsManager with config enable and purchase checks."))
    else:
        report.findings.append(Finding.pass_("FLOW_INTER_WELCOME_BACK_MANAGER", "placement_flow", "AdsManager load/show applies config enable and purchase gates", "found"))
    registration_token = f"addObserver({observer_class}"
    if registration_token in global_text:
        report.findings.append(Finding.pass_("FLOW_INTER_WELCOME_BACK_REGISTRATION", "placement_flow", f"Application registers {observer_class} with ProcessLifecycleOwner", "found"))
    else:
        report.findings.append(Finding.fail("FLOW_INTER_WELCOME_BACK_REGISTRATION", "placement_flow", f"Application registers {observer_class} with ProcessLifecycleOwner", "registration not found", f"Register `{observer_class}` using `ProcessLifecycleOwner.get().lifecycle.addObserver(...)` in Application.onCreate()."))
    report.findings.append(Finding.needs_runtime("RUNTIME:inter_welcome_back", "resume app from background/recents, route to Welcome, tap CTA, close/fail interstitial, return to previous screen", "static analysis cannot prove lifecycle timing, ad readiness, or no duplicate App Open ad", "Record this journey with device logs/video after static checks pass."))


def _check_global_base_rules(report: AuditReport, root: Path, global_app: Path | None, global_text: str, gradle_text: str) -> None:
    _check_ordered_tokens(
        report,
        root,
        "ARCH_GLOBAL_INIT_ORDER",
        "architecture",
        "GlobalApp initializes MobileAds, DevConfig, local AdRemoteConfig, then ERainAd in that order",
        global_text,
        ("MobileAds.initialize", "DevConfig.init", "AdRemoteConfig.initializeFromAssets", "ERainAd.getInstance().init"),
        "Keep the base order in GlobalApp.onCreate(): MobileAds.initialize -> DevConfig.init -> initAdRemoteConfig/AdRemoteConfig.initializeFromAssets -> initAds/ERainAd.init.",
        global_app,
    )
    _check_tokens(
        report,
        root,
        "ARCH_DEV_CONFIG_INIT",
        "architecture",
        "DevConfig.init receives BuildConfig ad library version fields",
        global_text,
        ("DevConfig.init", "BuildConfig.ERAIN_STUDIO_VERSION", "BuildConfig.PLAY_SERVICES_ADS_VERSION", "BuildConfig.GDPR_MODULE_VERSION"),
        "Call DevConfig.init early from GlobalApp and pass the three BuildConfig version fields.",
        global_app,
    )
    _check_tokens(
        report,
        root,
        "ARCH_DEV_CONFIG_BUILD_FIELDS",
        "architecture",
        "debug/release buildConfigField values exist for ERain Studio, Play Services Ads, and GDPR versions",
        gradle_text,
        ("ERAIN_STUDIO_VERSION", "PLAY_SERVICES_ADS_VERSION", "GDPR_MODULE_VERSION"),
        "Declare all three buildConfigField values in app/build.gradle for debug and release.",
    )
    _check_tokens(
        report,
        root,
        "ARCH_ADS_CONFIG_FIELDS",
        "architecture",
        "ERainAdConfig receives Adjust, Facebook, TikTok, interval, and resume id fields before ERainAd.init",
        global_text,
        ("AdjustConfig", "facebookClientToken", "adjustTokenTiktok", "intervalInterstitialAd", "idAdResume", "ERainAd.getInstance().init"),
        "Preserve the base GlobalApp.initAds fields before ERainAd.getInstance().init(...).",
        global_app,
    )
    _check_tokens(
        report,
        root,
        "ARCH_APP_OPEN_EXCLUSIONS",
        "architecture",
        "AppOpen resume is disabled on Splash, Language, and Onboarding primary flow screens",
        global_text,
        ("disableAppResumeWithActivity(SplashActivity::class.java", "disableAppResumeWithActivity(LanguageActivity::class.java", "disableAppResumeWithActivity(OnBoardingActivity::class.java"),
        "Disable AppOpen resume on SplashActivity, LanguageActivity, and OnBoardingActivity in GlobalApp.initAds().",
        global_app,
    )


def _check_screen_flow_rules(report: AuditReport, root: Path, source_paths: list[Path]) -> None:
    splash = _source_by_class(source_paths, "SplashActivity")
    splash_text = _read(splash) if splash else ""
    _check_tokens(
        report,
        root,
        "FLOW_SPLASH_REMOTE_CONFIG",
        "placement_flow",
        "Splash initializes RemoteConfig, applies AdRemoteConfig from RemoteConfigUtils, and falls back after timeout",
        splash_text,
        ("RemoteConfigUtils.init", "loadingRemoteConfig", "AdRemoteConfig.initialize", "RemoteConfigUtils.getAdRemoteConfig"),
        "Keep SplashActivity consent/remote-config loading and apply AdRemoteConfig.initialize(this, RemoteConfigUtils.getAdRemoteConfig()).",
        splash,
    )
    _check_tokens(
        report,
        root,
        "FLOW_SPLASH_INTER_PRELOAD_LANGUAGE",
        "placement_flow",
        "Splash gates inter_splash by config/network, loads splash interstitial, preloads native language onAdLoaded, and navigates onNextAction",
        splash_text,
        ("AdRemoteConfig.inter_splash.isEnable", "isNetwork", "loadSplashInterstitialAds", "onAdLoaded", "loadNativeLanguage", "onNextAction", "moveActivity"),
        "Preserve Splash interstitial load/show and preload native language only from the splash loaded callback.",
        splash,
    )
    _check_tokens(
        report,
        root,
        "FLOW_SPLASH_OPEN_RESUME",
        "placement_flow",
        "Splash enables or disables open_resume through ResumeAdsEntryRule and AppOpenManager",
        splash_text,
        ("ResumeAdsEntryRule.shouldEnableOpenResume", "setAppResumeAdId", "AdRemoteConfig.open_resume.id", "enableAppResume", "disableAppResume"),
        "Configure AppOpen resume in Splash after AdRemoteConfig is initialized.",
        splash,
    )

    language = _source_by_class(source_paths, "LanguageActivity")
    language_text = _read(language) if language else ""
    _check_tokens(
        report,
        root,
        "FLOW_LANGUAGE_DEV_SETTING",
        "placement_flow",
        "Language screen exposes DevSetting through tvTitle admin ads toggle",
        language_text,
        ("tvTitle.setOnAdminAdToggleListener", "Routes.startSplashActivity"),
        "Keep mBinding.tvTitle.setOnAdminAdToggleListener() so QA can open DevConfig/ads testing.",
        language,
    )
    _check_tokens(
        report,
        root,
        "FLOW_LANGUAGE_PRELOAD_AND_RENDER",
        "placement_flow",
        "Language loads click native, preloads onboarding page 1, observes language LiveData, renders non-null ads, and hides null/offline ads",
        language_text,
        ("postDelayed", "100L", "loadNativeLanguageClick", "loadNativeOnboarding1", "nativeLanguageAdLive.observe", "nativeLanguageClickAdLive.observe", "populateNativeAdView", "flAds.goneView"),
        "Preserve Language native/click rendering and onboarding page-1 preload after the short base delay.",
        language,
    )

    onboarding = _source_by_class(source_paths, "OnBoardingActivity")
    onboarding_text = _read(onboarding) if onboarding else ""
    _check_tokens(
        report,
        root,
        "FLOW_ONBOARDING_PRELOAD_AND_SHOW",
        "placement_flow",
        "Onboarding preloads native page 4, native full, inter_onboarding, widget shortcut gate, and shows inter before Main",
        onboarding_text,
        ("postDelayed", "100L", "loadNativeOnboarding4", "loadNativeOnboardingFull", "loadInterOnboarding", "getShouldDisplayWidgetUninstall", "getShouldDisplayNativeOnboardingFull1", "showInterOnboarding", "Routes.startMainActivity"),
        "Keep OnBoardingActivity preload timing, native full/widget gates, and final interstitial callback navigation.",
        onboarding,
    )

    onboarding_page = _source_by_class(source_paths, "OnboardingPageFragment")
    onboarding_page_text = _read(onboarding_page) if onboarding_page else ""
    _check_tokens(
        report,
        root,
        "FLOW_ONBOARDING_PAGE_RENDERING",
        "placement_flow",
        "Onboarding page fragment maps page flags to AdsManager LiveData and renders/hides native ads",
        onboarding_page_text,
        ("nativeOnboarding1AdLive", "nativeOnboarding4AdLive", "nativeAdOnBoardingFullLive", "observe", "renderAd", "populateNativeAdView"),
        "Keep OnboardingPageFragment LiveData mapping for page 1, page 4, and fullscreen native ads.",
        onboarding_page,
    )

    resume_rule = _source_by_class(source_paths, "ResumeAdsEntryRule")
    resume_rule_text = _read(resume_rule) if resume_rule else ""
    observer = _source_by_class(source_paths, "AppLifecycleObserver")
    observer_text = _read(observer) if observer else ""
    _check_tokens(
        report,
        root,
        "FLOW_RESUME_RULE",
        "placement_flow",
        "Resume rule selects open_resume or welcome mode and observer blocks disabled screens before routing Welcome",
        resume_rule_text + "\n" + observer_text,
        ("open_resume.isEnable", "native_welcome.isEnable", "inter_welcome.isEnable", "shouldEnableOpenResume", "shouldShowWelcomeOnResume", "listActivityDisableResume", "isInterstitialShowing", "getShouldDisplayInterWelcomeBack", "Routes.startWelcomeActivity"),
        "Preserve ResumeAdsEntryRule plus AppLifecycleObserver gating before WelcomeActivity routing.",
        observer or resume_rule,
    )

    welcome = _source_by_class(source_paths, "WelcomeActivity")
    welcome_text = _read(welcome) if welcome else ""
    _check_tokens(
        report,
        root,
        "FLOW_WELCOME_NATIVE_AND_INTER",
        "placement_flow",
        "Welcome loads native and inter on start, observes native LiveData, renders/hides native, and shows inter on CTA before finish",
        welcome_text,
        ("loadNativeWelcome", "loadInterWelcome", "nativeWelcomeAdLive.observe", "renderWelcomeAd", "populateNativeAdView", "showInterWelcome", "finish"),
        "Keep WelcomeActivity load/show chain through AdsManager and hide native container on null/offline state.",
        welcome,
    )

    banner = _source_by_class(source_paths, "BaseActivityWithBanner")
    banner_text = _read(banner) if banner else ""
    _check_tokens(
        report,
        root,
        "ARCH_BANNER_BASE_RELOAD",
        "architecture",
        "BaseActivityWithBanner loads banner onCreate, reloads onResume by reloadIntervalSeconds, and gates isEnable/purchase/container",
        banner_text,
        ("BannerConfig", "loadBanner", "reloadBannerIfNeeded", "reloadIntervalSeconds", "postDelayed", "shouldShowBanner", "AppPurchase.getInstance().isPurchased", "AdsManager.loadBanner"),
        "Use BaseActivityWithBanner for banner screens and preserve reloadIntervalSeconds handling.",
        banner,
    )


def _check_ads_manager_base_rules(report: AuditReport, root: Path, manager_paths: list[Path], manager_text: str) -> None:
    manager_path = manager_paths[0] if manager_paths else None
    _check_tokens(
        report,
        root,
        "ARCH_ADS_MANAGER_NATIVE_GATES",
        "architecture",
        "Native loads use one central helper with isEnable, purchase, network, shouldDisplay, load callback, and null fallback",
        manager_text,
        ("loadNativeInternal", "config.isEnable", "AppPurchase.getInstance().isPurchased", "isNetworkAvailable", "shouldDisplay", "loadNativeAdResultCallback", "liveData.postValue(null)"),
        "Centralize native load logic in AdsManager.loadNativeInternal with enable, purchase, network, shouldDisplay, and null fallback gates.",
        manager_path,
    )
    required_ua_methods = (
        "getShouldDisplayNativeOnboardingNormal2",
        "getShouldDisplayNativeOnboardingFull1",
        "getShouldDisplayNativeHome",
        "getShouldDisplayNativeWelcomeBack",
        "getShouldDisplayInterOnboarding",
        "getShouldDisplayInterWelcomeBack",
    )
    missing_ua = _missing_tokens(manager_text, required_ua_methods)
    hardcoded = re.findall(r"getShouldDisplay[A-Za-z0-9_]*\(\s*(?:true|false)\s*\)", manager_text)
    if missing_ua or hardcoded:
        observed = []
        if missing_ua:
            observed.append(f"missing: {', '.join(missing_ua)}")
        if hardcoded:
            observed.append(f"hard-coded UA args: {', '.join(sorted(set(hardcoded)))}")
        report.findings.append(Finding.fail(
            "ARCH_ADS_MANAGER_UA_GATES",
            "architecture",
            "mandatory getShouldDisplay* gates use the placement's config.enableUaCheck",
            "; ".join(observed),
            "Use the correct ERainAd.getShouldDisplay*(config.enableUaCheck) gate for each sensitive placement; do not hard-code true/false.",
            _location(root, manager_path),
        ))
    else:
        report.findings.append(Finding.pass_(
            "ARCH_ADS_MANAGER_UA_GATES",
            "architecture",
            "mandatory getShouldDisplay* gates use the placement's config.enableUaCheck",
            "found",
            _location(root, manager_path, "getShouldDisplay"),
        ))
    _check_tokens(
        report,
        root,
        "ARCH_ADS_MANAGER_INTER_GATES",
        "architecture",
        "Interstitial onboarding/welcome load/show uses config enable, purchase, SDK gate, getInterstitialAds, forceShowInterstitial, and onNextAction callback",
        manager_text,
        ("loadInterOnboarding", "showInterOnboarding", "loadInterWelcome", "showInterWelcome", "config.isEnable", "AppPurchase.getInstance().isPurchased", "getInterstitialAds", "forceShowInterstitial", "onNextAction"),
        "Keep interstitial load/show inside AdsManager with config, purchase, UA gate, ready check, and close/fail callback continuation.",
        manager_path,
    )
    _check_tokens(
        report,
        root,
        "ARCH_ADS_MANAGER_BANNER",
        "architecture",
        "Banner loads are centralized in AdsManager and support normal/collapsible variants with disabled fallback",
        manager_text,
        ("fun loadBanner", "adUnitConfig.isEnable", "loadCollapsibleBanner", "loadBanner", "frAds.goneView"),
        "Load banners only through AdsManager.loadBanner and preserve normal/collapsible disabled-state handling.",
        manager_path,
    )


def inspect_project(root: str | Path, contract: AuditContract, checklist: ProjectChecklist, overrides_path: str | Path | None = None) -> AuditReport:
    root = Path(root).resolve()
    report = AuditReport(str(root), contract, checklist)
    gradle_paths = [path for path in _files(root, {".gradle", ".kts"}) if path.name.startswith("build.gradle")]
    xml_paths = _files(root, {".xml"})
    manifests = [path for path in xml_paths if path.name == "AndroidManifest.xml"]
    navigation_paths = [path for path in xml_paths if "navigation" in path.relative_to(root).parts]
    source_paths = _files(root, SOURCE_SUFFIXES)
    all_text_paths = gradle_paths + manifests + _files(root, {".xml", ".kt", ".java", ".properties"})
    gradle_text = _combined_text(gradle_paths)
    manifest_text = _combined_text(manifests)
    package = _first_match(r'applicationId\s*[=(]?\s*["\']([^"\']+)', gradle_text) or _first_match(r'namespace\s*[=(]?\s*["\']([^"\']+)', gradle_text)
    _check_equal(report, "APP_PACKAGE", "identity", checklist.package_name, package, "Set `applicationId` and `namespace` to the package name in the working checklist.")
    app_id = _first_match(r'app_id\s*[:=]\s*["\'](ca-app-pub-[^"\']+)', gradle_text)
    _check_equal(report, "ADMOB_APP_ID", "identity", contract.admob_app_id, app_id, "Set the AdMob manifest placeholder to the ADS Script APP ID.")
    if "com.google.android.gms.ads.APPLICATION_ID" not in manifest_text:
        report.findings.append(Finding.fail("ADMOB_MANIFEST_META", "identity", "AdMob APPLICATION_ID meta-data", "missing", "Add the Google Mobile Ads APPLICATION_ID meta-data entry to AndroidManifest.xml."))
    else:
        report.findings.append(Finding.pass_("ADMOB_MANIFEST_META", "identity", "AdMob APPLICATION_ID meta-data", "found"))
    string_paths = [path for path in all_text_paths if path.name == "strings.xml"]
    # Android's default resource (`res/values`) is the app identity. Locale
    # files may intentionally contain translated names and must not override
    # the contract value merely because filesystem traversal lists them first.
    string_paths.sort(key=lambda path: (path.parent.name != "values", str(path)))
    app_name = None
    for string_path in string_paths:
        match = re.search(r'<string\s+name=["\']app_name["\'][^>]*>([^<]+)', _read(string_path), flags=re.MULTILINE)
        if match:
            app_name = unescape(match.group(1).strip())
            break
    _check_equal(report, "APP_NAME", "identity", checklist.app_name, app_name, "Set `app_name` to the working checklist value.")
    # The partner contract is the release configuration. Debug/test IDs are
    # intentionally not compared with ADS SCRIPTS because they are expected to
    # differ from production IDs.
    _check_config(report, root, contract, "ad_config.json", "RELEASE")
    searchable = _combined_text(all_text_paths)
    for key, value in checklist.required_values.items():
        _check_equal(report, f"TOKEN:{key}", "token", value, value if value and value in searchable else None, f"Add the configured {key} using the approved Android resource/build configuration.", redact=key in SECRET_LABELS)
    firebase_files = [path for path in _files(root, {".json"}) if path.name == "google-services.json"]
    firebase_text = _combined_text(firebase_files)
    firebase_found = _first_match(r'["\']project_id["\']\s*:\s*["\']([^"\']+)', firebase_text)
    _check_equal(report, "FIREBASE_PROJECT", "service", checklist.firebase_project, firebase_found, "Add the `google-services.json` for the Firebase project in the working checklist.")
    global_app = next((path for path in source_paths if path.name in {"GlobalApp.kt", "GlobalApp.java"}), None)
    global_text = _read(global_app) if global_app else ""
    _check_global_base_rules(report, root, global_app, global_text, gradle_text)
    for rule_id, token, fix in (
        ("ARCH_MOBILE_ADS_INIT", "MobileAds.initialize", "Initialize Mobile Ads early in the Application."),
        ("ARCH_REMOTE_CONFIG_INIT", "AdRemoteConfig.initializeFromAssets", "Initialize asset config before ad SDK setup."),
        ("ARCH_ERAIN_INIT", "ERainAd.getInstance().init", "Initialize ERainAd from the Application."),
    ):
        if token in global_text:
            report.findings.append(Finding.pass_(rule_id, "architecture", token, "found", _line_ref(root, global_app, token)))
        else:
            report.findings.append(Finding.fail(rule_id, "architecture", token, "not found in Application", fix, str(global_app.relative_to(root)) if global_app else None))
    manager_paths = [path for path in source_paths if path.name in {"AdsManager.kt", "AdsManager.java"}]
    if manager_paths:
        report.findings.append(Finding.pass_("ARCH_ADS_MANAGER", "architecture", "central AdsManager", "found", str(manager_paths[0].relative_to(root))))
    else:
        report.findings.append(Finding.fail("ARCH_ADS_MANAGER", "architecture", "central AdsManager", "not found", "Centralize placement load/show logic in AdsManager."))
    manager_text = _combined_text(manager_paths)
    _check_ads_manager_base_rules(report, root, manager_paths, manager_text)
    for rule_id, token, fix in (
        ("ARCH_ENABLE_GATE", ".isEnable", "Check `config.isEnable` before each load/show."),
        ("ARCH_PURCHASE_GATE", "AppPurchase.getInstance().isPurchased", "Skip ads for purchased users in the central manager."),
        ("ARCH_NETWORK_GATE", "isNetworkAvailable", "Skip native loading without a valid network connection."),
        ("ARCH_UA_GATE", "config.enableUaCheck", "Use the placement config's `enableUaCheck` with the mapped `getShouldDisplay*` method."),
    ):
        if token in manager_text:
            report.findings.append(Finding.pass_(rule_id, "architecture", token, "found"))
        else:
            report.findings.append(Finding.fail(rule_id, "architecture", token, "not found in AdsManager", fix))
    if "fun showInterOnboarding" in manager_text and re.search(r"showInterOnboarding[\s\S]{0,900}?&&\s*\(?\s*ignoreLimit\s*\)?", manager_text):
        report.findings.append(Finding.fail("FLOW_INTER_ONBOARDING_SHOW", "placement_flow", "normal onboarding can show its loaded interstitial", "show condition requires `ignoreLimit`", "Replace the debug-only `ignoreLimit` show condition with the normal config/UA gate; retain navigation in the close/fail callback."))
    if "fun showInterWelcome" in manager_text and re.search(r"showInterWelcome[\s\S]{0,900}?&&\s*\(?\s*ignoreLimit\s*\)?", manager_text):
        report.findings.append(Finding.fail("FLOW_INTER_WELCOME_SHOW", "placement_flow", "normal Welcome can show its loaded interstitial", "show condition requires `ignoreLimit`", "Replace the debug-only `ignoreLimit` show condition with the normal config/UA gate; retain finish/navigation in the close/fail callback."))
    if re.search(r"intervalInterstitialAd\s*=\s*35\b", global_text):
        report.findings.append(Finding.pass_("ARCH_INTERSTITIAL_INTERVAL", "architecture", "35-second interstitial interval", "found", _line_ref(root, global_app, "intervalInterstitialAd")))
    else:
        report.findings.append(Finding.fail("ARCH_INTERSTITIAL_INTERVAL", "architecture", "35-second interstitial interval", "not found", "Set `mERainAdConfig.intervalInterstitialAd = 35` unless the ADS Script explicitly approves another interval."))
    bypasses = []
    direct_sdk_tokens = ("loadNativeAd", "loadBanner", "loadCollapsibleBanner", "getInterstitialAds", "forceShowInterstitial", "showRewardAds")
    for path in source_paths:
        if path.name in {"AdsManager.kt", "AdsManager.java", "SplashActivity.kt", "SplashActivity.java", "GlobalApp.kt", "GlobalApp.java"}:
            continue
        if "Activity" in path.name and "ERainAd.getInstance()" in _read(path) and any(token in _read(path) for token in direct_sdk_tokens):
            bypasses.append(_line_ref(root, path, "ERainAd.getInstance()"))
    if bypasses:
        report.findings.append(Finding.fail("ARCH_DIRECT_SDK_BYPASS", "architecture", "SDK calls centralized in AdsManager", "; ".join(bypasses), "Move direct ad load/show calls into AdsManager unless documented as an approved exception."))
    else:
        report.findings.append(Finding.pass_("ARCH_DIRECT_SDK_BYPASS", "architecture", "no unapproved direct Activity SDK calls", "none found"))
    _check_primary_screen_activities(report, root, manifests, source_paths, navigation_paths)
    _check_screen_flow_rules(report, root, source_paths)
    overrides = _load_overrides(Path(overrides_path) if overrides_path else None)
    _check_flow(report, root, contract, source_paths, overrides)
    _check_inter_welcome_back(report, root, contract, source_paths, manager_text, global_text, overrides)
    return report


def _mkt_error(finding: Finding) -> dict[str, str]:
    if finding.rule_id == "ARCH_PRIMARY_SCREENS_ACTIVITY":
        return {
            "tieu_de": "Cấu trúc màn hình chưa đúng base",
            "mo_ta": "App đang dùng 1 Activity và nhiều Fragment cho các màn chính có quảng cáo.",
            "can_lam": "Dev chuyển Splash, Language, Onboarding, Home hoặc Welcome đang dùng Fragment thành Activity riêng theo base Infinity.",
        }
    return {
        "tieu_de": "Cần dev kiểm tra phần gắn quảng cáo",
        "mo_ta": "Có lỗi gắn quảng cáo chưa đúng base.",
        "can_lam": "Dev kiểm tra và sửa theo ads-audit-summary.md.",
    }


def _mkt_area_for_finding(finding: Finding) -> tuple[str, str, str] | None:
    rule_id = finding.rule_id
    if rule_id == "ARCH_PRIMARY_SCREENS_ACTIVITY":
        return (
            "Cấu trúc màn hình chưa đúng base",
            "App đang dùng 1 Activity/Fragment cho màn chính có quảng cáo.",
            "Dev chuyển Splash, Language, Onboarding, Home hoặc Welcome đang dùng Fragment thành Activity riêng theo base Infinity.",
        )
    if rule_id.startswith(("ARCH_GLOBAL_", "ARCH_DEV_CONFIG", "ARCH_ADS_CONFIG", "ARCH_APP_OPEN", "ARCH_MOBILE_ADS", "ARCH_REMOTE_CONFIG", "ARCH_ERAIN", "ARCH_INTERSTITIAL_INTERVAL")):
        return (
            "Khởi tạo Ads/Config chưa đúng base",
            "Sai hoặc thiếu phần init ads/config.",
            "Dev sửa GlobalApp/build.gradle theo thứ tự base: MobileAds -> DevConfig -> AdRemoteConfig -> ERainAd.",
        )
    if rule_id.startswith(("ARCH_ADS_MANAGER", "ARCH_ENABLE_GATE", "ARCH_PURCHASE_GATE", "ARCH_NETWORK_GATE", "ARCH_UA_GATE", "ARCH_DIRECT_SDK_BYPASS", "FLOW_INTER_ONBOARDING_SHOW", "FLOW_INTER_WELCOME_SHOW")):
        return (
            "AdsManager chưa đúng base",
            "Sai hoặc thiếu central load/show/gate trong AdsManager.",
            "Dev đưa load/show về AdsManager và giữ đủ isEnable, purchase, network, config.enableUaCheck, callback close/fail.",
        )
    if rule_id.startswith("ARCH_BANNER"):
        return (
            "Banner chưa đúng base",
            "Sai hoặc thiếu BaseActivityWithBanner/banner reload.",
            "Dev dùng BaseActivityWithBanner, AdsManager.loadBanner và reloadIntervalSeconds theo config.",
        )
    if rule_id.startswith("FLOW_SPLASH"):
        return (
            "Flow Splash chưa đúng base",
            "Sai hoặc thiếu luồng Splash ads.",
            "Dev giữ consent/RemoteConfig, inter_splash, preload native language ở onAdLoaded và điều hướng ở onNextAction.",
        )
    if rule_id.startswith("FLOW_LANGUAGE"):
        return (
            "Flow Language chưa đúng base",
            "Sai hoặc thiếu luồng Language ads.",
            "Dev giữ DevSetting tvTitle, load native click, preload onboarding page 1 và observe/render/hide native ads.",
        )
    if rule_id.startswith("FLOW_ONBOARDING"):
        return (
            "Flow Onboarding chưa đúng base",
            "Sai hoặc thiếu luồng Onboarding ads.",
            "Dev giữ preload native page 4/full/inter, page LiveData mapping và show inter_onboarding trước khi vào Home.",
        )
    if rule_id.startswith(("FLOW_RESUME", "FLOW_WELCOME", "FLOW_INTER_WELCOME_BACK")):
        return (
            "Flow Resume/Welcome chưa đúng base",
            "Sai hoặc thiếu luồng resume/welcome ads.",
            "Dev giữ ResumeAdsEntryRule, AppLifecycleObserver, WelcomeActivity load/show và gate AppOpen/purchase/UA.",
        )
    return None


def _mkt_detail_for_area(title: str, rule_ids: list[str], fallback_description: str, fallback_action: str) -> tuple[str, str]:
    rules = set(rule_ids)
    if title == "Khởi tạo Ads/Config chưa đúng base":
        details = []
        if rules & {"ARCH_GLOBAL_INIT_ORDER", "ARCH_MOBILE_ADS_INIT", "ARCH_DEV_CONFIG_INIT", "ARCH_REMOTE_CONFIG_INIT", "ARCH_ERAIN_INIT"}:
            details.append("Mobile Ads, DevConfig, config quảng cáo và SDK quảng cáo chưa được khởi tạo đúng thứ tự.")
        if rules & {"ARCH_DEV_CONFIG_BUILD_FIELDS"}:
            details.append("Thiếu thông tin version thư viện ads trong build.gradle nên màn DevConfig khó kiểm tra đúng.")
        if rules & {"ARCH_ADS_CONFIG_FIELDS", "ARCH_INTERSTITIAL_INTERVAL"}:
            details.append("Thiếu cấu hình tracking hoặc khoảng cách hiển thị quảng cáo inter theo base.")
        if rules & {"ARCH_APP_OPEN_EXCLUSIONS"}:
            details.append("Chưa loại trừ các màn Splash, Language, Onboarding khỏi quảng cáo mở lại app, dễ làm quảng cáo chồng lên nhau.")
        description = "\n".join(f"- {detail}" for detail in details) or fallback_description
        action = "\n".join([
            "- Trong GlobalApp, khởi tạo lần lượt: MobileAds -> DevConfig -> AdRemoteConfig -> ERainAd.",
            "- Bổ sung đủ version fields trong build.gradle và giữ interval interstitial theo base.",
            "- Tắt App Open Resume ở các màn Splash, Language, Onboarding và các màn đặc biệt theo base.",
        ])
        return description, action
    if title == "Flow Splash chưa đúng base":
        details = []
        if "FLOW_SPLASH_REMOTE_CONFIG" in rules:
            details.append("Splash chưa lấy và áp dụng cấu hình quảng cáo từ RemoteConfig đúng điểm bắt đầu app.")
        if "FLOW_SPLASH_INTER_PRELOAD_LANGUAGE" in rules:
            details.append("Native Language phải được preload ở Splash sau khi inter_splash tải thành công; audit chưa thấy đúng vị trí này.")
        if "FLOW_SPLASH_OPEN_RESUME" in rules:
            details.append("Open Resume chưa được bật/tắt theo cấu hình sau khi Splash lấy xong config.")
        description = "\n".join(f"- {detail}" for detail in details) or fallback_description
        action = "\n".join([
            "- Trong SplashActivity, lấy RemoteConfig rồi cập nhật AdRemoteConfig trước khi load quảng cáo.",
            "- Chỉ gọi preload Native Language trong callback onAdLoaded của inter_splash.",
            "- Sau khi quảng cáo đóng, lỗi hoặc bị bỏ qua, mới chuyển màn trong onNextAction.",
        ])
        return description, action
    if title == "Flow Language chưa đúng base":
        details = []
        if "FLOW_LANGUAGE_DEV_SETTING" in rules:
            details.append("Màn Language thiếu lối vào DevSetting trên tiêu đề để QA kiểm tra cấu hình ads.")
        if "FLOW_LANGUAGE_PRELOAD_AND_RENDER" in rules:
            details.append("Language chưa load quảng cáo click và preload quảng cáo cho trang Onboarding đầu tiên đúng thời điểm.")
            details.append("Phần hiển thị native Language cần lắng nghe dữ liệu quảng cáo, có ad thì render, không có ad hoặc mất mạng thì ẩn khung ads.")
        description = "\n".join(f"- {detail}" for detail in details) or fallback_description
        action = "\n".join([
            "- Trong LanguageActivity, giữ DevSetting trên tvTitle.",
            "- Sau khoảng delay ngắn, load Native Language Click và preload Native Onboarding page 1.",
            "- Khi nhận ad thì render vào container; khi null hoặc offline thì ẩn container ads.",
        ])
        return description, action
    if title == "Flow Onboarding chưa đúng base":
        details = []
        if "FLOW_ONBOARDING_PRELOAD_AND_SHOW" in rules:
            details.append("Onboarding chưa preload đủ native page 4, native fullscreen và inter_onboarding trước khi người dùng tới bước cuối.")
            details.append("Inter Onboarding phải show khi bấm Next ở trang cuối, rồi mới vào Home sau callback đóng/lỗi.")
        if "FLOW_ONBOARDING_PAGE_RENDERING" in rules:
            details.append("Các trang Onboarding chưa map đúng nguồn ad cho page 1, page 4 hoặc fullscreen.")
        description = "\n".join(f"- {detail}" for detail in details) or fallback_description
        action = "\n".join([
            "- Trong OnBoardingActivity, preload native page 4, native fullscreen và inter_onboarding sau khi màn được tạo.",
            "- Trong OnboardingPageFragment, page nào có ads thì lắng nghe đúng nguồn ad và render/ẩn theo kết quả load.",
            "- Ở trang cuối, gọi showInterOnboarding và chỉ vào Home trong callback.",
        ])
        return description, action
    if title == "AdsManager chưa đúng base":
        details = []
        if rules & {"ARCH_ADS_MANAGER_NATIVE_GATES", "ARCH_ENABLE_GATE", "ARCH_PURCHASE_GATE", "ARCH_NETWORK_GATE", "ARCH_UA_GATE", "ARCH_ADS_MANAGER_UA_GATES"}:
            details.append("AdsManager chưa giữ đủ điều kiện bật quảng cáo, trạng thái mua VIP, mạng và kiểm tra người dùng trước khi load/show.")
        if rules & {"ARCH_ADS_MANAGER_INTER_GATES", "FLOW_INTER_ONBOARDING_SHOW", "FLOW_INTER_WELCOME_SHOW"}:
            details.append("Quảng cáo inter cần đi tiếp màn hình qua callback đóng/lỗi, không được phụ thuộc vào nút test hoặc điều kiện debug.")
        if "ARCH_DIRECT_SDK_BYPASS" in rules:
            details.append("Có màn hình gọi SDK quảng cáo trực tiếp thay vì đi qua AdsManager, dễ lệch flow giữa các app.")
        if "ARCH_ADS_MANAGER_BANNER" in rules:
            details.append("Banner chưa đi qua hàm quản lý chung trong AdsManager.")
        description = "\n".join(f"- {detail}" for detail in details) or fallback_description
        action = "\n".join([
            "- Đưa toàn bộ load/show quảng cáo về AdsManager.",
            "- Trước khi load/show, kiểm tra đủ: ads đang bật, user chưa mua VIP, có mạng và điều kiện hiển thị từ config.",
            "- Với inter, chỉ chuyển màn sau callback đóng/lỗi quảng cáo.",
        ])
        return description, action
    if title == "Banner chưa đúng base":
        return (
            "- Banner cần dùng màn base có sẵn để tự load lại theo thời gian cấu hình.\n- Nếu tự load banner ở từng màn, app dễ bị lệch vị trí hiển thị hoặc reload không đúng.",
            "- Cho màn có banner kế thừa BaseActivityWithBanner.\n- Cấu hình BannerConfig và để AdsManager.loadBanner xử lý load/reload theo reloadIntervalSeconds.",
        )
    if title == "Flow Resume/Welcome chưa đúng base":
        return (
            "- App cần chọn một trong hai luồng khi mở lại app: App Open hoặc Welcome, không để hai loại quảng cáo chồng lên nhau.\n- Welcome phải load native/inter khi mở màn và chỉ đóng màn sau callback của inter.",
            "- Giữ ResumeAdsEntryRule để quyết định Open Resume hoặc Welcome.\n- Trong AppLifecycleObserver, kiểm tra màn đang mở, trạng thái mua VIP và điều kiện hiển thị trước khi vào Welcome.\n- Trong WelcomeActivity, load native/inter rồi show inter ở nút bắt đầu.",
        )
    return fallback_description, fallback_action


def _limited_list(values: list[str], label: str, limit: int = 10) -> str:
    unique = list(dict.fromkeys(value for value in values if value))
    shown = unique[:limit]
    suffix = f" và {len(unique) - len(shown)} {label} khác" if len(unique) > len(shown) else ""
    return ", ".join(shown) + suffix


def _config_key(rule_id: str, label: str) -> str | None:
    prefix = f"AD_CONFIG_{label}:"
    if not rule_id.startswith(prefix):
        return None
    key = rule_id[len(prefix):]
    if key.startswith("ENABLE:"):
        key = key[len("ENABLE:"):]
    return "file config" if key == "FILE" else key


def _group_mkt_errors(findings: list[Finding]) -> list[dict[str, str]]:
    app_field_names = {
        "APP_NAME": "app_name",
        "APP_PACKAGE": "package_name",
        "ADMOB_APP_ID": "AdMob App ID",
        "ADMOB_MANIFEST_META": "AdMob App ID",
    }
    app_findings = [finding for finding in findings if finding.status == "FAIL" and finding.rule_id in app_field_names]
    app_fields = [app_field_names[finding.rule_id] for finding in app_findings]
    grouped: list[dict[str, str]] = []
    if app_fields:
        details = "; ".join(
            f"{app_field_names[finding.rule_id]}: expected `{finding.expected}`, observed `{finding.observed}`"
            for finding in app_findings
        )
        grouped.append({
            "tieu_de": "Thông tin app chưa khớp checklist",
            "mo_ta": f"Sai hoặc thiếu: {_limited_list(app_fields, 'field')}. {details}.",
            "can_lam": "Dev đối chiếu working file và cập nhật thông tin app.",
        })
    release_keys = [
        key for finding in findings if finding.status == "FAIL"
        for key in [_config_key(finding.rule_id, "RELEASE")] if key
    ]
    if release_keys:
        grouped.append({
            "tieu_de": "Cấu hình quảng cáo release (ad_config.json) chưa đúng",
            "mo_ta": f"Key sai hoặc thiếu: {_limited_list(release_keys, 'key')}.",
            "can_lam": "Dev cập nhật key và ID trong `ad_config.json` theo file ADS SCRIPTS.",
        })
    if any(finding.status == "FAIL" and finding.category == "token" for finding in findings):
        grouped.append({
            "tieu_de": "Thiếu cấu hình dịch vụ cần thiết",
            "mo_ta": "Một hoặc nhiều cấu hình dịch vụ bắt buộc đang thiếu hoặc chưa khớp.",
            "can_lam": "Dev kiểm tra ads-audit-summary.md và cập nhật các cấu hình còn thiếu.",
        })
    grouped_areas: dict[str, dict[str, Any]] = {}
    fallback_findings: list[Finding] = []
    for finding in findings:
        if (
            finding.status != "FAIL"
            or finding.rule_id in app_field_names
            or finding.rule_id.startswith("AD_CONFIG_")
            or finding.category == "token"
        ):
            continue
        area = _mkt_area_for_finding(finding)
        if area is None:
            fallback_findings.append(finding)
            continue
        title, description, action = area
        entry = grouped_areas.setdefault(title, {
            "tieu_de": title,
            "mo_ta": description,
            "can_lam": action,
            "rules": [],
        })
        entry["rules"].append(finding.rule_id)
    for entry in grouped_areas.values():
        rules = entry.pop("rules")
        entry["mo_ta"], entry["can_lam"] = _mkt_detail_for_area(entry["tieu_de"], rules, entry["mo_ta"], entry["can_lam"])
        grouped.append(entry)
    seen = {(entry["tieu_de"], entry["mo_ta"], entry["can_lam"]) for entry in grouped}
    for finding in fallback_findings:
        entry = _mkt_error(finding)
        fingerprint = (entry["tieu_de"], entry["mo_ta"], entry["can_lam"])
        if fingerprint not in seen:
            grouped.append(entry)
            seen.add(fingerprint)
    return grouped


def _group_mkt_confirmations(findings: list[Finding]) -> list[str]:
    mapping_keys = [
        finding.rule_id.split(":", 1)[1]
        for finding in findings
        if finding.status == "NEEDS_MAPPING" and finding.rule_id.startswith("PLACEMENT_FLOW:")
    ]
    runtime_journeys = [
        finding.rule_id.split(":", 1)[1]
        for finding in findings
        if finding.status == "NEEDS_RUNTIME_PROOF" and ":" in finding.rule_id
    ]
    confirmations = []
    if mapping_keys:
        confirmations.append(f"Cần mapping placement: {_limited_list(mapping_keys, 'placement')}.")
    if runtime_journeys:
        confirmations.append(f"Cần test thực tế: {_limited_list(runtime_journeys, 'journey')}.")
    return confirmations


def build_webhook_payload(
    project_name: str,
    checklist: ProjectChecklist | list[Finding] | None = None,
    findings: list[Finding] | str | None = None,
    readiness: str | None = None,
) -> dict[str, Any]:
    if isinstance(checklist, list):
        # Backward-compatible call: build_webhook_payload(project, findings, readiness).
        if isinstance(findings, str) and readiness is None:
            readiness = findings
        findings = checklist
        checklist = None
    if findings is None:
        findings = []
    if isinstance(findings, str):
        findings = []
    counts = Counter(finding.status.lower() for finding in findings)
    status = readiness or ("BLOCKED" if counts["fail"] else "REVIEW_REQUIRED")
    if counts["fail"]:
        result = "CẦN SỬA"
    elif counts["needs_mapping"] or counts["needs_runtime_proof"]:
        result = "CẦN KỸ THUẬT XÁC NHẬN"
    else:
        result = "ĐẠT"
    errors = _group_mkt_errors(findings)
    confirmations = _group_mkt_confirmations(findings)
    return {
        "ket_qua": result,
        "ten_app": (checklist.app_name if isinstance(checklist, ProjectChecklist) else None) or project_name,
        "package_name": (checklist.package_name if isinstance(checklist, ProjectChecklist) else None) or "<chưa tìm thấy>",
        "tong_quan": {
            "loi_can_sua": counts["fail"],
            "can_ky_thuat_xac_nhan": counts["needs_mapping"] + counts["needs_runtime_proof"],
            "muc_da_kiem_tra_dung": counts["pass"],
        },
        "loi": errors,
        "can_xac_nhan": confirmations,
        "trang_thai_ky_thuat": status,
    }


def render_summary(report: AuditReport) -> str:
    counts = report.counts()
    payload = build_webhook_payload(Path(report.project_root).name, report.checklist, report.findings, report.readiness())
    lines = [
        "# Infinity Ads Compliance Audit",
        "",
        f"**Readiness:** {report.readiness()}",
        f"**Project:** `{report.project_root}`",
        f"**Contract:** `{report.contract.source}`",
        "",
        "## Summary",
        "",
        f"- FAIL: {counts.get('fail', 0)}",
        f"- NEEDS_MAPPING: {counts.get('needs_mapping', 0)}",
        f"- NEEDS_RUNTIME_PROOF: {counts.get('needs_runtime_proof', 0)}",
        f"- PASS: {counts.get('pass', 0)}",
        "",
        "## MKT short report",
        "",
        f"- Kết quả: {payload['ket_qua']}",
        f"- App: {payload['ten_app']}",
        f"- Package: `{payload['package_name']}`",
        f"- Tổng: {payload['tong_quan']['loi_can_sua']} lỗi | {payload['tong_quan']['can_ky_thuat_xac_nhan']} cần xác nhận | {payload['tong_quan']['muc_da_kiem_tra_dung']} đạt",
        "",
    ]
    if payload["loi"]:
        lines.extend(["### Lỗi cần sửa", ""])
        for index, error in enumerate(payload["loi"], start=1):
            lines.append(f"**{index}. {error['tieu_de']}**")
            lines.append("**Mô tả:**")
            lines.append(error["mo_ta"])
            lines.append("**Cách sửa:**")
            lines.append(error["can_lam"])
        lines.append("")
    if payload["can_xac_nhan"]:
        lines.extend(["### Cần xác nhận", ""])
        lines.extend(f"{index}. {item}" for index, item in enumerate(payload["can_xac_nhan"], start=1))
        lines.append("")
    lines.extend([
        "## Required actions",
        "",
    ])
    actions = [finding for finding in report.findings if finding.status != "PASS"]
    if not actions:
        lines.append("No static-rule failures. Complete all runtime proof cases before release approval.")
    config_actions = [finding for finding in actions if finding.rule_id.startswith("AD_CONFIG_")]
    for group in ("AD_CONFIG_RELEASE",):
        group_actions = [finding for finding in config_actions if finding.rule_id.startswith(group + ":") and ":ENABLE:" not in finding.rule_id]
        if group_actions:
            names = ", ".join(finding.rule_id.split(":", 1)[1] for finding in group_actions)
            lines.extend([
                f"### FAIL — `{group}` ({len(group_actions)} placements)",
                f"Keys with missing/mismatched IDs: {names}",
                "Fix: align every listed key and ID with ADS SCRIPTS; see `ads-audit-evidence.json` for exact expected/observed IDs.",
                "",
            ])
    for finding in actions:
        if finding in config_actions:
            continue
        location = f" ({finding.location})" if finding.location else ""
        lines.extend([
            f"### {finding.status} — `{finding.rule_id}`{location}",
            f"Expected: {finding.expected}",
            f"Observed: {finding.observed}",
            f"Fix: {finding.recommendation}",
            "",
        ])
    return "\n".join(lines)
