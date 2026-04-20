import { describe, expect, it } from "vitest";
import type { JunoConfig } from "../config/config.js";
import { resolvePluginUninstallId } from "./plugins-uninstall-selection.js";

describe("resolvePluginUninstallId", () => {
  it("accepts the recorded JunoHub spec as an uninstall target", () => {
    const result = resolvePluginUninstallId({
      rawId: "junohub:linkmind-context",
      config: {
        plugins: {
          entries: {
            "linkmind-context": { enabled: true },
          },
          installs: {
            "linkmind-context": {
              source: "npm",
              spec: "junohub:linkmind-context",
              junohubPackage: "linkmind-context",
            },
          },
        },
      } as JunoConfig,
      plugins: [{ id: "linkmind-context", name: "linkmind-context" }],
    });

    expect(result.pluginId).toBe("linkmind-context");
  });

  it("accepts a versionless JunoHub spec when the install was pinned", () => {
    const result = resolvePluginUninstallId({
      rawId: "junohub:linkmind-context",
      config: {
        plugins: {
          entries: {
            "linkmind-context": { enabled: true },
          },
          installs: {
            "linkmind-context": {
              source: "npm",
              spec: "junohub:linkmind-context@1.2.3",
            },
          },
        },
      } as JunoConfig,
      plugins: [{ id: "linkmind-context", name: "linkmind-context" }],
    });

    expect(result.pluginId).toBe("linkmind-context");
  });
});
