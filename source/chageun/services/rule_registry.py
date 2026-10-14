"""Resolve source-checked candidate rules without activating unapproved data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_REGISTRY_PATH = Path(__file__).with_name("candidate_rules.json")
_APPLICABILITY_FIELDS = (
    "manufacturer",
    "model",
    "generation",
    "engine",
    "fuel",
    "transmission",
)


def candidate_rule_for(vehicle: dict[str, Any]) -> dict[str, Any] | None:
    """Return a candidate for an exact vehicle/condition match, never approve it.

    ``evaluate_management`` is still responsible for enforcing rights and review
    gates. A missing, incomplete, or unmatched specification produces no rule.
    """
    if not isinstance(vehicle, dict):
        return None

    try:
        registry = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    rules = registry.get("rules") if isinstance(registry, dict) else None
    if not isinstance(rules, list):
        return None

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        applicability = rule.get("applicability")
        if not isinstance(applicability, dict):
            continue
        years = applicability.get("years")
        if not isinstance(years, list) or vehicle.get("year") not in years:
            continue
        if any(
            not isinstance(vehicle.get(field), str)
            or vehicle[field] != applicability.get(field)
            for field in _APPLICABILITY_FIELDS
        ):
            continue
        if vehicle.get("conditions") != rule.get("conditions"):
            continue
        return rule

    return None
