"""Universal AI GIS Studio — Bridge Package."""

from bridge.socket_server import SocketServer
from bridge.registry import COMMANDS, command
from bridge.wire import (
    HEADER_STRUCT,
    MAX_MESSAGE_SIZE,
    RECV_CHUNK_SIZE,
    OutboundBuffer,
    OutboundOverflow,
    frame,
    BATCH_BLOCKED_COMMANDS,
    UNRECORDED_COMMANDS,
)

__all__ = [
    "SocketServer",
    "COMMANDS",
    "command",
    "BATCH_BLOCKED_COMMANDS",
    "UNRECORDED_COMMANDS",
    "HEADER_STRUCT",
    "MAX_MESSAGE_SIZE",
    "RECV_CHUNK_SIZE",
    "OutboundBuffer",
    "OutboundOverflow",
    "frame",
]

# Backward compatibility
BridgeServer = SocketServer