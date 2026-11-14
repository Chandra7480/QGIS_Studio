"""Universal AI GIS Studio — Skill Validator.

Validates imported skills before execution. Untrusted skills are NOT granted
unrestricted shell, filesystem, or network access.
"""

import logging

from core.exceptions import SkillError

logger = logging.getLogger("uagis.skill_validator")


FORBIDDEN_KEYS = {"shell", "exec", "eval", "subprocess", "os.system",
                  "urllib", "requests", "socket", "ftplib"}

REQUIRED_MANIFEST_FIELDS = ["name", "version", "description"]


class SkillValidator:
    def validate(self, manifest: dict) -> list[str]:
        """Return list of validation problems (empty = valid)."""
        problems = []

        # Check required fields
        for field in REQUIRED_MANIFEST_FIELDS:
            if not manifest.get(field):
                problems.append(f"Missing required field: {field}")

        # Validate version format
        version = manifest.get("version", "")
        if version and not self._is_valid_version(version):
            problems.append(f"Invalid version format: {version} (expected semver)")

        # Check for dangerous permissions
        perms = manifest.get("permissions", [])
        for p in perms:
            if p in ("shell:*", "filesystem:*", "network:*", "*"):
                problems.append(f"Overly broad permission: {p}")

        # Scan embedded code for forbidden calls
        code = manifest.get("code", "")
        lower = code.lower()
        for fk in FORBIDDEN_KEYS:
            if fk in lower:
                problems.append(f"Forbidden construct in code: {fk}")

        # Validate security section
        security = manifest.get("security", {})
        if security:
            self._validate_security(security, problems)

        # Validate entrypoint if present
        entrypoint = manifest.get("entrypoint", "")
        if entrypoint and not self._is_safe_entrypoint(entrypoint):
            problems.append(f"Unsafe entrypoint: {entrypoint}")

        return problems

    def _validate_security(self, security: dict, problems: list[str]) -> None:
        """Validate security section of skill manifest."""
        if security.get("shell_access", False):
            problems.append("Security violation: shell_access must be false")
        if security.get("network_access", False):
            problems.append("Security violation: network_access must be false")
        if security.get("file_access") == "unrestricted":
            problems.append("Security violation: file_access must not be unrestricted")

        # Check coordinate policy
        coord_policy = security.get("coordinate_policy", "")
        if coord_policy and coord_policy != "never_invent_coordinates":
            problems.append(f"Security violation: coordinate_policy must be 'never_invent_coordinates', got '{coord_policy}'")

    def _is_valid_version(self, version: str) -> bool:
        """Simple semver check."""
        parts = version.split(".")
        return len(parts) == 3 and all(p.isdigit() for p in parts)

    def _is_safe_entrypoint(self, entrypoint: str) -> bool:
        """Check that entrypoint doesn't reference dangerous modules."""
        dangerous = ["os.system", "subprocess", "eval(", "exec("]
        lower = entrypoint.lower()
        for d in dangerous:
            if d in lower:
                return False
        return True

    def is_safe(self, manifest: dict) -> bool:
        return len(self.validate(manifest)) == 0


validator = SkillValidator()
