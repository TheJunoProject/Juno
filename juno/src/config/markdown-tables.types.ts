import type { MarkdownTableMode } from "./types.base.js";
import type { JunoConfig } from "./types.juno.js";

export type ResolveMarkdownTableModeParams = {
  cfg?: Partial<JunoConfig>;
  channel?: string | null;
  accountId?: string | null;
};

export type ResolveMarkdownTableMode = (
  params: ResolveMarkdownTableModeParams,
) => MarkdownTableMode;
