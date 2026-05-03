"""Async pub/sub event bus.

The interrupt path documented in CLAUDE.md is:

    Background job → EventBus.publish("interrupts", ...)
                  → WS /api/events/stream subscriber
                  → companion notification

Each subscriber gets its own bounded queue. A slow subscriber back-pressures
itself (its queue overflows and oldest events are dropped) without
affecting other subscribers or the publisher. The publisher never blocks.

Topics are arbitrary strings; the wire-level convention is documented in
the Event payload.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    topic: str
    payload: dict[str, Any]
    # Seconds since epoch. Useful for clients that miss frames and want to
    # debounce or order-recover.
    timestamp: float = field(default_factory=time.time)


# Bounded queue size per subscriber. 100 is plenty for interrupt-style
# events; if a subscriber is so slow that 100 events pile up, dropping
# oldest is the correct behaviour.
DEFAULT_QUEUE_SIZE = 100


class EventBus:
    def __init__(self, *, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        self._queue_size = queue_size
        self._subs: dict[str, list[asyncio.Queue[Event]]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, payload: dict[str, Any]) -> Event:
        event = Event(topic=topic, payload=payload)
        async with self._lock:
            queues = list(self._subs.get(topic, ()))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest, append newest. Logged once per drop so a
                # broken subscriber is visible.
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(event)
                    log.warning(
                        "EventBus: dropped oldest event on full queue (topic=%s)",
                        topic,
                    )
                except asyncio.QueueFull:
                    pass
        return event

    @asynccontextmanager
    async def subscribe(self, topic: str) -> AsyncIterator[AsyncIterator[Event]]:
        """Async context-managed subscription.

        Usage:

            async with bus.subscribe("interrupts") as stream:
                async for event in stream:
                    ...

        Cleanup is automatic — the subscriber's queue is removed from the
        topic's fan-out list when the context exits.
        """
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_size)
        async with self._lock:
            self._subs.setdefault(topic, []).append(q)
        try:
            yield self._consume(q)
        finally:
            async with self._lock:
                if topic in self._subs:
                    try:
                        self._subs[topic].remove(q)
                    except ValueError:
                        pass
                    if not self._subs[topic]:
                        del self._subs[topic]

    async def _consume(self, q: asyncio.Queue[Event]) -> AsyncIterator[Event]:
        while True:
            yield await q.get()

    def subscriber_count(self, topic: str) -> int:
        return len(self._subs.get(topic, ()))
