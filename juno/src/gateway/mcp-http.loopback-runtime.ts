export type McpLoopbackRuntime = {
  port: number;
  token: string;
};

let activeRuntime: McpLoopbackRuntime | undefined;

export function getActiveMcpLoopbackRuntime(): McpLoopbackRuntime | undefined {
  return activeRuntime ? { ...activeRuntime } : undefined;
}

export function setActiveMcpLoopbackRuntime(runtime: McpLoopbackRuntime): void {
  activeRuntime = { ...runtime };
}

export function clearActiveMcpLoopbackRuntime(token: string): void {
  if (activeRuntime?.token === token) {
    activeRuntime = undefined;
  }
}

export function createMcpLoopbackServerConfig(port: number) {
  return {
    mcpServers: {
      juno: {
        type: "http",
        url: `http://127.0.0.1:${port}/mcp`,
        headers: {
          Authorization: "Bearer ${JUNO_MCP_TOKEN}",
          "x-session-key": "${JUNO_MCP_SESSION_KEY}",
          "x-juno-agent-id": "${JUNO_MCP_AGENT_ID}",
          "x-juno-account-id": "${JUNO_MCP_ACCOUNT_ID}",
          "x-juno-message-channel": "${JUNO_MCP_MESSAGE_CHANNEL}",
          "x-juno-sender-is-owner": "${JUNO_MCP_SENDER_IS_OWNER}",
        },
      },
    },
  };
}
