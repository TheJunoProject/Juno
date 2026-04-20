import path from "node:path";
import { describe, expect, it } from "vitest";
import { formatCliCommand } from "./command-format.js";
import { applyCliProfileEnv, parseCliProfileArgs } from "./profile.js";

describe("parseCliProfileArgs", () => {
  it("leaves gateway --dev for subcommands", () => {
    const res = parseCliProfileArgs([
      "node",
      "juno",
      "gateway",
      "--dev",
      "--allow-unconfigured",
    ]);
    if (!res.ok) {
      throw new Error(res.error);
    }
    expect(res.profile).toBeNull();
    expect(res.argv).toEqual(["node", "juno", "gateway", "--dev", "--allow-unconfigured"]);
  });

  it("leaves gateway --dev for subcommands after leading root options", () => {
    const res = parseCliProfileArgs([
      "node",
      "juno",
      "--no-color",
      "gateway",
      "--dev",
      "--allow-unconfigured",
    ]);
    if (!res.ok) {
      throw new Error(res.error);
    }
    expect(res.profile).toBeNull();
    expect(res.argv).toEqual([
      "node",
      "juno",
      "--no-color",
      "gateway",
      "--dev",
      "--allow-unconfigured",
    ]);
  });

  it("still accepts global --dev before subcommand", () => {
    const res = parseCliProfileArgs(["node", "juno", "--dev", "gateway"]);
    if (!res.ok) {
      throw new Error(res.error);
    }
    expect(res.profile).toBe("dev");
    expect(res.argv).toEqual(["node", "juno", "gateway"]);
  });

  it("parses --profile value and strips it", () => {
    const res = parseCliProfileArgs(["node", "juno", "--profile", "work", "status"]);
    if (!res.ok) {
      throw new Error(res.error);
    }
    expect(res.profile).toBe("work");
    expect(res.argv).toEqual(["node", "juno", "status"]);
  });

  it("parses interleaved --profile after the command token", () => {
    const res = parseCliProfileArgs(["node", "juno", "status", "--profile", "work", "--deep"]);
    if (!res.ok) {
      throw new Error(res.error);
    }
    expect(res.profile).toBe("work");
    expect(res.argv).toEqual(["node", "juno", "status", "--deep"]);
  });

  it("parses interleaved --dev after the command token", () => {
    const res = parseCliProfileArgs(["node", "juno", "status", "--dev"]);
    if (!res.ok) {
      throw new Error(res.error);
    }
    expect(res.profile).toBe("dev");
    expect(res.argv).toEqual(["node", "juno", "status"]);
  });

  it("rejects missing profile value", () => {
    const res = parseCliProfileArgs(["node", "juno", "--profile"]);
    expect(res.ok).toBe(false);
  });

  it.each([
    ["--dev first", ["node", "juno", "--dev", "--profile", "work", "status"]],
    ["--profile first", ["node", "juno", "--profile", "work", "--dev", "status"]],
    ["interleaved after command", ["node", "juno", "status", "--profile", "work", "--dev"]],
  ])("rejects combining --dev with --profile (%s)", (_name, argv) => {
    const res = parseCliProfileArgs(argv);
    expect(res.ok).toBe(false);
  });
});

describe("applyCliProfileEnv", () => {
  it("fills env defaults for dev profile", () => {
    const env: Record<string, string | undefined> = {};
    applyCliProfileEnv({
      profile: "dev",
      env,
      homedir: () => "/home/peter",
    });
    const expectedStateDir = path.join(path.resolve("/home/peter"), ".juno-dev");
    expect(env.JUNO_PROFILE).toBe("dev");
    expect(env.JUNO_STATE_DIR).toBe(expectedStateDir);
    expect(env.JUNO_CONFIG_PATH).toBe(path.join(expectedStateDir, "juno.json"));
    expect(env.JUNO_GATEWAY_PORT).toBe("19001");
  });

  it("does not override explicit env values", () => {
    const env: Record<string, string | undefined> = {
      JUNO_STATE_DIR: "/custom",
      JUNO_GATEWAY_PORT: "19099",
    };
    applyCliProfileEnv({
      profile: "dev",
      env,
      homedir: () => "/home/peter",
    });
    expect(env.JUNO_STATE_DIR).toBe("/custom");
    expect(env.JUNO_GATEWAY_PORT).toBe("19099");
    expect(env.JUNO_CONFIG_PATH).toBe(path.join("/custom", "juno.json"));
  });

  it("uses JUNO_HOME when deriving profile state dir", () => {
    const env: Record<string, string | undefined> = {
      JUNO_HOME: "/srv/juno-home",
      HOME: "/home/other",
    };
    applyCliProfileEnv({
      profile: "work",
      env,
      homedir: () => "/home/fallback",
    });

    const resolvedHome = path.resolve("/srv/juno-home");
    expect(env.JUNO_STATE_DIR).toBe(path.join(resolvedHome, ".juno-work"));
    expect(env.JUNO_CONFIG_PATH).toBe(
      path.join(resolvedHome, ".juno-work", "juno.json"),
    );
  });
});

describe("formatCliCommand", () => {
  it.each([
    {
      name: "no profile is set",
      cmd: "juno doctor --fix",
      env: {},
      expected: "juno doctor --fix",
    },
    {
      name: "profile is default",
      cmd: "juno doctor --fix",
      env: { JUNO_PROFILE: "default" },
      expected: "juno doctor --fix",
    },
    {
      name: "profile is Default (case-insensitive)",
      cmd: "juno doctor --fix",
      env: { JUNO_PROFILE: "Default" },
      expected: "juno doctor --fix",
    },
    {
      name: "profile is invalid",
      cmd: "juno doctor --fix",
      env: { JUNO_PROFILE: "bad profile" },
      expected: "juno doctor --fix",
    },
    {
      name: "--profile is already present",
      cmd: "juno --profile work doctor --fix",
      env: { JUNO_PROFILE: "work" },
      expected: "juno --profile work doctor --fix",
    },
    {
      name: "--dev is already present",
      cmd: "juno --dev doctor",
      env: { JUNO_PROFILE: "dev" },
      expected: "juno --dev doctor",
    },
  ])("returns command unchanged when $name", ({ cmd, env, expected }) => {
    expect(formatCliCommand(cmd, env)).toBe(expected);
  });

  it("inserts --profile flag when profile is set", () => {
    expect(formatCliCommand("juno doctor --fix", { JUNO_PROFILE: "work" })).toBe(
      "juno --profile work doctor --fix",
    );
  });

  it("trims whitespace from profile", () => {
    expect(formatCliCommand("juno doctor --fix", { JUNO_PROFILE: "  jbjuno  " })).toBe(
      "juno --profile jbjuno doctor --fix",
    );
  });

  it("handles command with no args after juno", () => {
    expect(formatCliCommand("juno", { JUNO_PROFILE: "test" })).toBe(
      "juno --profile test",
    );
  });

  it("handles pnpm wrapper", () => {
    expect(formatCliCommand("pnpm juno doctor", { JUNO_PROFILE: "work" })).toBe(
      "pnpm juno --profile work doctor",
    );
  });

  it("inserts --container when a container hint is set", () => {
    expect(
      formatCliCommand("juno gateway status --deep", { JUNO_CONTAINER_HINT: "demo" }),
    ).toBe("juno --container demo gateway status --deep");
  });

  it("ignores unsafe container hints", () => {
    expect(
      formatCliCommand("juno gateway status --deep", {
        JUNO_CONTAINER_HINT: "demo; rm -rf /",
      }),
    ).toBe("juno gateway status --deep");
  });

  it("preserves both --container and --profile hints", () => {
    expect(
      formatCliCommand("juno doctor", {
        JUNO_CONTAINER_HINT: "demo",
        JUNO_PROFILE: "work",
      }),
    ).toBe("juno --container demo doctor");
  });

  it("does not prepend --container for update commands", () => {
    expect(formatCliCommand("juno update", { JUNO_CONTAINER_HINT: "demo" })).toBe(
      "juno update",
    );
    expect(
      formatCliCommand("pnpm juno update --channel beta", { JUNO_CONTAINER_HINT: "demo" }),
    ).toBe("pnpm juno update --channel beta");
  });
});
