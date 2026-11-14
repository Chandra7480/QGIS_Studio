"""Universal AI GIS Studio — Agent Manager.

Manages built-in and custom agents, tool/skill assignments, permissions.
"""

import logging
import json
from typing import Optional, List, Dict

from database.db import Database
from core.exceptions import NotFoundError
from core.capability_registry import CapabilityRegistry
from agents.base_agent import BaseAgent
from agents.custom.custom_builder import CustomAgentBuilder
from agents.builtins import BUILTIN_AGENT_CLASSES, create_builtin_agent

logger = logging.getLogger("uagis.agent_manager")


# Agent tool allowlist: maps agent_id to list of allowed MCP tool IDs
# Based on agent domain and permission level
AGENT_TOOL_ALLOWLISTS: Dict[str, List[str]] = {
    "agent_gis_supervisor": [
        "qgis.agents.list", "qgis.skills.list", "qgis.jobs.cancel", "qgis.history.inspect",
        "qgis.approval.grant", "qgis.approval.deny", "qgis.approval.list",
        "qgis.workflow.execute", "qgis.algorithms.discover", "qgis.algorithms.execute",
        "qgis.project.inspect", "qgis.layers.inspect", "qgis.layers.load",
        "qgis.system.inspect", "qgis.system.health",
    ],
    "agent_gis_research": [
        "qgis.algorithms.discover", "qgis.algorithms.execute",
        "qgis.system.inspect", "qgis.system.health",
        "qgis.layers.inspect", "qgis.project.inspect",
        "qgis.agents.list", "qgis.skills.list", "qgis.verify.status",
    ],
    "agent_data_acquisition": [
        "qgis.layers.load", "qgis.layers.inspect", "qgis.layers.remove",
        "qgis.project.inspect", "qgis.project.open", "qgis.project.save",
        "qgis.system.inspect", "qgis.system.health",
        "qgis.database.info", "qgis.algorithms.discover",
    ],
    "agent_data_management": [
        "qgis.layers.inspect", "qgis.layers.remove", "qgis.layers.load",
        "qgis.project.inspect", "qgis.project.save",
        "qgis.system.inspect", "qgis.algorithms.discover", "qgis.algorithms.execute",
    ],
    "agent_georeferencing": [
        "qgis.georeference.analyze", "qgis.gcp.generate", "qgis.gcp.validate",
        "qgis.layers.load", "qgis.layers.inspect", "qgis.algorithms.execute",
        "qgis.raster.info", "qgis.system.inspect",
    ],
    "agent_digitization": [
        "qgis.layers.load", "qgis.layers.inspect", "qgis.algorithms.execute",
        "qgis.cursor.move", "qgis.cursor.click", "qgis.cursor.drag",
        "qgis.keyboard.type", "qgis.keyboard.hotkey",
        "qgis.screen.capture", "qgis.window.inspect", "qgis.dialog.inspect",
    ],
    "agent_vector_processing": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.vector.info", "qgis.layers.inspect", "qgis.layers.load",
        "qgis.project.inspect", "qgis.system.inspect",
    ],
    "agent_raster_processing": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.raster.info", "qgis.layers.inspect", "qgis.layers.load",
        "qgis.project.inspect", "qgis.system.inspect",
    ],
    "agent_spatial_analysis": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.spatial.info", "qgis.vector.info", "qgis.raster.info",
        "qgis.layers.inspect", "qgis.project.inspect",
    ],
    "agent_terrain": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.raster.info", "qgis.layers.inspect", "qgis.project.inspect",
    ],
    "agent_hydrology": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.raster.info", "qgis.layers.inspect", "qgis.project.inspect",
    ],
    "agent_network": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.vector.info", "qgis.layers.inspect", "qgis.project.inspect",
    ],
    "agent_remote_sensing": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.raster.info", "qgis.layers.inspect", "qgis.layers.load",
        "qgis.web_gis", "qgis.project.inspect",
    ],
    "agent_classification": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.raster.info", "qgis.layers.inspect", "qgis.project.inspect",
    ],
    "agent_change_detection": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.raster.info", "qgis.layers.inspect", "qgis.project.inspect",
    ],
    "agent_3d_gis": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.raster.info", "qgis.vector.info", "qgis.layers.inspect",
        "qgis.canvas.inspect", "qgis.screen.capture", "qgis.project.inspect",
    ],
    "agent_lidar": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.raster.info", "qgis.layers.inspect", "qgis.layers.load",
        "qgis.project.inspect",
    ],
    "agent_survey_gps": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.vector.info", "qgis.layers.inspect", "qgis.layers.load",
        "qgis.project.inspect", "qgis.database.info",
    ],
    "agent_cadastral": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.vector.info", "qgis.layers.inspect", "qgis.layers.load",
        "qgis.project.inspect", "qgis.database.info",
    ],
    "agent_cartography": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.layout.info", "qgis.layers.inspect", "qgis.vector.info",
        "qgis.raster.info", "qgis.project.inspect", "qgis.project.save",
        "qgis.screen.capture",
    ],
    "agent_temporal_gis": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.raster.info", "qgis.vector.info", "qgis.layers.inspect",
        "qgis.project.inspect",
    ],
    "agent_database": [
        "qgis.database.info", "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.layers.load", "qgis.layers.inspect", "qgis.project.inspect",
        "qgis.system.inspect",
    ],
    "agent_web_gis": [
        "qgis.layers.load", "qgis.layers.inspect", "qgis.project.inspect",
        "qgis.algorithms.discover", "qgis.system.inspect",
    ],
    "agent_automation": [
        "qgis.workflow.execute", "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.jobs.cancel", "qgis.history.inspect", "qgis.project.inspect",
    ],
    "agent_quality_control": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.vector.info", "qgis.raster.info", "qgis.layers.inspect",
        "qgis.project.inspect", "qgis.verify.status",
    ],
    "agent_reporting": [
        "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.layout.info", "qgis.layers.inspect", "qgis.project.inspect",
        "qgis.screen.capture", "qgis.verify.status",
    ],
    "agent_visual_desktop_control": [
        "qgis.screen.capture", "qgis.cursor.move", "qgis.cursor.click",
        "qgis.cursor.drag", "qgis.keyboard.type", "qgis.keyboard.hotkey",
        "qgis.mouse.scroll", "qgis.window.inspect", "qgis.dialog.inspect",
        "qgis.layers.inspect", "qgis.project.inspect", "qgis.canvas.inspect",
    ],
    "agent_computer_vision": [
        "qgis.georeference.analyze", "qgis.gcp.generate", "qgis.gcp.validate",
        "qgis.raster.info", "qgis.layers.inspect", "qgis.algorithms.execute",
        "qgis.screen.capture", "qgis.project.inspect",
    ],
    "agent_gis_verification": [
        "qgis.verify.status", "qgis.algorithms.execute", "qgis.algorithms.discover",
        "qgis.vector.info", "qgis.raster.info", "qgis.layers.inspect",
        "qgis.project.inspect", "qgis.gcp.validate",
    ],
}


class AgentManager:
    def __init__(self, db: Database):
        self.db = db
        self._agents: dict[str, BaseAgent] = {}
        self._builtin_defs = self._builtin_definitions()
        self._custom_builder = CustomAgentBuilder(db)

    # ------------------------------------------------------------------ #
    # Built-in agents
    # ------------------------------------------------------------------ #
    def _builtin_definitions(self) -> dict[str, dict]:
        return {
            "agent_gis_supervisor": {
                "name": "GIS Supervisor Agent",
                "description": "Plans and delegates GIS tasks to specialist workers.",
                "permission_level": "elevated",
            },
            "agent_gis_research": {
                "name": "GIS Research Agent",
                "description": "Researches GIS data and methods.",
                "permission_level": "read",
            },
            "agent_data_acquisition": {
                "name": "Data Acquisition Agent",
                "description": "Discovers and imports datasets.",
                "permission_level": "standard",
            },
            "agent_data_management": {
                "name": "Data Management Agent",
                "description": "Organizes layers and metadata.",
                "permission_level": "standard",
            },
            "agent_georeferencing": {
                "name": "Georeferencing Agent",
                "description": "Automatic georeferencing of scanned maps.",
                "permission_level": "standard",
            },
            "agent_digitization": {
                "name": "Digitization Agent",
                "description": "Digitizes features from imagery/maps.",
                "permission_level": "standard",
            },
            "agent_vector_processing": {
                "name": "Vector Processing Agent",
                "description": "Buffer, clip, dissolve, overlay operations.",
                "permission_level": "standard",
            },
            "agent_raster_processing": {
                "name": "Raster Processing Agent",
                "description": "Raster calculation, reclassify, mosaic.",
                "permission_level": "standard",
            },
            "agent_spatial_analysis": {
                "name": "Spatial Analysis Agent",
                "description": "Joins, proximity, overlay, interpolation.",
                "permission_level": "standard",
            },
            "agent_terrain": {
                "name": "Terrain Analysis Agent",
                "description": "Slope, aspect, hillshade, contours.",
                "permission_level": "standard",
            },
            "agent_hydrology": {
                "name": "Hydrology Agent",
                "description": "Flow, watershed, stream extraction.",
                "permission_level": "standard",
            },
            "agent_network": {
                "name": "Network Analysis Agent",
                "description": "Shortest path, service areas, routing.",
                "permission_level": "standard",
            },
            "agent_remote_sensing": {
                "name": "Remote Sensing Agent",
                "description": "Satellite imagery, band combinations, indices.",
                "permission_level": "standard",
            },
            "agent_classification": {
                "name": "Image Classification Agent",
                "description": "Supervised/unsupervised classification.",
                "permission_level": "standard",
            },
            "agent_change_detection": {
                "name": "Change Detection Agent",
                "description": "Temporal comparison, land-cover change.",
                "permission_level": "standard",
            },
            "agent_3d_gis": {
                "name": "3D GIS Agent",
                "description": "3D visualization and terrain models.",
                "permission_level": "standard",
            },
            "agent_lidar": {
                "name": "LiDAR Agent",
                "description": "Point-cloud inspection and terrain extraction.",
                "permission_level": "standard",
            },
            "agent_survey_gps": {
                "name": "Survey and GPS Agent",
                "description": "GPS import and coordinate validation.",
                "permission_level": "standard",
            },
            "agent_cadastral": {
                "name": "Cadastral Agent",
                "description": "Parcel management and boundary digitization.",
                "permission_level": "standard",
            },
            "agent_cartography": {
                "name": "Cartography Agent",
                "description": "Symbology, labels, layouts, export.",
                "permission_level": "standard",
            },
            "agent_temporal_gis": {
                "name": "Temporal GIS Agent",
                "description": "Time-enabled layers and temporal analysis.",
                "permission_level": "standard",
            },
            "agent_database": {
                "name": "Database Agent",
                "description": "GeoPackage, PostGIS, spatial SQL.",
                "permission_level": "standard",
            },
            "agent_web_gis": {
                "name": "Web GIS Agent",
                "description": "WMS, WFS, WMTS, XYZ tiles.",
                "permission_level": "standard",
            },
            "agent_automation": {
                "name": "Automation Agent",
                "description": "Processing models and batch workflows.",
                "permission_level": "standard",
            },
            "agent_quality_control": {
                "name": "Quality Control Agent",
                "description": "Geometry, topology, CRS, attribute validation.",
                "permission_level": "standard",
            },
            "agent_reporting": {
                "name": "Reporting Agent",
                "description": "Generates GIS reports and map exports.",
                "permission_level": "read",
            },
            "agent_visual_desktop_control": {
                "name": "Visual Desktop Control Agent",
                "description": "Controls QGIS GUI via screen/cursor/mouse/keyboard.",
                "permission_level": "elevated",
            },
            "agent_computer_vision": {
                "name": "Computer Vision Agent",
                "description": "Landmark detection and image registration.",
                "permission_level": "standard",
            },
            "agent_gis_verification": {
                "name": "GIS Verification Agent",
                "description": "Verifies operation results and GCP residuals.",
                "permission_level": "read",
            },
        }

    def list_agents(self) -> list[dict]:
        out = []
        for aid, d in self._builtin_defs.items():
            out.append({"agent_id": aid, **d, "agent_type": "builtin"})
        for aid, agent in self._agents.items():
            if aid not in self._builtin_defs:
                out.append(agent.to_dict() | {"agent_type": "custom"})
        return out

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        if agent_id in self._agents:
            return self._agents[agent_id]
        if agent_id in self._builtin_defs:
            d = self._builtin_defs[agent_id]
            # Use the actual agent class from builtins
            agent = create_builtin_agent(agent_id, db=self.db)
            if agent is None:
                # Fallback to base agent
                agent = BaseAgent(
                    agent_id=agent_id, name=d["name"], description=d["description"],
                    instructions=f"Instructions for {d['name']}",
                    permission_level=d["permission_level"],
                    db=self.db,
                )
            # Set allowed tools from allowlist
            allowed_tools = AGENT_TOOL_ALLOWLISTS.get(agent_id, [])
            agent.set_allowed_tools(allowed_tools)
            self._agents[agent_id] = agent
            return agent
        return None

    def get_agent_allowed_tools(self, agent_id: str) -> List[str]:
        """Get the list of allowed tools for an agent."""
        return AGENT_TOOL_ALLOWLISTS.get(agent_id, [])

    def populate_agent_tools_table(self) -> int:
        """Populate the agent_tools database table with allowlists."""
        count = 0
        for agent_id, tool_ids in AGENT_TOOL_ALLOWLISTS.items():
            for tool_id in tool_ids:
                try:
                    self.db.execute(
                        "INSERT OR IGNORE INTO agent_tools(agent_id, tool_id) VALUES(?, ?)",
                        (agent_id, tool_id)
                    )
                    count += 1
                except Exception as exc:
                    logger.warning("Failed to insert agent_tool %s-%s: %s", agent_id, tool_id, exc)
        logger.info("Populated agent_tools table with %d entries", count)
        return count

    def sync_agent_tools(self) -> None:
        """Sync agent tool assignments from database to memory."""
        rows = self.db.fetchall("SELECT agent_id, tool_id FROM agent_tools")
        for row in rows:
            agent_id = row["agent_id"]
            tool_id = row["tool_id"]
            if agent_id in self._agents:
                agent = self._agents[agent_id]
                current = agent._allowed_tools
                if tool_id not in current:
                    current.append(tool_id)

    # ------------------------------------------------------------------ #
    # Custom agents
    # ------------------------------------------------------------------ #
    def create_custom_agent(self, spec: dict) -> str:
        return self._custom_builder.create(spec)

    def get_custom_agent(self, agent_id: str) -> Optional[dict]:
        return self._custom_builder.get(agent_id)

    def register_agents_capabilities(self, capability_registry: CapabilityRegistry) -> None:
        """Register all agent capabilities with the CapabilityRegistry."""
        for agent_id, defn in self._builtin_defs.items():
            capability_registry.register(
                category="agent",
                name=agent_id,
                version="1.0.0",
                available=True,
                details={
                    "name": defn.get("name"),
                    "description": defn.get("description"),
                    "permission_level": defn.get("permission_level"),
                    "allowed_tools": AGENT_TOOL_ALLOWLISTS.get(agent_id, []),
                }
            )
        
        # Also register custom agents
        for agent_id, agent in self._agents.items():
            if agent_id not in self._builtin_defs:
                capability_registry.register(
                    category="agent",
                    name=agent_id,
                    version="1.0.0",
                    available=True,
                    details={
                        "name": getattr(agent, 'name', agent_id),
                        "description": getattr(agent, 'description', ''),
                        "permission_level": getattr(agent, 'permission_level', 'standard'),
                        "custom": True,
                    }
                )
