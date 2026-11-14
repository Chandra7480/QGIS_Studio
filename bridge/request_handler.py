"""Universal AI GIS Studio — Bridge HTTP request handler.

Handles authenticated POST /dispatch requests from the MCP server.
Returns JSON protocol Responses.
"""

import json
import time
from http.server import BaseHTTPRequestHandler

from bridge.protocol import Request, error_response
from bridge.metrics import get_metrics
from core.logging import get_logger
from core.exceptions import ConfigurationError

logger = get_logger("bridge.request_handler")


class BridgeRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for bridge dispatch. dispatcher is injected via class attr."""

    dispatcher = None
    auth_token = None

    def log_message(self, format, *args):  # noqa: A002
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status_code, text: str, content_type: str = "text/plain"):
        body = text.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        if self.auth_token is None:
            raise ConfigurationError(
                "Bridge auth token not configured. Set UAGIS_BRIDGE_AUTH_TOKEN environment variable "
                "or configure auth_token in bridge server. Authentication is mandatory in production."
            )
        auth = self.headers.get("Authorization", "")
        if auth == f"Bearer {self.auth_token}":
            return True
        return False

    def _check_ready(self) -> tuple[bool, dict]:
        """Check if bridge is ready to handle requests.
        
        Returns:
            (ready: bool, details: dict)
        """
        if self.dispatcher is None:
            return False, {"ready": False, "reason": "dispatcher not initialized"}

        try:
            # Check executor health
            executor = self.dispatcher.executor
            health = executor.health()
            
            if not health.get("qgis_connected", False):
                return False, {"ready": False, "reason": "QGIS not connected", "health": health}
            
            # Check if project is loaded (optional - some tools work without project)
            project_info = executor.inspect_project()
            project_loaded = bool(project_info.get("project_file"))
            
            return True, {
                "ready": True,
                "qgis_connected": True,
                "project_loaded": project_loaded,
                "project_file": project_info.get("project_file"),
                "layer_count": health.get("layer_count", 0),
            }
        except Exception as exc:
            logger.exception("Readiness check failed")
            return False, {"ready": False, "reason": f"readiness check error: {exc}"}

    def do_POST(self):  # noqa: N802
        if self.path not in ("/dispatch", "/health", "/ready"):
            self._send_json(404, error_response("unknown", "NOT_FOUND",
                                                "Endpoint not found").to_dict())
            return

        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        if self.path == "/ready":
            ready, details = self._check_ready()
            status_code = 200 if ready else 503
            self._send_json(status_code, details)
            return

        if not self._check_auth():
            self._send_json(401, error_response("unknown", "UNAUTHORIZED",
                                                "Invalid or missing auth token").to_dict())
            return

        start_time = time.perf_counter()
        metrics = get_metrics()

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, ValueError) as exc:
            latency = time.perf_counter() - start_time
            metrics.record_request("unknown", "validation_error", latency)
            self._send_json(400, error_response("unknown", "VALIDATION_ERROR",
                                                f"Invalid JSON body: {exc}").to_dict())
            return

        request_id = data.get("request_id")
        tool = data.get("tool")
        if not request_id or not tool:
            latency = time.perf_counter() - start_time
            metrics.record_request("unknown", "validation_error", latency)
            self._send_json(400, error_response(request_id or "unknown", "VALIDATION_ERROR",
                                                "request_id and tool are required").to_dict())
            return

        req = Request(
            request_id=request_id,
            tool=tool,
            params=data.get("params", {}),
            timeout_seconds=data.get("timeout_seconds", 300),
            require_approval=data.get("require_approval", False),
            metadata=data.get("metadata", {}),
        )

        response = self.dispatcher.dispatch(req)
        
        latency = time.perf_counter() - start_time
        status = "success" if response.status == "ok" else "error"
        metrics.record_request(tool, status, latency)
        
        self._send_json(200, response.to_dict())

    def do_GET(self):  # noqa: N802
        metrics = get_metrics()
        
        if self.path in ("/health", "/healthz", "/livez"):
            # Liveness probe - simple check that process is alive
            health_checker = get_health_checker()
            health = health_checker.run_liveness()
            status_code = 200 if health.is_healthy() else 503
            self._send_json(status_code, health.to_dict())
            return
        
        if self.path in ("/ready", "/readyz"):
            # Readiness probe - check all subsystems
            start_time = time.perf_counter()
            health_checker = get_health_checker()
            health = health_checker.run_readiness()
            latency = time.perf_counter() - start_time
            metrics.record_request("ready", "success" if health.is_ready() else "error", latency)
            status_code = 200 if health.is_ready() else 503
            self._send_json(status_code, health.to_dict())
            return
            
        if self.path == "/metrics":
            # Prometheus metrics endpoint
            output = metrics.get_metrics_output()
            self._send_text(200, output.decode("utf-8"), "text/plain; version=0.0.4; charset=utf-8")
            return
            
        self._send_json(404, {"error": "not_found"})
