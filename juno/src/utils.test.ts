import fs from "node:fs";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { withTempDir } from "./test-helpers/temp-dir.js";
import {
  ensureDir,
  resolveConfigDir,
  resolveHomeDir,
  resolveUserPath,
  shortenHomeInString,
  shortenHomePath,
  sleep,
} from "./utils.js";

describe("ensureDir", () => {
  it("creates nested directory", async () => {
    await withTempDir({ prefix: "juno-test-" }, async (tmp) => {
      const target = path.join(tmp, "nested", "dir");
      await ensureDir(target);
      expect(fs.existsSync(target)).toBe(true);
    });
  });
});

describe("sleep", () => {
  it("resolves after delay using fake timers", async () => {
    vi.useFakeTimers();
    const promise = sleep(1000);
    vi.advanceTimersByTime(1000);
    await expect(promise).resolves.toBeUndefined();
    vi.useRealTimers();
  });
});

describe("resolveConfigDir", () => {
  it("prefers ~/.juno when legacy dir is missing", async () => {
    await withTempDir({ prefix: "juno-config-dir-" }, async (root) => {
      const newDir = path.join(root, ".juno");
      await fs.promises.mkdir(newDir, { recursive: true });
      const resolved = resolveConfigDir({} as NodeJS.ProcessEnv, () => root);
      expect(resolved).toBe(newDir);
    });
  });

  it("expands JUNO_STATE_DIR using the provided env", () => {
    const env = {
      HOME: "/tmp/juno-home",
      JUNO_STATE_DIR: "~/state",
    } as NodeJS.ProcessEnv;

    expect(resolveConfigDir(env)).toBe(path.resolve("/tmp/juno-home", "state"));
  });

  it("falls back to the config file directory when only JUNO_CONFIG_PATH is set", () => {
    const env = {
      HOME: "/tmp/juno-home",
      JUNO_CONFIG_PATH: "~/profiles/dev/juno.json",
    } as NodeJS.ProcessEnv;

    expect(resolveConfigDir(env)).toBe(path.resolve("/tmp/juno-home", "profiles", "dev"));
  });
});

describe("resolveHomeDir", () => {
  it("prefers JUNO_HOME over HOME", () => {
    vi.stubEnv("JUNO_HOME", "/srv/juno-home");
    vi.stubEnv("HOME", "/home/other");

    expect(resolveHomeDir()).toBe(path.resolve("/srv/juno-home"));

    vi.unstubAllEnvs();
  });
});

describe("shortenHomePath", () => {
  it("uses $JUNO_HOME prefix when JUNO_HOME is set", () => {
    vi.stubEnv("JUNO_HOME", "/srv/juno-home");
    vi.stubEnv("HOME", "/home/other");

    expect(shortenHomePath(`${path.resolve("/srv/juno-home")}/.juno/juno.json`)).toBe(
      "$JUNO_HOME/.juno/juno.json",
    );

    vi.unstubAllEnvs();
  });
});

describe("shortenHomeInString", () => {
  it("uses $JUNO_HOME replacement when JUNO_HOME is set", () => {
    vi.stubEnv("JUNO_HOME", "/srv/juno-home");
    vi.stubEnv("HOME", "/home/other");

    expect(
      shortenHomeInString(`config: ${path.resolve("/srv/juno-home")}/.juno/juno.json`),
    ).toBe("config: $JUNO_HOME/.juno/juno.json");

    vi.unstubAllEnvs();
  });
});

describe("resolveUserPath", () => {
  it("expands ~ to home dir", () => {
    expect(resolveUserPath("~", {}, () => "/Users/thoffman")).toBe(path.resolve("/Users/thoffman"));
  });

  it("expands ~/ to home dir", () => {
    expect(resolveUserPath("~/juno", {}, () => "/Users/thoffman")).toBe(
      path.resolve("/Users/thoffman", "juno"),
    );
  });

  it("resolves relative paths", () => {
    expect(resolveUserPath("tmp/dir")).toBe(path.resolve("tmp/dir"));
  });

  it("prefers JUNO_HOME for tilde expansion", () => {
    vi.stubEnv("JUNO_HOME", "/srv/juno-home");
    vi.stubEnv("HOME", "/home/other");

    expect(resolveUserPath("~/juno")).toBe(path.resolve("/srv/juno-home", "juno"));

    vi.unstubAllEnvs();
  });

  it("uses the provided env for tilde expansion", () => {
    const env = {
      HOME: "/tmp/juno-home",
      JUNO_HOME: "/srv/juno-home",
    } as NodeJS.ProcessEnv;

    expect(resolveUserPath("~/juno", env)).toBe(path.resolve("/srv/juno-home", "juno"));
  });

  it("keeps blank paths blank", () => {
    expect(resolveUserPath("")).toBe("");
    expect(resolveUserPath("   ")).toBe("");
  });

  it("returns empty string for undefined/null input", () => {
    expect(resolveUserPath(undefined as unknown as string)).toBe("");
    expect(resolveUserPath(null as unknown as string)).toBe("");
  });
});
