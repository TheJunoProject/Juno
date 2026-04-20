import { describe, expect, it } from "vitest";
import type { PluginInstallRecord } from "../config/types.plugins.js";
import { resolvePluginUpdateSelection } from "./plugins-update-selection.js";

function createNpmInstall(params: {
  spec: string;
  installPath?: string;
  resolvedName?: string;
}): PluginInstallRecord {
  return {
    source: "npm",
    spec: params.spec,
    installPath: params.installPath ?? "/tmp/plugin",
    ...(params.resolvedName ? { resolvedName: params.resolvedName } : {}),
  };
}

describe("resolvePluginUpdateSelection", () => {
  it("maps an explicit unscoped npm dist-tag update to the tracked plugin id", () => {
    expect(
      resolvePluginUpdateSelection({
        installs: {
          "juno-codex-app-server": createNpmInstall({
            spec: "juno-codex-app-server",
            installPath: "/tmp/juno-codex-app-server",
            resolvedName: "juno-codex-app-server",
          }),
        },
        rawId: "juno-codex-app-server@beta",
      }),
    ).toEqual({
      pluginIds: ["juno-codex-app-server"],
      specOverrides: {
        "juno-codex-app-server": "juno-codex-app-server@beta",
      },
    });
  });

  it("maps an explicit scoped npm dist-tag update to the tracked plugin id", () => {
    expect(
      resolvePluginUpdateSelection({
        installs: {
          "voice-call": createNpmInstall({
            spec: "@juno/voice-call",
            installPath: "/tmp/voice-call",
            resolvedName: "@juno/voice-call",
          }),
        },
        rawId: "@juno/voice-call@beta",
      }),
    ).toEqual({
      pluginIds: ["voice-call"],
      specOverrides: {
        "voice-call": "@juno/voice-call@beta",
      },
    });
  });

  it("maps an explicit npm version update to the tracked plugin id", () => {
    expect(
      resolvePluginUpdateSelection({
        installs: {
          "juno-codex-app-server": createNpmInstall({
            spec: "juno-codex-app-server",
            installPath: "/tmp/juno-codex-app-server",
            resolvedName: "juno-codex-app-server",
          }),
        },
        rawId: "juno-codex-app-server@0.2.0-beta.4",
      }),
    ).toEqual({
      pluginIds: ["juno-codex-app-server"],
      specOverrides: {
        "juno-codex-app-server": "juno-codex-app-server@0.2.0-beta.4",
      },
    });
  });

  it("keeps recorded npm tags when update is invoked by plugin id", () => {
    expect(
      resolvePluginUpdateSelection({
        installs: {
          "juno-codex-app-server": createNpmInstall({
            spec: "juno-codex-app-server@beta",
            installPath: "/tmp/juno-codex-app-server",
            resolvedName: "juno-codex-app-server",
          }),
        },
        rawId: "juno-codex-app-server",
      }),
    ).toEqual({
      pluginIds: ["juno-codex-app-server"],
    });
  });
});
