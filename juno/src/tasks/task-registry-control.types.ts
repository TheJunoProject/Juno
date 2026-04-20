import type { JunoConfig } from "../config/types.juno.js";

export type CancelAcpSessionAdmin = (params: {
  cfg: JunoConfig;
  sessionKey: string;
  reason: string;
}) => Promise<void>;

export type KillSubagentRunAdminResult = {
  found: boolean;
  killed: boolean;
  runId?: string;
  sessionKey?: string;
  cascadeKilled?: number;
  cascadeLabels?: string[];
};

export type KillSubagentRunAdmin = (params: {
  cfg: JunoConfig;
  sessionKey: string;
}) => Promise<KillSubagentRunAdminResult>;

export type TaskRegistryControlRuntime = {
  getAcpSessionManager: () => {
    cancelSession: CancelAcpSessionAdmin;
  };
  killSubagentRunAdmin: KillSubagentRunAdmin;
};
