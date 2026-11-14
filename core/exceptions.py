"""Universal AI GIS Studio — Base exception hierarchy.

All platform exceptions derive from UAGISError. Each exception carries
a structured error code, human-readable message, and optional context
dict for logging and MCP structured error responses.
"""


class UAGISError(Exception):
    """Base exception for all Universal AI GIS Studio errors."""

    error_code = "UAGIS_ERROR"
    http_status = 500

    def __init__(self, message, error_code=None, context=None, cause=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.error_code
        self.context = context or {}
        self.cause = cause

    def to_dict(self):
        return {
            "error": self.error_code,
            "message": self.message,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None,
        }

    def __str__(self):
        return f"[{self.error_code}] {self.message}"


class ConfigurationError(UAGISError):
    """Raised when configuration is invalid or missing."""

    error_code = "CONFIG_ERROR"
    http_status = 400


class DatabaseError(UAGISError):
    """Raised on database layer failures."""

    error_code = "DATABASE_ERROR"
    http_status = 500


class BridgeError(UAGISError):
    """Raised by the QGIS Bridge layer."""

    error_code = "BRIDGE_ERROR"
    http_status = 500


class MCPError(UAGISError):
    """Raised by the MCP server layer."""

    error_code = "MCP_ERROR"
    http_status = 500


class ExecutionError(UAGISError):
    """Raised when a GIS operation fails to execute."""

    error_code = "EXECUTION_ERROR"
    http_status = 500


class VerificationError(UAGISError):
    """Raised when verification of an operation fails."""

    error_code = "VERIFICATION_ERROR"
    http_status = 422


class SecurityError(UAGISError):
    """Raised on security policy violations."""

    error_code = "SECURITY_ERROR"
    http_status = 403


class UAGISPermissionError(UAGISError):
    """Raised when an agent/tool lacks required permission."""

    error_code = "PERMISSION_DENIED"
    http_status = 403


class NotFoundError(UAGISError):
    """Raised when a requested resource is not found."""

    error_code = "NOT_FOUND"
    http_status = 404


class UAGISTimeoutError(UAGISError):
    """Raised when an operation times out."""

    error_code = "TIMEOUT"
    http_status = 504


class ValidationError(UAGISError):
    """Raised when input/output validation fails."""

    error_code = "VALIDATION_ERROR"
    http_status = 400


class DependencyError(UAGISError):
    """Raised when a required dependency is missing or incompatible."""

    error_code = "DEPENDENCY_ERROR"
    http_status = 500


class ExtensionError(UAGISError):
    """Raised when an extension fails validation or loading."""

    error_code = "EXTENSION_ERROR"
    http_status = 400


class SkillError(UAGISError):
    """Raised when a skill fails validation or execution."""

    error_code = "SKILL_ERROR"
    http_status = 400


class WorkflowError(UAGISError):
    """Raised when a workflow execution fails."""

    error_code = "WORKFLOW_ERROR"
    http_status = 500
