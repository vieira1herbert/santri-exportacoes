from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import Mock

from santri_automation.scheduler import WorkflowScheduler, next_scheduled_run, normalize_schedule
from santri_automation.services.schedule_center import ScheduleCenter


class ProfessionalScheduleTest(unittest.TestCase):
    def test_policy_normalizes_priority_attempts_and_exceptions(self) -> None:
        schedule = normalize_schedule({"enabled": True, "entries": [{"weekday": 0, "time": "08:00"}], "exceptions": [{"date": "2026-08-17", "action": "skip"}], "priority": 9, "max_attempts": 0, "retry_failed_stage": True}, strict=True)
        self.assertEqual(5, schedule["priority"])
        self.assertEqual(3, schedule["max_attempts"])
        self.assertEqual("2026-08-17", schedule["exceptions"][0]["date"])

    def test_next_run_skips_exception(self) -> None:
        schedule = {"enabled": True, "entries": [{"weekday": 0, "time": "08:00"}], "exceptions": [{"date": "2026-08-17", "action": "skip"}]}
        next_run = next_scheduled_run(schedule, datetime(2026, 8, 16, 12, 0))
        self.assertEqual("2026-08-24T08:00", next_run.isoformat(timespec="minutes"))

    def test_scheduler_prioritizes_due_workflows(self) -> None:
        state = {"companies": {"sol": {"workflows": [
            {"id": "normal", "enabled": True, "implemented": True, "schedule": {"enabled": True, "entries": [{"weekday": 3, "time": "08:00"}], "priority": 3}},
            {"id": "critical", "enabled": True, "implemented": True, "schedule": {"enabled": True, "entries": [{"weekday": 3, "time": "08:00"}], "priority": 5}},
        ]}}}
        catalog = Mock()
        catalog.load.return_value = state
        order: list[str] = []
        scheduler = WorkflowScheduler(catalog, lambda _company, workflow: order.append(workflow) or {"ok": True})
        scheduler.run_pending(datetime(2026, 8, 13, 8, 5))
        self.assertEqual(["critical", "normal"], order)

    def test_schedule_center_builds_queue_calendar_and_forecast(self) -> None:
        state = {"companies": {"sol": {"name": "SOL", "workflows": [{"id": "cadastro", "name": "Cadastro", "enabled": True, "schedule": {"enabled": True, "entries": [{"weekday": 4, "time": "08:00"}], "priority": 4, "max_attempts": 2}}]}}}
        reports = [{"company": "sol", "workflow_ids": ["cadastro"], "started_at": "2026-08-13T08:00:00", "finished_at": "2026-08-13T08:10:00"}]
        result = ScheduleCenter().snapshot(state, reports, datetime(2026, 8, 13, 12, 0))
        self.assertEqual(1, result["summary"]["active"])
        self.assertEqual(600, result["queue"][0]["estimated_duration_seconds"])
        self.assertTrue(result["calendar"])


if __name__ == "__main__":
    unittest.main()
