"""Pure management timing evaluation for the v1.0 contract.

This module deliberately has no Flask, database, filesystem, or HTML dependency.
Fixture rules are test-only and their output is explicitly marked as such.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any


ITEM_KEY = "engine-oil"
LABEL_RECORDED = "확인된 관리 이력"
LABEL_DUE = "지금 확인할 항목"
LABEL_UNKNOWN = "이력 미확인"
LABEL_UPCOMING = "향후 관리 예정"

_APPLICABILITY_FIELDS = (
    "manufacturer",
    "model",
    "generation",
    "year",
    "engine",
    "fuel",
    "transmission",
)
_MILEAGE_LIMIT = 1_000_000


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _valid_mileage(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= _MILEAGE_LIMIT


def _valid_vehicle_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _add_months(value: date, months: int) -> date:
    """Add calendar months, clamping to the destination month's final day."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _empty_item(
    *,
    history_status: str = "unknown",
    timing_status: str = "unknown",
    labels: list[str] | None = None,
    reasons: list[str] | None = None,
    missing_fields: list[str] | None = None,
    rule: dict[str, Any] | None = None,
    is_fixture: bool = False,
) -> dict[str, Any]:
    rule = rule or {}
    return {
        "item_key": ITEM_KEY,
        "history_status": history_status,
        "timing_status": timing_status,
        "labels": labels or ([LABEL_UNKNOWN] if history_status == "unknown" else [LABEL_RECORDED]),
        "next_mileage": None,
        "next_date": None,
        "reasons": reasons or [],
        "missing_fields": missing_fields or [],
        "rule_id": rule.get("rule_id") if isinstance(rule.get("rule_id"), str) else None,
        "source": rule.get("source") if isinstance(rule.get("source"), str) else None,
        "checked_date": (
            rule.get("checked_date")
            if _parse_iso_date(rule.get("checked_date")) is not None
            else None
        ),
        "questions": [],
        "is_fixture": is_fixture,
    }


def _finish(
    item: dict[str, Any],
    *,
    timing_status: str,
    reasons: list[str],
    missing_fields: list[str],
) -> dict[str, Any]:
    item["timing_status"] = timing_status
    item["reasons"] = list(dict.fromkeys(reasons))
    item["missing_fields"] = list(dict.fromkeys(missing_fields))

    labels = [LABEL_RECORDED] if item["history_status"] == "recorded" else [LABEL_UNKNOWN]
    if timing_status == "due":
        labels.append(LABEL_DUE)
    elif timing_status == "upcoming":
        labels.append(LABEL_UPCOMING)
    item["labels"] = labels

    if timing_status == "due":
        question = "마지막 교환 기록과 운행조건을 함께 확인해 주실 수 있나요?"
    elif "vehicle.conditions" in item["missing_fields"]:
        question = "실제 운행조건을 확인해 주실 수 있나요?"
    elif "record.date" in item["missing_fields"] or "record.mileage" in item["missing_fields"]:
        question = "마지막 교환 기록의 날짜와 주행거리를 확인해 주실 수 있나요?"
    elif "vehicle.mileage" in item["missing_fields"] or "vehicle.reference_date" in item["missing_fields"]:
        question = "현재 주행거리와 측정일을 확인해 주실 수 있나요?"
    elif item["history_status"] == "unknown":
        question = "엔진 오일의 이전 교환 기록과 실제 운행조건을 확인해 주실 수 있나요?"
    else:
        question = "마지막 교환 기록과 운행조건을 함께 확인해 주실 수 있나요?"
    item["questions"] = [question]
    return item


def _history_for_vehicle(vehicle: dict[str, Any], records: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(records, (list, tuple)):
        return [], []

    vehicle_id = vehicle.get("id")
    relevant: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict) or record.get("item_key") != ITEM_KEY:
            continue
        if vehicle_id is not None and record.get("vehicle_id") != vehicle_id:
            continue
        if record.get("kind") not in ("previous_history", "maintenance_result"):
            continue
        if record.get("work_type") in ("inspection", "replacement"):
            relevant.append(record)

    replacements = [record for record in relevant if record.get("work_type") == "replacement"]
    return relevant, replacements


def _latest_replacement(
    replacements: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Return a chronology-safe replacement, or explain why none can be selected."""
    if not replacements:
        return None, [], []

    dated: list[tuple[date, dict[str, Any]]] = []
    undated: list[dict[str, Any]] = []
    reasons: list[str] = []
    missing: list[str] = []
    for record in replacements:
        parsed = _parse_iso_date(record.get("date"))
        if parsed is None:
            undated.append(record)
        else:
            dated.append((parsed, record))

    if len(replacements) > 1 and undated:
        reasons.append("교환 날짜가 없는 기록이 있어 마지막 교환 순서를 확인할 수 없습니다")
        missing.append("record.date")
        return None, reasons, missing

    if not dated:
        # A single dated-unknown replacement can still support distance-only math.
        reasons.append("교환 날짜가 확인되지 않아 기간 기준은 계산할 수 없습니다")
        missing.append("record.date")
        return undated[0], reasons, missing

    dated.sort(key=lambda pair: pair[0])
    if len(dated) > 1:
        previous_date, previous = dated[0]
        for current_date, current in dated[1:]:
            previous_mileage = previous.get("mileage")
            current_mileage = current.get("mileage")
            if (
                _valid_mileage(previous_mileage)
                and _valid_mileage(current_mileage)
                and (
                    current_mileage < previous_mileage
                    or (current_date == previous_date and current_mileage != previous_mileage)
                )
            ):
                reasons.append("교환 날짜와 주행거리 순서가 맞지 않아 계산할 수 없습니다")
                missing.append("record.date")
                missing.append("record.mileage")
                return None, reasons, missing
            previous_date, previous = current_date, current

    return dated[-1][1], reasons, missing


def _applicability(
    vehicle: dict[str, Any], rule: dict[str, Any]
) -> tuple[bool, list[str], list[str]]:
    applicability = rule.get("applicability")
    if not isinstance(applicability, dict):
        return False, ["관리 기준의 적용 사양이 없어 계산할 수 없습니다"], ["rule.applicability"]

    missing: list[str] = []
    mismatched: list[str] = []
    for field in _APPLICABILITY_FIELDS:
        expected = applicability.get("years" if field == "year" else field)
        actual = vehicle.get(field)
        if field == "year":
            if not isinstance(expected, (list, tuple)):
                missing.append("rule.applicability.years")
                continue
            if not isinstance(actual, int) or isinstance(actual, bool):
                missing.append("vehicle.year")
            elif actual not in expected:
                mismatched.append("year")
        else:
            if not isinstance(expected, str) or not expected:
                missing.append(f"rule.applicability.{field}")
            elif not isinstance(actual, str) or not actual:
                missing.append(f"vehicle.{field}")
            elif actual != expected:
                mismatched.append(field)

    if mismatched:
        detail = ", ".join(mismatched)
        return False, [f"차량 사양({detail})이 기준 적용 대상과 다릅니다"], missing
    if missing:
        return False, ["차량 사양 또는 기준 적용 범위가 확인되지 않았습니다"], missing
    return True, [], []


def evaluate_management(
    vehicle: dict[str, Any],
    records: list[dict[str, Any]],
    rule: dict[str, Any] | None,
    as_of_date: str,
) -> dict[str, Any]:
    """Evaluate the engine-oil replacement timing under a supplied rule.

    ``as_of_date`` is injected by the caller so the result is deterministic.
    The function treats user-entered records as unverified statements and never
    uses ``created_at`` to infer a maintenance date or record order.
    """
    vehicle = vehicle if isinstance(vehicle, dict) else {}
    rule = rule if isinstance(rule, dict) else None

    vehicle_id = vehicle.get("id")
    if not _valid_vehicle_id(vehicle_id):
        is_fixture = bool(
            rule
            and rule.get("rights_status") == "test_fixture"
            and rule.get("is_fixture") is True
        )
        item = _empty_item(
            history_status="unknown",
            rule=rule,
            is_fixture=is_fixture,
        )
        return _finish(
            item,
            timing_status="unknown",
            reasons=["차량 ID가 없어 해당 차량의 기록을 안전하게 구분할 수 없습니다"],
            missing_fields=["vehicle.id"],
        )

    relevant_records, replacements = _history_for_vehicle(vehicle, records)
    history_status = "recorded" if relevant_records else "unknown"

    parsed_as_of = _parse_iso_date(as_of_date)
    if parsed_as_of is None:
        item = _empty_item(
            history_status=history_status,
            rule=rule,
            is_fixture=bool(rule and rule.get("is_fixture") is True),
        )
        return _finish(
            item,
            timing_status="unknown",
            reasons=["기준일이 YYYY-MM-DD 형식이 아니어서 계산할 수 없습니다"],
            missing_fields=["as_of_date"],
        )

    if rule is None:
        item = _empty_item(history_status=history_status)
        return _finish(
            item,
            timing_status="unknown",
            reasons=["적용 가능한 관리 기준이 확인되지 않았습니다"],
            missing_fields=["rule"],
        )

    is_fixture = rule.get("rights_status") == "test_fixture" and rule.get("is_fixture") is True
    item = _empty_item(history_status=history_status, rule=rule, is_fixture=is_fixture)

    # Only an explicitly reviewed real rule or a clearly marked test fixture is usable.
    fixture_rule = is_fixture and rule.get("review_status") == "reviewed"
    verified_rule = (
        rule.get("rights_status") == "allowed"
        and rule.get("review_status") == "reviewed"
        and rule.get("is_fixture") is False
    )
    if not (fixture_rule or verified_rule):
        return _finish(
            item,
            timing_status="unknown",
            reasons=["기준의 이용 권한 또는 검토 상태가 확정되지 않아 계산하지 않았습니다"],
            missing_fields=["rule.rights_status", "rule.review_status"],
        )

    if rule.get("item_key") != ITEM_KEY or rule.get("action") != "replacement":
        return _finish(
            item,
            timing_status="unsupported",
            reasons=["현재 계산 범위는 엔진 오일 교환 한 항목입니다"],
            missing_fields=[],
        )

    supported, reasons, missing = _applicability(vehicle, rule)
    if not supported:
        mismatched = any("다릅니다" in reason for reason in reasons)
        return _finish(
            item,
            timing_status="unsupported" if mismatched else "unknown",
            reasons=reasons,
            missing_fields=missing,
        )

    vehicle_conditions = vehicle.get("conditions")
    rule_conditions = rule.get("conditions")
    if vehicle_conditions not in ("normal", "severe"):
        return _finish(
            item,
            timing_status="unknown",
            reasons=["운행조건이 확인되지 않아 기준을 선택할 수 없습니다"],
            missing_fields=["vehicle.conditions"],
        )
    if rule_conditions not in ("normal", "severe"):
        return _finish(
            item,
            timing_status="unknown",
            reasons=["관리 기준의 운행조건이 확인되지 않았습니다"],
            missing_fields=["rule.conditions"],
        )
    if vehicle_conditions != rule_conditions:
        return _finish(
            item,
            timing_status="unsupported",
            reasons=["차량 운행조건과 관리 기준의 운행조건이 다릅니다"],
            missing_fields=[],
        )

    latest, history_reasons, history_missing = _latest_replacement(replacements)
    if latest is None:
        if not replacements:
            reason = (
                "확인된 교환 기록이 없어 다음 교환 시점을 계산할 수 없습니다"
                if relevant_records
                else "관리 이력이 없어 다음 교환 시점을 계산할 수 없습니다"
            )
            missing_fields = ["record.work_type"]
            if not relevant_records:
                missing_fields = ["records"]
            return _finish(
                item,
                timing_status="unknown",
                reasons=[reason],
                missing_fields=missing_fields,
            )
        return _finish(
            item,
            timing_status="unknown",
            reasons=history_reasons,
            missing_fields=history_missing,
        )

    reasons = list(history_reasons)
    missing_fields = list(history_missing)
    due = False
    computed_axes = 0
    required_axes = 0

    interval_km = rule.get("interval_km")
    if _valid_mileage(interval_km) and interval_km > 0:
        required_axes += 1
        last_mileage = latest.get("mileage")
        if not _valid_mileage(last_mileage):
            reasons.append("마지막 교환 주행거리가 없어 거리 기준은 계산할 수 없습니다")
            missing_fields.append("record.mileage")
        elif not _valid_mileage(vehicle.get("mileage")):
            reasons.append("현재 주행거리가 없어 거리 기준은 계산할 수 없습니다")
            missing_fields.append("vehicle.mileage")
        elif _parse_iso_date(vehicle.get("reference_date")) != parsed_as_of:
            reasons.append("주행거리 측정일이 기준일과 달라 현재 주행거리로 평가할 수 없습니다")
            missing_fields.append("vehicle.reference_date")
        elif vehicle["mileage"] < last_mileage:
            reasons.append("현재 주행거리가 마지막 교환 기록보다 작아 거리 기준을 확인할 수 없습니다")
            missing_fields.append("vehicle.mileage")
        else:
            item["next_mileage"] = last_mileage + interval_km
            computed_axes += 1
            if vehicle["mileage"] >= item["next_mileage"]:
                due = True
    else:
        required_axes += 1
        reasons.append("거리 주기가 확인되지 않아 거리 기준은 계산할 수 없습니다")
        missing_fields.append("rule.interval_km")

    interval_months = rule.get("interval_months")
    if isinstance(interval_months, int) and not isinstance(interval_months, bool) and interval_months > 0:
        required_axes += 1
        last_date = _parse_iso_date(latest.get("date"))
        if last_date is None:
            if "record.date" not in missing_fields:
                reasons.append("마지막 교환일이 없어 기간 기준은 계산할 수 없습니다")
                missing_fields.append("record.date")
        elif last_date > parsed_as_of:
            reasons.append("마지막 교환일이 기준일보다 뒤라 기간 기준을 확인할 수 없습니다")
            missing_fields.append("record.date")
        else:
            next_date = _add_months(last_date, interval_months)
            item["next_date"] = next_date.isoformat()
            computed_axes += 1
            if parsed_as_of >= next_date:
                due = True
    else:
        required_axes += 1
        reasons.append("개월 주기가 확인되지 않아 기간 기준은 계산할 수 없습니다")
        missing_fields.append("rule.interval_months")

    if due:
        timing_status = "due"
        reasons.insert(0, "계산 가능한 관리 기준 중 하나에 도달했습니다")
    elif computed_axes == 0:
        timing_status = "unknown"
    elif computed_axes < required_axes:
        timing_status = "partial"
    else:
        timing_status = "upcoming"
        if is_fixture:
            reasons = ["가상 기준의 거리·기간 모두 미도달"]
        else:
            reasons = ["계산 가능한 거리·기간 기준이 모두 미도달"]

    return _finish(
        item,
        timing_status=timing_status,
        reasons=reasons,
        missing_fields=missing_fields,
    )
