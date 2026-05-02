"""Minimal command-line client for verifying Phase 1 end-to-end.

Not part of the companion app — purely a smoke-test tool.

    python client.py "Hey Juno, what is 2 + 2?"

Connects to the streaming WebSocket at ws://127.0.0.1:8000/api/chat/stream,
prints chunks as they arrive, and exits cleanly on `done`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

import websockets
from websockets.exceptions import ConnectionClosed


async def run(message: str, host: str, port: int, session_id: str | None) -> int:
    url = f"ws://{host}:{port}/api/chat/stream"
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"message": message, "session_id": session_id}))
            async for raw in ws:
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    print(f"\n[non-JSON frame] {raw}", file=sys.stderr)
                    continue

                if "error" in frame:
                    print(
                        f"\n[server error] {frame['error']}: "
                        f"{frame.get('detail', '')}",
                        file=sys.stderr,
                    )
                    return 1

                if frame.get("done"):
                    print()  # trailing newline
                    return 0

                delta = frame.get("delta", "")
                if delta:
                    print(delta, end="", flush=True)
    except ConnectionClosed as e:
        print(f"\n[connection closed: {e.code} {e.reason}]", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"[could not connect to {url}: {e}]", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Juno test client.")
    p.add_argument("message", help="Message to send to Juno.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--session-id", default=None)
    args = p.parse_args()

    return asyncio.run(run(args.message, args.host, args.port, args.session_id))


if __name__ == "__main__":
    raise SystemExit(main())
