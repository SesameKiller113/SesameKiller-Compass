export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  sessionId: string;
  answer: string;
  mode: "openai";
  retrieval: {
    semantic: Array<Record<string, unknown>>;
    graph: Record<string, unknown>;
    promptPreview: string;
  };
}

export interface AirportSummary {
  code: string;
  name: string;
  city: string;
  terminalCount: number;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function sendChatMessage(message: string, sessionId?: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, sessionId })
  });

  if (!response.ok) {
    const details = await response.text();
    let message = details;
    try {
      const parsed = JSON.parse(details) as { error?: string };
      message = parsed.error ?? details;
    } catch {
      message = details;
    }
    throw new Error(message);
  }

  return (await response.json()) as ChatResponse;
}

export async function loadAirports(): Promise<AirportSummary[]> {
  const response = await fetch(`${API_BASE}/airports`);
  if (!response.ok) {
    throw new Error("Could not load airport catalog");
  }
  const payload = (await response.json()) as { airports: AirportSummary[] };
  return payload.airports;
}
