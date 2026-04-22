import { describe, expect, it } from "vitest";
import { shortenText } from "./text-format.js";

describe("shortenText", () => {
  it("returns original text when it fits", () => {
    expect(shortenText("juno", 16)).toBe("juno");
  });

  it("truncates and appends ellipsis when over limit", () => {
    expect(shortenText("juno-status-output", 10)).toBe("juno-stat…");
  });

  it("counts multi-byte characters correctly", () => {
    expect(shortenText("hello🙂world", 7)).toBe("hello🙂…");
  });
});
