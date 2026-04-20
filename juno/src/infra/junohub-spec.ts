import { normalizeLowercaseStringOrEmpty } from "../shared/string-coerce.js";

export function parseJunoHubPluginSpec(raw: string): {
  name: string;
  version?: string;
  baseUrl?: string;
} | null {
  const trimmed = raw.trim();
  if (!normalizeLowercaseStringOrEmpty(trimmed).startsWith("junohub:")) {
    return null;
  }
  const spec = trimmed.slice("junohub:".length).trim();
  if (!spec) {
    return null;
  }
  const atIndex = spec.lastIndexOf("@");
  if (atIndex <= 0 || atIndex >= spec.length - 1) {
    return { name: spec };
  }
  return {
    name: spec.slice(0, atIndex).trim(),
    version: spec.slice(atIndex + 1).trim() || undefined,
  };
}
