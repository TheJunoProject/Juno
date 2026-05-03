"""JunoScheduler tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from server.scheduler import JunoScheduler


async def test_in_memory_scheduler_lists_jobs(tmp_path: Path) -> None:
    s = JunoScheduler(persist_db_path=None)
    s.start()
    try:
        ran = asyncio.Event()

        async def job() -> None:
            ran.set()

        s.add_cron_job("test", "* * * * *", job)
        jobs = s.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].name == "test"
        assert jobs[0].schedule is not None
    finally:
        s.shutdown()


async def test_run_now_triggers_callable_directly() -> None:
    s = JunoScheduler(persist_db_path=None)
    s.start()
    try:
        ran = asyncio.Event()

        async def job() -> None:
            ran.set()

        s.add_cron_job("manual", "0 0 1 1 *", job)  # essentially never
        await s.run_now("manual")
        assert ran.is_set()
    finally:
        s.shutdown()


async def test_run_now_unknown_raises() -> None:
    s = JunoScheduler(persist_db_path=None)
    s.start()
    try:
        with pytest.raises(KeyError):
            await s.run_now("nonexistent")
    finally:
        s.shutdown()


async def test_persistent_scheduler_creates_db(tmp_path: Path) -> None:
    """SQLAlchemy jobstore writes a SQLite file at the configured path."""
    db = tmp_path / "scheduler.db"
    s = JunoScheduler(persist_db_path=db)
    s.start()
    try:
        async def job_module_func() -> None:
            return None

        # Persistent jobstore can't pickle closures; use a module-level
        # callable so the job survives serialisation.
        s.add_cron_job("persistent", "0 * * * *", _module_level_job)
        assert db.exists()
        jobs = s.list_jobs()
        assert any(j.name == "persistent" for j in jobs)
    finally:
        s.shutdown()


async def _module_level_job() -> None:
    """Module-level callable used by the persistent-store test."""
    return None


async def test_remove_job_clears_registration() -> None:
    s = JunoScheduler(persist_db_path=None)
    s.start()
    try:
        async def job() -> None:
            return None

        s.add_cron_job("removable", "* * * * *", job)
        assert any(j.name == "removable" for j in s.list_jobs())
        s.remove_job("removable")
        assert not any(j.name == "removable" for j in s.list_jobs())
    finally:
        s.shutdown()
