# Phase 2 — Voice Pipeline

Status: complete (2026-05-03).

Phase 2 adds server-side speech-to-text and text-to-speech, plumbed
through the same provider-router pattern as the inference layer. The
companion app does not exist yet — the test client and `curl` are how
we verified it.

---

## What was built

### STT-placement decision (Open Question #3)

Resolved: **server-side by default**. Companion uploads audio, server
transcribes. Reasons:

- Hard rule from CLAUDE.md: companion runs no models. STT is a model
  call.
- On a single-machine setup latency is negligible.
- On a multi-machine setup the server has the GPU.

The config reserves a `voice.stt.location` field set to `server` today;
a future `client` value will let the companion run whisper.cpp locally
and send transcripts. Wake word detection is the inverse — it lives
on the companion, server only exposes the wake word config.

### Voice provider layer (`server/voice/`)

```
server/voice/
  base.py                    STTProvider, TTSProvider, request/response types
  audio.py                   pure-stdlib WAV helpers (silent_wav, tone_wav, read_wav_info)
  router.py                  VoiceRouter — one selected STT + TTS per config
  providers/
    stt_stub.py              Always-available placeholder STT
    stt_whisper.py           faster-whisper (optional [voice] install)
    tts_stub.py              Always-available silent-WAV TTS
    tts_piper.py             Piper (optional [voice] install + voice model)
```

- **Default config** picks `stub` for both STT and TTS so the API
  contract works end-to-end without any model downloads. Switching to
  real providers is one line in `~/.juno/config.yaml`.
- **Real providers gracefully unavailable.** When `faster-whisper` /
  `piper-tts` isn't installed, the provider's `is_available()` returns
  False and `transcribe` / `synthesize` raise a clear error pointing at
  the install command. The server boots either way.
- **Lazy model loading.** Whisper and Piper models load on first call,
  not at startup, and run in `asyncio.to_thread` so they don't block
  the event loop.
- **Stub TTS produces real WAVs.** Duration scales with text length
  (60 ms / char, capped at 8 s, floor 0.5 s), 22050 Hz mono — close
  enough to Piper output that the companion can treat them
  identically.

### Voice config

New section in `~/.juno/config.yaml`:

```yaml
voice:
  stt:
    provider: stub          # stub | whisper
    location: server        # server | client (client reserved for future)
    whisper:
      model_size: base
      compute_type: int8
      download_root: null
      default_language: null
  tts:
    provider: stub          # stub | piper
    piper:
      model_path: null
      speaker_id: null
  wakeword:
    enabled: true
    keyword: juno
    sensitivity: 0.5
    model: null
```

Validated by Pydantic on every server start with `extra="forbid"` —
typos in keys are validation errors, not silent ignores.

### Voice API surface

| Endpoint                       | Purpose                                                |
| ------------------------------ | ------------------------------------------------------ |
| `POST /api/voice/transcribe`   | Multipart WAV upload → `{text, language, duration, ...}` |
| `POST /api/voice/synthesize`   | JSON `{text, voice?}` → `audio/wav` bytes              |
| `POST /api/voice/turn`         | Multipart WAV → STT → chat → TTS → JSON with transcript, response, base64 audio, session id |
| `WS   /api/voice/turn/stream`  | Same flow, streamed: header + audio in; `transcribed` event, `delta` events, audio binary frame, `done` event out |
| `GET  /api/voice/wakeword`     | Companion fetches wake word config (model, keyword, sensitivity) |

- Upload size capped at 25 MB (~25 minutes of 16-bit mono 16 kHz WAV).
- Audio uploads use multipart; everything else is JSON.
- All errors are JSON with HTTP status; WebSocket failures send
  `{"event": "error", "detail": "..."}` and close the socket.

### Wake word

Server-side this is purely a config surface — the spoken trigger
phrase, threshold, and openWakeWord model name. The companion (Phase 6)
fetches it from `GET /api/voice/wakeword` and runs detection locally
against its mic stream. Detection never runs server-side; it would
require streaming audio continuously across the network for no benefit.

### Health check

`GET /api/health` now reports per-voice-provider availability and which
one is selected:

```json
{
  "status": "ok",
  "providers": { "ollama": { "available": false, "model": "qwen2.5:7b" } },
  "voice": {
    "stt": {
      "stub":    { "available": true,  "selected": true,  "detail": null },
      "whisper": { "available": false, "selected": false, "detail": null }
    },
    "tts": {
      "stub":  { "available": true,  "selected": true,  "detail": null },
      "piper": { "available": false, "selected": false, "detail": null }
    }
  }
}
```

### Test client (`client.py`)

Three modes now:

```bash
# Phase 1 — text in / text out via WebSocket
python client.py "What is 2 + 2?"

# Phase 2 — voice turn over REST
python client.py --audio in.wav --speak out.wav

# Phase 2 — voice turn over WebSocket (streams response text live)
python client.py --audio in.wav --stream --speak out.wav
```

`--speak` writes the synthesized audio to disk so you can play it back
manually. Same `--host`, `--port`, `--session-id` flags as before.

---

## Definition of done — verified

- [x] `voice` config section is loaded, validated, and exposed to the
      router.
- [x] Stub STT returns a placeholder string with duration + byte count.
      Tests assert on the prefix.
- [x] Stub TTS returns a real WAV the test parses successfully and the
      `file` command identifies as "RIFF (little-endian) data, WAVE
      audio, Microsoft PCM, 16 bit, mono 22050 Hz".
- [x] Real Whisper + Piper providers boot cleanly when their deps
      aren't installed (`is_available() -> False`, no import errors at
      startup).
- [x] All voice endpoints respond correctly against the stubs (full
      pipeline test uses a stub chat provider so STT → chat → TTS
      completes end-to-end).
- [x] `/api/health` surfaces voice provider state.
- [x] `/api/voice/wakeword` exposes the config.
- [x] WebSocket streaming sends `transcribed` → `delta`...→ binary
      audio → `done`.
- [x] Test client works in REST and WS voice modes.
- [x] Phase 1 surface unchanged: 15 chat tests still green.

`pytest -q` → **35 passed, 1 skipped** (the live-Ollama integration
test).

---

## Notable decisions

1. **Pure stdlib for audio.** No numpy, no soundfile, no ffmpeg. The
   `wave` module + `struct` is enough for WAV header parsing, silent
   WAV generation, and tone generation. Keeps the install lean and the
   format guarantees explicit.
2. **WAV is the canonical format.** Other formats may be accepted by
   individual providers in the future, but the API documents WAV.
   Companion will record WAV and play WAV.
3. **Stubs are functional defaults, not test mocks.** They produce
   real output that the rest of the system can consume. A user who
   forgets to install the `[voice]` extra still sees a working API
   contract; the placeholder strings make it obvious what's happening.
4. **Lazy model loading on a worker thread.** Loading a Whisper model
   takes seconds and reads disk; it must not block uvicorn's event
   loop. `asyncio.to_thread` is the canonical pattern in 3.11+.
5. **WebSocket protocol uses tagged JSON events.** `event` field
   discriminates `start` / `transcribed` / `delta` / `done` / `error`,
   plus one binary frame for the response audio. Easy to extend with
   new event types.
6. **VoiceRouter constructs all providers up front but only uses the
   selected one.** Cheap (no model load in `__init__`), and the health
   endpoint can probe everything for the operator without the router
   tracking unselected providers separately.
7. **Wake word stays on the companion.** Server only holds and serves
   the config. Forcing audio streaming for wake word detection would
   waste bandwidth on every multi-machine setup and add latency that
   the on-device wake word doesn't have.

---

## What Phase 3 needs from this

Phase 3 (Background Layer) doesn't touch the voice pipeline. The
relationship is one-way: when the Background Layer regenerates context
reports, the Interactive Layer picks them up on the next turn (text or
voice — the layer is text-in / text-out either way).

The voice pipeline does need to know about wake word triggers
eventually — the companion sends "I just heard the wake word" and the
server starts listening. That's Phase 6 (companion polish).

---

## How to enable real voice

For real STT and TTS:

```bash
pip install -e '.[voice]'

# Optional: download a Piper voice model
mkdir -p ~/.juno/voices
curl -L -o ~/.juno/voices/en_US-amy-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
curl -L -o ~/.juno/voices/en_US-amy-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json
```

Then in `~/.juno/config.yaml`:

```yaml
voice:
  stt:
    provider: whisper
    whisper:
      model_size: base   # or small / medium / large-v3
  tts:
    provider: piper
    piper:
      model_path: /Users/you/.juno/voices/en_US-amy-medium.onnx
```

Restart the server. `GET /api/health` will report
`whisper.available: true` and `piper.available: true`.
