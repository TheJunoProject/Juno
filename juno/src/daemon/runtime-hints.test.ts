import { describe, expect, it } from "vitest";
import { buildPlatformRuntimeLogHints, buildPlatformServiceStartHints } from "./runtime-hints.js";

describe("buildPlatformRuntimeLogHints", () => {
  it("renders launchd log hints on darwin", () => {
    expect(
      buildPlatformRuntimeLogHints({
        platform: "darwin",
        env: {
          JUNO_STATE_DIR: "/tmp/juno-state",
          JUNO_LOG_PREFIX: "gateway",
        },
        systemdServiceName: "juno-gateway",
        windowsTaskName: "Juno Gateway",
      }),
    ).toEqual([
      "Launchd stdout (if installed): /tmp/juno-state/logs/gateway.log",
      "Launchd stderr (if installed): /tmp/juno-state/logs/gateway.err.log",
      "Restart attempts: /tmp/juno-state/logs/gateway-restart.log",
    ]);
  });

  it("renders systemd and windows hints by platform", () => {
    expect(
      buildPlatformRuntimeLogHints({
        platform: "linux",
        env: {
          JUNO_STATE_DIR: "/tmp/juno-state",
        },
        systemdServiceName: "juno-gateway",
        windowsTaskName: "Juno Gateway",
      }),
    ).toEqual([
      "Logs: journalctl --user -u juno-gateway.service -n 200 --no-pager",
      "Restart attempts: /tmp/juno-state/logs/gateway-restart.log",
    ]);
    expect(
      buildPlatformRuntimeLogHints({
        platform: "win32",
        env: {
          JUNO_STATE_DIR: "/tmp/juno-state",
        },
        systemdServiceName: "juno-gateway",
        windowsTaskName: "Juno Gateway",
      }),
    ).toEqual([
      'Logs: schtasks /Query /TN "Juno Gateway" /V /FO LIST',
      "Restart attempts: /tmp/juno-state/logs/gateway-restart.log",
    ]);
  });
});

describe("buildPlatformServiceStartHints", () => {
  it("builds platform-specific service start hints", () => {
    expect(
      buildPlatformServiceStartHints({
        platform: "darwin",
        installCommand: "juno gateway install",
        startCommand: "juno gateway",
        launchAgentPlistPath: "~/Library/LaunchAgents/com.juno.gateway.plist",
        systemdServiceName: "juno-gateway",
        windowsTaskName: "Juno Gateway",
      }),
    ).toEqual([
      "juno gateway install",
      "juno gateway",
      "launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.juno.gateway.plist",
    ]);
    expect(
      buildPlatformServiceStartHints({
        platform: "linux",
        installCommand: "juno gateway install",
        startCommand: "juno gateway",
        launchAgentPlistPath: "~/Library/LaunchAgents/com.juno.gateway.plist",
        systemdServiceName: "juno-gateway",
        windowsTaskName: "Juno Gateway",
      }),
    ).toEqual([
      "juno gateway install",
      "juno gateway",
      "systemctl --user start juno-gateway.service",
    ]);
  });
});
