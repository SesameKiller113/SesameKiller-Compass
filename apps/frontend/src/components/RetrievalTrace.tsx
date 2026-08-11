import { Segmented, Tag } from "antd";
import { useState } from "react";

import { compactText } from "../lib/format";
import type { RootState } from "../store";

interface RetrievalTraceProps {
  retrieval?: RootState["chat"]["retrieval"];
  mode?: RootState["chat"]["mode"];
}

export function RetrievalTrace({ retrieval, mode }: RetrievalTraceProps) {
  const [tab, setTab] = useState<string>("Semantic");

  if (!retrieval) {
    return (
      <aside className="trace-panel">
        <h2>Retrieval Trace</h2>
        <p className="muted">Ask a question to see semantic chunks, Cypher output, and the prompt preview.</p>
      </aside>
    );
  }

  const semantic = retrieval.semantic ?? [];
  const graph = retrieval.graph as { strategy?: string; cypher?: string; records?: unknown[] };

  return (
    <aside className="trace-panel">
      <div className="trace-title">
        <h2>Retrieval Trace</h2>
        <Tag color={mode === "openai" ? "green" : "orange"}>{mode}</Tag>
      </div>
      <Segmented
        size="small"
        value={tab}
        options={["Semantic", "Cypher", "Prompt"]}
        onChange={(value) => setTab(String(value))}
      />

      {tab === "Semantic" && (
        <div className="trace-stack">
          {semantic.map((item, index) => (
            <div className="trace-item" key={index}>
              <strong>
                {String(item.sourceType ?? "Chunk")} {String(item.sourceId ?? "")}
              </strong>
              <span>score {Number(item.score ?? 0).toFixed(2)}</span>
              <p>{compactText(String(item.text ?? ""), 220)}</p>
            </div>
          ))}
        </div>
      )}

      {tab === "Cypher" && (
        <div className="trace-stack">
          <div className="trace-item">
            <strong>Strategy</strong>
            <span>{graph.strategy ?? "unknown"}</span>
          </div>
          <pre>{graph.cypher}</pre>
          <pre>{JSON.stringify(graph.records ?? [], null, 2)}</pre>
        </div>
      )}

      {tab === "Prompt" && <pre>{retrieval.promptPreview}</pre>}
    </aside>
  );
}

