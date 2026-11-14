"""Universal AI GIS Studio — Async Bridge HTTP Server (FastAPI + uvicorn).

Replaces ThreadingHTTPServer with async-first FastAPI for high concurrency.
Uses QgsTask for background PyQGIS operations and WebSocket for real-time updates.

Features:
- Request queue with backpressure (configurable maxsize, default 1000)
- Worker pool for controlled concurrency (configurable, default 10)
- Semaphore for limiting concurrent PyQGIS operations
- Batch dispatch endpoint for processing multiple tools in one HTTP call
- Prometheus metrics for queue depth, wait time, rejection rate
"""

import asyncio
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from bridge.protocol import (
    Request, Response, success_response, error_response,
    VERIFICATION_SUCCESS, VERIFICATION_FAILED, VERIFICATION_PARTIAL,
    VERIFICATION_NEEDS_REVIEW, VERIFICATION_CANCELLED,
)
from bridge.dispatcher import BridgeDispatcher
from bridge.metrics import init_metrics, get_metrics
from core.logging import get_logger

logger = get_logger("bridge.server_async")


# ---- Request/Response Models ----

class DispatchRequest(BaseModel):
    """Pydantic model for /dispatch request."""
    request_id: str
    tool: str
    params: dict = Field(default_factory=dict)
    timeout_seconds: int = 300
    require_approval: bool = False
    metadata: dict = Field(default_factory=dict)


class BatchDispatchRequest(BaseModel):
    """Pydantic model for /batch-dispatch request."""
    requests: list[DispatchRequest] = Field(min_length=1, max_length=500)


class BatchDispatchResponse(BaseModel):
    """Pydantic model for /batch-dispatch response."""
    results: list[dict]
    processed: int
    failed: int


class HealthResponse(BaseModel):
    """Pydantic model for health check."""
    status: str = "ok"
    qgis_connected: bool = True
    bridge_latency_ms: int = 0


class ReadyResponse(BaseModel):
    """Pydantic model for readiness check."""
    ready: bool
    qgis_connected: bool = True
    project_loaded: bool = False
    project_file: Optional[str] = None
    layer_count: int = 0
    bridge_latency_ms: int = 0
    error: Optional[str] = None


# ---- Global State ----

_dispatcher: Optional[BridgeDispatcher] = None
_metrics = init_metrics()
_bridge_up = False
_websocket_connections: set[WebSocket] = set()

# Request queue and worker pool
_request_queue: Optional[asyncio.Queue] = None
_worker_tasks: list[asyncio.Task] = []
_queue_maxsize = 1000
_worker_count = 10
_pyqgis_semaphore: Optional[asyncio.Semaphore] = None
_shutdown_event: Optional[asyncio.Event] = None


# ---- Helper Functions ----

def set_dispatcher(dispatcher: BridgeDispatcher) -> None:
    """Set the global dispatcher instance (called by plugin on startup)."""
    global _dispatcher
    _dispatcher = dispatcher


def get_dispatcher() -> BridgeDispatcher:
    """Get the global dispatcher instance."""
    if _dispatcher is None:
        raise RuntimeError("Bridge dispatcher not initialized")
    return _dispatcher


def init_queue_system(maxsize: int = 1000, worker_count: int = 10, pyqgis_concurrency: int = 5) -> None:
    """Initialize the request queue and worker pool."""
    global _request_queue, _worker_count, _queue_maxsize, _pyqgis_semaphore, _shutdown_event
    
    _queue_maxsize = maxsize
    _worker_count = worker_count
    _request_queue = asyncio.Queue(maxsize=maxsize)
    _pyqgis_semaphore = asyncio.Semaphore(pyqgis_concurrency)
    _shutdown_event = asyncio.Event()
    
    logger.info(f"Request queue initialized: maxsize={maxsize}, workers={worker_count}, pyqgis_concurrency={pyqgis_concurrency}")


async def start_workers() -> None:
    """Start the worker pool."""
    global _worker_tasks
    
    if _request_queue is None:
        init_queue_system()
    
    _worker_tasks = [
        asyncio.create_task(_dispatch_worker(i))
        for i in range(_worker_count)
    ]
    logger.info(f"Started {len(_worker_tasks)} dispatch workers")


async def stop_workers() -> None:
    """Stop the worker pool gracefully."""
    global _worker_tasks
    
    if _shutdown_event:
        _shutdown_event.set()
    
    # Wait for queue to drain
    if _request_queue:
        await _request_queue.join()
    
    # Cancel workers
    for task in _worker_tasks:
        task.cancel()
    
    # Wait for cancellation
    if _worker_tasks:
        await asyncio.gather(*_worker_tasks, return_exceptions=True)
    
    _worker_tasks.clear()
    logger.info("Dispatch workers stopped")


async def _dispatch_worker(worker_id: int) -> None:
    """Worker coroutine that processes requests from the queue."""
    dispatcher = get_dispatcher()
    metrics = get_metrics()
    
    logger.debug(f"Dispatch worker {worker_id} started")
    
    while not _shutdown_event.is_set():
        try:
            # Get request from queue with timeout to allow shutdown check
            queue_item = await asyncio.wait_for(
                _request_queue.get(),
                timeout=1.0
            )
            
            request_data, response_future = queue_item
            req = request_data["request"]
            start_wait = request_data["queue_time"]
            
            # Record queue wait time
            wait_time = time.perf_counter() - start_wait
            metrics.record_queue_wait(wait_time)
            metrics.set_queue_depth(_request_queue.qsize())
            
            # Process request with PyQGIS semaphore
            async with _pyqgis_semaphore:
                try:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, 
                        dispatcher.dispatch, 
                        req
                    )
                    
                    latency = time.perf_counter() - request_data["total_start"]
                    status = "success" if response.status == "ok" else "error"
                    metrics.record_request(req.tool, status, latency)
                    
                    response_future.set_result(response.to_dict())
                    
                except Exception as exc:
                    latency = time.perf_counter() - request_data["total_start"]
                    metrics.record_request(req.tool, "error", latency)
                    logger.exception("Worker %d dispatch error for %s", worker_id, req.tool)
                    
                    if isinstance(exc, HTTPException):
                        response_future.set_exception(exc)
                    else:
                        response_future.set_result(
                            error_response(
                                req.request_id, "INTERNAL_ERROR", str(exc),
                                verification_state=VERIFICATION_FAILED
                            ).to_dict()
                        )
            
            _request_queue.task_done()
            
        except asyncio.TimeoutError:
            # Timeout allows checking shutdown_event
            continue
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Worker %d unexpected error", worker_id)
            # Don't break - continue processing
    
    logger.debug(f"Dispatch worker {worker_id} stopped")


async def check_auth(request: Request) -> bool:
    """Check authentication token from Authorization header."""
    dispatcher = get_dispatcher()
    auth_token = getattr(dispatcher, 'auth_token', None)
    
    if auth_token is None:
        raise HTTPException(
            status_code=500,
            detail={"code": "CONFIG_ERROR", "message": "Bridge auth token not configured. Set UAGIS_BRIDGE_AUTH_TOKEN environment variable or configure auth_token in bridge server. Authentication is mandatory in production."}
        )
    
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {auth_token}":
        return True
    
    raise HTTPException(
        status_code=401,
        detail={"code": "UNAUTHORIZED", "message": "Invalid or missing auth token"}
    )


async def check_ready(dispatcher: BridgeDispatcher = Depends(get_dispatcher)) -> dict:
    """Check if bridge is ready to handle requests."""
    try:
        executor = dispatcher.executor
        health = await asyncio.get_event_loop().run_in_executor(None, executor.health)
        
        if not health.get("qgis_connected", False):
            return {
                "ready": False,
                "reason": "QGIS not connected",
                "health": health,
            }
        
        project_info = await asyncio.get_event_loop().run_in_executor(None, executor.inspect_project)
        project_loaded = bool(project_info.get("project_file"))
        
        return {
            "ready": True,
            "qgis_connected": True,
            "project_loaded": project_loaded,
            "project_file": project_info.get("project_file"),
            "layer_count": health.get("layer_count", 0),
        }
    except Exception as exc:
        logger.exception("Readiness check failed")
        return {
            "ready": False,
            "reason": f"readiness check error: {exc}",
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _bridge_up
    
    # Initialize queue system
    init_queue_system()
    await start_workers()
    
    logger.info("Async Bridge Server starting up...")
    _bridge_up = True
    _metrics.set_bridge_up(True)
    
    yield
    
    logger.info("Async Bridge Server shutting down...")
    await stop_workers()
    _bridge_up = False
    _metrics.set_bridge_up(False)


app = FastAPI(
    title="Universal AI GIS Studio Bridge",
    description="Async QGIS Bridge Server for MCP integration",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/ready", response_model=ReadyResponse)
async def ready(dispatcher: BridgeDispatcher = Depends(get_dispatcher)):
    """Readiness check - verifies bridge can process requests."""
    result = await check_ready(dispatcher)
    result["bridge_latency_ms"] = 0
    if result.get("ready"):
        return ReadyResponse(**result)
    else:
        return ReadyResponse(
            ready=False,
            error=result.get("reason", "Service not ready"),
            bridge_latency_ms=0,
        )


@app.post("/dispatch")
async def dispatch(
    req: DispatchRequest,
    request: Request,
    authorized: bool = Depends(check_auth),
):
    """Dispatch a tool call to the bridge via queue (with backpressure)."""
    metrics = get_metrics()
    
    # Check if queue is full (backpressure)
    if _request_queue is None or _request_queue.full():
        metrics.record_rejected()
        raise HTTPException(
            status_code=429,
            detail={"code": "QUEUE_FULL", "message": "Request queue full, try again later"},
            headers={"Retry-After": "1"}
        )
    
    # Create future for response
    response_future: asyncio.Future = asyncio.get_event_loop().create_future()
    
    queue_item = {
        "request": req,
        "queue_time": time.perf_counter(),
        "total_start": time.perf_counter(),
    }
    
    # Put in queue
    await _request_queue.put((queue_item, response_future))
    metrics.set_queue_depth(_request_queue.qsize())
    
    # Wait for response
    try:
        result = await response_future
        return JSONResponse(content=result)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Dispatch error for %s", req.tool)
        if isinstance(exc, HTTPException):
            raise
        return JSONResponse(
            status_code=500,
            content=error_response(
                req.request_id, "INTERNAL_ERROR", str(exc),
                verification_state=VERIFICATION_FAILED
            ).to_dict()
        )


@app.post("/batch-dispatch", response_model=BatchDispatchResponse)
async def batch_dispatch(
    batch: BatchDispatchRequest,
    request: Request,
    authorized: bool = Depends(check_auth),
):
    """Batch dispatch multiple tool calls in a single HTTP request."""
    metrics = get_metrics()
    metrics.record_batch_request("received")
    
    if _request_queue is None:
        raise HTTPException(status_code=503, detail="Queue not initialized")
    
    results = []
    processed = 0
    failed = 0
    
    for req in batch.requests:
        # Check queue capacity
        if _request_queue.full():
            metrics.record_rejected()
            failed += 1
            results.append(error_response(
                req.request_id, "QUEUE_FULL", "Request queue full",
                verification_state=VERIFICATION_FAILED
            ).to_dict())
            continue
        
        # Create future for response
        response_future: asyncio.Future = asyncio.get_event_loop().create_future()
        
        queue_item = {
            "request": req,
            "queue_time": time.perf_counter(),
            "total_start": time.perf_counter(),
        }
        
        await _request_queue.put((queue_item, response_future))
        
        # Wait for response (with timeout)
        try:
            result = await asyncio.wait_for(response_future, timeout=req.timeout_seconds)
            results.append(result)
            processed += 1
        except asyncio.TimeoutError:
            failed += 1
            results.append(error_response(
                req.request_id, "TIMEOUT", f"Request timed out after {req.timeout_seconds}s",
                verification_state=VERIFICATION_FAILED
            ).to_dict())
        except Exception as exc:
            failed += 1
            results.append(error_response(
                req.request_id, "INTERNAL_ERROR", str(exc),
                verification_state=VERIFICATION_FAILED
            ).to_dict())
    
    metrics.set_queue_depth(_request_queue.qsize())
    
    if failed == 0:
        metrics.record_batch_request("success")
    elif processed == 0:
        metrics.record_batch_request("failed")
    else:
        metrics.record_batch_request("partial")
    
    return BatchDispatchResponse(
        results=results,
        processed=processed,
        failed=failed,
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates (screen streaming, job progress, etc.)."""
    await websocket.accept()
    _websocket_connections.add(websocket)
    logger.info("WebSocket connected. Total connections: %d", len(_websocket_connections))
    
    try:
        while True:
            data = await websocket.receive_json()
            
            msg_type = data.get("type")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": data.get("timestamp")})
            
            elif msg_type == "subscribe":
                subscription = data.get("subscription", {})
                await websocket.send_json({
                    "type": "subscribed",
                    "subscription": subscription,
                })
            
            elif msg_type == "screen_stream":
                await _handle_screen_stream(websocket, data.get("params", {}))
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as exc:
        logger.exception("WebSocket error")
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        _websocket_connections.discard(websocket)
        logger.info("WebSocket connection closed. Total connections: %d", len(_websocket_connections))


async def _handle_screen_stream(websocket: WebSocket, params: dict):
    """Handle screen streaming via WebSocket."""
    dispatcher = get_dispatcher()
    executor = dispatcher.executor
    interval = params.get("interval_ms", 100)
    max_frames = params.get("max_frames", 0)
    
    frame_count = 0
    try:
        while True:
            result = await asyncio.get_event_loop().run_in_executor(None, executor.capture_canvas)
            
            await websocket.send_json({
                "type": "screen_frame",
                "frame": frame_count,
                "image_base64": result.get("image_base64"),
                "width": result.get("width"),
                "height": result.get("height"),
                "format": result.get("format"),
            })
            
            frame_count += 1
            if max_frames > 0 and frame_count >= max_frames:
                break
            
            await asyncio.sleep(interval / 1000.0)
    
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("Screen stream error")
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    output = get_metrics().get_metrics_output()
    return PlainTextResponse(
        content=output.decode("utf-8"),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


# ---- Server Classes ----

class AsyncBridgeServer:
    """Async Bridge Server using FastAPI + uvicorn."""
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        auth_token: Optional[str] = None,
        queue_maxsize: int = 1000,
        worker_count: int = 10,
        pyqgis_concurrency: int = 5,
    ):
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.queue_maxsize = queue_maxsize
        self.worker_count = worker_count
        self.pyqgis_concurrency = pyqgis_concurrency
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
            loop="asyncio",
        )
    
    def start(self, dispatcher: BridgeDispatcher) -> bool:
        """Start the async bridge server."""
        try:
            if self._running:
                logger.warning("Async bridge server already running")
                return True
            
            # Re-initialize queue with custom settings
            init_queue_system(self.queue_maxsize, self.worker_count, self.pyqgis_concurrency)
            
            # Set global dispatcher
            set_dispatcher(dispatcher)
            dispatcher.auth_token = self.auth_token
            
            # Create and start uvicorn server in a thread
            self._server = uvicorn.Server(self._config)
            self._thread = threading.Thread(
                target=self._run_server,
                daemon=True,
                name="uagis-bridge-async",
            )
            self._thread.start()
            
            # Wait for server to start
            start_time = time.time()
            while not self._server.started and (time.time() - start_time) < 10:
                time.sleep(0.1)
            
            if not self._server.started:
                logger.error("Failed to start async bridge server within timeout")
                return False
            
            self._running = True
            logger.info("Async Bridge server listening on http://%s:%s", self.host, self.port)
            return True
            
        except Exception as exc:
            logger.exception("Unexpected error starting async bridge server: %s", exc)
            self._running = False
            return False
    
    def _run_server(self):
        """Run the uvicorn server (blocking)."""
        asyncio.run(self._server.serve())
    
    def stop(self) -> None:
        """Stop the async bridge server."""
        try:
            if not self._running or self._server is None:
                return
            self._server.should_exit = True
            if self._thread:
                self._thread.join(timeout=5.0)
        except Exception:
            pass
        finally:
            self._running = False
            logger.info("Async Bridge server stopped")
    
    @property
    def running(self) -> bool:
        return self._running


# Backward compatibility: async wrapper that mimics the old BridgeServer interface
class BridgeServer:
    """Backward-compatible wrapper for existing plugin code."""
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        auth_token: Optional[str] = None,
    ):
        self._async_server = AsyncBridgeServer(host, port, auth_token)
        self._metrics = get_metrics()
    
    def start(self, dispatcher) -> bool:
        return self._async_server.start(dispatcher)
    
    def stop(self) -> None:
        self._async_server.stop()
    
    @property
    def running(self) -> bool:
        return self._async_server.running
    
    @property
    def metrics(self):
        return self._metrics
    
    @property
    def port(self) -> int:
        return self._async_server.port