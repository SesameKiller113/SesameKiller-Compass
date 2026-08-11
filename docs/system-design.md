# SesameKiller-Compass System Design

## Frontend Workflow

```mermaid
flowchart TD
  A["User opens React app"] --> B["Redux initializes chat state"]
  B --> C["User submits travel question"]
  C --> D["Frontend calls POST /api/chat"]
  D --> E["Show loading state"]
  E --> F["Render assistant answer"]
  F --> G["Render semantic, Cypher, and prompt trace"]
```

## Backend Q&A Orchestration

```mermaid
flowchart TD
  A["Express receives /api/chat"] --> B["Normalize message and session ID"]
  B --> C["Load recent MongoDB chat history"]
  C --> D["Call Flask RAG service"]
  D --> E["Semantic retrieval through LangChain embedding adapter"]
  D --> F["Cypher retrieval against Neo4j graph"]
  E --> G["Merge retrieved context"]
  F --> G
  G --> H["OpenAI answer generation"]
  H --> I["Save assistant message to MongoDB"]
  I --> J["Return response to React"]
```

## Database Workflow

```mermaid
flowchart TD
  A["Fake airport JSON seed"] --> B["Flask seed script"]
  B --> C["Neo4j Airport, Terminal, Restaurant, CreditCard, Benefit nodes"]
  B --> D["KnowledgeChunk nodes with embeddings"]
  C --> E["Cypher exact relationship lookup"]
  D --> F["Semantic vector retrieval"]
  G["User and assistant messages"] --> H["MongoDB chatmessages collection"]
```

## Retrieval Strategy

The service uses two retrieval paths:

- Semantic retrieval: the user question is embedded by a LangChain-compatible embedding model. The vector is queried against `KnowledgeChunk` nodes in Neo4j.
- Structured retrieval: the service resolves airport codes or names from the question and runs a safe read-only Cypher template to fetch exact terminals, restaurants, and card benefits.

The two outputs are sent into the answer generator. `OPENAI_API_KEY` is required for final answer generation. Without a key, retrieval still runs, but the service returns an explicit error instead of generating any local answer.
