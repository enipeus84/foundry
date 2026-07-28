"""Report the structural and completion state of security documentation.

Missing files fail structural validation. Placeholder or in-progress
documents remain valid repository structure and are reported without
failing the command.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

REQUIRED_SECURITY_DOCUMENTS = (
    Path("SECURITY.md"),
    Path("docs/security/README.md"),
    Path("docs/security/threat-model.md"),
    Path("docs/security/security-assurance.md"),
    Path("docs/security/security-checklist.md"),
)

MISSING = "Missing"
EMPTY_PLACEHOLDER = "Empty placeholder"
PRESENT = "Present"
COMPLETE = "Complete"

_TODO = re.compile(r"\b(?:TODO|TBD|PLACEHOLDER)\b", re.IGNORECASE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class DocumentStatus:
    path: Path
    status: str


def classify_document(path: Path) -> str:
    """Classify one required document without treating TODOs as failure."""
    if not path.exists():
        return MISSING

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return EMPTY_PLACEHOLDER

    without_comments = _HTML_COMMENT.sub("", text)
    meaningful_lines = []
    for line in without_comments.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            continue
        if _TODO.fullmatch(stripped.rstrip(".:;- ")):
            continue
        meaningful_lines.append(stripped)

    if not meaningful_lines:
        return EMPTY_PLACEHOLDER
    if _TODO.search(text):
        return PRESENT
    return COMPLETE


def inspect_security_documents(root: Path) -> list[DocumentStatus]:
    return [
        DocumentStatus(relative, classify_document(root / relative))
        for relative in REQUIRED_SECURITY_DOCUMENTS
    ]


def print_report(statuses: list[DocumentStatus]) -> None:
    print("Security documentation")
    for item in statuses:
        print(f"  {item.status:<17} {item.path}")

    structure_complete = all(item.status != MISSING for item in statuses)
    documentation_complete = all(item.status == COMPLETE for item in statuses)
    print()
    print(
        "Repository structure: "
        + ("COMPLETE" if structure_complete else "INCOMPLETE")
    )
    print(
        "Documentation: "
        + ("COMPLETE" if documentation_complete else "IN PROGRESS")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args()
    statuses = inspect_security_documents(args.root.resolve())
    print_report(statuses)
    return 1 if any(item.status == MISSING for item in statuses) else 0


if __name__ == "__main__":
    raise SystemExit(main())
