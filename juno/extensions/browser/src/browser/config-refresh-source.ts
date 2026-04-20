import { createConfigIO, getRuntimeConfigSnapshot, type JunoConfig } from "../config/config.js";

export function loadBrowserConfigForRuntimeRefresh(): JunoConfig {
  return getRuntimeConfigSnapshot() ?? createConfigIO().loadConfig();
}
