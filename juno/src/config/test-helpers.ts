import fs from "node:fs/promises";
import path from "node:path";
import { withTempHome as withTempHomeBase } from "../../test/helpers/temp-home.js";
import { resetPluginLoaderTestStateForTest } from "../plugins/loader.test-fixtures.js";
import { clearPluginSetupRegistryCache } from "../plugins/setup-registry.js";
import { resetConfigRuntimeState, type JunoConfig } from "./config.js";

function resetConfigTestRuntimeState(): void {
  resetConfigRuntimeState();
  resetPluginLoaderTestStateForTest();
  clearPluginSetupRegistryCache();
}

export async function withTempHome<T>(fn: (home: string) => Promise<T>): Promise<T> {
  resetConfigTestRuntimeState();
  try {
    return await withTempHomeBase(fn, {
      prefix: "juno-config-",
      env: {
        JUNO_CONFIG_PATH: undefined,
        JUNO_BUNDLED_PLUGINS_DIR: undefined,
        JUNO_DISABLE_BUNDLED_PLUGINS: undefined,
        JUNO_DISABLE_PLUGIN_DISCOVERY_CACHE: undefined,
        JUNO_DISABLE_PLUGIN_MANIFEST_CACHE: undefined,
        JUNO_PLUGIN_CATALOG_PATHS: undefined,
        JUNO_MPM_CATALOG_PATHS: undefined,
        JUNO_PLUGIN_DISCOVERY_CACHE_MS: undefined,
        JUNO_PLUGIN_MANIFEST_CACHE_MS: undefined,
        JUNO_LOAD_SHELL_ENV: undefined,
        JUNO_DEFER_SHELL_ENV_FALLBACK: undefined,
        JUNO_SHELL_ENV_TIMEOUT_MS: undefined,
        ANTHROPIC_API_KEY: undefined,
        ANTHROPIC_OAUTH_TOKEN: undefined,
      },
    });
  } finally {
    resetConfigTestRuntimeState();
  }
}

export async function writeJunoConfig(home: string, config: unknown): Promise<string> {
  const configPath = path.join(home, ".juno", "juno.json");
  await fs.mkdir(path.dirname(configPath), { recursive: true });
  await fs.writeFile(configPath, JSON.stringify(config, null, 2), "utf-8");
  return configPath;
}

export async function writeStateDirDotEnv(
  content: string,
  params?: {
    env?: NodeJS.ProcessEnv;
    stateDir?: string;
  },
): Promise<{ dotEnvPath: string; stateDir: string }> {
  const stateDir = params?.stateDir ?? params?.env?.JUNO_STATE_DIR?.trim();
  if (!stateDir) {
    throw new Error("Expected JUNO_STATE_DIR or explicit stateDir for .env test setup");
  }
  const dotEnvPath = path.join(stateDir, ".env");
  await fs.mkdir(path.dirname(dotEnvPath), { recursive: true });
  await fs.writeFile(dotEnvPath, content, "utf-8");
  return { dotEnvPath, stateDir };
}

export async function withTempHomeConfig<T>(
  config: unknown,
  fn: (params: { home: string; configPath: string }) => Promise<T>,
): Promise<T> {
  return withTempHome(async (home) => {
    const configPath = await writeJunoConfig(home, config);
    return fn({ home, configPath });
  });
}

/**
 * Helper to test env var overrides. Saves/restores env vars for a callback.
 */
export async function withEnvOverride<T>(
  overrides: Record<string, string | undefined>,
  fn: () => Promise<T>,
): Promise<T> {
  const saved: Record<string, string | undefined> = {};
  for (const key of Object.keys(overrides)) {
    saved[key] = process.env[key];
    if (overrides[key] === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = overrides[key];
    }
  }
  try {
    return await fn();
  } finally {
    for (const key of Object.keys(saved)) {
      if (saved[key] === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = saved[key];
      }
    }
  }
}

export function buildWebSearchProviderConfig(params: {
  provider: NonNullable<
    NonNullable<NonNullable<NonNullable<JunoConfig["tools"]>["web"]>["search"]>["provider"]
  >;
  enabled?: boolean;
  providerConfig?: Record<string, unknown>;
}): Record<string, unknown> {
  const search: Record<string, unknown> = { provider: params.provider };
  if (params.enabled !== undefined) {
    search.enabled = params.enabled;
  }
  const pluginId =
    params.provider === "gemini"
      ? "google"
      : params.provider === "grok"
        ? "xai"
        : params.provider === "kimi"
          ? "moonshot"
          : params.provider;
  return {
    tools: {
      web: {
        search,
      },
    },
    ...(params.providerConfig
      ? {
          plugins: {
            entries: {
              [pluginId]: {
                config: {
                  webSearch: params.providerConfig,
                },
              },
            },
          },
        }
      : {}),
  };
}
