from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class ExecutionObservability:
    TECHNICAL_STEPS = frozenset({"session", "workflow", "automation", "evidence"})
    TERMINAL_STATUSES = frozenset({"success", "error", "skipped"})

    def snapshot(
        self,
        reports: list[dict[str, Any]],
        current: datetime,
        days: int = 30,
    ) -> dict[str, Any]:
        recent = self._recent_reports(reports, current, days)
        return {
            "period_days": days,
            "step_performance": self._step_performance(recent),
            "recurring_failures": self._recurring_failures(recent),
            "recent_artifacts": self._recent_artifacts(recent),
        }

    def _step_performance(
        self,
        reports: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str, str], dict[str, Any]] = {}
        for report in reports:
            company = str(report.get("company") or "")
            workflow_id = self._workflow_id(report)
            for step, events in self._step_events(report).items():
                key = (company, workflow_id, step)
                group = groups.setdefault(
                    key,
                    {
                        "company": company,
                        "workflow_id": workflow_id,
                        "step": step,
                        "executions": 0,
                        "successes": 0,
                        "failures": 0,
                        "retries": 0,
                        "durations": [],
                    },
                )
                group["executions"] += 1
                terminal = next(
                    (
                        event
                        for event in reversed(events)
                        if event.get("status") in self.TERMINAL_STATUSES
                    ),
                    {},
                )
                group["successes"] += terminal.get("status") in {"success", "skipped"}
                group["failures"] += terminal.get("status") == "error"
                group["retries"] += sum(
                    event.get("status") == "retry" for event in events
                )
                duration = self._event_duration(events)
                if duration is not None:
                    group["durations"].append(duration)
        values = []
        for group in groups.values():
            executions = int(group["executions"])
            durations = group.pop("durations")
            group["success_rate"] = (
                round(int(group["successes"]) * 100 / executions) if executions else 0
            )
            group["average_duration_seconds"] = (
                round(sum(durations) / len(durations)) if durations else 0
            )
            values.append(group)
        values.sort(
            key=lambda item: (
                -int(item["failures"]),
                -int(item["retries"]),
                -int(item["executions"]),
                str(item["step"]),
            )
        )
        return values[:12]

    def _recurring_failures(
        self,
        reports: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for report in reports:
            company = str(report.get("company") or "")
            workflow_id = self._workflow_id(report)
            errors = [
                event
                for event in report.get("timeline", [])
                if event.get("status") == "error"
            ]
            operational_errors = [
                event
                for event in errors
                if str(event.get("step") or "") not in self.TECHNICAL_STEPS
            ]
            for event in operational_errors or errors:
                step = str(event.get("step") or "Execução")
                message = str(event.get("message") or report.get("error") or "Falha")
                signature = self._failure_signature(message)
                key = (company, workflow_id, step, signature)
                timestamp = str(
                    event.get("timestamp") or report.get("finished_at") or ""
                )
                group = groups.setdefault(
                    key,
                    {
                        "company": company,
                        "workflow_id": workflow_id,
                        "step": step,
                        "message": message[:180],
                        "count": 0,
                        "last_seen": timestamp,
                    },
                )
                group["count"] += 1
                if timestamp > str(group["last_seen"]):
                    group["last_seen"] = timestamp
                    group["message"] = message[:180]
        values = list(groups.values())
        values.sort(
            key=lambda item: (int(item["count"]), str(item["last_seen"])),
            reverse=True,
        )
        return values[:8]

    def _recent_artifacts(
        self,
        reports: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for report in reports:
            manifest = {
                str(item.get("path") or ""): item
                for item in report.get("artifact_manifest", [])
                if isinstance(item, dict)
            }
            for value in report.get("artifacts", []):
                path = str(value or "")
                if not path:
                    continue
                evidence = manifest.get(path, {})
                values.append(
                    {
                        "company": str(report.get("company") or ""),
                        "workflow_id": self._workflow_id(report),
                        "name": str(evidence.get("name") or Path(path).name),
                        "path": path,
                        "size": int(evidence.get("size") or 0),
                        "sha256": str(evidence.get("sha256") or ""),
                        "finished_at": str(report.get("finished_at") or ""),
                    }
                )
        values.sort(key=lambda item: str(item["finished_at"]), reverse=True)
        return values[:10]

    def _step_events(
        self,
        report: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for event in report.get("timeline", []):
            step = str(event.get("step") or "").strip()
            if not step or step in self.TECHNICAL_STEPS:
                continue
            result.setdefault(step, []).append(event)
        return result

    @classmethod
    def _event_duration(cls, events: list[dict[str, Any]]) -> int | None:
        timestamps = [
            parsed
            for event in events
            if (parsed := cls._date(event.get("timestamp"))) is not None
        ]
        if len(timestamps) < 2:
            return None
        return max(0, round((max(timestamps) - min(timestamps)).total_seconds()))

    @classmethod
    def _recent_reports(
        cls,
        reports: list[dict[str, Any]],
        current: datetime,
        days: int,
    ) -> list[dict[str, Any]]:
        threshold = current - timedelta(days=days)
        return [
            report
            for report in reports
            if (finished := cls._date(report.get("finished_at"))) is not None
            and finished >= threshold
        ]

    @staticmethod
    def _workflow_id(report: dict[str, Any]) -> str:
        values = report.get("workflow_ids", [])
        return str(values[0]) if values else ""

    @staticmethod
    def _failure_signature(message: str) -> str:
        normalized = message.casefold()
        normalized = re.sub(r"[a-z]:\\[^\s]+", "<path>", normalized)
        normalized = re.sub(r"\b\d+\b", "<n>", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized[:180]

    @staticmethod
    def _date(value: Any) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(str(value))
            return parsed if parsed.tzinfo else parsed.astimezone()
        except (TypeError, ValueError):
            return None
