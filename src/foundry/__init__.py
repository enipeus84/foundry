"""
Foundry — durable, model-independent, fully provenanced memory.

Public API. Everything importable from here is stable within a major
version; internals (underscore-prefixed) are not.

    from foundry import EventLog, Kernel, Canon
    from foundry.models import MockModelAlpha, AnthropicAdapter
    from foundry.ingestors import ingest_file
"""

from .canon import Canon, Claim
from .errors import EventNotFoundError, FoundryError, IntegrityError
from .eventlog import EventLog
from .kernel import Kernel

__version__ = "1.5.1"
__all__ = [
    "Canon", "Claim", "EventLog", "Kernel",
    "FoundryError", "EventNotFoundError", "IntegrityError",
    "__version__",
]
