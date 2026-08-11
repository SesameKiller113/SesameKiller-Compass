import { describe, expect, it } from "vitest";

import { compactText } from "./format";

describe("compactText", () => {
  it("keeps short strings unchanged", () => {
    expect(compactText("RWI")).toBe("RWI");
  });

  it("shortens long strings", () => {
    expect(compactText("a".repeat(20), 10)).toBe("aaaaaaa...");
  });
});

