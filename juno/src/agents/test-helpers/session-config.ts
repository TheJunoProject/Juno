import type { JunoConfig } from "../../config/types.juno.js";

export function createPerSenderSessionConfig(
  overrides: Partial<NonNullable<JunoConfig["session"]>> = {},
): NonNullable<JunoConfig["session"]> {
  return {
    mainKey: "main",
    scope: "per-sender",
    ...overrides,
  };
}
