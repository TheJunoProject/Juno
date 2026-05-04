"""Individual skill behaviour tests.

Each skill is exercised against its own backend (sandbox dir, mock
HTTP, etc.) — no network, no real model.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

from server.config import JunoConfig
from server.config.paths import resolve_paths
from server.inference import InferenceRouter
from server.scheduler import EventBus
from server.skills import SkillContext, SkillError
from server.skills.clipboard.skill import ClipboardSkill
from server.skills.file_read.skill import FileReadSkill
from server.skills.file_write.skill import FileWriteSkill
from server.skills.web_search.skill import WebSearchSkill


def _ctx(tmp_path: Path) -> SkillContext:
    config = JunoConfig()
    config.paths.base = str(tmp_path / "juno")
    paths = resolve_paths(config.paths)
    paths.ensure()
    inference = InferenceRouter(config.inference)
    return SkillContext(
        config=config,
        paths=paths,
        inference=inference,
        bus=EventBus(),
        sandbox_dir=paths.base / "skill-data",
    )


# ---- file_read / file_write -------------------------------------------


async def test_file_write_then_read_round_trip(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    write = FileWriteSkill()
    read = FileReadSkill()

    w = await write.execute({"path": "notes.md", "content": "hello world"}, ctx)
    assert w.output["created"] is True
    assert w.output["size_bytes"] == len("hello world")

    r = await read.execute({"path": "notes.md"}, ctx)
    assert r.output["content"] == "hello world"
    assert r.output["truncated"] is False

    await ctx.inference.aclose()


async def test_file_write_refuses_overwrite_by_default(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    write = FileWriteSkill()
    await write.execute({"path": "x.txt", "content": "first"}, ctx)
    with pytest.raises(SkillError):
        await write.execute({"path": "x.txt", "content": "second"}, ctx)
    # With overwrite=true it succeeds.
    out = await write.execute(
        {"path": "x.txt", "content": "second", "overwrite": True}, ctx
    )
    assert out.output["created"] is False
    assert out.output["size_bytes"] == len("second")
    await ctx.inference.aclose()


async def test_file_read_truncates_large_files(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    write = FileWriteSkill()
    read = FileReadSkill()
    big = "A" * 1000
    await write.execute({"path": "big.txt", "content": big}, ctx)
    out = await read.execute({"path": "big.txt", "max_bytes": 100}, ctx)
    assert out.output["truncated"] is True
    # Assertion on length: 100 bytes + the truncation note.
    assert "truncated at 100 bytes" in out.output["content"]
    await ctx.inference.aclose()


async def test_file_skills_reject_paths_outside_sandbox(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    write = FileWriteSkill()
    read = FileReadSkill()
    with pytest.raises(SkillError):
        await write.execute({"path": "/etc/passwd", "content": "no"}, ctx)
    with pytest.raises(SkillError):
        await read.execute({"path": "/etc/passwd"}, ctx)
    # Relative path with .. that escapes sandbox should also fail.
    with pytest.raises(SkillError):
        await read.execute({"path": "../../../etc/passwd"}, ctx)
    await ctx.inference.aclose()


async def test_file_read_rejects_binary(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    sandbox = ctx.paths.base / "skill-data"
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "blob.bin").write_bytes(b"\xff\xfe\x00\x01\x02")
    with pytest.raises(SkillError) as exc:
        await FileReadSkill().execute({"path": "blob.bin"}, ctx)
    assert "UTF-8" in str(exc.value)
    await ctx.inference.aclose()


# ---- web_search --------------------------------------------------------


SAMPLE_DDG_HTML = """
<html><body>
<div class="result results_links results_links_deep web-result">
  <h2 class="result__title">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa">First Result</a>
  </h2>
  <a class="result__snippet" href="//x">Snippet for the first result.</a>
</div>
<div class="result results_links results_links_deep web-result">
  <h2 class="result__title">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fb">Second Result</a>
  </h2>
  <a class="result__snippet" href="//x">Another snippet.</a>
</div>
</body></html>
"""


@pytest.fixture
def patch_httpx(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SAMPLE_DDG_HTML)

    transport = httpx.MockTransport(handler)
    real_init = httpx.AsyncClient.__init__

    def fake_init(self, *args, **kwargs):
        for k in ("timeout", "follow_redirects", "headers"):
            kwargs.pop(k, None)
        real_init(self, transport=transport, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", fake_init)
    yield


async def test_web_search_parses_ddg_html(tmp_path: Path, patch_httpx) -> None:
    ctx = _ctx(tmp_path)
    skill = WebSearchSkill()
    out = await skill.execute({"query": "anything"}, ctx)
    results = out.output["results"]
    assert out.output["count"] == 2
    assert results[0]["title"] == "First Result"
    assert results[0]["url"] == "https://example.com/a"
    assert "first result" in results[0]["snippet"].lower()
    await ctx.inference.aclose()


async def test_web_search_clamps_max_results(tmp_path: Path, patch_httpx) -> None:
    ctx = _ctx(tmp_path)
    out = await WebSearchSkill().execute(
        {"query": "x", "max_results": 1}, ctx
    )
    assert out.output["count"] == 1
    await ctx.inference.aclose()


async def test_web_search_empty_query_rejected(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    with pytest.raises(SkillError):
        await WebSearchSkill().execute({"query": ""}, ctx)
    await ctx.inference.aclose()


# ---- clipboard --------------------------------------------------------


@pytest.mark.skipif(
    sys.platform != "darwin", reason="clipboard skill is macOS-only in Phase 4"
)
async def test_clipboard_round_trip(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    skill = ClipboardSkill()
    await skill.execute({"mode": "write", "text": "juno-test-clip"}, ctx)
    out = await skill.execute({"mode": "read"}, ctx)
    assert "juno-test-clip" in out.output["text"]
    await ctx.inference.aclose()


@pytest.mark.skipif(
    sys.platform == "darwin", reason="this test is for the non-Mac fallback"
)
async def test_clipboard_unavailable_off_mac(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    with pytest.raises(SkillError):
        await ClipboardSkill().execute({"mode": "read"}, ctx)
    await ctx.inference.aclose()


async def test_clipboard_rejects_unknown_mode(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    if sys.platform != "darwin":
        pytest.skip("Mac-only path")
    with pytest.raises(SkillError):
        await ClipboardSkill().execute({"mode": "nope"}, ctx)
    await ctx.inference.aclose()
