"""RSS news job — fetches feeds, summarises, writes news.md.

This is the canonical Phase 3 job: pure-network input, no OS deps, no
credentials. It exercises the full pipeline end-to-end:

    feedparser -> per-item normalisation -> (optional) inference summary
              -> markdown report -> reports_dir/news.md

When `summarize=False` in config, it skips the model call and produces
a list of titles + URLs. That keeps the job useful even when no model
is available.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass

import feedparser
import httpx

from server.agents.background.jobs.base import BackgroundJob, JobContext, JobResult
from server.config.schema import RSSJobConfig
from server.inference.base import InferenceRequest, Message

log = logging.getLogger(__name__)


@dataclass
class _Item:
    feed_title: str
    title: str
    link: str
    summary: str  # plain text, normalised


SUMMARY_SYSTEM_PROMPT = """\
You are Juno's background news summariser. Produce a concise daily
news brief from the items provided.

Rules:
- Group related items into themes when sensible. Don't repeat the same
  story twice.
- Each line: one short sentence, in plain prose. No headers, no bullets
  beyond a single dash, no markdown bold.
- 5-10 lines total, even if there are more items. Skip noise.
- Lead with the most consequential items.
- If there is genuinely nothing newsworthy, write: "No notable news today."
"""


class RSSJob(BackgroundJob):
    name = "rss"

    def __init__(self, context: JobContext) -> None:
        super().__init__(context)
        self._cfg: RSSJobConfig = context.config.background.jobs.rss

    async def run(self) -> JobResult:
        items = await self._fetch_all()
        body = await self._render(items)
        return JobResult(report_filename="news.md", report_body=body)

    # ---- fetching -------------------------------------------------------

    async def _fetch_all(self) -> list[_Item]:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "JunoBackgroundLayer/0.1"},
        ) as client:
            results = await asyncio.gather(
                *(self._fetch_one(client, url) for url in self._cfg.feeds),
                return_exceptions=True,
            )
        out: list[_Item] = []
        for url, r in zip(self._cfg.feeds, results, strict=False):
            if isinstance(r, Exception):
                log.warning("RSS feed %s failed: %s", url, r)
                continue
            out.extend(r)
        return out

    async def _fetch_one(
        self, client: httpx.AsyncClient, url: str
    ) -> list[_Item]:
        try:
            r = await client.get(url)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"GET {url}: {e}") from e
        # feedparser is sync and CPU-bound on the parse; push to a thread
        # so we don't stall the loop for big feeds.
        parsed = await asyncio.to_thread(feedparser.parse, r.content)
        feed_title = (parsed.feed.get("title") or url).strip()
        items: list[_Item] = []
        for entry in parsed.entries[: self._cfg.max_items_per_feed]:
            title = (entry.get("title") or "(no title)").strip()
            link = (entry.get("link") or "").strip()
            summary = _clean_html(
                entry.get("summary")
                or entry.get("description")
                or "",
                self._cfg.max_chars_per_item,
            )
            items.append(
                _Item(feed_title=feed_title, title=title, link=link, summary=summary)
            )
        return items

    # ---- rendering ------------------------------------------------------

    async def _render(self, items: list[_Item]) -> str:
        header = self.report_header("News")
        if not items:
            return header + "\nNo items fetched."

        # Always include the raw items list — gives the user (and the
        # Interactive Layer) source links to verify against.
        raw = ["\n## Raw items\n"]
        by_feed: dict[str, list[_Item]] = {}
        for it in items:
            by_feed.setdefault(it.feed_title, []).append(it)
        for feed_title, feed_items in by_feed.items():
            raw.append(f"\n### {feed_title}\n")
            for it in feed_items:
                if it.link:
                    raw.append(f"- [{it.title}]({it.link})")
                else:
                    raw.append(f"- {it.title}")

        if not self._cfg.summarize:
            return header + "\n".join(raw)

        try:
            summary = await self._summarise(items)
        except Exception as e:
            # Never let the summariser take down the whole job — the raw
            # items list is still useful by itself.
            log.warning("RSS summariser failed; falling back to titles only: %s", e)
            return (
                header
                + "\n## Summary\n\n_Summariser unavailable: "
                + str(e)
                + "_\n"
                + "\n".join(raw)
            )

        return (
            header
            + "\n## Summary\n\n"
            + summary.strip()
            + "\n"
            + "\n".join(raw)
        )

    async def _summarise(self, items: list[_Item]) -> str:
        # Compact, easy-to-parse prompt. The router sends this to the
        # provider configured for `background_summarization`.
        bullets = []
        for it in items:
            line = f"- [{it.feed_title}] {it.title}"
            if it.summary:
                line += f" — {it.summary}"
            bullets.append(line)
        body = "\n".join(bullets)
        request = InferenceRequest(
            messages=[
                Message(role="system", content=SUMMARY_SYSTEM_PROMPT),
                Message(
                    role="user",
                    content=f"Today's news items:\n\n{body}\n\nWrite the brief.",
                ),
            ],
            task_type="background_summarization",
            temperature=0.3,
        )
        response = await self.context.inference.complete(request)
        return response.content


# ---- helpers ------------------------------------------------------------


_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def _clean_html(text: str, max_chars: int) -> str:
    """Strip HTML tags + collapse whitespace + truncate. Pure-stdlib."""
    if not text:
        return ""
    no_tags = _HTML_TAG.sub(" ", text)
    decoded = html.unescape(no_tags)
    collapsed = _WHITESPACE.sub(" ", decoded).strip()
    if len(collapsed) > max_chars:
        return collapsed[: max_chars - 1].rstrip() + "…"
    return collapsed
