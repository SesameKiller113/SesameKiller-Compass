import { describe, expect, it } from "vitest";

import { normalizeUserMessage, resolveSessionId } from "../src/services/session.js";

describe("session utilities", () => {
  it("keeps a valid client session id", () => {
    expect(resolveSessionId("demo_session-123")).toBe("demo_session-123");
  });

  it("creates a new id when the client value is unsafe", () => {
    expect(resolveSessionId("../bad")).not.toBe("../bad");
  });

  it("normalizes user whitespace", () => {
    expect(normalizeUserMessage("  What   benefits   at RWI? ")).toBe("What benefits at RWI?");
  });
});

