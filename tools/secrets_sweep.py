#!/usr/bin/env python
"""# QA: offline secrets sweep – no values are printed."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
QA_DIR = REPO_ROOT / "qa"
REPORT_PATH = QA_DIR / "SECRETS_REPORT.md"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "frontend/.next",
    ".next",
    "qa",
    "htmlcov",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "docker",
    "data",
}

EXCLUDE_FILES = {
    ".env",
    ".env.local",
    "backend/.env",
    "backend/.env.local",
    "backend/.env.production",
    "backend/.env.staging",
    "frontend/.env",
    "frontend/.env.local",
}

URI_CREDENTIAL_PATTERN = re.compile(
    r"(?P<scheme>[a-zA-Z][\w+.-]*://)(?P<user>[^:\s]+):(?P<pw>[^@\s]+)@(?P<host>[^/\s\"']+)"
)
ENV_SECRET_PATTERN = re.compile(
    r"\b(?P<key>(?:JWT_SECRET|JWT_ALGORITHM|VAPID_(?:PUBLIC|PRIVATE)_KEY|SUPABASE_(?:ANON_KEY|SERVICE_ROLE)|SERVICE_ROLE_KEY|API_KEY|SECRET_KEY))\s*=\s*(?P<value>.+)"
)
JSON_KEY_PATTERN = re.compile(
    r"\"(?P<key>p256dh|auth)\"\s*[:=]\s*\"(?P<value>[A-Za-z0-9_\-+/=]{16,})\""
)

PATTERNS = (
    ("credential-uri", URI_CREDENTIAL_PATTERN),
    ("env-secret", ENV_SECRET_PATTERN),
    ("json-key", JSON_KEY_PATTERN),
)


@dataclass
class Finding:
    line: int
    category: str
    message: str


def should_skip(path: Path) -> bool:
    relative = path.relative_to(REPO_ROOT).as_posix()
    if relative in EXCLUDE_FILES:
        return True
    for part in path.relative_to(REPO_ROOT).parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


def iter_repository_files() -> Iterable[Path]:
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        yield path


def mask_uri(match: re.Match[str]) -> str:
    user = match.group("user")
    host = match.group("host")
    return f"{user}:****@{host}"


def mask_env(match: re.Match[str]) -> str:
    key = match.group("key")
    return f"{key}=<hidden>"


def mask_json(match: re.Match[str]) -> str:
    key = match.group("key")
    return f"{key}:<hidden>"


MASKERS = {
    "credential-uri": mask_uri,
    "env-secret": mask_env,
    "json-key": mask_json,
}


def scan_file(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    findings: list[Finding] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for category, pattern in PATTERNS:
            for match in pattern.finditer(line):
                masker = MASKERS[category]
                message = masker(match)
                findings.append(Finding(line=idx, category=category, message=message))
    return findings


def ensure_report_directory() -> None:
    QA_DIR.mkdir(exist_ok=True)


def write_report(findings_map: dict[str, list[Finding]], scanned_files: int) -> None:
    ensure_report_directory()
    lines: list[str] = ["# QA: offline secrets sweep – no values are printed.", ""]
    lines.append(f"- Generated: {datetime.now(UTC).isoformat()}")
    lines.append(f"- Files scanned: {scanned_files}")
    total_findings = sum(len(entries) for entries in findings_map.values())
    lines.append(f"- Findings: {total_findings}")
    lines.append("")

    if total_findings == 0:
        lines.append("No potential secrets detected. 🎉")
    else:
        for relative, entries in sorted(findings_map.items()):
            lines.append(f"## {relative}")
            for entry in entries:
                lines.append(
                    f"- L{entry.line}: {entry.category} → {entry.message}"
                )
            lines.append("")

    REPORT_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")



def main() -> None:
    findings_map: dict[str, list[Finding]] = defaultdict(list)
    scanned = 0

    for file_path in iter_repository_files():
        scanned += 1
        findings = scan_file(file_path)
        if findings:
            relative = file_path.relative_to(REPO_ROOT).as_posix()
            findings_map[relative].extend(findings)

    write_report(findings_map, scanned)


if __name__ == "__main__":
    main()
