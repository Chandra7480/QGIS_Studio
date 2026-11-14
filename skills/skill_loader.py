"""Universal AI GIS Studio — Skill Loader."""

import json
import os
import logging
from typing import Optional, Dict

from skills.skill_validator import validator
from core.exceptions import SkillError

logger = logging.getLogger("uagis.skill_loader")


class SkillLoader:
    def load_from_directory(self, skill_dir: str) -> dict:
        """Load and validate a skill from a directory.

        Looks for manifest.yaml or manifest.json in the skill directory.
        Returns the parsed manifest dict if valid.
        """
        if not os.path.isdir(skill_dir):
            raise SkillError(f"Skill directory not found: {skill_dir}")

        manifest_path = os.path.join(skill_dir, "manifest.yaml")
        if not os.path.exists(manifest_path):
            manifest_path = os.path.join(skill_dir, "manifest.json")

        if not os.path.exists(manifest_path):
            raise SkillError(f"No manifest found in {skill_dir}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            text = f.read()

        if manifest_path.endswith(".json"):
            manifest = json.loads(text)
        else:
            try:
                import yaml
                manifest = yaml.safe_load(text)
            except ImportError:
                raise SkillError("PyYAML not installed; use manifest.json")
            except Exception as exc:
                raise SkillError(f"Failed to parse YAML manifest: {exc}")

        if not isinstance(manifest, dict):
            raise SkillError("Manifest must be a YAML/JSON object")

        problems = validator.validate(manifest)
        if problems:
            raise SkillError(f"Skill validation failed: {', '.join(problems)}")

        logger.info("Skill loaded and validated: %s", manifest.get("name", "unknown"))
        return manifest

    def load_builtin_skill(self, skill_name: str) -> dict:
        """Load a built-in skill by name."""
        skill_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "builtin", skill_name
        )
        return self.load_from_directory(skill_dir)
