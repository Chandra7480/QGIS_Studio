"""Universal AI GIS Studio — Skill Manager.

Create, edit, import, export, enable/disable, assign, search, version,
validate, and document skills.
"""

import json
import uuid
import datetime as dt
import logging

from database.db import Database
from core.exceptions import NotFoundError, SkillError
from core.capability_registry import CapabilityRegistry
from skills.skill_loader import SkillLoader

logger = logging.getLogger("uagis.skills")


class SkillManager:
    def __init__(self, db: Database):
        self.db = db
        self._loader = SkillLoader()
        self._builtin_skills = {
            "automatic-georeferencing": {
                "name": "Automatic Georeferencing",
                "description": "Detect GCPs and georeference scanned maps automatically.",
                "version": "1.0.0",
            },
        }

    def list_skills(self) -> list[dict]:
        rows = self.db.fetchall("SELECT * FROM skills ORDER BY name")
        out = [dict(r) for r in rows]
        for sid, d in self._builtin_skills.items():
            if not any(r["id"] == sid for r in out):
                out.append({"id": sid, "agent_type": "builtin", **d,
                            "enabled": True, "trusted": True})
        return out

    def import_skill(self, skill_dir: str, skill_id: str | None = None) -> str:
        manifest = self._loader.load_from_directory(skill_dir)
        sid = skill_id or f"skill_{uuid.uuid4().hex[:10]}"
        now = dt.datetime.utcnow().isoformat()
        self.db.execute(
            "INSERT OR REPLACE INTO skills(id, name, version, description, manifest, "
            "enabled, trusted, installed_at, updated_at) VALUES(?, ?, ?, ?, ?, 1, 0, ?, ?)",
            (sid, manifest.get("name", sid), manifest.get("version", "1.0.0"),
             manifest.get("description", ""), json.dumps(manifest), now, now))
        logger.info("Skill imported: %s", sid)
        return sid

    def set_enabled(self, skill_id: str, enabled: bool) -> None:
        self.db.execute("UPDATE skills SET enabled = ? WHERE id = ?",
                        (int(enabled), skill_id))

    def assign_to_agent(self, agent_id: str, skill_id: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO agent_skills(agent_id, skill_id) VALUES(?, ?)",
            (agent_id, skill_id))

    def register_skills_capabilities(self, capability_registry: CapabilityRegistry) -> None:
        """Register all skill capabilities with the CapabilityRegistry."""
        # Register built-in skills
        for skill_id, skill_info in self._builtin_skills.items():
            capability_registry.register(
                category="skill",
                name=skill_id,
                version=skill_info.get("version", "1.0.0"),
                available=True,
                details={
                    "name": skill_info.get("name"),
                    "description": skill_info.get("description"),
                    "builtin": True,
                }
            )
        
        # Register custom skills from database
        try:
            rows = self.db.fetchall("SELECT id, name, version, description FROM skills WHERE id NOT LIKE 'builtin_%'")
            for row in rows:
                capability_registry.register(
                    category="skill",
                    name=row["id"],
                    version=row.get("version", "1.0.0"),
                    available=True,
                    details={
                        "name": row.get("name"),
                        "description": row.get("description"),
                        "builtin": False,
                    }
                )
        except Exception as exc:
            logger.warning("Could not register custom skill capabilities: %s", exc)
