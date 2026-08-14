#!/usr/bin/env python3
"""Run the Infinity ads static audit without modifying the target project."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ads_audit_lib import Finding, build_webhook_payload, inspect_project, parse_ads_script, parse_working_file, render_summary


DEFAULT_WEBHOOK_URL = "https://discord.com/api/webhooks/1536937706842755122/SCT5zl1HOoRGL2D2EbOFKmttUN4lCCOTs8PRo9fyoe4sjliFNJEBq76QE-8XkmnLSmCO"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit an Android partner ads integration against Infinity CSV contracts.")
    parser.add_argument("--project", default=".", help="Android project root (default: current directory)")
    parser.add_argument("--ads-script", required=True, help="Path to the project ADS SCRIPTS CSV")
    parser.add_argument("--working-file", required=True, help="Path to the project working-file CSV")
    parser.add_argument("--output-dir", default="ads-audit-output", help="Directory for report files")
    parser.add_argument("--overrides", help="Optional approved ads-audit-overrides.yaml path")
    parser.add_argument("--webhook-url", help="Override the embedded HTTPS endpoint for a sanitized JSON report")
    parser.add_argument("--webhook-token", help="Optional bearer token; never written to output")
    parser.add_argument("--no-webhook", action="store_true", help="Create local reports only; do not send a webhook")
    return parser


def post_webhook(url: str, token: str | None, payload: dict, attachment_path: Path | None = None) -> str | None:
    separator = "&" if "?" in url else "?"
    wait_url = f"{url}{separator}wait=true"
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--output",
        "/dev/null",
        "--write-out",
        "%{http_code}",
        "--max-time",
        "10",
        "--request",
        "POST",
    ]
    if token:
        command.extend(["--header", f"Authorization: Bearer {token}"])
    input_bytes: bytes | None = None
    if attachment_path:
        command.extend([
            "--form",
            f"payload_json={json.dumps(payload, ensure_ascii=False)}",
            "--form",
            f"files[0]=@{attachment_path};filename={attachment_path.name}",
            wait_url,
        ])
    else:
        command.extend([
            "--header",
            "Content-Type: application/json",
            "--data-binary",
            "@-",
            wait_url,
        ])
        input_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        completed = subprocess.run(
            command,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except FileNotFoundError:
        return "curl is not installed"
    except subprocess.TimeoutExpired:
        return "curl timed out"
    if completed.returncode != 0:
        return f"curl exited with code {completed.returncode}"
    status_text = completed.stdout.decode("ascii", errors="ignore").strip()
    if not status_text.isdigit():
        return "curl returned an invalid HTTP status"
    status = int(status_text)
    return None if 200 <= status < 300 else f"HTTP {status}"


def _discord_error_block(index: int, error: dict) -> str:
    return "\n".join([
        f"**{index}. {error['tieu_de']}**",
        "**Mô tả:**",
        error["mo_ta"],
        "**Cách sửa:**",
        error["can_lam"],
    ])


def _fit_discord_block(block: str, max_length: int) -> str:
    if len(block) <= max_length:
        return block
    suffix = "\n... Chi tiết đầy đủ nằm trong file ads-audit-summary.md."
    return block[: max(0, max_length - len(suffix))].rstrip() + suffix


def discord_message_payloads(payload: dict, max_content_length: int = 2000) -> list[dict]:
    """Render the sanitized MKT payload as one or more Discord messages."""
    summary = payload["tong_quan"]
    icon = "🚨" if payload["ket_qua"] == "CẦN SỬA" else "⚠️" if payload["ket_qua"] == "CẦN KỸ THUẬT XÁC NHẬN" else "✅"
    header_lines = [
        f"{icon} **Ads Audit: {payload['ket_qua']}**",
        f"App: {payload['ten_app']}",
        f"Package: `{payload['package_name']}`",
        f"Tổng: {summary['loi_can_sua']} lỗi | {summary['can_ky_thuat_xac_nhan']} cần xác nhận | {summary['muc_da_kiem_tra_dung']} đạt",
    ]
    sections = ["\n".join(header_lines)]
    errors = payload["loi"]
    if errors:
        sections.append("**Lỗi cần sửa:**")
        for index, error in enumerate(errors, start=1):
            sections.append(_discord_error_block(index, error))
    confirmations = payload["can_xac_nhan"]
    if confirmations:
        sections.append("**Cần xác nhận:**")
        sections.extend(f"{index}. {item}" for index, item in enumerate(confirmations, start=1))
    sections.append("File ads-audit-summary.md được đính kèm bên dưới để xem chi tiết.")

    chunks: list[str] = []
    current = ""
    for section in sections:
        separator = "\n" if current else ""
        candidate = current + separator + section
        if len(candidate) <= max_content_length:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = _fit_discord_block(section, max_content_length)
    if current:
        chunks.append(current)

    if len(chunks) > 1:
        for index in range(1, len(chunks)):
            prefix = f"**Ads Audit chi tiết ({index + 1}/{len(chunks)})**\n"
            chunks[index] = prefix + _fit_discord_block(chunks[index], max_content_length - len(prefix))

    return [{"content": chunk, "allowed_mentions": {"parse": []}} for chunk in chunks]


def discord_message_payload(payload: dict) -> dict:
    """Backward-compatible first Discord message."""
    return discord_message_payloads(payload)[0]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project = Path(args.project).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        report = inspect_project(project, parse_ads_script(args.ads_script), parse_working_file(args.working_file), args.overrides)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Audit setup error: {error}", file=sys.stderr)
        return 1
    payload = build_webhook_payload(project.name, report.checklist, report.findings, report.readiness())
    summary_path = output_dir / "ads-audit-summary.md"
    evidence_path = output_dir / "ads-audit-evidence.json"
    summary_path.write_text(render_summary(report), encoding="utf-8")
    evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    webhook_url = None if args.no_webhook else (args.webhook_url or DEFAULT_WEBHOOK_URL)
    if webhook_url:
        error = None
        for index, message in enumerate(discord_message_payloads(payload)):
            error = post_webhook(
                webhook_url,
                args.webhook_token,
                message,
                attachment_path=summary_path if index == 0 else None,
            )
            if error:
                break
        if error:
            report.findings.append(Finding.needs_runtime("WEBHOOK_DELIVERY", "successful webhook delivery", error, "Check the configured Discord webhook, TLS, authorization and network, then rerun the audit."))
            payload = build_webhook_payload(project.name, report.checklist, report.findings, report.readiness())
            summary_path.write_text(render_summary(report), encoding="utf-8")
            evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Summary: {summary_path}")
    print(f"Evidence: {evidence_path}")
    return 2 if report.readiness() == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
