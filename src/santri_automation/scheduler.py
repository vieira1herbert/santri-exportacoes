from __future__ import annotations

import re
import threading
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .catalog import ExportCatalog


DAY_LABELS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


def normalize_schedule(value: Any, strict: bool = False) -> dict[str, Any]:
    if isinstance(value, str):
        return _schedule_from_text(value)
    if not isinstance(value, dict):
        return _empty_schedule()

    entries: list[dict[str, Any]] = []
    seen: set[int] = set()
    raw_entries = value.get("entries")
    if not isinstance(raw_entries, list):
        raw_entries = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            if strict:
                raise ValueError("Agendamento inválido.")
            continue
        try:
            weekday = int(raw.get("weekday"))
        except (TypeError, ValueError):
            if strict:
                raise ValueError("Dia do agendamento inválido.") from None
            continue
        time_value = str(raw.get("time") or "").strip()
        if weekday not in range(7) or not _valid_time(time_value):
            if strict:
                raise ValueError("Dia ou horário do agendamento inválido.")
            continue
        if weekday in seen:
            if strict:
                raise ValueError("Configure apenas um horário por dia.")
            continue
        seen.add(weekday)
        entries.append({"weekday": weekday, "time": time_value})

    enabled = bool(value.get("enabled"))
    if strict and enabled and not entries:
        raise ValueError("Selecione ao menos um dia e horário.")
    exceptions = _normalize_exceptions(value.get("exceptions"), strict)
    result = {
        "enabled": enabled and bool(entries),
        "entries": sorted(entries, key=lambda item: item["weekday"]),
    }
    if any(key in value for key in ("exceptions", "priority", "max_attempts", "retry_failed_stage")):
        result.update({
            "exceptions": exceptions,
            "priority": max(1, min(5, int(value.get("priority") or 3))),
            "max_attempts": max(1, min(5, int(value.get("max_attempts") or 3))),
            "retry_failed_stage": bool(value.get("retry_failed_stage", True)),
        })
    return result


def format_schedule(value: Any) -> str:
    schedule = normalize_schedule(value)
    if not schedule["enabled"]:
        return "Desligado"
    entries = schedule["entries"]
    times = {entry["time"] for entry in entries}
    weekdays = [entry["weekday"] for entry in entries]
    if len(times) == 1 and weekdays == list(range(7)):
        return f"Todos os dias · {entries[0]['time']}"
    if len(times) == 1 and weekdays == list(range(5)):
        return f"Segunda a sexta · {entries[0]['time']}"
    return " · ".join(
        f"{DAY_LABELS[entry['weekday']]} {entry['time']}"
        for entry in entries
    )


class WorkflowScheduler:
    def __init__(
        self,
        catalog: ExportCatalog,
        runner: Callable[[str, str], dict[str, Any]],
        interval_seconds: float = 20,
        now: Callable[[], datetime] = datetime.now,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.catalog = catalog
        self.runner = runner
        self.interval_seconds = interval_seconds
        self.now = now
        self.on_error = on_error or (lambda _error: None)
        self._stop_event = threading.Event()
        self._claimed: set[tuple[str, str, str, str]] = set()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._loop,
            name="santri-workflow-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def run_pending(self, moment: datetime | None = None) -> list[dict[str, Any]]:
        current = moment or self.now()
        date_key = current.strftime("%Y-%m-%d")
        time_key = current.strftime("%H:%M")
        self._claimed = {
            item for item in self._claimed if item[2] == date_key
        }
        results: list[dict[str, Any]] = []
        catalog = self.catalog.load()
        due: list[tuple[int, str, dict[str, Any], dict[str, Any], str]] = []
        for company_key, company in catalog["companies"].items():
            for workflow in company["workflows"]:
                schedule = normalize_schedule(workflow.get("schedule"))
                if (
                    not workflow.get("enabled")
                    or not workflow.get("implemented")
                    or not schedule["enabled"]
                ):
                    continue
                if _is_skipped_date(schedule, current.date()):
                    continue
                due_entry = next(
                    (
                        entry
                        for entry in schedule["entries"]
                        if entry["weekday"] == current.weekday()
                        and entry["time"] <= time_key
                    ),
                    None,
                )
                exception = next(
                    (item for item in schedule.get("exceptions", []) if item["date"] == date_key),
                    None,
                )
                if due_entry is None and exception and exception["action"] == "run":
                    due_entry = {"weekday": current.weekday(), "time": "08:00"}
                if due_entry is None:
                    continue
                slot_value = f"{date_key}T{due_entry['time']}"
                slot = (
                    company_key,
                    workflow["id"],
                    date_key,
                    due_entry["time"],
                )
                if (
                    slot in self._claimed
                    or workflow.get("last_scheduled_slot") == slot_value
                ):
                    continue
                due.append((int(schedule.get("priority", 3)), company_key, workflow, schedule, slot_value))
        for _priority, company_key, workflow, _schedule, slot_value in sorted(
            due,
            key=lambda item: (-item[0], item[4], item[1], item[2]["id"]),
        ):
            slot = (company_key, workflow["id"], date_key, slot_value[-5:])
            if slot in self._claimed or workflow.get("last_scheduled_slot") == slot_value:
                continue
            result = self.runner(company_key, workflow["id"])
            results.append(result)
            error = str(result.get("error") or "").lower()
            if result.get("ok") or "em andamento" not in error:
                self._claimed.add(slot)
                self.catalog.mark_scheduled_slot(
                    company_key,
                    workflow["id"],
                    slot_value,
                )
        return results

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_pending()
            except Exception as error:
                self.on_error(error)
            self._stop_event.wait(self.interval_seconds)


def _schedule_from_text(value: str) -> dict[str, Any]:
    text = value.strip()
    lowered = text.lower()
    time_match = re.search(r"\b([01]\d|2[0-3]):[0-5]\d\b", text)
    if not time_match or lowered == "manual":
        return _empty_schedule()
    time_value = time_match.group(0)
    weekdays = range(7) if "diariamente" in lowered else range(5)
    return {
        "enabled": True,
        "entries": [
            {"weekday": weekday, "time": time_value}
            for weekday in weekdays
        ],
        "exceptions": [],
        "priority": 3,
        "max_attempts": 3,
        "retry_failed_stage": True,
    }


def _empty_schedule() -> dict[str, Any]:
    return {
        "enabled": False,
        "entries": [],
        "exceptions": [],
        "priority": 3,
        "max_attempts": 3,
        "retry_failed_stage": True,
    }


def _normalize_exceptions(value: Any, strict: bool) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            if strict:
                raise ValueError("Exceção de agenda inválida.")
            continue
        day = str(raw.get("date") or "").strip()
        action = str(raw.get("action") or "skip").strip()
        try:
            date.fromisoformat(day)
        except ValueError:
            if strict:
                raise ValueError("Data de exceção inválida.") from None
            continue
        if action not in {"skip", "run"}:
            if strict:
                raise ValueError("Ação da exceção inválida.")
            continue
        result.append({"date": day, "action": action})
    return sorted({item["date"]: item for item in result}.values(), key=lambda item: item["date"])


def _is_skipped_date(schedule: dict[str, Any], day: date) -> bool:
    exception = next(
        (item for item in schedule.get("exceptions", []) if item["date"] == day.isoformat()),
        None,
    )
    return bool(exception and exception["action"] == "skip")


def next_scheduled_run(value: Any, moment: datetime | None = None) -> datetime | None:
    schedule = normalize_schedule(value)
    if not schedule["enabled"]:
        return None
    current = moment or datetime.now()
    for offset in range(0, 370):
        candidate_date = current.date() + timedelta(days=offset)
        exception = next(
            (item for item in schedule.get("exceptions", []) if item["date"] == candidate_date.isoformat()),
            None,
        )
        if exception and exception["action"] == "skip":
            continue
        entries = [item for item in schedule["entries"] if item["weekday"] == candidate_date.weekday()]
        if exception and exception["action"] == "run" and not entries:
            entries = [{"weekday": candidate_date.weekday(), "time": "08:00"}]
        for entry in sorted(entries, key=lambda item: item["time"]):
            hour, minute = (int(part) for part in entry["time"].split(":"))
            candidate = datetime.combine(candidate_date, datetime.min.time()).replace(hour=hour, minute=minute)
            if candidate > current:
                return candidate
    return None


def _valid_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        return False
    return bool(re.fullmatch(r"\d{2}:\d{2}", value))
