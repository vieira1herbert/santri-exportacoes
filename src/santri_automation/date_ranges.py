from __future__ import annotations

from datetime import date
from typing import Any

AUTOMATIC_MODE = "previous_month_to_today"
CUSTOM_MODE = "custom"


def normalize_date_range(value: Any) -> dict[str, str]:
    if value is None:
        return {"mode": AUTOMATIC_MODE}
    if not isinstance(value, dict):
        raise ValueError("Período do relatório inválido.")
    mode = str(value.get("mode") or AUTOMATIC_MODE).strip().lower()
    if mode in {"automatic", AUTOMATIC_MODE}:
        return {"mode": AUTOMATIC_MODE}
    if mode != CUSTOM_MODE:
        raise ValueError("Modo do período do relatório inválido.")
    start = str(value.get("start") or "").strip()
    end = str(value.get("end") or "").strip()
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError as error:
        raise ValueError("Informe as datas inicial e final do relatório.") from error
    if start_date > end_date:
        raise ValueError("A data inicial não pode ser posterior à data final.")
    return {"mode": CUSTOM_MODE, "start": start, "end": end}


def resolve_date_range(
    value: Any,
    today: date | None = None,
) -> tuple[date, date]:
    normalized = normalize_date_range(value)
    current = today or date.today()
    if normalized["mode"] == CUSTOM_MODE:
        return (
            date.fromisoformat(normalized["start"]),
            date.fromisoformat(normalized["end"]),
        )
    if current.month == 1:
        start = date(current.year - 1, 12, 1)
    else:
        start = date(current.year, current.month - 1, 1)
    return start, current
