import type { JunoConfig } from "../../config/types.juno.js";

export function makeModelFallbackCfg(overrides: Partial<JunoConfig> = {}): JunoConfig {
  return {
    agents: {
      defaults: {
        model: {
          primary: "openai/gpt-4.1-mini",
          fallbacks: ["anthropic/claude-haiku-3-5"],
        },
      },
    },
    ...overrides,
  } as JunoConfig;
}
