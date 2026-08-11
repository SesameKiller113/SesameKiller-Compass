import { Route, Routes } from "react-router-dom";
import styled from "styled-components";

import { TopNav } from "./components/TopNav";
import { ArchitecturePage } from "./pages/ArchitecturePage";
import { ChatPage } from "./pages/ChatPage";

const AppShell = styled.div`
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(245, 247, 250, 0.94), rgba(238, 241, 244, 0.98)),
    #f5f7fa;
  color: #172026;
`;

export default function App() {
  return (
    <AppShell>
      <TopNav />
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/architecture" element={<ArchitecturePage />} />
      </Routes>
    </AppShell>
  );
}

