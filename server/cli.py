"""`juno` CLI.

Currently exposes one command:

    juno start [--config PATH] [--host HOST] [--port PORT]

Loads and validates config, then runs the FastAPI app under uvicorn.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from server import __version__
from server.api.app import create_app
from server.config import ConfigError, ensure_default_config, load_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="juno", description="Juno server CLI.")
    parser.add_argument("--version", action="version", version=f"juno {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Start the Juno server.")
    start.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file (default: ~/.juno/config.yaml).",
    )
    start.add_argument(
        "--host", default=None, help="Override the host from config."
    )
    start.add_argument(
        "--port", type=int, default=None, help="Override the port from config."
    )

    sub.add_parser(
        "init-config",
        help="Write the default config file to ~/.juno/config.yaml if missing.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-config":
        path = ensure_default_config()
        print(f"Config: {path}")
        return 0

    if args.command == "start":
        try:
            config = load_config(args.config)
        except ConfigError as e:
            # Plain text on stderr — never a stack trace. The user edits this
            # file by hand and needs to know what's wrong, not see Python guts.
            print(str(e), file=sys.stderr)
            return 2

        host = args.host or config.server.host
        port = args.port or config.server.port

        app = create_app(config)
        # log_config=None: we configure logging ourselves in create_app so
        # uvicorn doesn't fight us for the root logger handlers.
        uvicorn.run(app, host=host, port=port, log_config=None)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2  # unreachable, satisfies type-checkers


if __name__ == "__main__":
    raise SystemExit(main())
