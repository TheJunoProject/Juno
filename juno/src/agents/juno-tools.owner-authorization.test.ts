import { describe, expect, it } from "vitest";
import {
  isJunoOwnerOnlyCoreToolName,
  JUNO_OWNER_ONLY_CORE_TOOL_NAMES,
} from "./tools/owner-only-tools.js";

describe("createJunoTools owner authorization", () => {
  it("marks owner-only core tool names", () => {
    expect(JUNO_OWNER_ONLY_CORE_TOOL_NAMES).toEqual(["cron", "gateway", "nodes"]);
    expect(isJunoOwnerOnlyCoreToolName("cron")).toBe(true);
    expect(isJunoOwnerOnlyCoreToolName("gateway")).toBe(true);
    expect(isJunoOwnerOnlyCoreToolName("nodes")).toBe(true);
  });

  it("keeps canvas non-owner-only", () => {
    expect(isJunoOwnerOnlyCoreToolName("canvas")).toBe(false);
  });
});
