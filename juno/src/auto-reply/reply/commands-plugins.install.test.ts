import fs from "node:fs/promises";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { withTempHome } from "../../config/home-env.test-harness.js";
import { createCommandWorkspaceHarness } from "./commands-filesystem.test-support.js";
import { handlePluginsCommand } from "./commands-plugins.js";
import type { HandleCommandsParams } from "./commands-types.js";

const { installPluginFromPathMock, installPluginFromJunoHubMock, persistPluginInstallMock } =
  vi.hoisted(() => ({
    installPluginFromPathMock: vi.fn(),
    installPluginFromJunoHubMock: vi.fn(),
    persistPluginInstallMock: vi.fn(),
  }));

vi.mock("../../plugins/install.js", async () => {
  const actual = await vi.importActual<typeof import("../../plugins/install.js")>(
    "../../plugins/install.js",
  );
  return {
    ...actual,
    installPluginFromPath: installPluginFromPathMock,
  };
});

vi.mock("../../plugins/junohub.js", async () => {
  const actual = await vi.importActual<typeof import("../../plugins/junohub.js")>(
    "../../plugins/junohub.js",
  );
  return {
    ...actual,
    installPluginFromJunoHub: installPluginFromJunoHubMock,
  };
});

vi.mock("../../cli/plugins-install-persist.js", () => ({
  persistPluginInstall: persistPluginInstallMock,
}));

const workspaceHarness = createCommandWorkspaceHarness("juno-command-plugins-install-");

function buildPluginsParams(
  commandBodyNormalized: string,
  workspaceDir: string,
): HandleCommandsParams {
  return {
    cfg: {
      commands: {
        text: true,
        plugins: true,
      },
      plugins: { enabled: true },
    },
    ctx: {
      Provider: "whatsapp",
      Surface: "whatsapp",
      CommandSource: "text",
      GatewayClientScopes: ["operator.admin", "operator.write", "operator.pairing"],
      AccountId: undefined,
    },
    command: {
      commandBodyNormalized,
      rawBodyNormalized: commandBodyNormalized,
      isAuthorizedSender: true,
      senderIsOwner: true,
      senderId: "owner",
      channel: "whatsapp",
      channelId: "whatsapp",
      surface: "whatsapp",
      ownerList: [],
      from: "test-user",
      to: "test-bot",
    },
    sessionKey: "agent:main:whatsapp:direct:test-user",
    sessionEntry: {
      sessionId: "session-plugin-command",
      updatedAt: Date.now(),
    },
    workspaceDir,
  } as unknown as HandleCommandsParams;
}

describe("handleCommands /plugins install", () => {
  afterEach(async () => {
    installPluginFromPathMock.mockReset();
    installPluginFromJunoHubMock.mockReset();
    persistPluginInstallMock.mockReset();
    await workspaceHarness.cleanupWorkspaces();
  });

  it("installs a plugin from a local path", async () => {
    installPluginFromPathMock.mockResolvedValue({
      ok: true,
      pluginId: "path-install-plugin",
      targetDir: "/tmp/path-install-plugin",
      version: "0.0.1",
      extensions: ["index.js"],
    });
    persistPluginInstallMock.mockResolvedValue({});

    await withTempHome("juno-command-plugins-home-", async () => {
      const workspaceDir = await workspaceHarness.createWorkspace();
      const pluginDir = path.join(workspaceDir, "fixtures", "path-install-plugin");
      await fs.mkdir(pluginDir, { recursive: true });

      const params = buildPluginsParams(`/plugins install ${pluginDir}`, workspaceDir);
      const result = await handlePluginsCommand(params, true);
      if (result === null) {
        throw new Error("expected plugin install result");
      }
      expect(result.reply?.text).toContain('Installed plugin "path-install-plugin"');
      expect(installPluginFromPathMock).toHaveBeenCalledWith(
        expect.objectContaining({
          path: pluginDir,
        }),
      );
      expect(persistPluginInstallMock).toHaveBeenCalledWith(
        expect.objectContaining({
          pluginId: "path-install-plugin",
          install: expect.objectContaining({
            source: "path",
            sourcePath: pluginDir,
            installPath: "/tmp/path-install-plugin",
            version: "0.0.1",
          }),
        }),
      );
    });
  });

  it("installs from an explicit junohub: spec", async () => {
    installPluginFromJunoHubMock.mockResolvedValue({
      ok: true,
      pluginId: "junohub-demo",
      targetDir: "/tmp/junohub-demo",
      version: "1.2.3",
      extensions: ["index.js"],
      packageName: "@juno/junohub-demo",
      junohub: {
        source: "junohub",
        junohubUrl: "https://junohub.ai",
        junohubPackage: "@juno/junohub-demo",
        junohubFamily: "code-plugin",
        junohubChannel: "official",
        version: "1.2.3",
        integrity: "sha512-demo",
        resolvedAt: "2026-03-22T12:00:00.000Z",
      },
    });
    persistPluginInstallMock.mockResolvedValue({});

    await withTempHome("juno-command-plugins-home-", async () => {
      const workspaceDir = await workspaceHarness.createWorkspace();
      const params = buildPluginsParams(
        "/plugins install junohub:@juno/junohub-demo@1.2.3",
        workspaceDir,
      );
      const result = await handlePluginsCommand(params, true);
      if (result === null) {
        throw new Error("expected plugin install result");
      }
      expect(result.reply?.text).toContain('Installed plugin "junohub-demo"');
      expect(installPluginFromJunoHubMock).toHaveBeenCalledWith(
        expect.objectContaining({
          spec: "junohub:@juno/junohub-demo@1.2.3",
        }),
      );
      expect(persistPluginInstallMock).toHaveBeenCalledWith(
        expect.objectContaining({
          pluginId: "junohub-demo",
          install: expect.objectContaining({
            source: "junohub",
            spec: "junohub:@juno/junohub-demo@1.2.3",
            installPath: "/tmp/junohub-demo",
            version: "1.2.3",
            integrity: "sha512-demo",
            junohubPackage: "@juno/junohub-demo",
            junohubChannel: "official",
          }),
        }),
      );
    });
  });

  it("treats /plugin add as an install alias", async () => {
    installPluginFromJunoHubMock.mockResolvedValue({
      ok: true,
      pluginId: "alias-demo",
      targetDir: "/tmp/alias-demo",
      version: "1.0.0",
      extensions: ["index.js"],
      packageName: "@juno/alias-demo",
      junohub: {
        source: "junohub",
        junohubUrl: "https://junohub.ai",
        junohubPackage: "@juno/alias-demo",
        junohubFamily: "code-plugin",
        junohubChannel: "official",
        version: "1.0.0",
        integrity: "sha512-alias",
        resolvedAt: "2026-03-23T12:00:00.000Z",
      },
    });
    persistPluginInstallMock.mockResolvedValue({});

    await withTempHome("juno-command-plugins-home-", async () => {
      const workspaceDir = await workspaceHarness.createWorkspace();
      const params = buildPluginsParams(
        "/plugin add junohub:@juno/alias-demo@1.0.0",
        workspaceDir,
      );
      const result = await handlePluginsCommand(params, true);
      if (result === null) {
        throw new Error("expected plugin install result");
      }
      expect(result.reply?.text).toContain('Installed plugin "alias-demo"');
      expect(installPluginFromJunoHubMock).toHaveBeenCalledWith(
        expect.objectContaining({
          spec: "junohub:@juno/alias-demo@1.0.0",
        }),
      );
    });
  });
});
