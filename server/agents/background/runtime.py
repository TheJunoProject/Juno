"""Background Layer runtime.

Owns the lifecycle of the registered background jobs:
- Constructs each job with a shared `JobContext`.
- Registers it with the scheduler at the configured cron.
- Wraps the job invocation so report write + error handling + last-run
  bookkeeping happen consistently.
- Exposes "list jobs", "run now", "list reports" for the API.

The runtime is deliberately the only thing that touches `reports_dir`
on disk for jobs — jobs return `JobResult`, the runtime persists it.
That keeps job code testable without a filesystem.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from server.agents.background.jobs import (
    BackgroundJob,
    CalendarJob,
    EmailJob,
    JobContext,
    JobResult,
    MessagesJob,
    RSSJob,
)
from server.config import JunoConfig
from server.config.schema import StubJobConfig
from server.inference import InferenceRouter
from server.integrations import IntegrationsRouter
from server.scheduler import EventBus, JunoScheduler

log = logging.getLogger(__name__)


@dataclass
class JobRunRecord:
    name: str
    started_at: datetime
    duration_seconds: float
    success: bool
    error: str | None = None


class BackgroundRuntime:
    def __init__(
        self,
        config: JunoConfig,
        *,
        reports_dir: Path,
        inference: InferenceRouter,
        bus: EventBus,
        scheduler: JunoScheduler,
        integrations: IntegrationsRouter | None = None,
    ) -> None:
        self._config = config
        self._reports_dir = reports_dir
        self._inference = inference
        self._bus = bus
        self._scheduler = scheduler
        self._integrations = integrations
        self._jobs: dict[str, BackgroundJob] = {}
        self._job_schedules: dict[str, str] = {}
        self._last_run: dict[str, JobRunRecord] = {}

        reports_dir.mkdir(parents=True, exist_ok=True)

    # ---- registration ---------------------------------------------------

    def register_default_jobs(self) -> None:
        """Register the Phase 3 jobs declared in config."""
        if not self._config.background.enabled:
            log.info("Background layer disabled in config; no jobs registered.")
            return

        ctx = JobContext(
            config=self._config,
            reports_dir=self._reports_dir,
            inference=self._inference,
            bus=self._bus,
            integrations=self._integrations,
        )
        jobs_cfg = self._config.background.jobs

        # RSS — pure-network, no OS deps.
        if jobs_cfg.rss.enabled:
            self._register(RSSJob(ctx), jobs_cfg.rss.schedule)

        # macOS-integration jobs (Phase 5). Each gracefully degrades to a
        # "permission required" report if its automation prompt is denied.
        for job_cls, stub_cfg in (
            (EmailJob, jobs_cfg.email),
            (CalendarJob, jobs_cfg.calendar),
            (MessagesJob, jobs_cfg.messages),
        ):
            assert isinstance(stub_cfg, StubJobConfig)
            if stub_cfg.enabled:
                self._register(job_cls(ctx), stub_cfg.schedule)

        log.info(
            "Background layer registered %d job(s): %s",
            len(self._jobs),
            ", ".join(self._jobs.keys()),
        )

    def _register(self, job: BackgroundJob, cron: str) -> None:
        self._jobs[job.name] = job
        self._job_schedules[job.name] = cron
        self._scheduler.add_cron_job(
            name=job.name,
            cron=cron,
            func=lambda j=job: self._run_wrapped(j),
        )

    async def _run_wrapped(self, job: BackgroundJob) -> None:
        """Invocation envelope: persist the report, record the run, swallow
        exceptions so a failing job doesn't take down the scheduler."""
        started = datetime.now().astimezone()
        t0 = time.perf_counter()
        try:
            result = await job.run()
            self._write_report(result)
            elapsed = time.perf_counter() - t0
            self._last_run[job.name] = JobRunRecord(
                name=job.name,
                started_at=started,
                duration_seconds=elapsed,
                success=True,
            )
            log.info("Background job '%s' completed in %.2fs", job.name, elapsed)
        except Exception as e:
            elapsed = time.perf_counter() - t0
            self._last_run[job.name] = JobRunRecord(
                name=job.name,
                started_at=started,
                duration_seconds=elapsed,
                success=False,
                error=str(e),
            )
            log.exception("Background job '%s' failed after %.2fs", job.name, elapsed)

    def _write_report(self, result: JobResult) -> None:
        path = self._reports_dir / result.report_filename
        # Atomic-ish write: write to .tmp then rename, so a partial write
        # never leaves a half-readable report for the Interactive Layer.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(result.report_body, encoding="utf-8")
        tmp.replace(path)

    # ---- introspection / API surface ------------------------------------

    @property
    def reports_dir(self) -> Path:
        return self._reports_dir

    def list_jobs(self) -> list[dict]:
        out = []
        scheduler_jobs = {j.name: j for j in self._scheduler.list_jobs()}
        for name, job in self._jobs.items():
            sj = scheduler_jobs.get(name)
            last = self._last_run.get(name)
            out.append(
                {
                    "name": name,
                    "schedule": self._job_schedules.get(name),
                    "next_run": sj.next_run.isoformat() if sj and sj.next_run else None,
                    "last_run": (
                        {
                            "started_at": last.started_at.isoformat(),
                            "duration_seconds": last.duration_seconds,
                            "success": last.success,
                            "error": last.error,
                        }
                        if last
                        else None
                    ),
                    "report_filename": _filename_for(job),
                }
            )
        return out

    def list_reports(self) -> list[dict]:
        out = []
        if not self._reports_dir.exists():
            return out
        for path in sorted(self._reports_dir.glob("*.md")):
            stat = path.stat()
            out.append(
                {
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                }
            )
        return out

    async def run_now(self, name: str) -> JobRunRecord:
        if name not in self._jobs:
            raise KeyError(name)
        await self._run_wrapped(self._jobs[name])
        return self._last_run[name]


def _filename_for(job: BackgroundJob) -> str:
    """Best-effort static lookup so list_jobs works without invoking run()."""
    # The simplest source of truth is the result of run() but we don't
    # want list_jobs to be expensive. Hard-coded mapping mirrors each
    # job's `report_filename` constant.
    mapping = {
        "rss": "news.md",
        "email": "email-digest.md",
        "calendar": "calendar.md",
        "messages": "messages.md",
    }
    return mapping.get(job.name, f"{job.name}.md")
