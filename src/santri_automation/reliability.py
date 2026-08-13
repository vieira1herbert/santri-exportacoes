from __future__ import annotations

import html
import json
import os
import re
import shutil
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .security import FileIntegrityService, SecurityViolation


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def redact_text(value: Any) -> str:
    return re.sub(
        r"(?i)\b(password|senha|secret|token|credential)\s*[:=]\s*\S+",
        r"\1=[PROTEGIDO]",
        str(value),
    )


def atomic_json_write(
    path: Path,
    data: Any,
    integrity: FileIntegrityService | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if integrity is not None:
        integrity.seal_file(path)


class NotificationCenter:
    def __init__(
        self,
        path: Path,
        integrity: FileIntegrityService | None = None,
    ) -> None:
        self.path = path
        self.integrity = integrity
        self._lock = threading.RLock()

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return self._load()[: max(1, min(500, limit))]

    def add(
        self,
        level: str,
        title: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            items = self._load()
            saved = {
                "id": uuid4().hex,
                "timestamp": timestamp(),
                "level": level if level in {"success", "warning", "error", "info"} else "info",
                "title": redact_text(title)[:160],
                "message": redact_text(message)[:2000],
                "details": details or {},
                "read": False,
            }
            items.insert(0, saved)
            atomic_json_write(self.path, items[:500], self.integrity)
            return dict(saved)

    def mark_all_read(self) -> int:
        with self._lock:
            items = self._load()
            changed = sum(not bool(item.get("read")) for item in items)
            for item in items:
                item["read"] = True
            atomic_json_write(self.path, items, self.integrity)
            return changed

    def clear(self) -> int:
        with self._lock:
            count = len(self._load())
            atomic_json_write(self.path, [], self.integrity)
            return count

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        if self.integrity is not None:
            self.integrity.require_file(self.path, migrate_legacy=True)
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, json.JSONDecodeError):
            return []


class ExecutionSession:
    TRANSIENT_MARKERS = (
        "timeout",
        "tempo limite",
        "não respondeu",
        "não apareceu",
        "janela",
        "temporariamente",
        "indisponível",
        "conexão",
        "ocupado",
    )

    def __init__(
        self,
        root: Path,
        company: str,
        workflow_ids: list[str],
        action: str,
        source: str,
        execution_id: str | None = None,
        delay: Callable[[float], None] = time.sleep,
        integrity: FileIntegrityService | None = None,
    ) -> None:
        self.root = root
        self.checkpoint_dir = root / "checkpoints"
        self.report_dir = root / "reports"
        self.evidence_dir = root / "evidence"
        self.execution_id = execution_id or (
            datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
        )
        self.path = self.checkpoint_dir / f"{self.execution_id}.json"
        self.delay = delay
        self.integrity = integrity
        self.data = self._load_existing() or {
            "id": self.execution_id,
            "started_at": timestamp(),
            "updated_at": timestamp(),
            "finished_at": None,
            "status": "in_progress",
            "company": company,
            "workflow_ids": list(workflow_ids),
            "action": action,
            "source": source,
            "current_workflow": "",
            "current_step": "",
            "completed_steps": [],
            "timeline": [],
            "artifacts": [],
            "error": "",
            "evidence": "",
            "report": "",
        }
        self.data["status"] = "in_progress"
        self.record("session", "started", "Execução iniciada.")

    def record(
        self,
        step: str,
        status: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.data["updated_at"] = timestamp()
        self.data.setdefault("timeline", []).append(
            {
                "timestamp": timestamp(),
                "step": step,
                "status": status,
                "message": redact_text(message),
                "details": details or {},
            }
        )
        self._save()

    def run_step(
        self,
        workflow_id: str,
        step: str,
        operation: Callable[[], tuple[Path, ...]],
        retries: int = 2,
        progress: Callable[[str], None] | None = None,
    ) -> tuple[Path, ...]:
        key = f"{workflow_id}:{step}"
        if key in self.data.get("completed_steps", []):
            message = f"Etapa retomada sem repetição: {step}."
            self.record(step, "skipped", message)
            if progress:
                progress(message)
            return ()
        self.data["current_workflow"] = workflow_id
        self.data["current_step"] = step
        self._save()
        maximum = max(1, retries + 1)
        for attempt in range(1, maximum + 1):
            message = f"{step}: tentativa {attempt} de {maximum}."
            self.record(step, "running", message, {"attempt": attempt})
            if progress:
                progress(message)
            try:
                result = tuple(operation())
                self.data.setdefault("completed_steps", []).append(key)
                self.data.setdefault("artifacts", []).extend(str(path) for path in result)
                if self.integrity is not None:
                    self.data["artifact_manifest"] = self.integrity.file_manifest(
                        Path(path) for path in self.data.get("artifacts", [])
                    )
                self.record(step, "success", f"Etapa concluída: {step}.")
                return result
            except Exception as error:
                transient = self._is_transient(error)
                self.record(
                    step,
                    "retry" if transient and attempt < maximum else "error",
                    f"{type(error).__name__}: {error}",
                    {"attempt": attempt, "transient": transient},
                )
                if not transient or attempt >= maximum:
                    raise
                waiting = min(4.0, float(attempt))
                if progress:
                    progress(f"Falha temporária. Nova tentativa em {int(waiting)} segundo(s).")
                self.delay(waiting)
        return ()

    def finish(self, message: str) -> Path:
        self.data["status"] = "success"
        self.data["finished_at"] = timestamp()
        self.data["current_step"] = ""
        self.record("session", "success", message)
        return self._write_report()

    def fail(self, message: str, evidence: Path | None = None) -> Path:
        self.data["status"] = "failed"
        self.data["finished_at"] = timestamp()
        self.data["error"] = redact_text(message)
        self.data["evidence"] = str(evidence or "")
        self.record("session", "error", message)
        return self._write_report()

    def capture_screen(self) -> Path | None:
        try:
            from PIL import ImageGrab

            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            path = self.evidence_dir / f"{self.execution_id}-falha.png"
            image = ImageGrab.grab(all_screens=True)
            image.save(path, "PNG")
            return path
        except Exception as error:
            self.record(
                "evidence",
                "warning",
                f"Não foi possível capturar a tela: {type(error).__name__}: {error}",
            )
            return None

    def _write_report(self) -> Path:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.report_dir / f"{self.execution_id}.json"
        html_path = self.report_dir / f"{self.execution_id}.html"
        self.data["report"] = str(html_path)
        atomic_json_write(json_path, self.data, self.integrity)
        rows = "".join(
            "<tr>"
            f"<td>{html.escape(str(item.get('timestamp', '')))}</td>"
            f"<td>{html.escape(str(item.get('step', '')))}</td>"
            f"<td>{html.escape(str(item.get('status', '')))}</td>"
            f"<td>{html.escape(str(item.get('message', '')))}</td>"
            "</tr>"
            for item in self.data.get("timeline", [])
        )
        artifacts = "".join(
            f"<li>{html.escape(str(path))}</li>"
            for path in self.data.get("artifacts", [])
        ) or "<li>Nenhum arquivo registrado.</li>"
        document = (
            "<!doctype html><html lang=\"pt-BR\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Relatório Santri Exportações</title>"
            "<style>body{font:14px Segoe UI,sans-serif;margin:32px;color:#1a1c1f}"
            "h1{color:#314354}table{border-collapse:collapse;width:100%;margin-top:20px}"
            "td,th{border:1px solid #dfe4e8;padding:8px;text-align:left}th{background:#f4f6f8}"
            ".meta{padding:16px;background:#f4f6f8;border-radius:10px;line-height:1.8}</style>"
            "<h1>Santri Exportações · Relatório de execução</h1>"
            f"<div class=\"meta\"><strong>ID:</strong> {html.escape(self.execution_id)}<br>"
            f"<strong>Empresa:</strong> {html.escape(str(self.data.get('company', '')))}<br>"
            f"<strong>Ação:</strong> {html.escape(str(self.data.get('action', '')))}<br>"
            f"<strong>Resultado:</strong> {html.escape(str(self.data.get('status', '')))}<br>"
            f"<strong>Início:</strong> {html.escape(str(self.data.get('started_at', '')))}<br>"
            f"<strong>Fim:</strong> {html.escape(str(self.data.get('finished_at', '')))}</div>"
            "<h2>Arquivos e evidências</h2><ul>" + artifacts + "</ul>"
            "<h2>Linha do tempo</h2><table><thead><tr><th>Data</th><th>Etapa</th>"
            "<th>Status</th><th>Descrição</th></tr></thead><tbody>" + rows + "</tbody></table>"
            "<p><strong>Projeto idealizado e desenvolvido por Herbert Vieira.</strong></p></html>"
        )
        html_path.write_text(document, encoding="utf-8")
        atomic_json_write(self.path, self.data, self.integrity)
        return html_path

    def _load_existing(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        if self.integrity is not None:
            self.integrity.require_file(self.path, migrate_legacy=True)
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _save(self) -> None:
        atomic_json_write(self.path, self.data, self.integrity)

    @classmethod
    def _is_transient(cls, error: Exception) -> bool:
        normalized = str(error).casefold()
        return any(marker in normalized for marker in cls.TRANSIENT_MARKERS)


class ReliabilityCenter:
    def __init__(
        self,
        root: Path,
        integrity: FileIntegrityService | None = None,
    ) -> None:
        self.root = root / "reliability"
        self.integrity = integrity or FileIntegrityService(root)
        self.notifications = NotificationCenter(
            self.root / "notifications.json",
            self.integrity,
        )

    def start_session(
        self,
        company: str,
        workflow_ids: list[str],
        action: str,
        source: str,
        execution_id: str | None = None,
    ) -> ExecutionSession:
        return ExecutionSession(
            self.root,
            company,
            workflow_ids,
            action,
            source,
            execution_id=execution_id,
            integrity=self.integrity,
        )

    def pending_checkpoint(self) -> dict[str, Any] | None:
        checkpoints = self._load_checkpoints()
        return next(
            (item for item in checkpoints if item.get("status") == "failed"),
            None,
        )

    def latest_reports(self, limit: int = 20) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        for path in sorted(
            (self.root / "reports").glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[:limit]:
            try:
                self.integrity.require_file(path, migrate_legacy=True)
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    reports.append(value)
            except (OSError, json.JSONDecodeError, SecurityViolation):
                continue
        return reports

    def apply_retention(self, days: int) -> dict[str, int]:
        retention = max(15, min(365, int(days or 90)))
        cutoff = datetime.now().timestamp() - retention * 86400
        removed = {"reports": 0, "checkpoints": 0, "evidence": 0, "support": 0}
        locations = {
            "reports": self.root / "reports",
            "checkpoints": self.root / "checkpoints",
            "evidence": self.root / "evidence",
            "support": self.root / "support",
        }
        for category, folder in locations.items():
            if not folder.is_dir():
                continue
            for path in folder.iterdir():
                if (
                    not path.is_file()
                    or path.name.endswith(".integrity")
                    or path.stat().st_mtime >= cutoff
                ):
                    continue
                path.unlink(missing_ok=True)
                self.integrity.sidecar_path(path).unlink(missing_ok=True)
                removed[category] += 1
        return removed

    def dismiss_checkpoint(self, execution_id: str) -> bool:
        safe_id = Path(str(execution_id)).name
        if safe_id != execution_id:
            return False
        path = self.root / "checkpoints" / f"{safe_id}.json"
        if not path.is_file():
            return False
        try:
            self.integrity.require_file(path, migrate_legacy=True)
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, SecurityViolation):
            return False
        if not isinstance(value, dict):
            return False
        value["status"] = "dismissed"
        value["updated_at"] = timestamp()
        atomic_json_write(path, value, self.integrity)
        return True

    def create_support_package(
        self,
        state: dict[str, Any],
        health: dict[str, Any],
        error_log: Path,
    ) -> Path:
        destination = self.root / "support"
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / f"Santri-Diagnostico-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        sanitized = self._sanitize(state)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "estado-sanitizado.json",
                json.dumps(sanitized, ensure_ascii=False, indent=2),
            )
            archive.writestr(
                "diagnostico.json",
                json.dumps(health, ensure_ascii=False, indent=2),
            )
            for report in sorted((self.root / "reports").glob("*"), reverse=True)[:6]:
                if report.is_file():
                    try:
                        content = report.read_text(encoding="utf-8")
                        if report.suffix.casefold() == ".json":
                            parsed = json.loads(content)
                            content = json.dumps(
                                self._sanitize(parsed),
                                ensure_ascii=False,
                                indent=2,
                            )
                        else:
                            content = redact_text(content)
                        archive.writestr(f"relatorios/{report.name}", content)
                    except (OSError, json.JSONDecodeError):
                        continue
            if error_log.exists():
                archive.writestr(
                    "app-errors.log",
                    redact_text(error_log.read_text(encoding="utf-8", errors="replace")),
                )
        self.integrity.seal_file(path)
        return path

    def _load_checkpoints(self) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for path in sorted(
            (self.root / "checkpoints").glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            try:
                self.integrity.require_file(path, migrate_legacy=True)
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    values.append(value)
            except (OSError, json.JSONDecodeError, SecurityViolation):
                continue
        return values

    @classmethod
    def _sanitize(cls, value: Any, key: str = "") -> Any:
        if any(marker in key.casefold() for marker in ("password", "senha", "secret", "token", "credential")):
            return "[PROTEGIDO]"
        if isinstance(value, dict):
            return {str(item_key): cls._sanitize(item, str(item_key)) for item_key, item in value.items()}
        if isinstance(value, list):
            return [cls._sanitize(item, key) for item in value]
        if isinstance(value, str):
            return redact_text(value)
        if isinstance(value, (bool, int, float)) or value is None:
            return value
        return str(value)
