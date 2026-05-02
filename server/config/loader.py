"""Load, validate, and (on first run) generate the user's Juno config.

Validation errors are surfaced as `ConfigError` with a human-readable message
that points at the file and the specific field — never a raw Pydantic dump
or stack trace, since the user edits this file by hand.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from server.config.defaults import DEFAULT_CONFIG_YAML
from server.config.schema import JunoConfig


class ConfigError(Exception):
    """Raised when the config file is missing, malformed, or invalid."""


def user_config_path() -> Path:
    """Resolve the canonical config location.

    Honours JUNO_CONFIG for tests and one-off overrides; otherwise falls back
    to ~/.juno/config.yaml.
    """
    override = os.environ.get("JUNO_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".juno" / "config.yaml"


def ensure_default_config(path: Path | None = None) -> Path:
    """Create the default config file if none exists yet. Return the path."""
    target = path or user_config_path()
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
    return target


def load_config(path: Path | None = None) -> JunoConfig:
    """Load and validate the Juno config from disk.

    Generates a default config if none exists. Raises ConfigError with a
    user-readable message on any failure.
    """
    target = path or user_config_path()
    if not target.exists():
        ensure_default_config(target)

    try:
        raw_text = target.read_text(encoding="utf-8")
    except OSError as e:
        raise ConfigError(f"Could not read config file at {target}: {e}") from e

    try:
        data = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as e:
        raise ConfigError(
            f"Config file at {target} is not valid YAML:\n  {e}"
        ) from e

    if not isinstance(data, dict):
        raise ConfigError(
            f"Config file at {target} must be a YAML mapping at the top level, "
            f"got {type(data).__name__}."
        )

    try:
        return JunoConfig.model_validate(data)
    except ValidationError as e:
        raise ConfigError(_format_validation_error(target, e)) from e


def _format_validation_error(path: Path, error: ValidationError) -> str:
    """Turn a Pydantic ValidationError into a config-editor-friendly message."""
    lines = [f"Invalid config at {path}:"]
    for err in error.errors():
        loc = ".".join(str(part) for part in err["loc"]) or "<root>"
        lines.append(f"  - {loc}: {err['msg']}")
    lines.append("")
    lines.append(
        "Fix the values above, or delete the file to regenerate defaults."
    )
    return "\n".join(lines)
