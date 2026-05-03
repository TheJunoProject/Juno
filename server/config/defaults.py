"""The default config file written on first run.

Kept as a literal string (not generated from the schema) so that comments
survive — users edit this file by hand and need the explanations.
"""

DEFAULT_CONFIG_YAML = """\
# Juno configuration.
# Full schema: see CLAUDE.md and server/config/schema.py.
# Re-validated on every server start; invalid values produce a clear error.

server:
  # Bind address. Keep as 127.0.0.1 unless you have a deliberate reason to
  # expose Juno on the local network. Never set this to 0.0.0.0 on a
  # machine that is reachable from the internet.
  host: 127.0.0.1
  port: 8000

inference:
  # The provider used when no per-task override applies.
  default_provider: ollama

  # Provider used when the default fails `escalation_attempts` times in a row
  # for a single request. null disables fallback.
  fallback_provider: null

  # Local attempts before escalating to the fallback provider.
  escalation_attempts: 2

  # Per-task-type provider routing. The router looks up the task_type of
  # each request here and dispatches to the matching provider.
  task_routing:
    conversational: ollama
    agentic_reasoning: ollama
    background_summarization: ollama
    complex_tasks: ollama

  providers:
    ollama:
      # URL of your Ollama server. Default is the standard local install.
      base_url: http://localhost:11434
      # Model name as it appears in `ollama list`.
      default_model: qwen2.5:7b
      # How long to wait for a single request, in seconds.
      request_timeout_seconds: 120

voice:
  stt:
    # `stub` returns a placeholder string; lets the API contract work
    # without any model downloads. Switch to `whisper` after running
    # `pip install -e '.[voice]'` to get real transcription via
    # faster-whisper.
    provider: stub
    # Where transcription happens. Today only `server` is implemented.
    # `client` is reserved for future companion-side STT.
    location: server
    whisper:
      # faster-whisper model size: tiny / base / small / medium /
      # large-v3. Smaller is faster and uses less memory.
      model_size: base
      # Compute precision. `int8` is the safe CPU default.
      # On NVIDIA GPUs use `float16` or `int8_float16`.
      compute_type: int8
      # Where to cache downloaded model weights. null = library default.
      download_root: null
      # null = autodetect language from the audio.
      default_language: null

  tts:
    # `stub` returns silent WAV audio of duration proportional to text
    # length — useful for end-to-end pipeline testing without model
    # downloads. Switch to `piper` after installing the voice extra
    # AND downloading a Piper voice model (see VOICES.md in the Piper
    # repo).
    provider: stub
    piper:
      # Path to a downloaded Piper .onnx voice model. null = stub.
      model_path: null
      # Optional speaker id for multi-voice models.
      speaker_id: null

  wakeword:
    # Companion-side wake word detection. Server holds the config so the
    # companion can fetch it via GET /api/voice/wakeword.
    enabled: true
    # Spoken trigger phrase.
    keyword: juno
    # Detection threshold, 0.0-1.0. Higher = fewer false triggers.
    sensitivity: 0.5
    # openWakeWord model identifier. null = companion's default.
    model: null
"""
