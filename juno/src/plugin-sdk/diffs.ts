// Narrow plugin-sdk surface for the bundled diffs plugin.
// Keep this list additive and scoped to the bundled diffs surface.

export { definePluginEntry } from "./plugin-entry.js";
export type { JunoConfig } from "../config/config.js";
export { resolvePreferredJunoTmpDir } from "../infra/tmp-juno-dir.js";
export type {
  AnyAgentTool,
  JunoPluginApi,
  JunoPluginConfigSchema,
  JunoPluginToolContext,
  PluginLogger,
} from "../plugins/types.js";
