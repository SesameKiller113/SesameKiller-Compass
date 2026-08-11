import { randomUUID } from "node:crypto";

const SESSION_ID_RE = /^[a-zA-Z0-9_-]{6,80}$/;

export function resolveSessionId(candidate: unknown): string {
  if (typeof candidate === "string" && SESSION_ID_RE.test(candidate)) {
    return candidate;
  }
  return randomUUID();
}

export function normalizeUserMessage(message: unknown): string {
  if (typeof message !== "string") {
    return "";
  }
  return message.trim().replace(/\s+/g, " ");
}
