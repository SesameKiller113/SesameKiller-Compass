import { Database, GitBranch, MessageSquareText } from "lucide-react";
import { NavLink } from "react-router-dom";

export function TopNav() {
  return (
    <header className="top-nav">
      <div className="brand">
        <Database size={22} />
        <div>
          <strong>SesameKiller-Compass</strong>
          <span>airport-benefit GraphRAG</span>
        </div>
      </div>
      <nav>
        <NavLink to="/">
          <MessageSquareText size={16} />
          Chat
        </NavLink>
        <NavLink to="/architecture">
          <GitBranch size={16} />
          Workflow
        </NavLink>
      </nav>
    </header>
  );
}
