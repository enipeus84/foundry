"""Render the authenticated Flight Deck to a static visual-QA fixture.

This does not add a bypass to the application. It uses the same signed-session
test-client path as the web test suite, renders existing synthetic demo events,
and copies only public static assets beside the HTML output.
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    data_dir = Path(tempfile.mkdtemp(prefix="foundry-flight-deck-review-"))
    data_path = data_dir / "events.jsonl"
    os.environ.update({
        "FOUNDRY_DATA_PATH": str(data_path),
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "synthetic-review-key",
        "FOUNDRY_ALLOWED_EMAIL": "synthetic-review@example.com",
        "SESSION_SECRET": "synthetic-review-secret-0123456789abcdef",
        "APP_BASE_URL": "http://testserver",
    })

    from fastapi.testclient import TestClient

    from foundry import webauth
    from foundry.demo_data import build
    from foundry.eventlog import EventLog
    from foundry.web import app

    build(EventLog(data_path), as_of=1784577600.0)
    client = TestClient(app)
    client.cookies.set(
        webauth.SESSION_COOKIE,
        webauth.session_token("synthetic-review@example.com", webauth.load_config()),
    )
    response = client.get("/")
    response.raise_for_status()

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "index.html").write_bytes(response.content)
    source_static = Path(__file__).resolve().parents[1] / "src" / "foundry" / "static"
    destination_static = args.output / "static"
    destination_static.mkdir(exist_ok=True)
    for name in ("earthrise.webp", "flight-deck.js"):
        shutil.copy2(source_static / name, destination_static / name)

    print(f"rendered {len(response.content)} byte HTML fixture -> {args.output}")


if __name__ == "__main__":
    main()
