"""
Exceptions — Foundry's error taxonomy.

Why this module exists: callers need to distinguish "you asked for
something that doesn't exist" (recoverable) from "the substrate has
been tampered with" (stop everything). Raw ValueErrors can't carry
that distinction.

Design trade-off: deliberately tiny. Three exceptions cover every
failure mode V1.0 has. New exception types must earn their place by
representing a genuinely different caller response.
"""


class FoundryError(Exception):
    """Base class for all Foundry errors."""


class EventNotFoundError(FoundryError):
    """A referenced event id does not exist in the log."""


class IntegrityError(FoundryError):
    """The event log's hash chain is broken: the substrate was altered."""
