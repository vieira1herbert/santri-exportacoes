from __future__ import annotations

import base64
import ctypes
import getpass
import hashlib
import hmac
import json
import os
import platform
import secrets
import stat
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar


class SecurityViolation(RuntimeError):
    pass


class FileIntegrityService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.security_root = root / "security"
        self.key_path = self.security_root / "integrity.key"
        self._key: bytes | None = None

    def sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def sign_bytes(self, value: bytes) -> str:
        return hmac.new(self._load_key(), value, hashlib.sha256).hexdigest()

    def sign_mapping(self, value: dict[str, Any]) -> str:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return self.sign_bytes(encoded)

    def seal_file(self, path: Path) -> Path:
        if not path.is_file():
            raise FileNotFoundError(path)
        metadata = {
            "algorithm": "HMAC-SHA256",
            "filename": path.name,
            "size": path.stat().st_size,
            "sha256": self.sha256(path),
            "sealed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        metadata["signature"] = self.sign_mapping(metadata)
        sidecar = self.sidecar_path(path)
        self._atomic_write(sidecar, metadata)
        return sidecar

    def verify_file(self, path: Path) -> bool | None:
        sidecar = self.sidecar_path(path)
        if not path.is_file() or not sidecar.is_file():
            return None
        try:
            metadata = json.loads(sidecar.read_text(encoding="utf-8"))
            signature = str(metadata.pop("signature"))
            expected = self.sign_mapping(metadata)
            return (
                hmac.compare_digest(signature, expected)
                and metadata.get("filename") == path.name
                and metadata.get("size") == path.stat().st_size
                and hmac.compare_digest(str(metadata.get("sha256")), self.sha256(path))
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return False

    def require_file(self, path: Path, migrate_legacy: bool = False) -> None:
        status = self.verify_file(path)
        if status is True:
            return
        if status is None and migrate_legacy and path.is_file():
            self.seal_file(path)
            return
        raise SecurityViolation(f"Falha de integridade detectada em {path.name}.")

    def file_manifest(self, paths: Iterable[Path]) -> list[dict[str, Any]]:
        manifest: list[dict[str, Any]] = []
        for path in paths:
            if path.is_file():
                manifest.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "size": path.stat().st_size,
                        "sha256": self.sha256(path),
                    }
                )
        return manifest

    @staticmethod
    def sidecar_path(path: Path) -> Path:
        return path.with_name(path.name + ".integrity")

    def _load_key(self) -> bytes:
        if self._key is not None:
            return self._key
        self.security_root.mkdir(parents=True, exist_ok=True)
        if self.key_path.is_file():
            protected = base64.b64decode(self.key_path.read_bytes())
            self._key = self._unprotect(protected)
            return self._key
        self._key = secrets.token_bytes(32)
        protected = self._protect(self._key)
        temporary = self.key_path.with_suffix(".tmp")
        temporary.write_bytes(base64.b64encode(protected))
        os.replace(temporary, self.key_path)
        try:
            self.key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        return self._key

    @staticmethod
    def _protect(value: bytes) -> bytes:
        if os.name != "nt":
            return value
        import win32crypt

        return win32crypt.CryptProtectData(
            value,
            "Santri Exportações v1.4",
            None,
            None,
            None,
            0,
        )

    @staticmethod
    def _unprotect(value: bytes) -> bytes:
        if os.name != "nt":
            return value
        import win32crypt

        return win32crypt.CryptUnprotectData(value, None, None, None, 0)[1]

    @staticmethod
    def _atomic_write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)


class UpdateScriptPolicy:
    ALLOWED_NAMES: ClassVar = {
        "ShellCadastroProdutos.ps1",
        "ShellTransferencias.ps1",
        "ShellEstoqueDisp.ps1",
    }

    @classmethod
    def authorize(cls, script: Path, root: Path) -> Path:
        resolved_root = root.resolve(strict=True)
        resolved_script = script.resolve(strict=True)
        if resolved_script.parent != resolved_root:
            raise SecurityViolation("O atualizador está fora da pasta autorizada.")
        if resolved_script.name not in cls.ALLOWED_NAMES:
            raise SecurityViolation("Nome de atualizador não autorizado.")
        if resolved_script.suffix.casefold() != ".ps1" or not resolved_script.is_file():
            raise SecurityViolation("Atualizador inválido.")
        if script.is_symlink() or cls._is_reparse_point(resolved_script):
            raise SecurityViolation(
                "Links e pontos de nova análise não são permitidos."
            )
        if resolved_script.stat().st_size <= 0:
            raise SecurityViolation("O atualizador autorizado está vazio.")
        return resolved_script

    @staticmethod
    def powershell_executable() -> Path:
        windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        executable = (
            windows / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        )
        if os.name == "nt" and not executable.is_file():
            raise SecurityViolation("Windows PowerShell oficial não encontrado.")
        return executable

    @staticmethod
    def _is_reparse_point(path: Path) -> bool:
        attributes = getattr(path.stat(), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


class WindowsSecurityService:
    def __init__(self, root: Path, integrity: FileIntegrityService) -> None:
        self.root = root
        self.integrity = integrity
        self.acl_protected = self.harden_directory()

    def status(self, catalog: Path, audit_valid: bool) -> dict[str, Any]:
        integrity = self.integrity.verify_file(catalog)
        release = self.release_status()
        release_ready = release["verified"]
        return {
            "ready": integrity is True and audit_valid and release_ready,
            "configuration_integrity": self._label(integrity),
            "audit_integrity": "verified" if audit_valid else "failed",
            "key_protection": (
                "windows_dpapi" if os.name == "nt" else "local_permissions"
            ),
            "local_storage": (
                "restricted_acl" if self.acl_protected else "standard_permissions"
            ),
            "update_policy": "restricted_path_and_name",
            "identity": self.identity(),
            "elevated": self.is_elevated(),
            "release": release,
        }

    def release_status(self) -> dict[str, Any]:
        if not getattr(sys, "frozen", False):
            return {"mode": "development", "verified": True, "signed": False}
        executable = Path(sys.executable)
        manifest = executable.parent / "santri-exportacoes-release.json"
        if not manifest.is_file():
            return {"mode": "packaged", "verified": False, "signed": False}
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
            expected = str(value["executable"]["sha256"])
            actual = self.integrity.sha256(executable)
            signature = value.get("authenticode", {})
            return {
                "mode": "packaged",
                "verified": hmac.compare_digest(expected, actual),
                "signed": bool(signature.get("signed")),
                "signature_status": str(signature.get("status") or "unknown"),
            }
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            return {"mode": "packaged", "verified": False, "signed": False}

    def harden_directory(self) -> bool:
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            try:
                self.root.chmod(stat.S_IRWXU)
                return True
            except OSError:
                return False
        try:
            import ntsecuritycon
            import win32api
            import win32con
            import win32security

            token = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(),
                win32con.TOKEN_QUERY,
            )
            user_sid = win32security.GetTokenInformation(
                token,
                win32security.TokenUser,
            )[0]
            system_sid = win32security.CreateWellKnownSid(
                win32security.WinLocalSystemSid,
                None,
            )
            admins_sid = win32security.CreateWellKnownSid(
                win32security.WinBuiltinAdministratorsSid,
                None,
            )
            dacl = win32security.ACL()
            flags = win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE
            for sid in (user_sid, system_sid, admins_sid):
                dacl.AddAccessAllowedAceEx(
                    win32security.ACL_REVISION_DS,
                    flags,
                    ntsecuritycon.FILE_ALL_ACCESS,
                    sid,
                )
            win32security.SetNamedSecurityInfo(
                str(self.root),
                win32security.SE_FILE_OBJECT,
                win32security.DACL_SECURITY_INFORMATION
                | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
                None,
                None,
                dacl,
                None,
            )
            return True
        except (OSError, AttributeError, ImportError):
            return False

    @staticmethod
    def identity() -> dict[str, str]:
        return {
            "user": getpass.getuser(),
            "domain": os.environ.get("USERDOMAIN", ""),
            "computer": platform.node(),
        }

    @staticmethod
    def is_elevated() -> bool:
        if os.name != "nt":
            return False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except OSError:
            return False

    @staticmethod
    def _label(value: bool | None) -> str:
        if value is True:
            return "verified"
        if value is False:
            return "failed"
        return "legacy"
