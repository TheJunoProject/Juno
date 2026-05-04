"""Web search skill — DuckDuckGo HTML backend.

Phase 4 ships this as a real, working skill without any API keys, by
scraping DuckDuckGo's `html.duckduckgo.com` endpoint. CLAUDE.md's
canonical web_search uses the browser skill in agent mode (Phase 4+
later), at which point this implementation gets swapped out behind the
same `Skill` interface.

The HTML scraper is fragile by definition; treat the parser as
best-effort. We extract title + URL + snippet with stdlib HTMLParser
and bail cleanly if the page structure changes.
"""

from __future__ import annotations

import logging
import urllib.parse
from html.parser import HTMLParser
from typing import Any

import httpx

from server.skills.base import (
    Skill,
    SkillContext,
    SkillError,
    SkillInput,
    SkillResult,
)

log = logging.getLogger(__name__)


SEARCH_URL = "https://html.duckduckgo.com/html/"
USER_AGENT = (
    "Mozilla/5.0 (compatible; JunoWebSearch/0.1; "
    "+https://github.com/Juno-Personal-AI/Juno)"
)
MAX_ALLOWED_RESULTS = 10


class WebSearchSkill(Skill):
    name = "web_search"

    async def execute(
        self, payload: SkillInput, context: SkillContext
    ) -> SkillResult:
        query = (payload.get("query") or "").strip()
        if not query:
            raise SkillError("web_search requires a non-empty `query`.")
        max_results = int(payload.get("max_results") or 5)
        max_results = max(1, min(MAX_ALLOWED_RESULTS, max_results))

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.post(
                    SEARCH_URL,
                    data={"q": query, "kl": "us-en"},
                )
                resp.raise_for_status()
                html_body = resp.text
        except httpx.HTTPError as e:
            raise SkillError(f"web_search request failed: {e}") from e

        results = _parse_results(html_body, limit=max_results)
        # If parsing produced nothing, surface that as an error rather than
        # silently returning empty — usually means the HTML changed shape
        # and the parser needs an update.
        if not results:
            raise SkillError(
                "web_search parsed zero results — DuckDuckGo HTML may have "
                "changed or the request was rate-limited."
            )

        summary_lines = [f"{r['title']} — {r['url']}" for r in results]
        return SkillResult(
            output={"results": results, "count": len(results)},
            summary=f"{len(results)} results for {query!r}: \n  " + "\n  ".join(summary_lines),
        )


# ---- HTML parser --------------------------------------------------------


class _ResultsParser(HTMLParser):
    """Pulls (title, href, snippet) from DuckDuckGo HTML.

    The page uses a stable-ish structure:
      <div class="result results_links results_links_deep web-result ...">
        <h2 class="result__title">
          <a class="result__a" href="...DDG redirect...">Title</a>
        </h2>
        <a class="result__snippet" href="...">Snippet text</a>
      </div>
    """

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_result = False
        self._in_title_a = False
        self._in_snippet_a = False
        self._current_href: str | None = None
        self._title_buf: list[str] = []
        self._snippet_buf: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attr = dict(attrs)
        cls = (attr.get("class") or "").split()
        if tag == "div" and "result" in cls:
            self._in_result = True
            self._current_href = None
            self._title_buf.clear()
            self._snippet_buf.clear()
        elif self._in_result and tag == "a":
            href = attr.get("href")
            if "result__a" in cls:
                self._in_title_a = True
                self._current_href = _normalise_ddg_href(href)
            elif "result__snippet" in cls:
                self._in_snippet_a = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            if self._in_title_a:
                self._in_title_a = False
            if self._in_snippet_a:
                self._in_snippet_a = False
        elif tag == "div" and self._in_result:
            title = "".join(self._title_buf).strip()
            snippet = "".join(self._snippet_buf).strip()
            url = self._current_href or ""
            if title and url:
                self.results.append(
                    {"title": title, "url": url, "snippet": snippet}
                )
            self._in_result = False

    def handle_data(self, data: str) -> None:
        if self._in_title_a:
            self._title_buf.append(data)
        elif self._in_snippet_a:
            self._snippet_buf.append(data)


def _normalise_ddg_href(href: str | None) -> str | None:
    """DuckDuckGo wraps target URLs in `/l/?uddg=<encoded>`. Unwrap it.

    Falls back to the raw href when it isn't a redirect.
    """
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if parsed.path.endswith("/l/") or "uddg=" in parsed.query:
        params = urllib.parse.parse_qs(parsed.query)
        target = params.get("uddg", [None])[0]
        if target:
            return urllib.parse.unquote(target)
    if not parsed.scheme:
        return None
    return href


def _parse_results(html_body: str, *, limit: int) -> list[dict[str, Any]]:
    parser = _ResultsParser()
    try:
        parser.feed(html_body)
    except Exception as e:  # HTMLParser can throw on malformed input
        log.warning("DuckDuckGo HTML parse failed: %s", e)
        return []
    return parser.results[:limit]
