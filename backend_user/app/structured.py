from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any


class StructuredOutputValidationError(ValueError):
    """Provider-neutral domain validation failure with a bounded safe summary."""

    _SUPPORTED_CODES = frozenset({"day_schedule", "milestone_schedule"})

    def __init__(self, code: str, *, details: Mapping[str, Any] | None = None) -> None:
        if code not in self._SUPPORTED_CODES:
            self.code = "domain_validation_failed"
            self.details: dict[str, object] = {}
        else:
            self.code = code
            self.details = self._safe_details(code, details or {})
        super().__init__(self.safe_summary)

    @property
    def safe_summary(self) -> str:
        parts = [f"code={self.code}"]
        if self.code == "day_schedule":
            for key in ("missing", "duplicate", "unexpected", "out_of_range"):
                values = self.details.get(key)
                if values:
                    parts.append(f"{key}=" + ",".join(item.isoformat() for item in values))
            if "actual_count" in self.details:
                parts.append(f"count={self.details['actual_count']}")
            if "expected_count" in self.details:
                parts.append(f"expected={self.details['expected_count']}")
            if self.details.get("order_invalid") is True:
                parts.append("order=invalid")
        elif self.code == "milestone_schedule":
            if "actual_count" in self.details:
                parts.append(f"count={self.details['actual_count']}")
            if "expected_count" in self.details:
                parts.append(f"expected={self.details['expected_count']}")
            for week, starts_on, ends_on in self.details.get("invalid_windows", ()):
                parts.append(f"week={week} expected={starts_on.isoformat()}..{ends_on.isoformat()}")
        return "; ".join(parts)

    @classmethod
    def _safe_details(cls, code: str, details: Mapping[str, Any]) -> dict[str, object]:
        safe: dict[str, object] = {}
        for key in ("actual_count", "expected_count"):
            value = details.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1095:
                safe[key] = value
        if code == "day_schedule":
            for key in ("missing", "duplicate", "unexpected", "out_of_range"):
                dates = cls._safe_dates(details.get(key))
                if dates:
                    safe[key] = dates
            if details.get("order_invalid") is True:
                safe["order_invalid"] = True
        elif code == "milestone_schedule":
            windows: list[tuple[int, date, date]] = []
            value = details.get("invalid_windows")
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                for item in value[:53]:
                    if (
                        isinstance(item, tuple)
                        and len(item) == 3
                        and isinstance(item[0], int)
                        and not isinstance(item[0], bool)
                        and 1 <= item[0] <= 53
                        and isinstance(item[1], date)
                        and isinstance(item[2], date)
                    ):
                        windows.append(item)
            if windows:
                safe["invalid_windows"] = tuple(windows)
        return safe

    @staticmethod
    def _safe_dates(value: object) -> tuple[date, ...]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return ()
        return tuple(item for item in value[:365] if isinstance(item, date))
