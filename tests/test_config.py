"""Config loader / validator tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.config import ConfigError, ensure_default_config, load_config


def test_first_run_generates_default_config(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    assert not target.exists()
    cfg = load_config(target)
    assert target.exists(), "default config should be written on first run"
    assert cfg.server.host == "127.0.0.1"
    assert cfg.server.port == 8000
    assert cfg.inference.default_provider == "ollama"
    assert cfg.inference.providers.ollama.default_model == "qwen2.5:7b"


def test_invalid_yaml_raises_config_error(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text("server: { host: 127.0.0.1, port:\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_config(target)
    assert "not valid YAML" in str(exc.value)
    assert str(target) in str(exc.value)


def test_invalid_field_raises_clear_error(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text(
        "server:\n  host: 127.0.0.1\n  port: 99999\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as exc:
        load_config(target)
    msg = str(exc.value)
    assert "Invalid config" in msg
    assert "server.port" in msg


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text(
        "server:\n  host: 127.0.0.1\n  port: 8000\n  bogus: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as exc:
        load_config(target)
    assert "server.bogus" in str(exc.value)


def test_fallback_must_differ_from_default(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text(
        "inference:\n  default_provider: ollama\n  fallback_provider: ollama\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as exc:
        load_config(target)
    assert "fallback_provider" in str(exc.value)


def test_ensure_default_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    ensure_default_config(target)
    original = target.read_text(encoding="utf-8")
    ensure_default_config(target)
    assert target.read_text(encoding="utf-8") == original
