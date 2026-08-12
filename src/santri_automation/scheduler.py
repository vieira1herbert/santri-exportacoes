from __future__ import annotations

import re
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .catalog import ExportCatalog


DAY_LABELS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


def normalize_schedule(value: Any, strict: bool = False) -> dict[str, Any]:
    if isinstance(value, str):
        return _schedule_from_text(value)
    if not isinstance(value, dict):
        return {"enabled": False, "entries": []}

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
    return {
        "enabled": enabled and bool(entries),
        "entries": sorted(entries, key=lambda item: item["weekday"]),
    }


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
        for company_key, company in catalog["companies"].items():
            for workflow in company["workflows"]:
                schedule = normalize_schedule(workflow.get("schedule"))
                if (
                    not workflow.get("enabled")
                    or not workflow.get("implemented")
                    or not schedule["enabled"]
                ):
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
        return {"enabled": False, "entries": []}
    time_value = time_match.group(0)
    weekdays = range(7) if "diariamente" in lowered else range(5)
    return {
        "enabled": True,
        "entries": [
            {"weekday": weekday, "time": time_value}
            for weekday in weekdays
        ],
    }


def _valid_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        return False
    return bool(re.fullmatch(r"\d{2}:\d{2}", value))
