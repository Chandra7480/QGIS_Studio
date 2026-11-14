"""Universal AI GIS Studio — Bridge protocol.

Typed request/response structures exchanged between the MCP server and
the QGIS Bridge. All responses include a request_id for tracing and a
verification_state field so the AI never infers success from submission.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from datetime import datetime, timezone

VERIFICATION_SUCCESS = "SUCCESS"
VERIFICATION_PARTIAL = "PARTIAL_SUCCESS"
VERIFICATION_FAILED = "FAILED"
VERIFICATION_NEEDS_REVIEW = "NEEDS_REVIEW"
VERIFICATION_CANCELLED = "CANCELLED"

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"


@dataclass
class Request:
    request_id: str
    tool: str
    params: dict = field(default_factory=dict)
    timeout_seconds: int = 300
    require_approval: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class Response:
    request_id: str
    status: str  # 'ok' | 'error'
    result: Optional[dict] = None
    error: Optional[dict] = None
    verification_state: Optional[str] = None
    job_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return asdict(self)


def success_response(request_id, result=None, verification_state=VERIFICATION_SUCCESS,
                     job_id=None):
    return Response(
        request_id=request_id, status="ok", result=result or {},
        verification_state=verification_state, job_id=job_id,
    )


def error_response(request_id, error_code, message, context=None, job_id=None,
                   verification_state=VERIFICATION_FAILED):
    return Response(
        request_id=request_id, status="error",
        error={"code": error_code, "message": message, "context": context or {}},
        verification_state=verification_state, job_id=job_id,
    )
