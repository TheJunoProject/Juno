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
"""
