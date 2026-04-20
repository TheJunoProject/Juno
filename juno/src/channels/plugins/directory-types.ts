import type { JunoConfig } from "../../config/types.js";

export type DirectoryConfigParams = {
  cfg: JunoConfig;
  accountId?: string | null;
  query?: string | null;
  limit?: number | null;
};
