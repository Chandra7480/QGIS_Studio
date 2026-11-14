"""Universal AI GIS Studio — In-process event bus.

Publish/subscribe bus for decoupled module communication. Subscribers
receive event dicts. Used for job status updates, agent messages, and
cross-module notifications.
"""

import logging
from typing import Callable, Dict, List

logger = logging.getLogger("uagis.event_bus")


class EventBus:
    """Simple in-process pub/sub event bus."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[dict], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[dict], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(callback)
        logger.debug("Subscribed to %s", event_type)

    def unsubscribe(self, event_type: str, callback: Callable[[dict], None]) -> None:
        callbacks = self._subscribers.get(event_type, [])
        if callback in callbacks:
            callbacks.remove(callback)

    def publish(self, event_type: str, payload: dict) -> None:
        callbacks = list(self._subscribers.get(event_type, []))
        if not callbacks:
            logger.debug("No subscribers for %s", event_type)
            return
        for cb in callbacks:
            try:
                cb(dict(payload))
            except Exception as exc:
                logger.exception("Event subscriber %s failed for %s: %s", cb, event_type, exc)
