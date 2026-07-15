#!/usr/bin/env bash
# One command: venv, install, test, validate, transcript. < 5 minutes.
#   ./validate.sh                          -> mocks (architecture exercise)
#   ANTHROPIC_API_KEY=... ./validate.sh    -> real-model V1.0 validation
#   ./validate.sh mynotes.md export.json   -> validate over your documents
set -euo pipefail
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -e ".[dev,web]" -q
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then pip install anthropic -q; fi
if [ -n "${OPENAI_API_KEY:-}" ]; then pip install openai -q; fi
python -m pytest tests -q
python scripts/validate.py "$@"
echo
echo "Transcript: v1_transcript.md"
