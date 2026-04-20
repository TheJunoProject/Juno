import type { JunoConfig } from "../../../config/types.juno.js";
import {
  normalizeLegacyBrowserConfig,
  normalizeLegacyCrossContextMessageConfig,
  normalizeLegacyMediaProviderOptions,
  normalizeLegacyMistralModelMaxTokens,
  normalizeLegacyNanoBananaSkill,
  normalizeLegacyTalkConfig,
  seedMissingDefaultAccountsFromSingleAccountBase,
} from "./legacy-config-core-normalizers.js";
import { migrateLegacyWebFetchConfig } from "./legacy-web-fetch-migrate.js";
import { migrateLegacyWebSearchConfig } from "./legacy-web-search-migrate.js";
import { migrateLegacyXSearchConfig } from "./legacy-x-search-migrate.js";

export function normalizeBaseCompatibilityConfigValues(
  cfg: JunoConfig,
  changes: string[],
  afterBrowser?: (config: JunoConfig) => JunoConfig,
): JunoConfig {
  let next = seedMissingDefaultAccountsFromSingleAccountBase(cfg, changes);
  next = normalizeLegacyBrowserConfig(next, changes);
  next = afterBrowser ? afterBrowser(next) : next;

  for (const migrate of [
    migrateLegacyWebSearchConfig,
    migrateLegacyWebFetchConfig,
    migrateLegacyXSearchConfig,
  ]) {
    const migrated = migrate(next);
    if (migrated.changes.length === 0) {
      continue;
    }
    next = migrated.config;
    changes.push(...migrated.changes);
  }

  next = normalizeLegacyNanoBananaSkill(next, changes);
  next = normalizeLegacyTalkConfig(next, changes);
  next = normalizeLegacyCrossContextMessageConfig(next, changes);
  next = normalizeLegacyMediaProviderOptions(next, changes);
  return normalizeLegacyMistralModelMaxTokens(next, changes);
}
