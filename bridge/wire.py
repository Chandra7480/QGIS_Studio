"""Universal AI GIS Studio — Wire Protocol.

Length-prefixed JSON framing for socket communication.
"""

import struct

# Length-prefixed framing: 4-byte big-endian length + JSON payload
HEADER_STRUCT = struct.Struct(">I")

MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10 MB
RECV_CHUNK_SIZE = 65536


class OutboundOverflow(Exception):
    """Raised when outbound buffer exceeds limit."""
    pass


class OutboundBuffer:
    """Buffer for queuing outbound responses with backpressure."""

    MAX_SIZE = 5 * 1024 * 1024  # 5 MB per client

    def __init__(self):
        self._buf = bytearray()
        self._sent = 0

    def append(self, data: bytes):
        if len(self._buf) - self._sent + len(data) > self.MAX_SIZE:
            raise OutboundOverflow("Outbound buffer limit exceeded")
        self._buf.extend(data)

    def flush(self, sock) -> bool:
        """Flush as much as possible. Return True if buffer empty."""
        if self._sent >= len(self._buf):
            return True
        try:
            sent = sock.send(self._buf[self._sent:])
            self._sent += sent
            if self._sent >= len(self._buf):
                return True
            return False
        except BlockingIOError:
            return False
        except Exception:
            raise

    def __len__(self):
        return len(self._buf) - self._sent


def frame(payload: bytes) -> bytes:
    """Encode payload with 4-byte big-endian length prefix."""
    return HEADER_STRUCT.pack(len(payload)) + payload


# Re-export for compatibility
HEADER_STRUCT = __import__('struct').Struct(">I")
MAX_MESSAGE_SIZE = 10 * 1024 * 1024
RECV_CHUNK_SIZE = 65536

BATCH_BLOCKED_COMMANDS = {
    "execute_code",
    "remove_layer",
    "delete_features",
    "start_editing",
    "commit_edits",
    "rollback_edits",
    "execute_processing",
    "execute_processing_batch",
    "create_checkpoint",
    "restore_checkpoint",
    "execute_sql",
    "field_calculator",
    "add_features",
    "update_features",
    "update_feature_geometry",
    "delete_features",
}

UNRECORDED_COMMANDS = {
    "ping",
    "diagnose",
    "get_message_log",
    "get_qgis_info",
    "get_raster_info",
    "get_setting",
    "list_qgis_instances",
    "get_project_variables",
    "get_layer_property",
    "get_layer_extent",
    "get_layer_crs",
    "get_active_layer",
    "get_layer_features",
    "get_layer_extent",
    "get_field_statistics",
    "get_unique_values",
    "get_layer_labeling",
    "get_layer_style",
    "get_raster_info",
    "get_canvas_screenshot",
    "get_canvas_extent",
    "get_canvas_scale",
    "compound",
    "get_compound_groups",
}