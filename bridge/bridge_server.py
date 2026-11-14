"""Universal AI GIS Studio — Bridge HTTP + WebSocket server.

Runs inside QGIS on localhost. Serves the BridgeRequestHandler which
dispatches to the PyQGISExecutor. Threaded so QGIS GUI stays responsive.
Provides WebSocket endpoint /ws/screen for real-time screen streaming.
Health endpoints: /healthz (liveness), /readyz (readiness), /livez (liveness alias).
"""

import threading
import logging as _logging
import json
import asyncio
import time
from http.server import ThreadingHTTPServer
from typing import Optional, Callable, Set

from bridge.request_handler import BridgeRequestHandler
from bridge.metrics import init_metrics, get_metrics
from core.logging import get_logger
from monitoring.health import get_health_checker, init_health_checker, HealthStatus

logger = get_logger("bridge.server")


class WebSocketServer:
    """Simple WebSocket server for screen streaming."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8767):
        self.host = host
        self.port = port
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._clients: Set[asyncio.WebSocketServerProtocol] = set()
        self._frame_callback_id: Optional[int] = None
        self._executor = None

    def start(self, executor) -> bool:
        """Start WebSocket server."""
        try:
            if self._running:
                return True
            self._executor = executor
            
            # Register frame callback with executor
            self._frame_callback_id = executor.screen_capture_register_stream_callback(
                self._on_frame
            )
            
            self._thread = threading.Thread(
                target=self._run_server,
                daemon=True,
                name="uagis-websocket"
            )
            self._thread.start()
            self._running = True
            logger.info("WebSocket server started on ws://%s:%s", self.host, self.port)
            return True
        except Exception as exc:
            logger.exception("Failed to start WebSocket server: %s", exc)
            return False

    def _run_server(self):
        """Run the asyncio WebSocket server in a thread."""
        asyncio.run(self._serve())

    async def _serve(self):
        """Async WebSocket server."""
        try:
            import websockets
        except ImportError:
            logger.warning("websockets library not available, WebSocket server disabled")
            return

        async def handler(websocket):
            self._clients.add(websocket)
            logger.debug("WebSocket client connected: %s", websocket.remote_address)
            try:
                async for message in websocket:
                    # Handle incoming messages (ping, config changes)
                    try:
                        data = json.loads(message)
                        if data.get("type") == "ping":
                            await websocket.send(json.dumps({"type": "pong"}))
                        elif data.get("type") == "config":
                            # Handle config changes (interval, region, etc.)
                            await self._handle_config(websocket, data)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass
            finally:
                self._clients.discard(websocket)
                logger.debug("WebSocket client disconnected")

        self._server = await websockets.serve(handler, self.host, self.port)
        await self._server.wait_closed()

    async def _handle_config(self, websocket, data: dict):
        """Handle configuration messages from client."""
        if not self._executor:
            return
        
        config = data.get("config", {})
        if "interval" in config:
            # Restart periodic with new interval
            self._executor.screen_capture_stop_periodic()
            region = config.get("region")
            include_cursor = config.get("include_cursor", False)
            self._executor.screen_capture_start_periodic(
                interval_seconds=config["interval"],
                region=region,
                include_cursor=include_cursor
            )
            await websocket.send(json.dumps({
                "type": "config_ack",
                "config": config
            }))

    def _on_frame(self, frame: dict):
        """Callback for new screen frames - broadcast to all clients."""
        if not self._clients:
            return
        
        # Send frame to all connected clients
        message = json.dumps({
            "type": "frame",
            "data": frame
        })
        
        # Schedule sends on the event loop
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, create a task for the server thread's loop
            pass
        
        if loop and loop.is_running():
            for client in self._clients.copy():
                asyncio.create_task(self._safe_send(client, message))

    async def _safe_send(self, client, message: str):
        """Safely send message to client."""
        try:
            await client.send(message)
        except Exception:
            self._clients.discard(client)

    def stop(self):
        """Stop WebSocket server."""
        if not self._running:
            return
        
        # Unregister frame callback
        if self._frame_callback_id is not None and self._executor:
            self._executor.screen_capture_unregister_stream_callback(self._frame_callback_id)
            self._frame_callback_id = None
        
        # Stop periodic capture
        if self._executor:
            self._executor.screen_capture_stop_periodic()
        
        # Close all client connections
        for client in self._clients.copy():
            try:
                asyncio.run_coroutine_threadsafe(client.close(), asyncio.get_event_loop())
            except Exception:
                pass
        self._clients.clear()
        
        self._running = False
        logger.info("WebSocket server stopped")


class BridgeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765,
                 auth_token: str | None = None,
                 ws_port: int = 8767):
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.ws_port = ws_port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._metrics = init_metrics()
        self._ws_server = WebSocketServer(host, ws_port)
        self._dispatcher = None
        self._start_time = time.time()
        self._health_checker = get_health_checker()

    def start(self, dispatcher, db=None, orchestrator=None, job_manager=None,
              circuit_breaker=None, quota_manager=None, temp_manager=None,
              rate_limiter=None, mcp_server=None) -> bool:
        """Start bridge server. Returns True if started, False if disabled."""
        try:
            if self._running:
                logger.warning("Bridge server already running")
                return True
            self._dispatcher = dispatcher
            BridgeRequestHandler.dispatcher = dispatcher
            BridgeRequestHandler.auth_token = self.auth_token

            # Initialize health checker with all subsystems
            executor = dispatcher.executor
            init_health_checker(
                version="1.0.0",
                start_time=self._start_time,
                bridge_server=self,
                executor=executor,
                db=db,
                mcp_server=mcp_server,
                orchestrator=orchestrator,
                job_manager=job_manager,
                circuit_breaker=circuit_breaker,
                quota_manager=quota_manager,
                temp_manager=temp_manager,
                rate_limiter=rate_limiter,
            )

            # Set bridge up metric
            self._metrics.set_bridge_up(True)

            # Try preferred port, then fallbacks if busy — NEVER raise
            ports_to_try = [self.port, self.port + 1, self.port + 2,
                            self.port + 3, self.port + 4, self.port + 5]
            bound = False
            last_error = None
            for port in ports_to_try:
                try:
                    self._server = ThreadingHTTPServer((self.host, port),
                                                       BridgeRequestHandler)
                    self.port = port
                    bound = True
                    break
                except OSError as exc:
                    last_error = exc
                    logger.warning("Port %d busy, trying next...", port)
                    continue

            if not bound:
                logger.warning(
                    "Cannot bind bridge to %s: all ports %s busy. Last error: %s. "
                    "Bridge server disabled (running=False).",
                    self.host, ports_to_try, last_error,
                )
                self._server = None
                self._running = False
                self._metrics.set_bridge_up(False)
                return False
            
            # Start WebSocket server for screen streaming
            self._ws_server.start(executor)

            self._thread = threading.Thread(target=self._server.serve_forever,
                                            daemon=True, name="uagis-bridge")
            self._thread.start()
            self._running = True
            logger.info("Bridge server listening on http://%s:%s", self.host, self.port)
            logger.info("WebSocket server listening on ws://%s:%s", self.host, self.ws_port)
            logger.info("Health endpoints: /healthz (liveness), /readyz (readiness), /livez (liveness)")
            return True
        except Exception as exc:
            logger.exception("Unexpected error starting bridge server: %s", exc)
            self._server = None
            self._running = False
            self._metrics.set_bridge_up(False)
            return False

    def stop(self) -> None:
        try:
            # Stop WebSocket server
            self._ws_server.stop()
            
            if not self._running or self._server is None:
                return
            self._server.shutdown()
            self._server.server_close()
        except Exception:
            pass
        finally:
            self._running = False
            self._metrics.set_bridge_up(False)
            logger.info("Bridge server stopped")

    @property
    def running(self) -> bool:
        return self._running

    @property
    def metrics(self):
        return self._metrics
    
    @property
    def ws_server(self):
        return self._ws_server
