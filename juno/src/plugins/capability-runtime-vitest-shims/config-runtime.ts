import { resolveActiveTalkProviderConfig } from "../../config/talk.js";
import type { JunoConfig } from "../../config/types.js";

export { resolveActiveTalkProviderConfig };

export function getRuntimeConfigSnapshot(): JunoConfig | null {
  return null;
}
