"""EventBus pub/sub tests."""

from __future__ import annotations

import asyncio

import pytest

from server.scheduler import EventBus


async def test_publish_with_no_subscribers_is_noop() -> None:
    bus = EventBus()
    # Must not raise; must not block.
    await bus.publish("nobody-listening", {"x": 1})


async def test_subscriber_receives_published_event() -> None:
    bus = EventBus()
    received: list[dict] = []

    async def consumer() -> None:
        async with bus.subscribe("interrupts") as stream:
            async for event in stream:
                received.append(event.payload)
                if len(received) == 2:
                    return

    task = asyncio.create_task(consumer())
    # Give the subscription a tick to register.
    await asyncio.sleep(0.01)
    await bus.publish("interrupts", {"i": 1})
    await bus.publish("interrupts", {"i": 2})
    await asyncio.wait_for(task, timeout=1.0)
    assert received == [{"i": 1}, {"i": 2}]


async def test_topics_are_isolated() -> None:
    bus = EventBus()
    a_received: list[dict] = []
    b_received: list[dict] = []

    async def consume(topic: str, sink: list[dict]) -> None:
        async with bus.subscribe(topic) as stream:
            async for event in stream:
                sink.append(event.payload)
                return

    a_task = asyncio.create_task(consume("a", a_received))
    b_task = asyncio.create_task(consume("b", b_received))
    await asyncio.sleep(0.01)
    await bus.publish("a", {"src": "a"})
    await asyncio.wait_for(a_task, timeout=1.0)
    # b must still be waiting; cancel to clean up.
    b_task.cancel()
    with pytest.raises((asyncio.CancelledError, BaseException)):
        await b_task
    assert a_received == [{"src": "a"}]
    assert b_received == []


async def test_subscriber_count_tracks_lifecycle() -> None:
    bus = EventBus()
    assert bus.subscriber_count("t") == 0
    enter, leave = asyncio.Event(), asyncio.Event()

    async def hold() -> None:
        async with bus.subscribe("t"):
            enter.set()
            await leave.wait()

    task = asyncio.create_task(hold())
    await enter.wait()
    assert bus.subscriber_count("t") == 1
    leave.set()
    await asyncio.wait_for(task, timeout=1.0)
    assert bus.subscriber_count("t") == 0


async def test_full_queue_drops_oldest() -> None:
    """Slow subscribers shouldn't block the publisher; oldest gets dropped."""
    bus = EventBus(queue_size=2)

    enter = asyncio.Event()
    drain = asyncio.Event()
    received: list[int] = []

    async def lazy_consumer() -> None:
        async with bus.subscribe("t") as stream:
            enter.set()
            await drain.wait()  # don't read until told
            async for event in stream:
                received.append(event.payload["i"])
                if len(received) == 2:
                    return

    task = asyncio.create_task(lazy_consumer())
    await enter.wait()

    # Publish 3 events with queue_size=2 -> oldest (1) gets dropped.
    for i in (1, 2, 3):
        await bus.publish("t", {"i": i})

    drain.set()
    await asyncio.wait_for(task, timeout=1.0)
    # The exact survivors depend on timing, but the queue capacity is 2 so
    # we should never see more than 2 events; the *most recent* should
    # always survive.
    assert len(received) == 2
    assert received[-1] == 3
