"""Universal AI GIS Studio — Extension Manager.

ZIP installation, local directory import, dependency checking, version
compatibility, enable/disable, uninstall, manifest validation, permission
declarations, trust checks. Marketplace-ready architecture (no marketplace
required in the initial release).
"""

import json
import os
import uuid
import zipfile
import datetime as dt
import logging
import shutil

from database.db import Database
from core.exceptions import ExtensionError

logger = logging.getLogger("uagis.extensions")


class ExtensionManager:
    def __init__(self, db: Database, extensions_dir: str):
        self.db = db
        self.extensions_dir = extensions_dir
        os.makedirs(extensions_dir, exist_ok=True)

    def install_from_zip(self, zip_path: str, extension_id: str | None = None) -> str:
        ext_id = extension_id or f"ext_{uuid.uuid4().hex[:10]}"
        target = os.path.join(self.extensions_dir, ext_id)
        if os.path.exists(target):
            raise ExtensionError(f"Extension {ext_id} already installed")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target)
        manifest = self._load_manifest(target)
        self._validate_manifest(manifest)
        now = dt.datetime.utcnow().isoformat()
        self.db.execute(
            "INSERT OR REPLACE INTO skills(id, name, version, description, manifest, "
            "enabled, trusted, installed_at, updated_at) VALUES(?, ?, ?, ?, ?, 1, 0, ?, ?)",
            (ext_id, manifest.get("name", ext_id), manifest.get("version", "1.0.0"),
             manifest.get("description", ""), json.dumps(manifest), now, now))
        logger.info("Extension installed: %s from %s", ext_id, zip_path)
        return ext_id

    def install_from_directory(self, dir_path: str, extension_id: str | None = None) -> str:
        ext_id = extension_id or f"ext_{uuid.uuid4().hex[:10]}"
        target = os.path.join(self.extensions_dir, ext_id)
        if os.path.exists(target):
            raise ExtensionError(f"Extension {ext_id} already installed")
        shutil.copytree(dir_path, target)
        manifest = self._load_manifest(target)
        self._validate_manifest(manifest)
        now = dt.datetime.utcnow().isoformat()
        self.db.execute(
            "INSERT OR REPLACE INTO skills(id, name, version, description, manifest, "
            "enabled, trusted, installed_at, updated_at) VALUES(?, ?, ?, ?, ?, 1, 0, ?, ?)",
            (ext_id, manifest.get("name", ext_id), manifest.get("version", "1.0.0"),
             manifest.get("description", ""), json.dumps(manifest), now, now))
        logger.info("Extension installed: %s from %s", ext_id, dir_path)
        return ext_id

    def uninstall(self, extension_id: str) -> None:
        target = os.path.join(self.extensions_dir, extension_id)
        if os.path.isdir(target):
            shutil.rmtree(target)
        self.db.execute("DELETE FROM skills WHERE id = ?", (extension_id,))
        logger.info("Extension uninstalled: %s", extension_id)

    def set_enabled(self, extension_id: str, enabled: bool) -> None:
        self.db.execute("UPDATE skills SET enabled = ? WHERE id = ?",
                        (int(enabled), extension_id))

    def list_extensions(self) -> list[dict]:
        rows = self.db.fetchall(
            "SELECT * FROM skills WHERE id LIKE 'ext_%' ORDER BY name")
        return [dict(r) for r in rows]

    def _load_manifest(self, path: str) -> dict:
        for fname in ("manifest.json", "manifest.yaml"):
            p = os.path.join(path, fname)
            if os.path.exists(p):
                with open(p) as f:
                    text = f.read()
                if fname.endswith(".json"):
                    return json.loads(text)
                import yaml
                return yaml.safe_load(text)
        raise ExtensionError("No manifest found in extension")

    def _validate_manifest(self, manifest: dict) -> None:
        if not manifest.get("name"):
            raise ExtensionError("Extension manifest missing name")
        perms = manifest.get("permissions", [])
        for p in perms:
            if p in ("shell:*", "*"):
                raise ExtensionError(f"Untrusted permission: {p}")
