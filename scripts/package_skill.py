#!/usr/bin/env python3
"""Create a portable infinity-ads-compliance-audit zip package."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


EXCLUDED_DIRS = {"__pycache__", ".git", ".pytest_cache", "ads-audit-output"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def should_include(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    return path.suffix not in EXCLUDED_SUFFIXES


def package_skill(skill_root: str | Path, output_zip: str | Path) -> Path:
    root = Path(skill_root).resolve()
    output = Path(output_zip).resolve()
    if not (root / "SKILL.md").is_file():
        raise ValueError(f"Skill root is missing SKILL.md: {root}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and should_include(path, root):
                archive.write(path, root.name / path.relative_to(root))
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package infinity-ads-compliance-audit for partner repos.")
    parser.add_argument("--skill-root", default=Path(__file__).resolve().parents[1], help="Path to the skill directory")
    parser.add_argument("--output", default="infinity-ads-compliance-audit.zip", help="Output zip path")
    args = parser.parse_args(argv)
    output = package_skill(args.skill_root, args.output)
    print(f"Packaged: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
