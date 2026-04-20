import type { JunoConfig } from "../../../config/types.juno.js";
import { runPluginSetupConfigMigrations } from "../../../plugins/setup-registry.js";
import { applyChannelDoctorCompatibilityMigrations } from "./channel-legacy-config-migrate.js";
import { normalizeBaseCompatibilityConfigValues } from "./legacy-config-compatibility-base.js";

export function normalizeCompatibilityConfigValues(cfg: JunoConfig): {
  config: JunoConfig;
  changes: string[];
} {
  const changes: string[] = [];
  let next = normalizeBaseCompatibilityConfigValues(cfg, changes, (config) => {
    const setupMigration = runPluginSetupConfigMigrations({
      config,
    });
    if (setupMigration.changes.length === 0) {
      return config;
    }
    changes.push(...setupMigration.changes);
    return setupMigration.config;
  });
  const channelMigrations = applyChannelDoctorCompatibilityMigrations(next);
  if (channelMigrations.changes.length > 0) {
    next = channelMigrations.next;
    changes.push(...channelMigrations.changes);
  }

  return { config: next, changes };
}
