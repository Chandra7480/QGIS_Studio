"""Universal AI GIS Studio — GIS Capability Discovery Engine.

Inspects the actual installed GIS environment (QGIS version, GDAL/OGR,
Processing providers, algorithms, plugins, CRS, transformations) and
maintains a dynamic capability registry. The AI consults this registry
before planning tasks so it never assumes an unavailable algorithm exists.
"""

import logging
from typing import Optional

from database.db import Database
from core.exceptions import DependencyError

logger = logging.getLogger("uagis.capability")


class CapabilityRegistry:
    """Dynamic registry of installed GIS capabilities."""

    def __init__(self, db: Database):
        self.db = db
        self._caps: dict[str, dict] = {}

    def discover_qgis(self) -> dict:
        """Discover QGIS version and PyQGIS availability."""
        info = {"qgis_available": False, "qgis_version": None,
                "python_version": None, "gdal_version": None}
        try:
            import sys
            info["python_version"] = sys.version
            import qgis
            info["qgis_available"] = True
            info["qgis_version"] = getattr(qgis, "__version__", "unknown")
        except Exception as exc:
            logger.debug("PyQGIS not importable: %s", exc)
        try:
            from osgeo import gdal
            info["gdal_version"] = gdal.VersionInfo("RELEASE_NAME")
        except Exception as exc:
            logger.debug("GDAL not importable: %s", exc)
        return info

    def discover_processing_algorithms(self) -> list[dict]:
        """Discover installed QGIS Processing algorithms (dynamic)."""
        algs = []
        try:
            import processing
            from qgis.core import QgsApplication
            registry = QgsApplication.processingRegistry()
            for a in registry.algorithms():
                algs.append({"id": a.id(), "name": a.name(),
                             "group": a.group()})
        except Exception as exc:
            logger.debug("Processing discovery failed: %s", exc)
        return algs

    def register(self, category: str, name: str, version: str | None = None,
                 available: bool = True, details: dict | None = None) -> None:
        cap_id = f"{category}:{name}"
        self._caps[cap_id] = {
            "id": cap_id, "category": category, "name": name,
            "version": version, "available": available,
            "details": details or {},
        }
        try:
            self.db.execute(
                "INSERT OR REPLACE INTO capability_registry(id, category, name, version, available, details) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (cap_id, category, name, version, int(available),
                 __import__("json").dumps(details or {})),
            )
        except Exception as exc:
            logger.warning("Failed to persist capability %s: %s", cap_id, exc)

    def is_available(self, category: str, name: str) -> bool:
        cap = self._caps.get(f"{category}:{name}")
        return bool(cap and cap.get("available"))

    def list_available(self, category: str | None = None) -> list[dict]:
        out = []
        for cap in self._caps.values():
            if category and cap["category"] != category:
                continue
            if cap["available"]:
                out.append(cap)
        return out

    def summary(self) -> dict:
        qgis = self.discover_qgis()
        return {
            "qgis": qgis,
            "capabilities": len(self._caps),
            "available": sum(1 for c in self._caps.values() if c["available"]),
        }
