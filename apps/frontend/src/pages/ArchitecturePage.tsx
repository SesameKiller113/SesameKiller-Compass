import { CheckCircle2, Database, GitBranch, ServerCog } from "lucide-react";

import { LatencyChart } from "../components/LatencyChart";

const STEPS = [
  {
    title: "Frontend",
    icon: CheckCircle2,
    items: ["React chat UI", "Redux session state", "REST call to Express", "Trace display for demo"]
  },
  {
    title: "Q&A Orchestration",
    icon: ServerCog,
    items: ["Load MongoDB history", "Run LangChain semantic retrieval", "Run Cypher graph retrieval", "Compose grounded answer"]
  },
  {
    title: "Database",
    icon: Database,
    items: ["Neo4j stores domain graph", "KnowledgeChunk nodes hold embeddings", "MongoDB stores messages", "Seed script creates sample travel data"]
  },
  {
    title: "Delivery",
    icon: GitBranch,
    items: ["Docker Compose for local demo", "Nginx reverse proxy", "GitHub Actions CI", "AWS/Cloudflare documented as future deploy"]
  }
];

export function ArchitecturePage() {
  return (
    <main className="architecture-page">
      <section className="workflow-strip">
        {STEPS.map((step, index) => {
          const Icon = step.icon;
          return (
            <article className="workflow-step" key={step.title}>
              <div className="step-index">{index + 1}</div>
              <Icon size={22} />
              <h2>{step.title}</h2>
              <ul>
                {step.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          );
        })}
      </section>
      <LatencyChart />
    </main>
  );
}
