import type { JunoConfig } from "../config/types.juno.js";
import {
  resolvePluginCapabilityProvider,
  resolvePluginCapabilityProviders,
} from "./capability-provider-runtime.js";
import {
  getRegisteredMemoryEmbeddingProvider,
  listRegisteredMemoryEmbeddingProviders,
  type MemoryEmbeddingProviderAdapter,
} from "./memory-embedding-providers.js";

export { listRegisteredMemoryEmbeddingProviders };

export function listRegisteredMemoryEmbeddingProviderAdapters(): MemoryEmbeddingProviderAdapter[] {
  return listRegisteredMemoryEmbeddingProviders().map((entry) => entry.adapter);
}
export function listMemoryEmbeddingProviders(
  cfg?: JunoConfig,
): MemoryEmbeddingProviderAdapter[] {
  const registered = listRegisteredMemoryEmbeddingProviderAdapters();
  const merged = new Map(registered.map((adapter) => [adapter.id, adapter]));
  for (const adapter of resolvePluginCapabilityProviders({
    key: "memoryEmbeddingProviders",
    cfg,
  })) {
    if (!merged.has(adapter.id)) {
      merged.set(adapter.id, adapter);
    }
  }
  return [...merged.values()];
}

export function getMemoryEmbeddingProvider(
  id: string,
  cfg?: JunoConfig,
): MemoryEmbeddingProviderAdapter | undefined {
  const registered = getRegisteredMemoryEmbeddingProvider(id);
  if (registered) {
    return registered.adapter;
  }
  return resolvePluginCapabilityProvider({
    key: "memoryEmbeddingProviders",
    providerId: id,
    cfg,
  });
}
