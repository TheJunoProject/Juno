import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const loadConfigMock = vi.fn();
const applyPluginAutoEnableMock = vi.fn();
const loadJunoPluginsMock = vi.fn();

let loadPluginMetadataRegistrySnapshot: typeof import("./metadata-registry-loader.js").loadPluginMetadataRegistrySnapshot;

vi.mock("../../config/config.js", () => ({
  loadConfig: () => loadConfigMock(),
}));

vi.mock("../../config/plugin-auto-enable.js", () => ({
  applyPluginAutoEnable: (...args: unknown[]) => applyPluginAutoEnableMock(...args),
}));

vi.mock("../loader.js", () => ({
  loadJunoPlugins: (...args: unknown[]) => loadJunoPluginsMock(...args),
}));

vi.mock("../../agents/agent-scope.js", () => ({
  resolveAgentWorkspaceDir: () => "/resolved-workspace",
  resolveDefaultAgentId: () => "default",
}));

describe("loadPluginMetadataRegistrySnapshot", () => {
  beforeAll(async () => {
    ({ loadPluginMetadataRegistrySnapshot } = await import("./metadata-registry-loader.js"));
  });

  beforeEach(() => {
    loadConfigMock.mockReset();
    applyPluginAutoEnableMock.mockReset();
    loadJunoPluginsMock.mockReset();
    loadConfigMock.mockReturnValue({ plugins: {} });
    applyPluginAutoEnableMock.mockImplementation((params: { config: unknown }) => ({
      config: params.config,
      changes: [],
      autoEnabledReasons: {},
    }));
    loadJunoPluginsMock.mockReturnValue({ plugins: [], diagnostics: [] });
  });

  it("defaults to a non-activating validate snapshot", () => {
    loadPluginMetadataRegistrySnapshot({
      config: { plugins: {} },
      activationSourceConfig: { plugins: { allow: ["demo"] } },
      env: { HOME: "/tmp/juno-home" } as NodeJS.ProcessEnv,
      workspaceDir: "/workspace",
      onlyPluginIds: ["demo"],
    });

    expect(loadJunoPluginsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        config: { plugins: {} },
        activationSourceConfig: { plugins: { allow: ["demo"] } },
        workspaceDir: "/workspace",
        env: { HOME: "/tmp/juno-home" },
        onlyPluginIds: ["demo"],
        cache: false,
        activate: false,
        mode: "validate",
        loadModules: undefined,
      }),
    );
  });

  it("forwards explicit manifest-only requests", () => {
    loadPluginMetadataRegistrySnapshot({
      config: { plugins: {} },
      loadModules: false,
    });

    expect(loadJunoPluginsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        loadModules: false,
        mode: "validate",
      }),
    );
  });

  it("preserves explicit empty plugin scopes on metadata snapshots", () => {
    loadPluginMetadataRegistrySnapshot({
      config: { plugins: {} },
      onlyPluginIds: [],
    });

    expect(loadJunoPluginsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        onlyPluginIds: [],
        mode: "validate",
      }),
    );
  });
});
