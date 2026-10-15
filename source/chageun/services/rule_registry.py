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


def candidate_rules_for(vehicle: dict[str, Any]) -> list[dict[str, Any]]:
    """Return exact vehicle/condition candidates, without approving them.

    ``evaluate_management`` is still responsible for enforcing rights and review
    gates. A missing, incomplete, or unmatched specification produces no rule.
    """
    if not isinstance(vehicle, dict):
        return []

    try:
        registry = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    rules = registry.get("rules") if isinstance(registry, dict) else None
    if not isinstance(rules, list):
        return []

    matches: list[dict[str, Any]] = []
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
        rule_conditions = rule.get("conditions")
        if rule_conditions not in ("any", vehicle.get("conditions")):
            continue
        if rule_conditions == "severe" and "severe_condition_codes" in rule:
            required_codes = rule.get("severe_condition_codes")
            selected_codes = vehicle.get("severe_condition_codes")
            if (
                not isinstance(required_codes, list)
                or not required_codes
                or any(
                    not isinstance(code, int) or isinstance(code, bool) or not 1 <= code <= 12
                    for code in required_codes
                )
            ):
                continue
            selected_codes = {
                code for code in selected_codes
                if isinstance(code, int) and not isinstance(code, bool) and 1 <= code <= 12
            } if isinstance(selected_codes, (list, tuple, set)) else set()
            if not selected_codes.intersection(required_codes):
                continue
        matches.append(rule)

    return matches


def candidate_rule_for(vehicle: dict[str, Any]) -> dict[str, Any] | None:
    """Compatibility helper returning the first candidate, if any."""
    matches = candidate_rules_for(vehicle)
    return matches[0] if matches else None
