import fs from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { syncPluginVersions } from "../../scripts/sync-plugin-versions.js";
import { cleanupTempDirs, makeTempDir } from "../../test/helpers/temp-dir.js";

const tempDirs: string[] = [];

function writeJson(filePath: string, value: unknown) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

describe("syncPluginVersions", () => {
  afterEach(() => {
    cleanupTempDirs(tempDirs);
  });

  it("preserves workspace juno devDependencies and plugin host floors", () => {
    const rootDir = makeTempDir(tempDirs, "juno-sync-plugin-versions-");

    writeJson(path.join(rootDir, "package.json"), {
      name: "juno",
      version: "2026.4.1",
    });
    writeJson(path.join(rootDir, "extensions/bluebubbles/package.json"), {
      name: "@juno/bluebubbles",
      version: "2026.3.30",
      devDependencies: {
        juno: "workspace:*",
      },
      peerDependencies: {
        juno: ">=2026.3.30",
      },
      juno: {
        install: {
          minHostVersion: ">=2026.3.30",
        },
        compat: {
          pluginApi: ">=2026.3.30",
        },
        build: {
          junoVersion: "2026.3.30",
        },
      },
    });

    const summary = syncPluginVersions(rootDir);
    const updatedPackage = JSON.parse(
      fs.readFileSync(path.join(rootDir, "extensions/bluebubbles/package.json"), "utf8"),
    ) as {
      version?: string;
      devDependencies?: Record<string, string>;
      peerDependencies?: Record<string, string>;
      juno?: {
        install?: {
          minHostVersion?: string;
        };
        compat?: {
          pluginApi?: string;
        };
        build?: {
          junoVersion?: string;
        };
      };
    };

    expect(summary.updated).toContain("@juno/bluebubbles");
    expect(updatedPackage.version).toBe("2026.4.1");
    expect(updatedPackage.devDependencies?.juno).toBe("workspace:*");
    expect(updatedPackage.peerDependencies?.juno).toBe(">=2026.4.1");
    expect(updatedPackage.juno?.install?.minHostVersion).toBe(">=2026.3.30");
    expect(updatedPackage.juno?.compat?.pluginApi).toBe(">=2026.4.1");
    expect(updatedPackage.juno?.build?.junoVersion).toBe("2026.4.1");
  });
});
