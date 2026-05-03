"""Thin async wrapper over APScheduler.

`JunoScheduler` is what the rest of the server talks to. It hides the
APScheduler API surface and keeps registration, listing, and one-off
triggering behind one consistent interface.

Design choices:

- AsyncIOScheduler runs jobs on the FastAPI event loop, so jobs can
  use the same `httpx.AsyncClient` and inference router instances the
  request path uses.
- SQLAlchemyJobStore against SQLite gives persistence across restarts.
  When `persist_jobs=False` we use the default in-memory store instead.
- Cron expressions follow the standard 5-field format
  (minute hour day month day_of_week). Other trigger kinds (one-off,
  interval) can be added later.
- Jobs are registered with `coalesce=True` and `misfire_grace_time`
  so that long server downtime doesn't replay a queue of missed runs.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

log = logging.getLogger(__name__)


JobCallable = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class JobInfo:
    name: str
    schedule: str | None  # cron expression, or None for date / interval
    next_run: datetime | None
    pending: bool


class JunoScheduler:
    def __init__(
        self,
        *,
        persist_db_path: Path | None = None,
    ) -> None:
        if persist_db_path is None:
            jobstores = {"default": MemoryJobStore()}
        else:
            persist_db_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{persist_db_path}"
            jobstores = {"default": SQLAlchemyJobStore(url=url)}

        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                # Drop missed runs older than 5 minutes — long downtime
                # shouldn't replay a queue of identical "summarise RSS" jobs.
                "misfire_grace_time": 300,
            },
        )
        self._callables: dict[str, JobCallable] = {}

    # ---- lifecycle ------------------------------------------------------

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            log.info("Juno scheduler started.")

    def shutdown(self) -> None:
        if self._scheduler.running:
            # wait=False: don't block server shutdown on a running job;
            # APScheduler will let the in-flight callable finish in the
            # background while we tear down.
            self._scheduler.shutdown(wait=False)
            log.info("Juno scheduler stopped.")

    # ---- job registration -----------------------------------------------

    def add_cron_job(
        self,
        name: str,
        cron: str,
        func: JobCallable,
        *,
        replace_existing: bool = True,
    ) -> None:
        """Register a coroutine to run on a 5-field cron schedule.

        The callable takes no args; jobs that need state hold it via
        closure or class instance.
        """
        trigger = CronTrigger.from_crontab(cron)
        self._scheduler.add_job(
            func=func,
            trigger=trigger,
            id=name,
            name=name,
            replace_existing=replace_existing,
        )
        self._callables[name] = func

    def add_one_off_job(
        self,
        name: str,
        when: datetime,
        func: JobCallable,
        *,
        replace_existing: bool = True,
    ) -> None:
        self._scheduler.add_job(
            func=func,
            trigger=DateTrigger(run_date=when),
            id=name,
            name=name,
            replace_existing=replace_existing,
        )
        self._callables[name] = func

    def remove_job(self, name: str) -> None:
        try:
            self._scheduler.remove_job(name)
        except Exception as e:  # APScheduler raises various exception types
            log.debug("remove_job(%s) failed: %s", name, e)
        self._callables.pop(name, None)

    # ---- introspection / control ----------------------------------------

    def list_jobs(self) -> list[JobInfo]:
        out: list[JobInfo] = []
        for job in self._scheduler.get_jobs():
            schedule = None
            if isinstance(job.trigger, CronTrigger):
                # CronTrigger.fields preserves the canonical form; render
                # back to a 5-field expression for display.
                schedule = " ".join(str(f) for f in job.trigger.fields[1:6])
            out.append(
                JobInfo(
                    name=job.id,
                    schedule=schedule,
                    next_run=job.next_run_time,
                    pending=job.pending,
                )
            )
        return out

    async def run_now(self, name: str) -> None:
        """Manually trigger a registered job (out-of-schedule).

        Bypasses APScheduler's queue and just awaits the callable directly,
        so the caller sees the job's exceptions and timing.
        """
        if name not in self._callables:
            raise KeyError(f"No registered job named '{name}'")
        await self._callables[name]()
