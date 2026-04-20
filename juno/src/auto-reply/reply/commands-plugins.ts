import fs from "node:fs";
import { buildNpmInstallRecordFields } from "../../cli/npm-resolution.js";
import {
  buildPreferredJunoHubSpec,
  createPluginInstallLogger,
  decidePreferredJunoHubFallback,
  resolveFileNpmSpecToLocalPath,
} from "../../cli/plugins-command-helpers.js";
import { persistPluginInstall } from "../../cli/plugins-install-persist.js";
import {
  readConfigFileSnapshot,
  validateConfigObjectWithPlugins,
  writeConfigFile,
} from "../../config/config.js";
import type { JunoConfig } from "../../config/types.juno.js";
import type { PluginInstallRecord } from "../../config/types.plugins.js";
import { resolveArchiveKind } from "../../infra/archive.js";
import { parseJunoHubPluginSpec } from "../../infra/junohub.js";
import { installPluginFromJunoHub } from "../../plugins/junohub.js";
import { installPluginFromNpmSpec, installPluginFromPath } from "../../plugins/install.js";
import { clearPluginManifestRegistryCache } from "../../plugins/manifest-registry.js";
import type { PluginRecord } from "../../plugins/registry.js";
import {
  buildAllPluginInspectReports,
  buildPluginDiagnosticsReport,
  buildPluginInspectReport,
  buildPluginSnapshotReport,
  formatPluginCompatibilityNotice,
  type PluginStatusReport,
} from "../../plugins/status.js";
import { setPluginEnabledInConfig } from "../../plugins/toggle-config.js";
import { normalizeOptionalLowercaseString } from "../../shared/string-coerce.js";
import { resolveUserPath } from "../../utils.js";
import { isInternalMessageChannel } from "../../utils/message-channel.js";
import {
  rejectNonOwnerCommand,
  rejectUnauthorizedCommand,
  requireCommandFlagEnabled,
  requireGatewayClientScopeForInternalChannel,
} from "./command-gates.js";
import type { CommandHandler } from "./commands-types.js";
import { parsePluginsCommand } from "./plugins-commands.js";

function renderJsonBlock(label: string, value: unknown): string {
  return `${label}\n\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\``;
}

function buildPluginInspectJson(params: {
  id: string;
  config: JunoConfig;
  report: PluginStatusReport;
}): {
  inspect: NonNullable<ReturnType<typeof buildPluginInspectReport>>;
  compatibilityWarnings: Array<{
    code: string;
    severity: string;
    message: string;
  }>;
  install: PluginInstallRecord | null;
} | null {
  const inspect = buildPluginInspectReport({
    id: params.id,
    config: params.config,
    report: params.report,
  });
  if (!inspect) {
    return null;
  }
  return {
    inspect,
    compatibilityWarnings: inspect.compatibility.map((warning) => ({
      code: warning.code,
      severity: warning.severity,
      message: formatPluginCompatibilityNotice(warning),
    })),
    install: params.config.plugins?.installs?.[inspect.plugin.id] ?? null,
  };
}

function buildAllPluginInspectJson(params: {
  config: JunoConfig;
  report: PluginStatusReport;
}): Array<{
  inspect: ReturnType<typeof buildAllPluginInspectReports>[number];
  compatibilityWarnings: Array<{
    code: string;
    severity: string;
    message: string;
  }>;
  install: PluginInstallRecord | null;
}> {
  return buildAllPluginInspectReports({
    config: params.config,
    report: params.report,
  }).map((inspect) => ({
    inspect,
    compatibilityWarnings: inspect.compatibility.map((warning) => ({
      code: warning.code,
      severity: warning.severity,
      message: formatPluginCompatibilityNotice(warning),
    })),
    install: params.config.plugins?.installs?.[inspect.plugin.id] ?? null,
  }));
}

function formatPluginLabel(plugin: PluginRecord): string {
  if (!plugin.name || plugin.name === plugin.id) {
    return plugin.id;
  }
  return `${plugin.name} (${plugin.id})`;
}

function formatPluginsList(report: PluginStatusReport): string {
  if (report.plugins.length === 0) {
    return `🔌 No plugins found for workspace ${report.workspaceDir ?? "(unknown workspace)"}.`;
  }

  const loaded = report.plugins.filter((plugin) => plugin.status === "loaded").length;
  const lines = [
    `🔌 Plugins (${loaded}/${report.plugins.length} loaded)`,
    ...report.plugins.map((plugin) => {
      const format = plugin.bundleFormat
        ? `${plugin.format ?? "juno"}/${plugin.bundleFormat}`
        : (plugin.format ?? "juno");
      return `- ${formatPluginLabel(plugin)} [${plugin.status}] ${format}`;
    }),
  ];
  return lines.join("\n");
}

function findPlugin(report: PluginStatusReport, rawName: string): PluginRecord | undefined {
  const target = normalizeOptionalLowercaseString(rawName);
  if (!target) {
    return undefined;
  }
  return report.plugins.find(
    (plugin) =>
      normalizeOptionalLowercaseString(plugin.id) === target ||
      normalizeOptionalLowercaseString(plugin.name) === target,
  );
}

function looksLikeLocalPluginInstallSpec(raw: string): boolean {
  return (
    raw.startsWith(".") ||
    raw.startsWith("~") ||
    raw.startsWith("/") ||
    raw.endsWith(".ts") ||
    raw.endsWith(".js") ||
    raw.endsWith(".mjs") ||
    raw.endsWith(".cjs") ||
    raw.endsWith(".tgz") ||
    raw.endsWith(".tar.gz") ||
    raw.endsWith(".tar") ||
    raw.endsWith(".zip")
  );
}

async function installPluginFromPluginsCommand(params: {
  raw: string;
  config: JunoConfig;
}): Promise<{ ok: true; pluginId: string } | { ok: false; error: string }> {
  const fileSpec = resolveFileNpmSpecToLocalPath(params.raw);
  if (fileSpec && !fileSpec.ok) {
    return { ok: false, error: fileSpec.error };
  }
  const normalized = fileSpec && fileSpec.ok ? fileSpec.path : params.raw;
  const resolved = resolveUserPath(normalized);

  if (fs.existsSync(resolved)) {
    const result = await installPluginFromPath({
      path: resolved,
      logger: createPluginInstallLogger(),
    });
    if (!result.ok) {
      return { ok: false, error: result.error };
    }
    clearPluginManifestRegistryCache();
    const source: "archive" | "path" = resolveArchiveKind(resolved) ? "archive" : "path";
    await persistPluginInstall({
      config: params.config,
      pluginId: result.pluginId,
      install: {
        source,
        sourcePath: resolved,
        installPath: result.targetDir,
        version: result.version,
      },
    });
    return { ok: true, pluginId: result.pluginId };
  }

  if (looksLikeLocalPluginInstallSpec(params.raw)) {
    return { ok: false, error: `Path not found: ${resolved}` };
  }

  const junohubSpec = parseJunoHubPluginSpec(params.raw);
  if (junohubSpec) {
    const result = await installPluginFromJunoHub({
      spec: params.raw,
      logger: createPluginInstallLogger(),
    });
    if (!result.ok) {
      return { ok: false, error: result.error };
    }
    clearPluginManifestRegistryCache();
    await persistPluginInstall({
      config: params.config,
      pluginId: result.pluginId,
      install: {
        source: "junohub",
        spec: params.raw,
        installPath: result.targetDir,
        version: result.version,
        integrity: result.junohub.integrity,
        resolvedAt: result.junohub.resolvedAt,
        junohubUrl: result.junohub.junohubUrl,
        junohubPackage: result.junohub.junohubPackage,
        junohubFamily: result.junohub.junohubFamily,
        junohubChannel: result.junohub.junohubChannel,
      },
    });
    return { ok: true, pluginId: result.pluginId };
  }

  const preferredJunoHubSpec = buildPreferredJunoHubSpec(params.raw);
  if (preferredJunoHubSpec) {
    const junohubResult = await installPluginFromJunoHub({
      spec: preferredJunoHubSpec,
      logger: createPluginInstallLogger(),
    });
    if (junohubResult.ok) {
      clearPluginManifestRegistryCache();
      await persistPluginInstall({
        config: params.config,
        pluginId: junohubResult.pluginId,
        install: {
          source: "junohub",
          spec: preferredJunoHubSpec,
          installPath: junohubResult.targetDir,
          version: junohubResult.version,
          integrity: junohubResult.junohub.integrity,
          resolvedAt: junohubResult.junohub.resolvedAt,
          junohubUrl: junohubResult.junohub.junohubUrl,
          junohubPackage: junohubResult.junohub.junohubPackage,
          junohubFamily: junohubResult.junohub.junohubFamily,
          junohubChannel: junohubResult.junohub.junohubChannel,
        },
      });
      return { ok: true, pluginId: junohubResult.pluginId };
    }
    if (decidePreferredJunoHubFallback(junohubResult) !== "fallback_to_npm") {
      return { ok: false, error: junohubResult.error };
    }
  }

  const result = await installPluginFromNpmSpec({
    spec: params.raw,
    logger: createPluginInstallLogger(),
  });
  if (!result.ok) {
    return { ok: false, error: result.error };
  }
  clearPluginManifestRegistryCache();
  const installRecord = buildNpmInstallRecordFields({
    spec: params.raw,
    installPath: result.targetDir,
    version: result.version,
    resolution: result.npmResolution,
  });
  await persistPluginInstall({
    config: params.config,
    pluginId: result.pluginId,
    install: installRecord,
  });
  return { ok: true, pluginId: result.pluginId };
}

async function loadPluginCommandState(
  workspaceDir: string,
  options?: { loadModules?: boolean },
): Promise<
  | {
      ok: true;
      path: string;
      config: JunoConfig;
      report: PluginStatusReport;
    }
  | { ok: false; path: string; error: string }
> {
  const snapshot = await readConfigFileSnapshot();
  if (!snapshot.valid) {
    return {
      ok: false,
      path: snapshot.path,
      error: "Config file is invalid; fix it before using /plugins.",
    };
  }
  const config = structuredClone(snapshot.resolved);
  return {
    ok: true,
    path: snapshot.path,
    config,
    report:
      options?.loadModules === true
        ? buildPluginDiagnosticsReport({ config, workspaceDir })
        : buildPluginSnapshotReport({ config, workspaceDir }),
  };
}

async function loadPluginCommandConfig(): Promise<
  { ok: true; path: string; config: JunoConfig } | { ok: false; path: string; error: string }
> {
  const snapshot = await readConfigFileSnapshot();
  if (!snapshot.valid) {
    return {
      ok: false,
      path: snapshot.path,
      error: "Config file is invalid; fix it before using /plugins.",
    };
  }
  return {
    ok: true,
    path: snapshot.path,
    config: structuredClone(snapshot.resolved),
  };
}

export const handlePluginsCommand: CommandHandler = async (params, allowTextCommands) => {
  if (!allowTextCommands) {
    return null;
  }
  const pluginsCommand = parsePluginsCommand(params.command.commandBodyNormalized);
  if (!pluginsCommand) {
    return null;
  }
  const unauthorized = rejectUnauthorizedCommand(params, "/plugins");
  if (unauthorized) {
    return unauthorized;
  }
  const allowInternalReadOnly =
    (pluginsCommand.action === "list" || pluginsCommand.action === "inspect") &&
    isInternalMessageChannel(params.command.channel);
  const nonOwner = allowInternalReadOnly ? null : rejectNonOwnerCommand(params, "/plugins");
  if (nonOwner) {
    return nonOwner;
  }
  const disabled = requireCommandFlagEnabled(params.cfg, {
    label: "/plugins",
    configKey: "plugins",
  });
  if (disabled) {
    return disabled;
  }
  if (pluginsCommand.action === "error") {
    return {
      shouldContinue: false,
      reply: { text: `⚠️ ${pluginsCommand.message}` },
    };
  }

  const missingAdminScope = requireGatewayClientScopeForInternalChannel(params, {
    label: "/plugins write",
    allowedScopes: ["operator.admin"],
    missingText: "❌ /plugins install|enable|disable requires operator.admin for gateway clients.",
  });
  if (missingAdminScope) {
    return missingAdminScope;
  }

  if (pluginsCommand.action === "install") {
    const loadedConfig = await loadPluginCommandConfig();
    if (!loadedConfig.ok) {
      return {
        shouldContinue: false,
        reply: { text: `⚠️ ${loadedConfig.error}` },
      };
    }
    const installed = await installPluginFromPluginsCommand({
      raw: pluginsCommand.spec,
      config: loadedConfig.config,
    });
    if (!installed.ok) {
      return {
        shouldContinue: false,
        reply: { text: `⚠️ ${installed.error}` },
      };
    }
    return {
      shouldContinue: false,
      reply: {
        text: `🔌 Installed plugin "${installed.pluginId}". Restart the gateway to load plugins.`,
      },
    };
  }

  const loaded = await loadPluginCommandState(params.workspaceDir, {
    loadModules: pluginsCommand.action !== "list",
  });
  if (!loaded.ok) {
    return {
      shouldContinue: false,
      reply: { text: `⚠️ ${loaded.error}` },
    };
  }

  if (pluginsCommand.action === "list") {
    return {
      shouldContinue: false,
      reply: { text: formatPluginsList(loaded.report) },
    };
  }

  if (pluginsCommand.action === "inspect") {
    if (!pluginsCommand.name) {
      return {
        shouldContinue: false,
        reply: { text: formatPluginsList(loaded.report) },
      };
    }
    if (normalizeOptionalLowercaseString(pluginsCommand.name) === "all") {
      return {
        shouldContinue: false,
        reply: {
          text: renderJsonBlock("🔌 Plugins", buildAllPluginInspectJson(loaded)),
        },
      };
    }
    const payload = buildPluginInspectJson({
      id: pluginsCommand.name,
      config: loaded.config,
      report: loaded.report,
    });
    if (!payload) {
      return {
        shouldContinue: false,
        reply: { text: `🔌 No plugin named "${pluginsCommand.name}" found.` },
      };
    }
    return {
      shouldContinue: false,
      reply: {
        text: renderJsonBlock(`🔌 Plugin "${payload.inspect.plugin.id}"`, {
          ...payload.inspect,
          compatibilityWarnings: payload.compatibilityWarnings,
          install: payload.install,
        }),
      },
    };
  }

  const plugin = findPlugin(loaded.report, pluginsCommand.name);
  if (!plugin) {
    return {
      shouldContinue: false,
      reply: { text: `🔌 No plugin named "${pluginsCommand.name}" found.` },
    };
  }

  const next = setPluginEnabledInConfig(
    structuredClone(loaded.config),
    plugin.id,
    pluginsCommand.action === "enable",
  );
  const validated = validateConfigObjectWithPlugins(next);
  if (!validated.ok) {
    const issue = validated.issues[0];
    return {
      shouldContinue: false,
      reply: {
        text: `⚠️ Config invalid after /plugins ${pluginsCommand.action} (${issue.path}: ${issue.message}).`,
      },
    };
  }
  await writeConfigFile(validated.config);

  return {
    shouldContinue: false,
    reply: {
      text: `🔌 Plugin "${plugin.id}" ${pluginsCommand.action}d in ${loaded.path}. Restart the gateway to apply.`,
    },
  };
};
