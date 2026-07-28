"""Documentation tests are named for the repository claims they defend."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from scripts.validate_security_docs import (
    COMPLETE,
    EMPTY_PLACEHOLDER,
    MISSING,
    PRESENT,
    REQUIRED_SECURITY_DOCUMENTS,
    classify_document,
)

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def test_required_security_document_structure_exists():
    statuses = {
        path: classify_document(ROOT / path)
        for path in REQUIRED_SECURITY_DOCUMENTS
    }
    assert MISSING not in statuses.values(), statuses


def test_placeholders_are_reported_without_being_structural_failures(tmp_path):
    missing = tmp_path / "missing.md"
    empty = tmp_path / "empty.md"
    placeholder = tmp_path / "placeholder.md"
    in_progress = tmp_path / "in-progress.md"
    complete = tmp_path / "complete.md"

    empty.write_text("", encoding="utf-8")
    placeholder.write_text("# Heading\n\nTODO\n", encoding="utf-8")
    in_progress.write_text(
        "# Heading\n\nCurrent factual content.\n\nTODO: finish review.\n",
        encoding="utf-8",
    )
    complete.write_text("# Heading\n\nCurrent factual content.\n", encoding="utf-8")

    assert classify_document(missing) == MISSING
    assert classify_document(empty) == EMPTY_PLACEHOLDER
    assert classify_document(placeholder) == EMPTY_PLACEHOLDER
    assert classify_document(in_progress) == PRESENT
    assert classify_document(complete) == COMPLETE


def test_relative_markdown_links_resolve():
    markdown_files = list(ROOT.glob("*.md")) + list((ROOT / "docs").rglob("*.md"))
    failures: list[str] = []

    for document in markdown_files:
        if ROOT / "docs" / "history" in document.parents:
            continue
        text = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().strip("<>")
            if (
                not target
                or target.startswith("#")
                or "://" in target
                or target.startswith("mailto:")
            ):
                continue
            path_part = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not path_part:
                continue
            resolved = (document.parent / path_part).resolve()
            if not resolved.exists():
                failures.append(
                    f"{document.relative_to(ROOT)} -> {raw_target}"
                )

    assert not failures, "Broken relative Markdown links:\n" + "\n".join(failures)


def test_engineering_review_gates_require_the_security_checklist():
    review_gates = (ROOT / "docs/engineering/review-gates.md").read_text(
        encoding="utf-8"
    )
    assert "security-checklist.md" in review_gates
