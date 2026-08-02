"""
Domain layer.

Defines the core business concepts of the application: entities, value
objects, and the errors that guard their invariants. Nothing in this layer
imports from application, infrastructure, or presentation.
"""

from __future__ import annotations

from lego_db.domain.errors import DomainError, InvalidConditionError, InvalidSetNumberError
from lego_db.domain.models import LegoSet, OwnedSet, Theme
from lego_db.domain.value_objects import Condition, SetNumber

__all__ = [
    "Theme",
    "LegoSet",
    "OwnedSet",
    "SetNumber",
    "Condition",
    "DomainError",
    "InvalidSetNumberError",
    "InvalidConditionError",
]
