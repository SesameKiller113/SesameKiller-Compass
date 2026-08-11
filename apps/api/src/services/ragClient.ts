import { env } from "../env.js";

export interface RagQueryInput {
  question: string;
  sessionId: string;
  chatHistory: Array<{ role: string; content: string }>;
}

export interface RagQueryResponse {
  answer: string;
  mode: "openai";
  retrieval: {
    semantic: unknown[];
    graph: unknown;
    promptPreview: string;
  };
}

export class RagServiceError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "RagServiceError";
    this.status = status;
  }
}

export interface AirportSummary {
  code: string;
  name: string;
  city: string;
  terminalCount: number;
}

export async function queryRagService(input: RagQueryInput): Promise<RagQueryResponse> {
  const response = await fetch(`${env.ragServiceUrl}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    signal: AbortSignal.timeout(20000)
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
    throw new RagServiceError(response.status, `RAG service failed: ${message}`);
  }

  return (await response.json()) as RagQueryResponse;
}

export async function getAirportCatalog(): Promise<AirportSummary[]> {
  const response = await fetch(`${env.ragServiceUrl}/catalog`, {
    signal: AbortSignal.timeout(10000)
  });

  if (!response.ok) {
    throw new Error(`Could not load airport catalog: ${response.status}`);
  }

  const payload = (await response.json()) as { airports: AirportSummary[] };
  return payload.airports;
}
