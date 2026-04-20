export const JUNO_OWNER_ONLY_CORE_TOOL_NAMES = ["cron", "gateway", "nodes"] as const;

const JUNO_OWNER_ONLY_CORE_TOOL_NAME_SET: ReadonlySet<string> = new Set(
  JUNO_OWNER_ONLY_CORE_TOOL_NAMES,
);

export function isJunoOwnerOnlyCoreToolName(toolName: string): boolean {
  return JUNO_OWNER_ONLY_CORE_TOOL_NAME_SET.has(toolName);
}
