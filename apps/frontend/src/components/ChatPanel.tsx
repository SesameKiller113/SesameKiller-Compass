import { FormEvent, useState } from "react";
import { Button, IconButton, Tooltip } from "@mui/material";
import { RefreshCw, Send } from "lucide-react";

import type { AppDispatch, RootState } from "../store";
import { addUserMessage, askQuestion, clearChat } from "../store/chatSlice";

interface ChatPanelProps {
  chat: RootState["chat"];
  dispatch: AppDispatch;
}

const EXAMPLES = [
  "What restaurants and Atlas Platinum benefits are available at RWI?",
  "Does Blue Harbor International have lounge access?",
  "Find dining credits at Desert Bloom Airport."
];

export function ChatPanel({ chat, dispatch }: ChatPanelProps) {
  const [draft, setDraft] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || chat.status === "loading") {
      return;
    }
    dispatch(addUserMessage(message));
    dispatch(askQuestion(message));
    setDraft("");
  };

  return (
    <section className="chat-panel">
      <div className="panel-header">
        <div>
          <h1>Travel Q&A</h1>
          <p>Hybrid semantic retrieval, Cypher graph lookup, and grounded answer generation.</p>
        </div>
        <Tooltip title="Reset conversation">
          <IconButton aria-label="Reset conversation" onClick={() => dispatch(clearChat())}>
            <RefreshCw size={18} />
          </IconButton>
        </Tooltip>
      </div>

      <div className="message-list" aria-live="polite">
        {chat.messages.map((message) => (
          <article className={`message ${message.role}`} key={message.id}>
            <span>{message.role}</span>
            <p>{message.content}</p>
          </article>
        ))}
        {chat.status === "loading" && (
          <article className="message assistant loading">
            <span>assistant</span>
            <p>Retrieving graph context...</p>
          </article>
        )}
      </div>

      <div className="example-row">
        {EXAMPLES.map((example) => (
          <button type="button" key={example} onClick={() => setDraft(example)}>
            {example}
          </button>
        ))}
      </div>

      <form className="composer" onSubmit={submit}>
        <input
          aria-label="Ask a travel question"
          placeholder="Ask about terminals, restaurants, lounges, or credit-card benefits..."
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button
          type="submit"
          variant="contained"
          endIcon={<Send size={16} />}
          disabled={!draft.trim() || chat.status === "loading"}
        >
          Ask
        </Button>
      </form>
    </section>
  );
}

