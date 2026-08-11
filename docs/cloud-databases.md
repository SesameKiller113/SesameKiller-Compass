# Cloud Database Setup

This project can run in two modes:

```text
Local demo:
docker-compose.yml starts MongoDB and Neo4j containers.

Cloud demo:
docker-compose.cloud.yml connects the app containers to MongoDB Atlas and Neo4j AuraDB.
```

Use the cloud mode when you want the demo to behave more like the future product without paying for self-hosted database servers.

## MongoDB Atlas Free

Official docs:

- [Deploy a Free Cluster](https://www.mongodb.com/docs/atlas/tutorial/deploy-free-tier-cluster/)
- [Atlas Free Cluster Limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/)

Create the Atlas database:

1. Go to MongoDB Atlas and create or open a project.
2. Build a database and choose the Free cluster option.
3. Pick a free-region provider/region close to your backend.
4. Create a database user such as `compass_app`.
5. Add your current IP address to the network access list.
6. Click Connect, choose Drivers, and copy the `mongodb+srv://...` connection string.
7. Replace the username, password, and database name in the string.

Use this format in `.env`:

```bash
MONGO_URI=mongodb+srv://compass_app:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/sesamekiller_compass?retryWrites=true&w=majority&appName=sesamekiller-compass
```

For a deployed backend, do not leave Atlas network access open to every IP. Use the backend server IP or private networking when you move beyond the demo.

## Neo4j AuraDB Free

Official docs:

- [Create an instance](https://neo4j.com/docs/aura/getting-started/create-instance/)
- [Neo4j Aura pricing](https://console.neo4j.io/pricing)

Create the AuraDB instance:

1. Go to the Neo4j Aura console.
2. Create an AuraDB instance and choose the Free tier.
3. Choose a cloud provider and region close to your backend.
4. Download or copy the generated password immediately.
5. Copy the connection URI from the instance details.

Use this format in `.env`:

```bash
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=YOUR_AURA_PASSWORD
```

The `neo4j+s://` scheme enables encrypted driver connections to AuraDB.

## Cloud Demo Run

After `.env` contains `OPENAI_API_KEY`, `MONGO_URI`, `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD`, run:

```bash
docker compose -f docker-compose.cloud.yml up --build
```

Open:

```text
http://localhost:8080
```

If your AuraDB instance is empty and you want to load the sample airport graph:

```bash
docker compose -f docker-compose.cloud.yml run --rm rag-service python -m app.seed
```

That command resets and reseeds the Neo4j graph with the sample demo data in `database/seed/airports.json`.

## Cost Notes

The intended MVP setup is:

```text
MongoDB Atlas Free for chat/session data
Neo4j AuraDB Free for the knowledge graph
OpenAI pay-per-use for final answer generation
Docker Compose for the local app demo
```

Free tiers are enough for a small demo and early proof of concept. They are not a production SLA, backup, or high-traffic setup.
