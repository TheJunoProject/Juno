import { describe, expect, it } from "vitest";
import {
  ensureJunoExecMarkerOnProcess,
  markJunoExecEnv,
  JUNO_CLI_ENV_VALUE,
  JUNO_CLI_ENV_VAR,
} from "./juno-exec-env.js";

describe("markJunoExecEnv", () => {
  it("returns a cloned env object with the exec marker set", () => {
    const env = { PATH: "/usr/bin", JUNO_CLI: "0" };
    const marked = markJunoExecEnv(env);

    expect(marked).toEqual({
      PATH: "/usr/bin",
      JUNO_CLI: JUNO_CLI_ENV_VALUE,
    });
    expect(marked).not.toBe(env);
    expect(env.JUNO_CLI).toBe("0");
  });
});

describe("ensureJunoExecMarkerOnProcess", () => {
  it.each([
    {
      name: "mutates and returns the provided process env",
      env: { PATH: "/usr/bin" } as NodeJS.ProcessEnv,
    },
    {
      name: "overwrites an existing marker on the provided process env",
      env: { PATH: "/usr/bin", [JUNO_CLI_ENV_VAR]: "0" } as NodeJS.ProcessEnv,
    },
  ])("$name", ({ env }) => {
    expect(ensureJunoExecMarkerOnProcess(env)).toBe(env);
    expect(env[JUNO_CLI_ENV_VAR]).toBe(JUNO_CLI_ENV_VALUE);
  });

  it("defaults to mutating process.env when no env object is provided", () => {
    const previous = process.env[JUNO_CLI_ENV_VAR];
    delete process.env[JUNO_CLI_ENV_VAR];

    try {
      expect(ensureJunoExecMarkerOnProcess()).toBe(process.env);
      expect(process.env[JUNO_CLI_ENV_VAR]).toBe(JUNO_CLI_ENV_VALUE);
    } finally {
      if (previous === undefined) {
        delete process.env[JUNO_CLI_ENV_VAR];
      } else {
        process.env[JUNO_CLI_ENV_VAR] = previous;
      }
    }
  });
});
