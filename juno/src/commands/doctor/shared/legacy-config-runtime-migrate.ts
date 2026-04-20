import type { JunoConfig } from "../../../config/types.juno.js";
import { normalizeBaseCompatibilityConfigValues } from "./legacy-config-compatibility-base.js";

export function normalizeRuntimeCompatibilityConfigValues(cfg: JunoConfig): {
  config: JunoConfig;
  changes: string[];
} {
  const changes: string[] = [];
  const next = normalizeBaseCompatibilityConfigValues(cfg, changes);
  return { config: next, changes };
}
