import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { Readable } from "node:stream";
import JSZip from "jszip";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const parseJunoHubPluginSpecMock = vi.fn();
const fetchJunoHubPackageDetailMock = vi.fn();
const fetchJunoHubPackageVersionMock = vi.fn();
const downloadJunoHubPackageArchiveMock = vi.fn();
const archiveCleanupMock = vi.fn();
const resolveLatestVersionFromPackageMock = vi.fn();
const resolveCompatibilityHostVersionMock = vi.fn();
const installPluginFromArchiveMock = vi.fn();

vi.mock("../infra/junohub.js", async () => {
  const actual = await vi.importActual<typeof import("../infra/junohub.js")>("../infra/junohub.js");
  return {
    ...actual,
    parseJunoHubPluginSpec: (...args: unknown[]) => parseJunoHubPluginSpecMock(...args),
    fetchJunoHubPackageDetail: (...args: unknown[]) => fetchJunoHubPackageDetailMock(...args),
    fetchJunoHubPackageVersion: (...args: unknown[]) => fetchJunoHubPackageVersionMock(...args),
    downloadJunoHubPackageArchive: (...args: unknown[]) =>
      downloadJunoHubPackageArchiveMock(...args),
    resolveLatestVersionFromPackage: (...args: unknown[]) =>
      resolveLatestVersionFromPackageMock(...args),
  };
});

vi.mock("../version.js", () => ({
  resolveCompatibilityHostVersion: (...args: unknown[]) =>
    resolveCompatibilityHostVersionMock(...args),
}));

vi.mock("./install.js", () => ({
  installPluginFromArchive: (...args: unknown[]) => installPluginFromArchiveMock(...args),
}));

vi.mock("../infra/archive.js", async () => {
  const actual = await vi.importActual<typeof import("../infra/archive.js")>("../infra/archive.js");
  return {
    ...actual,
    DEFAULT_MAX_ENTRIES: 50_000,
    DEFAULT_MAX_EXTRACTED_BYTES: 512 * 1024 * 1024,
    DEFAULT_MAX_ENTRY_BYTES: 256 * 1024 * 1024,
  };
});

const { JunoHubRequestError } = await import("../infra/junohub.js");
const { JUNOHUB_INSTALL_ERROR_CODE, formatJunoHubSpecifier, installPluginFromJunoHub } =
  await import("./junohub.js");

const DEMO_ARCHIVE_INTEGRITY = "sha256-qerEjGEpvES2+Tyan0j2xwDRkbcnmh4ZFfKN9vWbsa8=";
const tempDirs: string[] = [];

function sha256Hex(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

async function createJunoHubArchive(entries: Record<string, string>) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "juno-junohub-archive-"));
  tempDirs.push(dir);
  const archivePath = path.join(dir, "archive.zip");
  const zip = new JSZip();
  for (const [filePath, contents] of Object.entries(entries)) {
    zip.file(filePath, contents);
  }
  const archiveBytes = await zip.generateAsync({ type: "nodebuffer" });
  await fs.writeFile(archivePath, archiveBytes);
  return {
    archivePath,
    integrity: `sha256-${createHash("sha256").update(archiveBytes).digest("base64")}`,
  };
}

async function expectJunoHubInstallError(params: {
  setup?: () => void;
  spec: string;
  expected: {
    ok: false;
    code: (typeof JUNOHUB_INSTALL_ERROR_CODE)[keyof typeof JUNOHUB_INSTALL_ERROR_CODE];
    error: string;
  };
}) {
  params.setup?.();
  await expect(installPluginFromJunoHub({ spec: params.spec })).resolves.toMatchObject(
    params.expected,
  );
}

function createLoggerSpies() {
  return {
    info: vi.fn(),
    warn: vi.fn(),
  };
}

function expectJunoHubInstallFlow(params: {
  baseUrl: string;
  version: string;
  archivePath: string;
}) {
  expect(fetchJunoHubPackageDetailMock).toHaveBeenCalledWith(
    expect.objectContaining({
      name: "demo",
      baseUrl: params.baseUrl,
    }),
  );
  expect(fetchJunoHubPackageVersionMock).toHaveBeenCalledWith(
    expect.objectContaining({
      name: "demo",
      version: params.version,
    }),
  );
  expect(installPluginFromArchiveMock).toHaveBeenCalledWith(
    expect.objectContaining({
      archivePath: params.archivePath,
    }),
  );
}

function expectSuccessfulJunoHubInstall(result: unknown) {
  expect(result).toMatchObject({
    ok: true,
    pluginId: "demo",
    version: "2026.3.22",
    junohub: {
      source: "junohub",
      junohubPackage: "demo",
      junohubFamily: "code-plugin",
      junohubChannel: "official",
      integrity: DEMO_ARCHIVE_INTEGRITY,
    },
  });
}

describe("installPluginFromJunoHub", () => {
  afterEach(async () => {
    await Promise.all(
      tempDirs.splice(0).map((dir) => fs.rm(dir, { recursive: true, force: true })),
    );
  });

  beforeEach(() => {
    parseJunoHubPluginSpecMock.mockReset();
    fetchJunoHubPackageDetailMock.mockReset();
    fetchJunoHubPackageVersionMock.mockReset();
    downloadJunoHubPackageArchiveMock.mockReset();
    archiveCleanupMock.mockReset();
    resolveLatestVersionFromPackageMock.mockReset();
    resolveCompatibilityHostVersionMock.mockReset();
    installPluginFromArchiveMock.mockReset();

    parseJunoHubPluginSpecMock.mockReturnValue({ name: "demo" });
    fetchJunoHubPackageDetailMock.mockResolvedValue({
      package: {
        name: "demo",
        displayName: "Demo",
        family: "code-plugin",
        channel: "official",
        isOfficial: true,
        createdAt: 0,
        updatedAt: 0,
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    resolveLatestVersionFromPackageMock.mockReturnValue("2026.3.22");
    fetchJunoHubPackageVersionMock.mockResolvedValue({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        sha256hash: "a9eac48c6129bc44b6f93c9a9f48f6c700d191b7279a1e1915f28df6f59bb1af",
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValue({
      archivePath: "/tmp/junohub-demo/archive.zip",
      integrity: DEMO_ARCHIVE_INTEGRITY,
      cleanup: archiveCleanupMock,
    });
    archiveCleanupMock.mockResolvedValue(undefined);
    resolveCompatibilityHostVersionMock.mockReturnValue("2026.3.22");
    installPluginFromArchiveMock.mockResolvedValue({
      ok: true,
      pluginId: "demo",
      targetDir: "/tmp/juno/plugins/demo",
      version: "2026.3.22",
    });
  });

  it("formats junohub specifiers", () => {
    expect(formatJunoHubSpecifier({ name: "demo" })).toBe("junohub:demo");
    expect(formatJunoHubSpecifier({ name: "demo", version: "1.2.3" })).toBe("junohub:demo@1.2.3");
  });

  it("installs a JunoHub code plugin through the archive installer", async () => {
    const logger = createLoggerSpies();
    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
      baseUrl: "https://junohub.ai",
      logger,
    });

    expectJunoHubInstallFlow({
      baseUrl: "https://junohub.ai",
      version: "2026.3.22",
      archivePath: "/tmp/junohub-demo/archive.zip",
    });
    expectSuccessfulJunoHubInstall(result);
    expect(logger.info).toHaveBeenCalledWith("JunoHub code-plugin demo@2026.3.22 channel=official");
    expect(logger.info).toHaveBeenCalledWith(
      "Compatibility: pluginApi=>=2026.3.22 minGateway=2026.3.0",
    );
    expect(logger.warn).not.toHaveBeenCalled();
    expect(archiveCleanupMock).toHaveBeenCalledTimes(1);
  });

  it("passes dangerous force unsafe install through to archive installs", async () => {
    await installPluginFromJunoHub({
      spec: "junohub:demo",
      dangerouslyForceUnsafeInstall: true,
    });

    expect(installPluginFromArchiveMock).toHaveBeenCalledWith(
      expect.objectContaining({
        archivePath: "/tmp/junohub-demo/archive.zip",
        dangerouslyForceUnsafeInstall: true,
      }),
    );
  });

  it("cleans up the downloaded archive even when archive install fails", async () => {
    installPluginFromArchiveMock.mockResolvedValueOnce({
      ok: false,
      error: "bad archive",
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
      baseUrl: "https://junohub.ai",
    });

    expect(result).toMatchObject({
      ok: false,
      error: "bad archive",
    });
    expect(archiveCleanupMock).toHaveBeenCalledTimes(1);
  });

  it("accepts version-endpoint SHA-256 hashes expressed as raw hex", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        sha256hash: "a9eac48c6129bc44b6f93c9a9f48f6c700d191b7279a1e1915f28df6f59bb1af",
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      archivePath: "/tmp/junohub-demo/archive.zip",
      integrity: "sha256-qerEjGEpvES2+Tyan0j2xwDRkbcnmh4ZFfKN9vWbsa8=",
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({ ok: true, pluginId: "demo" });
  });

  it("accepts version-endpoint SHA-256 hashes expressed as unpadded SRI", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        sha256hash: "sha256-qerEjGEpvES2+Tyan0j2xwDRkbcnmh4ZFfKN9vWbsa8",
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      archivePath: "/tmp/junohub-demo/archive.zip",
      integrity: DEMO_ARCHIVE_INTEGRITY,
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({ ok: true, pluginId: "demo" });
  });

  it("falls back to strict files[] verification when sha256hash is missing", async () => {
    const archive = await createJunoHubArchive({
      "juno.plugin.json": '{"id":"demo"}',
      "dist/index.js": 'export const demo = "ok";',
      "_meta.json": '{"slug":"demo","version":"2026.3.22"}',
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        sha256hash: null,
        files: [
          {
            path: "dist/index.js",
            size: 25,
            sha256: sha256Hex('export const demo = "ok";'),
          },
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      ...archive,
      cleanup: archiveCleanupMock,
    });
    const logger = createLoggerSpies();

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
      logger,
    });

    expect(result).toMatchObject({ ok: true, pluginId: "demo" });
    expect(logger.warn).toHaveBeenCalledWith(
      'JunoHub package "demo@2026.3.22" is missing sha256hash; falling back to files[] verification. Validated files: dist/index.js, juno.plugin.json. Validated generated metadata files present in archive: _meta.json (JSON parse plus slug/version match only).',
    );
  });

  it("validates _meta.json against canonical package and resolved version metadata", async () => {
    const archive = await createJunoHubArchive({
      "juno.plugin.json": '{"id":"demo"}',
      "_meta.json": '{"slug":"demo","version":"2026.3.22"}',
    });
    parseJunoHubPluginSpecMock.mockReturnValueOnce({ name: "DemoAlias", version: "latest" });
    fetchJunoHubPackageDetailMock.mockResolvedValueOnce({
      package: {
        name: "demo",
        displayName: "Demo",
        family: "code-plugin",
        channel: "official",
        isOfficial: true,
        createdAt: 0,
        updatedAt: 0,
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        sha256hash: null,
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      ...archive,
      cleanup: archiveCleanupMock,
    });
    const logger = createLoggerSpies();

    const result = await installPluginFromJunoHub({
      spec: "junohub:DemoAlias@latest",
      logger,
    });

    expect(result).toMatchObject({ ok: true, pluginId: "demo", version: "2026.3.22" });
    expect(fetchJunoHubPackageDetailMock).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "DemoAlias",
      }),
    );
    expect(fetchJunoHubPackageVersionMock).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "demo",
        version: "latest",
      }),
    );
    expect(logger.warn).toHaveBeenCalledWith(
      'JunoHub package "demo@2026.3.22" is missing sha256hash; falling back to files[] verification. Validated files: juno.plugin.json. Validated generated metadata files present in archive: _meta.json (JSON parse plus slug/version match only).',
    );
  });

  it("fails closed when sha256hash is present but unrecognized instead of silently falling back", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        sha256hash: "definitely-not-a-sha256",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" has an invalid sha256hash (unrecognized value "definitely-not-a-sha256").',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects JunoHub installs when sha256hash is explicitly null and files[] is unavailable", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        sha256hash: null,
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" is missing sha256hash and usable files[] metadata for fallback archive verification.',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects JunoHub installs when the version metadata has no archive hash or fallback files[]", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" is missing sha256hash and usable files[] metadata for fallback archive verification.',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it("fails closed when files[] contains a malformed entry", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [null as unknown as { path: string; sha256: string }],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" has an invalid files[0] entry (expected an object, got null).',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it("fails closed when files[] contains an invalid sha256", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: "not-a-digest",
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" has an invalid files[0].sha256 (value "not-a-digest" is not a 64-character hexadecimal SHA-256 digest).',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it("fails closed when sha256hash is not a string", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        sha256hash: 123 as unknown as string,
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" has an invalid sha256hash (non-string value of type number).',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it("returns a typed install failure when the archive download throws", async () => {
    downloadJunoHubPackageArchiveMock.mockRejectedValueOnce(new Error("network timeout"));

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      error: "network timeout",
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("returns a typed install failure when fallback archive verification cannot read the zip", async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "juno-junohub-archive-"));
    tempDirs.push(dir);
    const archivePath = path.join(dir, "archive.zip");
    await fs.writeFile(archivePath, "not-a-zip", "utf8");
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      archivePath,
      integrity: "sha256-not-used-in-fallback",
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error: "JunoHub archive fallback verification failed while reading the downloaded archive.",
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects JunoHub installs when the downloaded archive hash drifts from metadata", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        sha256hash: "1111111111111111111111111111111111111111111111111111111111111111",
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      archivePath: "/tmp/junohub-demo/archive.zip",
      integrity: DEMO_ARCHIVE_INTEGRITY,
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error: `JunoHub archive integrity mismatch for "demo@2026.3.22": expected sha256-ERERERERERERERERERERERERERERERERERERERERERE=, got ${DEMO_ARCHIVE_INTEGRITY}.`,
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
    expect(archiveCleanupMock).toHaveBeenCalledTimes(1);
  });

  it("rejects fallback verification when an expected file is missing from the archive", async () => {
    const archive = await createJunoHubArchive({
      "juno.plugin.json": '{"id":"demo"}',
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
          {
            path: "dist/index.js",
            size: 25,
            sha256: sha256Hex('export const demo = "ok";'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      ...archive,
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error:
        'JunoHub archive contents do not match files[] metadata for "demo@2026.3.22": missing "dist/index.js".',
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback verification when the archive includes an unexpected file", async () => {
    const archive = await createJunoHubArchive({
      "juno.plugin.json": '{"id":"demo"}',
      "dist/index.js": 'export const demo = "ok";',
      "extra.txt": "surprise",
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
          {
            path: "dist/index.js",
            size: 25,
            sha256: sha256Hex('export const demo = "ok";'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      ...archive,
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error:
        'JunoHub archive contents do not match files[] metadata for "demo@2026.3.22": unexpected file "extra.txt".',
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("accepts root-level files[] paths and allows _meta.json as an unvalidated generated file", async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "juno-junohub-archive-"));
    tempDirs.push(dir);
    const archivePath = path.join(dir, "archive.zip");
    const zip = new JSZip();
    zip.file("scripts/search.py", "print('ok')\n");
    zip.file("SKILL.md", "# Demo\n");
    zip.file("_meta.json", '{"slug":"demo","version":"2026.3.22"}');
    const archiveBytes = await zip.generateAsync({ type: "nodebuffer" });
    await fs.writeFile(archivePath, archiveBytes);
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "scripts/search.py",
            size: 12,
            sha256: sha256Hex("print('ok')\n"),
          },
          {
            path: "SKILL.md",
            size: 7,
            sha256: sha256Hex("# Demo\n"),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      archivePath,
      integrity: `sha256-${createHash("sha256").update(archiveBytes).digest("base64")}`,
      cleanup: archiveCleanupMock,
    });
    const logger = createLoggerSpies();

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
      logger,
    });

    expect(result).toMatchObject({ ok: true, pluginId: "demo" });
    expect(logger.warn).toHaveBeenCalledWith(
      'JunoHub package "demo@2026.3.22" is missing sha256hash; falling back to files[] verification. Validated files: SKILL.md, scripts/search.py. Validated generated metadata files present in archive: _meta.json (JSON parse plus slug/version match only).',
    );
  });

  it("omits the skipped-files suffix when no generated extras are present", async () => {
    const archive = await createJunoHubArchive({
      "juno.plugin.json": '{"id":"demo"}',
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      ...archive,
      cleanup: archiveCleanupMock,
    });
    const logger = createLoggerSpies();

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
      logger,
    });

    expect(result).toMatchObject({ ok: true, pluginId: "demo" });
    expect(logger.warn).toHaveBeenCalledWith(
      'JunoHub package "demo@2026.3.22" is missing sha256hash; falling back to files[] verification. Validated files: juno.plugin.json.',
    );
  });

  it("rejects fallback verification when _meta.json is not valid JSON", async () => {
    const archive = await createJunoHubArchive({
      "juno.plugin.json": '{"id":"demo"}',
      "_meta.json": "{not-json",
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      ...archive,
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error:
        'JunoHub archive contents do not match files[] metadata for "demo@2026.3.22": _meta.json is not valid JSON.',
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback verification when _meta.json slug does not match the package name", async () => {
    const archive = await createJunoHubArchive({
      "juno.plugin.json": '{"id":"demo"}',
      "_meta.json": '{"slug":"wrong","version":"2026.3.22"}',
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      ...archive,
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error:
        'JunoHub archive contents do not match files[] metadata for "demo@2026.3.22": _meta.json slug does not match the package name.',
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback verification when _meta.json exceeds the per-file size limit", async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "juno-junohub-archive-"));
    tempDirs.push(dir);
    const archivePath = path.join(dir, "archive.zip");
    await fs.writeFile(archivePath, "placeholder", "utf8");
    const oversizedMetaEntry = {
      name: "_meta.json",
      dir: false,
      _data: { uncompressedSize: 256 * 1024 * 1024 + 1 },
      nodeStream: vi.fn(),
    } as unknown as JSZip.JSZipObject;
    const listedFileEntry = {
      name: "juno.plugin.json",
      dir: false,
      _data: { uncompressedSize: 13 },
      nodeStream: () => Readable.from([Buffer.from('{"id":"demo"}')]),
    } as unknown as JSZip.JSZipObject;
    const loadAsyncSpy = vi.spyOn(JSZip, "loadAsync").mockResolvedValueOnce({
      files: {
        "_meta.json": oversizedMetaEntry,
        "juno.plugin.json": listedFileEntry,
      },
    } as unknown as JSZip);
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      archivePath,
      integrity: "sha256-not-used-in-fallback",
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    loadAsyncSpy.mockRestore();
    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error:
        'JunoHub archive fallback verification rejected "_meta.json" because it exceeds the per-file size limit.',
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback verification when archive directories alone exceed the entry limit", async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "juno-junohub-archive-"));
    tempDirs.push(dir);
    const archivePath = path.join(dir, "archive.zip");
    await fs.writeFile(archivePath, "placeholder", "utf8");
    const zipEntries = Object.fromEntries(
      Array.from({ length: 50_001 }, (_, index) => [
        `folder-${index}/`,
        {
          name: `folder-${index}/`,
          dir: true,
        },
      ]),
    );
    const loadAsyncSpy = vi.spyOn(JSZip, "loadAsync").mockResolvedValueOnce({
      files: zipEntries,
    } as unknown as JSZip);
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      archivePath,
      integrity: "sha256-not-used-in-fallback",
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    loadAsyncSpy.mockRestore();
    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error: "JunoHub archive fallback verification exceeded the archive entry limit.",
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback verification when the downloaded archive exceeds the ZIP size limit", async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "juno-junohub-archive-"));
    tempDirs.push(dir);
    const archivePath = path.join(dir, "archive.zip");
    await fs.writeFile(archivePath, "placeholder", "utf8");
    const realStat = fs.stat.bind(fs);
    const statSpy = vi.spyOn(fs, "stat").mockImplementation(async (filePath, options) => {
      if (filePath === archivePath) {
        return {
          size: 256 * 1024 * 1024 + 1,
        } as Awaited<ReturnType<typeof fs.stat>>;
      }
      return await realStat(filePath, options);
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      archivePath,
      integrity: "sha256-not-used-in-fallback",
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    statSpy.mockRestore();
    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error:
        "JunoHub archive fallback verification rejected the downloaded archive because it exceeds the ZIP archive size limit.",
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback verification when a file hash drifts from files[] metadata", async () => {
    const archive = await createJunoHubArchive({
      "juno.plugin.json": '{"id":"demo"}',
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: "1".repeat(64),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      ...archive,
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error: `JunoHub archive contents do not match files[] metadata for "demo@2026.3.22": expected juno.plugin.json to hash to ${"1".repeat(64)}, got ${sha256Hex('{"id":"demo"}')}.`,
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback metadata with an unsafe files[] path", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "../evil.txt",
            size: 4,
            sha256: "1".repeat(64),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" has an invalid files[0].path (path "../evil.txt" contains dot segments).',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback metadata with leading or trailing path whitespace", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json ",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" has an invalid files[0].path (path "juno.plugin.json " has leading or trailing whitespace).',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback verification when the archive includes a whitespace-suffixed file path", async () => {
    const archive = await createJunoHubArchive({
      "juno.plugin.json": '{"id":"demo"}',
      "juno.plugin.json ": '{"id":"demo"}',
    });
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });
    downloadJunoHubPackageArchiveMock.mockResolvedValueOnce({
      ...archive,
      cleanup: archiveCleanupMock,
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.ARCHIVE_INTEGRITY_MISMATCH,
      error:
        'JunoHub archive contents do not match files[] metadata for "demo@2026.3.22": invalid package file path "juno.plugin.json " (path "juno.plugin.json " has leading or trailing whitespace).',
    });
    expect(installPluginFromArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback metadata with duplicate files[] paths", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
          {
            path: "juno.plugin.json",
            size: 13,
            sha256: sha256Hex('{"id":"demo"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" has duplicate files[] path "juno.plugin.json".',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it("rejects fallback metadata when files[] includes generated _meta.json", async () => {
    fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
      version: {
        version: "2026.3.22",
        createdAt: 0,
        changelog: "",
        files: [
          {
            path: "_meta.json",
            size: 64,
            sha256: sha256Hex('{"slug":"demo","version":"2026.3.22"}'),
          },
        ],
        compatibility: {
          pluginApiRange: ">=2026.3.22",
          minGatewayVersion: "2026.3.0",
        },
      },
    });

    const result = await installPluginFromJunoHub({
      spec: "junohub:demo",
    });

    expect(result).toMatchObject({
      ok: false,
      code: JUNOHUB_INSTALL_ERROR_CODE.MISSING_ARCHIVE_INTEGRITY,
      error:
        'JunoHub version metadata for "demo@2026.3.22" must not include generated file "_meta.json" in files[].',
    });
    expect(downloadJunoHubPackageArchiveMock).not.toHaveBeenCalled();
  });

  it.each([
    {
      name: "rejects packages whose plugin API range exceeds the runtime version",
      setup: () => {
        resolveCompatibilityHostVersionMock.mockReturnValueOnce("2026.3.21");
      },
      spec: "junohub:demo",
      expected: {
        ok: false,
        code: JUNOHUB_INSTALL_ERROR_CODE.INCOMPATIBLE_PLUGIN_API,
        error:
          'Plugin "demo" requires plugin API >=2026.3.22, but this Juno runtime exposes 2026.3.21.',
      },
    },
    {
      name: "rejects skill families and redirects to skills install",
      setup: () => {
        fetchJunoHubPackageDetailMock.mockResolvedValueOnce({
          package: {
            name: "calendar",
            displayName: "Calendar",
            family: "skill",
            channel: "official",
            isOfficial: true,
            createdAt: 0,
            updatedAt: 0,
          },
        });
      },
      spec: "junohub:calendar",
      expected: {
        ok: false,
        code: JUNOHUB_INSTALL_ERROR_CODE.SKILL_PACKAGE,
        error: '"calendar" is a skill. Use "juno skills install calendar" instead.',
      },
    },
    {
      name: "redirects skill families before missing archive metadata checks",
      setup: () => {
        fetchJunoHubPackageDetailMock.mockResolvedValueOnce({
          package: {
            name: "calendar",
            displayName: "Calendar",
            family: "skill",
            channel: "official",
            isOfficial: true,
            createdAt: 0,
            updatedAt: 0,
          },
        });
        fetchJunoHubPackageVersionMock.mockResolvedValueOnce({
          version: {
            version: "2026.3.22",
            createdAt: 0,
            changelog: "",
          },
        });
      },
      spec: "junohub:calendar",
      expected: {
        ok: false,
        code: JUNOHUB_INSTALL_ERROR_CODE.SKILL_PACKAGE,
        error: '"calendar" is a skill. Use "juno skills install calendar" instead.',
      },
    },
    {
      name: "returns typed package-not-found failures",
      setup: () => {
        fetchJunoHubPackageDetailMock.mockRejectedValueOnce(
          new JunoHubRequestError({
            path: "/api/v1/packages/demo",
            status: 404,
            body: "Package not found",
          }),
        );
      },
      spec: "junohub:demo",
      expected: {
        ok: false,
        code: JUNOHUB_INSTALL_ERROR_CODE.PACKAGE_NOT_FOUND,
        error: "Package not found on JunoHub.",
      },
    },
    {
      name: "returns typed version-not-found failures",
      setup: () => {
        parseJunoHubPluginSpecMock.mockReturnValueOnce({ name: "demo", version: "9.9.9" });
        fetchJunoHubPackageVersionMock.mockRejectedValueOnce(
          new JunoHubRequestError({
            path: "/api/v1/packages/demo/versions/9.9.9",
            status: 404,
            body: "Version not found",
          }),
        );
      },
      spec: "junohub:demo@9.9.9",
      expected: {
        ok: false,
        code: JUNOHUB_INSTALL_ERROR_CODE.VERSION_NOT_FOUND,
        error: "Version not found on JunoHub: demo@9.9.9.",
      },
    },
  ] as const)("$name", async ({ setup, spec, expected }) => {
    await expectJunoHubInstallError({ setup, spec, expected });
  });
});
