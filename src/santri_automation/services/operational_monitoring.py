from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from ..scheduler import normalize_schedule


class OperationalMonitoring:
    def __init__(
        self,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.now = now or (lambda: datetime.now().astimezone())

    def snapshot(
        self,
        state: dict[str, Any],
        reports: list[dict[str, Any]],
        health: dict[str, Any],
        security: dict[str, Any],
    ) -> dict[str, Any]:
        current = self.now()
        completed = [
            report
            for report in reports
            if report.get("status") in {"success", "failed"}
        ]
        recent = self._within(completed, current, 30)
        alerts = self._alerts(state, health, security, current)
        companies = {
            key: self._company_snapshot(
                key,
                company,
                completed,
                health.get("companies", {}).get(key, {}),
                current,
            )
            for key, company in state.get("companies", {}).items()
        }
        success = sum(item.get("status") == "success" for item in recent)
        durations = [
            duration
            for item in recent
            if (duration := self._duration(item)) is not None
        ]
        status = (
            "critical"
            if any(item["level"] == "error" for item in alerts)
            else "attention"
            if alerts
            else "healthy"
        )
        return {
            "generated_at": current.isoformat(timespec="seconds"),
            "status": status,
            "overview": {
                "executions_30d": len(recent),
                "success_rate_30d": self._percentage(success, len(recent)),
                "average_duration_seconds": self._average(durations),
                "alerts": len(alerts),
                "companies_ready": sum(
                    company.get("ready") is True
                    for company in health.get("companies", {}).values()
                ),
                "companies_total": len(state.get("companies", {})),
            },
            "runtime": health.get("runtime", {}),
            "trend": self._trend(completed, current, 14),
            "companies": companies,
            "alerts": alerts,
        }

    def technical_summary(
        self,
        monitoring: dict[str, Any],
        health: dict[str, Any],
        security: dict[str, Any],
    ) -> str:
        overview = monitoring["overview"]
        runtime = monitoring.get("runtime", {})
        lines = [
            "SANTRI EXPORTAÇÕES · RESUMO OPERACIONAL",
            f"Gerado em: {monitoring['generated_at']}",
            f"Estado geral: {monitoring['status'].upper()}",
            f"Empresas disponíveis: {overview['companies_ready']}/{overview['companies_total']}",
            f"Execuções em 30 dias: {overview['executions_30d']}",
            f"Taxa de sucesso em 30 dias: {overview['success_rate_30d']}%",
            f"Duração média: {self.duration_label(overview['average_duration_seconds'])}",
            f"Sessão Windows: {'desbloqueada' if runtime.get('session_unlocked') else 'indisponível ou bloqueada'}",
            f"Integridade corporativa: {'verificada' if security.get('ready') else 'requer atenção'}",
            f"Saúde do ambiente: {'pronta' if health.get('ready') else 'requer atenção'}",
            "",
            "EMPRESAS",
        ]
        for key, company in monitoring.get("companies", {}).items():
            lines.append(
                f"{key.upper()}: {company['success_rate_30d']}% de sucesso, "
                f"{company['executions_30d']} execuções, "
                f"média {self.duration_label(company['average_duration_seconds'])}"
            )
        lines.extend(["", "ALERTAS"])
        if monitoring.get("alerts"):
            lines.extend(
                f"[{item['level'].upper()}] {item['title']}: {item['message']}"
                for item in monitoring["alerts"]
            )
        else:
            lines.append("Nenhum alerta operacional ativo.")
        return "\n".join(lines)

    def _company_snapshot(
        self,
        company_key: str,
        company: dict[str, Any],
        reports: list[dict[str, Any]],
        health: dict[str, Any],
        current: datetime,
    ) -> dict[str, Any]:
        company_reports = [
            item for item in reports if item.get("company") == company_key
        ]
        recent = self._within(company_reports, current, 30)
        success = sum(item.get("status") == "success" for item in recent)
        durations = [
            duration
            for item in recent
            if (duration := self._duration(item)) is not None
        ]
        return {
            "ready": health.get("ready") is True,
            "executions_30d": len(recent),
            "success_rate_30d": self._percentage(success, len(recent)),
            "average_duration_seconds": self._average(durations),
            "last_execution": self._report_summary(company_reports[0])
            if company_reports
            else None,
            "workflows": [
                self._workflow_snapshot(workflow, recent)
                for workflow in company.get("workflows", [])
                if workflow.get("implemented")
            ],
        }

    def _workflow_snapshot(
        self,
        workflow: dict[str, Any],
        reports: list[dict[str, Any]],
    ) -> dict[str, Any]:
        relevant = [
            report
            for report in reports
            if workflow.get("id") in report.get("workflow_ids", [])
        ]
        success = sum(item.get("status") == "success" for item in relevant)
        durations = [
            duration
            for item in relevant
            if (duration := self._duration(item)) is not None
        ]
        last = relevant[0] if relevant else None
        return {
            "id": str(workflow.get("id") or ""),
            "name": str(workflow.get("name") or ""),
            "schedule_enabled": normalize_schedule(
                workflow.get("schedule")
            )["enabled"],
            "executions_30d": len(relevant),
            "success_rate_30d": self._percentage(success, len(relevant)),
            "average_duration_seconds": self._average(durations),
            "last_status": str(last.get("status") or "") if last else "never",
            "last_finished_at": str(last.get("finished_at") or "") if last else "",
        }

    def _alerts(
        self,
        state: dict[str, Any],
        health: dict[str, Any],
        security: dict[str, Any],
        current: datetime,
    ) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []
        runtime = health.get("runtime", {})
        if runtime.get("session_unlocked") is not True:
            alerts.append(
                self._alert(
                    "error",
                    "Sessão Windows indisponível",
                    "A sessão precisa permanecer aberta e desbloqueada para a automação visual.",
                    "windows_session",
                )
            )
        if security.get("ready") is not True:
            alerts.append(
                self._alert(
                    "error",
                    "Proteção corporativa requer atenção",
                    "A integridade da configuração, auditoria ou release não foi confirmada.",
                    "security",
                )
            )
        for key, company in health.get("companies", {}).items():
            if company.get("ready") is not True:
                alerts.append(
                    self._alert(
                        "error",
                        f"Ambiente {key.upper()} indisponível",
                        "Verifique o atalho do Santri e os destinos configurados.",
                        f"company:{key}",
                    )
                )
        alerts.extend(self._missed_schedule_alerts(state, current))
        return alerts

    def _missed_schedule_alerts(
        self,
        state: dict[str, Any],
        current: datetime,
    ) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []
        history = state.get("history", [])
        for company_key, company in state.get("companies", {}).items():
            for workflow in company.get("workflows", []):
                schedule = normalize_schedule(workflow.get("schedule"))
                if not workflow.get("enabled") or not workflow.get("implemented") or not schedule["enabled"]:
                    continue
                due = self._latest_due(schedule["entries"], current)
                if due is None or current - due < timedelta(minutes=30):
                    continue
                slot = due.strftime("%Y-%m-%dT%H:%M")
                if str(workflow.get("last_scheduled_slot") or "") >= slot:
                    continue
                if self._scheduled_history_exists(
                    history,
                    company_key,
                    str(workflow.get("id") or ""),
                    due,
                ):
                    continue
                alerts.append(
                    self._alert(
                        "warning",
                        "Agendamento não executado",
                        f"{company_key.upper()} · {workflow.get('name')} deveria iniciar em {due.strftime('%d/%m · %H:%M')}.",
                        f"schedule:{company_key}:{workflow.get('id')}:{slot}",
                    )
                )
        return alerts

    @staticmethod
    def _scheduled_history_exists(
        history: list[dict[str, Any]],
        company: str,
        workflow_id: str,
        due: datetime,
    ) -> bool:
        limit = due + timedelta(days=1)
        for event in history:
            if (
                event.get("source") != "schedule"
                or event.get("company") != company
                or event.get("workflow_id") != workflow_id
            ):
                continue
            timestamp = OperationalMonitoring._date(event.get("timestamp"))
            if timestamp is not None and due <= timestamp <= limit:
                return True
        return False

    @staticmethod
    def _latest_due(
        entries: list[dict[str, Any]],
        current: datetime,
    ) -> datetime | None:
        values: list[datetime] = []
        for offset in range(8):
            day = current - timedelta(days=offset)
            for entry in entries:
                if day.weekday() != entry["weekday"]:
                    continue
                hour, minute = map(int, entry["time"].split(":"))
                value = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if value <= current:
                    values.append(value)
        return max(values) if values else None

    def _trend(
        self,
        reports: list[dict[str, Any]],
        current: datetime,
        days: int,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for offset in reversed(range(days)):
            day = (current - timedelta(days=offset)).date()
            values = [
                item
                for item in reports
                if (finished := self._date(item.get("finished_at"))) is not None
                and finished.date() == day
            ]
            result.append(
                {
                    "date": day.isoformat(),
                    "success": sum(item.get("status") == "success" for item in values),
                    "failed": sum(item.get("status") == "failed" for item in values),
                }
            )
        return result

    @classmethod
    def _within(
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

    @classmethod
    def _duration(cls, report: dict[str, Any]) -> int | None:
        started = cls._date(report.get("started_at"))
        finished = cls._date(report.get("finished_at"))
        if started is None or finished is None or finished < started:
            return None
        return round((finished - started).total_seconds())

    @staticmethod
    def _date(value: Any) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(str(value))
            return parsed if parsed.tzinfo else parsed.astimezone()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _percentage(success: int, total: int) -> int:
        return round(success * 100 / total) if total else 0

    @staticmethod
    def _average(values: list[int]) -> int:
        return round(sum(values) / len(values)) if values else 0

    @staticmethod
    def duration_label(seconds: int) -> str:
        seconds = max(0, int(seconds or 0))
        if seconds < 60:
            return f"{seconds}s"
        minutes, remaining = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}min {remaining:02d}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}min"

    @staticmethod
    def _report_summary(report: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": str(report.get("status") or ""),
            "finished_at": str(report.get("finished_at") or ""),
            "duration_seconds": OperationalMonitoring._duration(report) or 0,
            "action": str(report.get("action") or ""),
        }

    @staticmethod
    def _alert(
        level: str,
        title: str,
        message: str,
        key: str,
    ) -> dict[str, str]:
        return {"level": level, "title": title, "message": message, "key": key}
