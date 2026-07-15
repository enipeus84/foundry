import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from foundry.eventlog import EventLog
from foundry.kernel import Kernel
from foundry.models import MockModelAlpha


@pytest.fixture
def kernel(tmp_path):
    return Kernel(EventLog(tmp_path / "events.jsonl"), MockModelAlpha())
