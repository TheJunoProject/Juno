"""Minimal command-line client for verifying Juno end-to-end.

Not part of the companion app — purely a smoke-test tool.

Text mode (Phase 1):
    python client.py "Hey Juno, what is 2 + 2?"

Voice turn (Phase 2 — REST):
    python client.py --audio path/to/utterance.wav
    python client.py --audio in.wav --speak out.wav

Voice turn (Phase 2 — streaming over WebSocket):
    python client.py --audio in.wav --stream --speak out.wav

The voice modes default to the stub STT/TTS providers, which means:
- Transcription returns a placeholder string (real text needs Whisper).
- Synthesis returns a silent WAV of plausible duration.
That's enough to verify the pipeline end-to-end.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

import httpx
import websockets
from websockets.exceptions import ConnectionClosed


# ---- Text-only chat (Phase 1 surface) -----------------------------------


async def run_text(message: str, host: str, port: int, session_id: str | None) -> int:
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
                    print()
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


# ---- Voice turn over REST -----------------------------------------------


async def run_voice_rest(
    audio_path: Path,
    host: str,
    port: int,
    session_id: str | None,
    speak_to: Path | None,
) -> int:
    url = f"http://{host}:{port}/api/voice/turn"
    audio_bytes = audio_path.read_bytes()

    files = {"audio": (audio_path.name, audio_bytes, "audio/wav")}
    data: dict[str, str] = {}
    if session_id:
        data["session_id"] = session_id

    async with httpx.AsyncClient(timeout=120.0) as http:
        try:
            r = await http.post(url, files=files, data=data)
        except httpx.HTTPError as e:
            print(f"[could not reach {url}: {e}]", file=sys.stderr)
            return 1

    if r.status_code != 200:
        print(f"[HTTP {r.status_code}] {r.text}", file=sys.stderr)
        return 1

    body = r.json()
    print(f"transcript: {body['transcript']}")
    print(f"response:   {body['response']}")
    print(
        f"meta:       chat={body['chat_provider']}/{body['chat_model']} "
        f"stt={body['stt_provider']} tts={body['tts_provider']}"
    )
    if speak_to is not None:
        speak_to.write_bytes(base64.b64decode(body["audio_base64"]))
        print(
            f"audio:      saved {body['audio_duration_seconds']:.2f}s "
            f"@ {body['audio_sample_rate']}Hz to {speak_to}"
        )
    return 0


# ---- Voice turn over WebSocket ------------------------------------------


async def run_voice_ws(
    audio_path: Path,
    host: str,
    port: int,
    session_id: str | None,
    speak_to: Path | None,
) -> int:
    url = f"ws://{host}:{port}/api/voice/turn/stream"
    audio_bytes = audio_path.read_bytes()

    try:
        async with websockets.connect(url, max_size=64 * 1024 * 1024) as ws:
            await ws.send(
                json.dumps(
                    {
                        "event": "start",
                        "session_id": session_id,
                        "language": None,
                        "audio_size": len(audio_bytes),
                    }
                )
            )
            await ws.send(audio_bytes)

            audio_out: bytes | None = None
            transcript: str | None = None
            response_chars: list[str] = []
            done_payload: dict | None = None

            async for raw in ws:
                if isinstance(raw, bytes):
                    audio_out = raw
                    continue
                frame = json.loads(raw)
                ev = frame.get("event")
                if ev == "transcribed":
                    transcript = frame["text"]
                    print(f"transcript: {transcript}")
                    print("response:   ", end="", flush=True)
                elif ev == "delta":
                    delta = frame["delta"]
                    response_chars.append(delta)
                    print(delta, end="", flush=True)
                elif ev == "done":
                    done_payload = frame
                    print()
                    break
                elif ev == "error":
                    print(f"\n[server error] {frame.get('detail')}", file=sys.stderr)
                    return 1
    except ConnectionClosed as e:
        print(f"\n[connection closed: {e.code} {e.reason}]", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"[could not connect to {url}: {e}]", file=sys.stderr)
        return 1

    if speak_to is not None and audio_out is not None and done_payload is not None:
        speak_to.write_bytes(audio_out)
        print(
            f"audio:      saved {done_payload['audio_duration_seconds']:.2f}s "
            f"@ {done_payload['audio_sample_rate']}Hz to {speak_to}"
        )
    return 0


# ---- argparse + dispatch ------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description="Juno test client.")
    p.add_argument("message", nargs="?", help="Text message (omit when using --audio).")
    p.add_argument("--audio", type=Path, help="Path to a WAV file to send as input.")
    p.add_argument(
        "--speak", type=Path, help="Save the response audio (WAV) to this path."
    )
    p.add_argument(
        "--stream",
        action="store_true",
        help="Use the WebSocket voice endpoint (streams response text).",
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--session-id", default=None)
    args = p.parse_args()

    if args.audio is None and args.message is None:
        p.error("either provide a text message or --audio FILE")
    if args.audio is not None and args.message is not None:
        p.error("pick one: text message OR --audio FILE")

    if args.audio is not None:
        if not args.audio.is_file():
            p.error(f"audio file not found: {args.audio}")
        runner = run_voice_ws if args.stream else run_voice_rest
        return asyncio.run(
            runner(args.audio, args.host, args.port, args.session_id, args.speak)
        )

    return asyncio.run(
        run_text(args.message, args.host, args.port, args.session_id)
    )


if __name__ == "__main__":
    raise SystemExit(main())
