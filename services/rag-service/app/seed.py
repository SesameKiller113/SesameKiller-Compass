from .config import get_settings
from .embeddings import create_embedding_model
from .neo4j_client import GraphRepository


def main() -> None:
    settings = get_settings()
    embeddings = create_embedding_model(settings.embedding_provider, settings.openai_api_key)
    graph = GraphRepository(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password, embeddings)
    graph.wait_until_ready()
    graph.ensure_schema()
    count = graph.seed_dataset(settings.seed_path, reset=True)
    print(f"Seeded {count} airports into Neo4j")
    graph.close()


if __name__ == "__main__":
    main()

