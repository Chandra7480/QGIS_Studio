"""Universal AI GIS Studio — Core Foundation Package.

Provides configuration, database, logging, error handling, event bus,
and job management for the platform.
"""

__version__ = "1.0.0"

from .exceptions import (
    UAGISError,
    ConfigurationError,
    DatabaseError,
    BridgeError,
    MCPError,
    ExecutionError,
    VerificationError,
    SecurityError,
    UAGISPermissionError,
    NotFoundError,
    UAGISTimeoutError,
    ValidationError,
    DependencyError,
    ExtensionError,
    SkillError,
    WorkflowError,
)

__all__ = [
    "UAGISError",
    "ConfigurationError",
    "DatabaseError",
    "BridgeError",
    "MCPError",
    "ExecutionError",
    "VerificationError",
    "SecurityError",
    "UAGISPermissionError",
    "NotFoundError",
    "UAGISTimeoutError",
    "ValidationError",
    "DependencyError",
    "ExtensionError",
    "SkillError",
    "WorkflowError",
]
