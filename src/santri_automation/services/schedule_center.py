from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..scheduler import next_scheduled_run, normalize_schedule


class ScheduleCenter:
    def snapshot(
        self,
        state: dict[str, Any],
        reports: list[dict[str, Any]],
        moment: datetime | None = None,
    ) -> dict[str, Any]:
        current = moment or datetime.now()
        durations = self._durations(reports)
        queue: list[dict[str, Any]] = []
        calendar: list[dict[str, Any]] = []
        for company_key, company in state.get("companies", {}).items():
            for workflow in company.get("workflows", []):
                schedule = normalize_schedule(workflow.get("schedule"))
                next_run = next_scheduled_run(schedule, current)
                average = durations.get((company_key, workflow.get("id")), 0)
                item = {
                    "company": company_key,
                    "company_name": company.get("name", company_key.upper()),
                    "workflow_id": workflow.get("id", ""),
                    "workflow_name": workflow.get("name", ""),
                    "enabled": bool(workflow.get("enabled") and schedule["enabled"]),
                    "priority": int(schedule.get("priority", 3)),
                    "max_attempts": int(schedule.get("max_attempts", 3)),
                    "retry_failed_stage": bool(schedule.get("retry_failed_stage", True)),
                    "next_run": next_run.isoformat(timespec="minutes") if next_run else "",
                    "estimated_duration_seconds": average,
                    "estimated_finish": (
                        (next_run + timedelta(seconds=average)).isoformat(timespec="minutes")
                        if next_run else ""
                    ),
                    "exceptions": schedule.get("exceptions", []),
                }
                if item["enabled"]:
                    queue.append(item)
                calendar.extend(self._calendar_entries(item, schedule, current))
        queue.sort(key=lambda item: (item["next_run"], -item["priority"], item["company"], item["workflow_name"]))
        calendar.sort(key=lambda item: (item["date"], item["time"], -item["priority"]))
        return {
            "generated_at": current.astimezone().isoformat(timespec="seconds"),
            "queue": queue,
            "calendar": calendar,
            "summary": {
                "active": len(queue),
                "next_run": queue[0]["next_run"] if queue else "",
                "exceptions": sum(len(item["exceptions"]) for item in queue),
                "estimated_duration_seconds": sum(item["estimated_duration_seconds"] for item in queue),
            },
        }

    @staticmethod
    def _durations(reports: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
        values: dict[tuple[str, str], list[float]] = {}
        for report in reports:
            started = report.get("started_at")
            finished = report.get("finished_at")
            if not started or not finished:
                continue
            try:
                duration = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
            except (TypeError, ValueError):
                continue
            for workflow_id in report.get("workflow_ids", []):
                values.setdefault((str(report.get("company")), str(workflow_id)), []).append(max(0, duration))
        return {key: round(sum(items) / len(items)) for key, items in values.items() if items}

    @staticmethod
    def _calendar_entries(
        item: dict[str, Any],
        schedule: dict[str, Any],
        current: datetime,
    ) -> list[dict[str, Any]]:
        if not item["enabled"]:
            return []
        entries: list[dict[str, Any]] = []
        for offset in range(31):
            day = current.date() + timedelta(days=offset)
            exception = next((value for value in schedule.get("exceptions", []) if value["date"] == day.isoformat()), None)
            if exception and exception["action"] == "skip":
                continue
            day_entries = [value for value in schedule["entries"] if value["weekday"] == day.weekday()]
            if exception and exception["action"] == "run" and not day_entries:
                day_entries = [{"time": "08:00"}]
            for value in day_entries:
                entries.append({
                    **item,
                    "date": day.isoformat(),
                    "time": value["time"],
                    "exception": bool(exception),
                })
        return entries
