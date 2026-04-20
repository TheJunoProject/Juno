import {
  createModelCatalogPresetAppliers,
  type JunoConfig,
} from "juno/plugin-sdk/provider-onboard";
import {
  buildTogetherModelDefinition,
  TOGETHER_BASE_URL,
  TOGETHER_MODEL_CATALOG,
} from "./models.js";

export const TOGETHER_DEFAULT_MODEL_REF = "together/moonshotai/Kimi-K2.5";

const togetherPresetAppliers = createModelCatalogPresetAppliers({
  primaryModelRef: TOGETHER_DEFAULT_MODEL_REF,
  resolveParams: (_cfg: JunoConfig) => ({
    providerId: "together",
    api: "openai-completions",
    baseUrl: TOGETHER_BASE_URL,
    catalogModels: TOGETHER_MODEL_CATALOG.map(buildTogetherModelDefinition),
    aliases: [{ modelRef: TOGETHER_DEFAULT_MODEL_REF, alias: "Together AI" }],
  }),
});

export function applyTogetherProviderConfig(cfg: JunoConfig): JunoConfig {
  return togetherPresetAppliers.applyProviderConfig(cfg);
}

export function applyTogetherConfig(cfg: JunoConfig): JunoConfig {
  return togetherPresetAppliers.applyConfig(cfg);
}
