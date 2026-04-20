import type { JunoConfig } from "../config/types.juno.js";
import { parseJunoHubPluginSpec } from "../infra/junohub-spec.js";
import type { PluginRecord } from "../plugins/registry.js";

export function resolvePluginUninstallId<
  TPlugin extends Pick<PluginRecord, "id" | "name">,
>(params: {
  rawId: string;
  config: JunoConfig;
  plugins: TPlugin[];
}): { pluginId: string; plugin?: TPlugin } {
  const rawId = params.rawId.trim();
  const plugin = params.plugins.find((entry) => entry.id === rawId || entry.name === rawId);
  if (plugin) {
    return { pluginId: plugin.id, plugin };
  }

  for (const [pluginId, install] of Object.entries(params.config.plugins?.installs ?? {})) {
    if (
      install.spec === rawId ||
      install.resolvedSpec === rawId ||
      install.resolvedName === rawId ||
      install.marketplacePlugin === rawId
    ) {
      return { pluginId };
    }
  }

  const requestedJunoHub = parseJunoHubPluginSpec(rawId);
  if (requestedJunoHub) {
    for (const [pluginId, install] of Object.entries(params.config.plugins?.installs ?? {})) {
      const installedJunoHubName =
        install.junohubPackage ??
        parseJunoHubPluginSpec(install.spec ?? "")?.name ??
        parseJunoHubPluginSpec(install.resolvedSpec ?? "")?.name;
      if (installedJunoHubName === requestedJunoHub.name) {
        return { pluginId };
      }
    }
  }

  return { pluginId: rawId };
}
