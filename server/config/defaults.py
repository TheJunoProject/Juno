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

paths:
  # Where Juno keeps user state on disk (reports, scheduler db, voices).
  # null = ~/.juno. An absolute path overrides.
  base: null

background:
  # Master switch for the Background Layer. When false, no jobs run and
  # /api/background/* returns empty.
  enabled: true
  # Persist scheduler state to <paths.base>/scheduler.db across restarts.
  # Default off in Phase 3: all jobs are cron triggers that get
  # re-registered on every startup, so persistence is a no-op. Turn on
  # once you have one-off date jobs (Phase 5+ reminders).
  persist_jobs: false
  jobs:
    rss:
      enabled: true
      # APScheduler cron: minute hour day month day_of_week. Hourly default.
      schedule: "0 * * * *"
      # Feeds to fetch each run. Add or remove freely; first-party RSS only.
      feeds:
        - https://hnrss.org/frontpage
        - https://feeds.bbci.co.uk/news/rss.xml
      # Items per feed per run.
      max_items_per_feed: 5
      # When true, the inference layer summarises the day's stories into
      # news.md (uses task_routing.background_summarization). When false,
      # the report just lists titles + URLs.
      summarize: true
      # Per-item character cap fed to the summariser.
      max_chars_per_item: 1500

    # The email / calendar / messages jobs ship as documented stubs in
    # Phase 3. They produce a placeholder report with the schema the real
    # implementations (Phase 5, macOS system integration) will follow.
    email:
      enabled: true
      schedule: "*/15 * * * *"
    calendar:
      enabled: true
      schedule: "*/15 * * * *"
    messages:
      enabled: true
      schedule: "*/15 * * * *"
"""
