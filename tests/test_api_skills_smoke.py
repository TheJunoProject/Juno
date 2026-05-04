"""Skills API smoke test."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server.api.app import create_app
from server.config import load_config


def test_skills_endpoint_lists_phase4_skills(tmp_path: Path) -> None:
    config = load_config(tmp_path / "config.yaml")
    config.paths.base = str(tmp_path / "juno")
    app = create_app(config)
    with TestClient(app) as client:
        body = client.get("/api/skills").json()
        names = {s["name"] for s in body["skills"]}
        assert {"web_search", "file_read", "file_write", "clipboard"}.issubset(names)
        # Each entry has the architecture-doc fields.
        for s in body["skills"]:
            assert s["description"]
            assert s["when_to_use"]
            assert "parallelizable" in s
