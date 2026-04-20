import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import dotenv from "dotenv";
import { resolveConfigDir } from "../utils.js";
import { resolveRequiredHomeDir } from "./home-dir.js";
import {
  isDangerousHostEnvOverrideVarName,
  isDangerousHostEnvVarName,
  normalizeEnvVarKey,
} from "./host-env-security.js";

const BLOCKED_WORKSPACE_DOTENV_KEYS = new Set([
  "ALL_PROXY",
  "ANTHROPIC_API_KEY",
  "ANTHROPIC_OAUTH_TOKEN",
  "BROWSER_EXECUTABLE_PATH",
  "JUNOHUB_AUTH_TOKEN",
  "JUNOHUB_CONFIG_PATH",
  "JUNOHUB_TOKEN",
  "JUNOHUB_URL",
  "HTTP_PROXY",
  "HTTPS_PROXY",
  "NODE_TLS_REJECT_UNAUTHORIZED",
  "NO_PROXY",
  "OPENAI_API_KEY",
  "OPENAI_API_KEYS",
  "JUNO_AGENT_DIR",
  "JUNO_ALLOW_INSECURE_PRIVATE_WS",
  "JUNO_ALLOW_PROJECT_LOCAL_BIN",
  "JUNO_BROWSER_EXECUTABLE_PATH",
  "JUNO_BROWSER_CONTROL_MODULE",
  "JUNO_BUNDLED_HOOKS_DIR",
  "JUNO_BUNDLED_PLUGINS_DIR",
  "JUNO_BUNDLED_SKILLS_DIR",
  "JUNO_CACHE_TRACE",
  "JUNO_CACHE_TRACE_FILE",
  "JUNO_CACHE_TRACE_MESSAGES",
  "JUNO_CACHE_TRACE_PROMPT",
  "JUNO_CACHE_TRACE_SYSTEM",
  "JUNO_CONFIG_PATH",
  "JUNO_GATEWAY_PASSWORD",
  "JUNO_GATEWAY_PORT",
  "JUNO_GATEWAY_SECRET",
  "JUNO_GATEWAY_TOKEN",
  "JUNO_GATEWAY_URL",
  "JUNO_HOME",
  "JUNO_LIVE_ANTHROPIC_KEY",
  "JUNO_LIVE_ANTHROPIC_KEYS",
  "JUNO_LIVE_GEMINI_KEY",
  "JUNO_LIVE_OPENAI_KEY",
  "JUNO_MPM_CATALOG_PATHS",
  "JUNO_NODE_EXEC_FALLBACK",
  "JUNO_NODE_EXEC_HOST",
  "JUNO_OAUTH_DIR",
  "JUNO_PINNED_PYTHON",
  "JUNO_PINNED_WRITE_PYTHON",
  "JUNO_PLUGIN_CATALOG_PATHS",
  "JUNO_PROFILE",
  "JUNO_RAW_STREAM",
  "JUNO_RAW_STREAM_PATH",
  "JUNO_SHOW_SECRETS",
  "JUNO_SKIP_BROWSER_CONTROL_SERVER",
  "JUNO_STATE_DIR",
  "JUNO_TEST_TAILSCALE_BINARY",
  "PI_CODING_AGENT_DIR",
  "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH",
  "UV_PYTHON",
]);

// Block endpoint redirection for any service without overfitting per-provider names.
const BLOCKED_WORKSPACE_DOTENV_SUFFIXES = ["_BASE_URL"];
const BLOCKED_WORKSPACE_DOTENV_PREFIXES = [
  "ANTHROPIC_API_KEY_",
  "JUNOHUB_",
  "OPENAI_API_KEY_",
  "JUNO_JUNOHUB_",
  "JUNO_DISABLE_",
  "JUNO_SKIP_",
  "JUNO_UPDATE_",
];

function shouldBlockWorkspaceRuntimeDotEnvKey(key: string): boolean {
  return isDangerousHostEnvVarName(key) || isDangerousHostEnvOverrideVarName(key);
}

function shouldBlockRuntimeDotEnvKey(key: string): boolean {
  // The global ~/.juno/.env (or JUNO_STATE_DIR/.env) is a trusted
  // operator-controlled runtime surface. Workspace .env is untrusted and gets
  // the strict blocklist, but the trusted global fallback is allowed to set
  // runtime vars like proxy/base-url/auth values.
  void key;
  return false;
}

function shouldBlockWorkspaceDotEnvKey(key: string): boolean {
  const upper = key.toUpperCase();
  return (
    shouldBlockWorkspaceRuntimeDotEnvKey(upper) ||
    BLOCKED_WORKSPACE_DOTENV_KEYS.has(upper) ||
    BLOCKED_WORKSPACE_DOTENV_PREFIXES.some((prefix) => upper.startsWith(prefix)) ||
    BLOCKED_WORKSPACE_DOTENV_SUFFIXES.some((suffix) => upper.endsWith(suffix))
  );
}

type DotEnvEntry = {
  key: string;
  value: string;
};

type LoadedDotEnvFile = {
  filePath: string;
  entries: DotEnvEntry[];
};

function readDotEnvFile(params: {
  filePath: string;
  shouldBlockKey: (key: string) => boolean;
  quiet?: boolean;
}): LoadedDotEnvFile | null {
  let content: string;
  try {
    content = fs.readFileSync(params.filePath, "utf8");
  } catch (error) {
    if (!params.quiet) {
      const code =
        error && typeof error === "object" && "code" in error ? String(error.code) : undefined;
      if (code !== "ENOENT") {
        console.warn(`[dotenv] Failed to read ${params.filePath}: ${String(error)}`);
      }
    }
    return null;
  }

  let parsed: Record<string, string>;
  try {
    parsed = dotenv.parse(content);
  } catch (error) {
    if (!params.quiet) {
      console.warn(`[dotenv] Failed to parse ${params.filePath}: ${String(error)}`);
    }
    return null;
  }
  const entries: DotEnvEntry[] = [];
  for (const [rawKey, value] of Object.entries(parsed)) {
    const key = normalizeEnvVarKey(rawKey, { portable: true });
    if (!key || params.shouldBlockKey(key)) {
      continue;
    }
    entries.push({ key, value });
  }
  return { filePath: params.filePath, entries };
}

export function loadRuntimeDotEnvFile(filePath: string, opts?: { quiet?: boolean }) {
  const parsed = readDotEnvFile({
    filePath,
    shouldBlockKey: shouldBlockRuntimeDotEnvKey,
    quiet: opts?.quiet ?? true,
  });
  if (!parsed) {
    return;
  }
  for (const { key, value } of parsed.entries) {
    if (process.env[key] !== undefined) {
      continue;
    }
    process.env[key] = value;
  }
}

export function loadWorkspaceDotEnvFile(filePath: string, opts?: { quiet?: boolean }) {
  const parsed = readDotEnvFile({
    filePath,
    shouldBlockKey: shouldBlockWorkspaceDotEnvKey,
    quiet: opts?.quiet ?? true,
  });
  if (!parsed) {
    return;
  }
  for (const { key, value } of parsed.entries) {
    if (process.env[key] !== undefined) {
      continue;
    }
    process.env[key] = value;
  }
}

function loadParsedDotEnvFiles(files: LoadedDotEnvFile[]) {
  const preExistingKeys = new Set(Object.keys(process.env));
  const conflicts = new Map<string, { keptPath: string; ignoredPath: string; keys: Set<string> }>();
  const firstSeen = new Map<string, { value: string; filePath: string }>();

  for (const file of files) {
    for (const { key, value } of file.entries) {
      if (preExistingKeys.has(key)) {
        continue;
      }
      const previous = firstSeen.get(key);
      if (previous) {
        if (previous.value !== value) {
          const conflictKey = `${previous.filePath}\u0000${file.filePath}`;
          const existing = conflicts.get(conflictKey);
          if (existing) {
            existing.keys.add(key);
          } else {
            conflicts.set(conflictKey, {
              keptPath: previous.filePath,
              ignoredPath: file.filePath,
              keys: new Set([key]),
            });
          }
        }
        continue;
      }
      firstSeen.set(key, { value, filePath: file.filePath });
      if (process.env[key] === undefined) {
        process.env[key] = value;
      }
    }
  }

  for (const conflict of conflicts.values()) {
    const keys = [...conflict.keys].toSorted();
    if (keys.length === 0) {
      continue;
    }
    console.warn(
      `[dotenv] Conflicting values in ${conflict.keptPath} and ${conflict.ignoredPath} for ${keys.join(", ")}; keeping ${conflict.keptPath}.`,
    );
  }
}

export function loadGlobalRuntimeDotEnvFiles(opts?: { quiet?: boolean; stateEnvPath?: string }) {
  const quiet = opts?.quiet ?? true;
  const stateEnvPath = opts?.stateEnvPath ?? path.join(resolveConfigDir(process.env), ".env");
  const defaultStateEnvPath = path.join(
    resolveRequiredHomeDir(process.env, os.homedir),
    ".juno",
    ".env",
  );
  const hasExplicitNonDefaultStateDir =
    process.env.JUNO_STATE_DIR?.trim() !== undefined &&
    path.resolve(stateEnvPath) !== path.resolve(defaultStateEnvPath);
  const parsedFiles = [
    readDotEnvFile({
      filePath: stateEnvPath,
      shouldBlockKey: shouldBlockRuntimeDotEnvKey,
      quiet,
    }),
  ];
  if (!hasExplicitNonDefaultStateDir) {
    parsedFiles.push(
      readDotEnvFile({
        filePath: path.join(
          resolveRequiredHomeDir(process.env, os.homedir),
          ".config",
          "juno",
          "gateway.env",
        ),
        shouldBlockKey: shouldBlockRuntimeDotEnvKey,
        quiet,
      }),
    );
  }
  const parsed = parsedFiles.filter((file): file is LoadedDotEnvFile => file !== null);
  loadParsedDotEnvFiles(parsed);
}

export function loadDotEnv(opts?: { quiet?: boolean }) {
  const quiet = opts?.quiet ?? true;
  const cwdEnvPath = path.join(process.cwd(), ".env");
  loadWorkspaceDotEnvFile(cwdEnvPath, { quiet });

  // Then load global fallback: ~/.juno/.env (or JUNO_STATE_DIR/.env),
  // without overriding any env vars already present.
  loadGlobalRuntimeDotEnvFiles({ quiet });
}
