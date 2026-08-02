"""
Domain-level exceptions.

These represent invariant violations of the domain model itself and must
stay independent of persistence, UI, or any other outer-layer concern.
Only exceptions that are actually raised by the domain live here; keeping
this file free of "just in case" entries is itself part of keeping the
domain model honest about the states it can actually be in.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain exceptions."""


class InvalidSetNumberError(DomainError):
    """Raised when a set number does not conform to the catalog format."""

    def __init__(self, raw_value: str) -> None:
        super().__init__(f"invalid set number: {raw_value!r}")
        self.raw_value = raw_value


class InvalidConditionError(DomainError):
    """Raised when a condition code outside {0, 1, 2} is used."""

    def __init__(self, raw_value: object) -> None:
        super().__init__(f"invalid condition: {raw_value!r}")
        self.raw_value = raw_value
