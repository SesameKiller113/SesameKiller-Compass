from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    port: int
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    openai_api_key: str
    openai_model: str
    embedding_provider: str
    auto_seed: bool
    seed_path: str


def get_settings() -> Settings:
    return Settings(
        port=int(os.getenv("PORT", "5001")),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "local-password"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "local").lower(),
        auto_seed=os.getenv("AUTO_SEED", "false").lower() == "true",
        seed_path=os.getenv("SEED_PATH", default_seed_path()),
    )


def default_seed_path() -> str:
    docker_path = Path("/app/database/seed/airports.json")
    if docker_path.exists():
        return str(docker_path)

    repo_path = Path(__file__).resolve().parents[3] / "database" / "seed" / "airports.json"
    return str(repo_path)
