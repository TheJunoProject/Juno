import path from "node:path";
import type { BrowserConfig, BrowserProfileConfig, JunoConfig } from "../config/config.js";
import type { SsrFPolicy } from "../infra/net/ssrf.js";
import { resolvePreferredJunoTmpDir } from "../infra/tmp-juno-dir.js";
import { loadBundledPluginPublicSurfaceModuleSync } from "./facade-loader.js";

export const DEFAULT_JUNO_BROWSER_ENABLED = true;
export const DEFAULT_BROWSER_EVALUATE_ENABLED = true;
export const DEFAULT_JUNO_BROWSER_COLOR = "#FF4500";
export const DEFAULT_JUNO_BROWSER_PROFILE_NAME = "juno";
export const DEFAULT_BROWSER_DEFAULT_PROFILE_NAME = "juno";
export const DEFAULT_AI_SNAPSHOT_MAX_CHARS = 80_000;
export const DEFAULT_UPLOAD_DIR = path.join(resolvePreferredJunoTmpDir(), "uploads");

export type ResolvedBrowserConfig = {
  enabled: boolean;
  evaluateEnabled: boolean;
  controlPort: number;
  cdpPortRangeStart: number;
  cdpPortRangeEnd: number;
  cdpProtocol: "http" | "https";
  cdpHost: string;
  cdpIsLoopback: boolean;
  remoteCdpTimeoutMs: number;
  remoteCdpHandshakeTimeoutMs: number;
  color: string;
  executablePath?: string;
  headless: boolean;
  noSandbox: boolean;
  attachOnly: boolean;
  defaultProfile: string;
  profiles: Record<string, BrowserProfileConfig>;
  ssrfPolicy?: SsrFPolicy;
  extraArgs: string[];
};

export type ResolvedBrowserProfile = {
  name: string;
  cdpPort: number;
  cdpUrl: string;
  cdpHost: string;
  cdpIsLoopback: boolean;
  userDataDir?: string;
  color: string;
  driver: "juno" | "existing-session";
  attachOnly: boolean;
};

type BrowserProfilesSurface = {
  resolveBrowserConfig: (
    cfg: BrowserConfig | undefined,
    rootConfig?: JunoConfig,
  ) => ResolvedBrowserConfig;
  resolveProfile: (
    resolved: ResolvedBrowserConfig,
    profileName: string,
  ) => ResolvedBrowserProfile | null;
};

let cachedBrowserProfilesSurface: BrowserProfilesSurface | undefined;

function loadBrowserProfilesSurface(): BrowserProfilesSurface {
  cachedBrowserProfilesSurface ??= loadBundledPluginPublicSurfaceModuleSync<BrowserProfilesSurface>(
    {
      dirName: "browser",
      artifactBasename: "browser-profiles.js",
    },
  );
  return cachedBrowserProfilesSurface;
}

export function resolveBrowserConfig(
  cfg: BrowserConfig | undefined,
  rootConfig?: JunoConfig,
): ResolvedBrowserConfig {
  return loadBrowserProfilesSurface().resolveBrowserConfig(cfg, rootConfig);
}

export function resolveProfile(
  resolved: ResolvedBrowserConfig,
  profileName: string,
): ResolvedBrowserProfile | null {
  return loadBrowserProfilesSurface().resolveProfile(resolved, profileName);
}
