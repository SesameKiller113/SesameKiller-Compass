import { useDispatch, useSelector } from "react-redux";

import { AirportCatalog } from "../components/AirportCatalog";
import { ChatPanel } from "../components/ChatPanel";
import { RetrievalTrace } from "../components/RetrievalTrace";
import type { AppDispatch, RootState } from "../store";

export function ChatPage() {
  const chat = useSelector((state: RootState) => state.chat);
  const dispatch = useDispatch<AppDispatch>();

  return (
    <main className="page-grid">
      <ChatPanel chat={chat} dispatch={dispatch} />
      <div className="side-stack">
        <RetrievalTrace retrieval={chat.retrieval} mode={chat.mode} />
        <AirportCatalog />
      </div>
    </main>
  );
}

