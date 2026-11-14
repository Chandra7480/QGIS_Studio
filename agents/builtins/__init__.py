"""Universal AI GIS Studio — Built-in Agents Package."""

from agents.builtins.agent_gis_supervisor import AGISSupervisorAgent
from agents.builtins.agent_gis_research import GISResearchAgent
from agents.builtins.agent_data_acquisition import DataAcquisitionAgent
from agents.builtins.agent_data_management import DataManagementAgent
from agents.builtins.agent_georeferencing import GeoreferencingAgent
from agents.builtins.agent_digitization import DigitizationAgent
from agents.builtins.agent_vector_processing import VectorProcessingAgent
from agents.builtins.agent_raster_processing import RasterProcessingAgent
from agents.builtins.agent_spatial_analysis import SpatialAnalysisAgent
from agents.builtins.agent_terrain import TerrainAnalysisAgent
from agents.builtins.agent_hydrology import HydrologyAgent
from agents.builtins.agent_network import NetworkAnalysisAgent
from agents.builtins.agent_remote_sensing import RemoteSensingAgent
from agents.builtins.agent_classification import ImageClassificationAgent
from agents.builtins.agent_change_detection import ChangeDetectionAgent
from agents.builtins.agent_3d_gis import Agent3DGIS
from agents.builtins.agent_lidar import LiDARAgent
from agents.builtins.agent_survey_gps import SurveyGPSAgent
from agents.builtins.agent_cadastral import CadastralAgent
from agents.builtins.agent_cartography import CartographyAgent
from agents.builtins.agent_temporal_gis import TemporalGISAgent
from agents.builtins.agent_database import DatabaseAgent
from agents.builtins.agent_web_gis import WebGISAgent
from agents.builtins.agent_automation import AutomationAgent
from agents.builtins.agent_quality_control import QualityControlAgent
from agents.builtins.agent_reporting import ReportingAgent
from agents.builtins.agent_visual_desktop_control import VisualDesktopControlAgent
from agents.builtins.agent_computer_vision import ComputerVisionAgent
from agents.builtins.agent_gis_verification import GISVerificationAgent

__all__ = [
    "AGISSupervisorAgent",
    "GISResearchAgent",
    "DataAcquisitionAgent",
    "DataManagementAgent",
    "GeoreferencingAgent",
    "DigitizationAgent",
    "VectorProcessingAgent",
    "RasterProcessingAgent",
    "SpatialAnalysisAgent",
    "TerrainAnalysisAgent",
    "HydrologyAgent",
    "NetworkAnalysisAgent",
    "RemoteSensingAgent",
    "ImageClassificationAgent",
    "ChangeDetectionAgent",
    "Agent3DGIS",
    "LiDARAgent",
    "SurveyGPSAgent",
    "CadastralAgent",
    "CartographyAgent",
    "TemporalGISAgent",
    "DatabaseAgent",
    "WebGISAgent",
    "AutomationAgent",
    "QualityControlAgent",
    "ReportingAgent",
    "VisualDesktopControlAgent",
    "ComputerVisionAgent",
    "GISVerificationAgent",
]

# Agent ID to class mapping for dynamic loading
BUILTIN_AGENT_CLASSES = {
    "agent_gis_supervisor": AGISSupervisorAgent,
    "agent_gis_research": GISResearchAgent,
    "agent_data_acquisition": DataAcquisitionAgent,
    "agent_data_management": DataManagementAgent,
    "agent_georeferencing": GeoreferencingAgent,
    "agent_digitization": DigitizationAgent,
    "agent_vector_processing": VectorProcessingAgent,
    "agent_raster_processing": RasterProcessingAgent,
    "agent_spatial_analysis": SpatialAnalysisAgent,
    "agent_terrain": TerrainAnalysisAgent,
    "agent_hydrology": HydrologyAgent,
    "agent_network": NetworkAnalysisAgent,
    "agent_remote_sensing": RemoteSensingAgent,
    "agent_classification": ImageClassificationAgent,
    "agent_change_detection": ChangeDetectionAgent,
    "agent_3d_gis": Agent3DGIS,
    "agent_lidar": LiDARAgent,
    "agent_survey_gps": SurveyGPSAgent,
    "agent_cadastral": CadastralAgent,
    "agent_cartography": CartographyAgent,
    "agent_temporal_gis": TemporalGISAgent,
    "agent_database": DatabaseAgent,
    "agent_web_gis": WebGISAgent,
    "agent_automation": AutomationAgent,
    "agent_quality_control": QualityControlAgent,
    "agent_reporting": ReportingAgent,
    "agent_visual_desktop_control": VisualDesktopControlAgent,
    "agent_computer_vision": ComputerVisionAgent,
    "agent_gis_verification": GISVerificationAgent,
}


def get_builtin_agent_class(agent_id: str):
    """Get built-in agent class by ID."""
    return BUILTIN_AGENT_CLASSES.get(agent_id)


def create_builtin_agent(agent_id: str, db=None):
    """Create built-in agent instance by ID."""
    cls = get_builtin_agent_class(agent_id)
    if cls:
        return cls(db=db)
    return None