from app.embeddings import LocalHashEmbeddings, cosine_similarity
from app.llm import build_grounded_prompt


def test_local_hash_embeddings_are_deterministic():
    model = LocalHashEmbeddings()
    left = model.embed_query("Atlas card lounge at Redwood airport")
    right = model.embed_query("Atlas card lounge at Redwood airport")
    assert left == right
    assert len(left) == 64


def test_related_queries_score_higher_than_empty_text():
    model = LocalHashEmbeddings()
    query = model.embed_query("airport lounge credit")
    related = model.embed_query("lounge access and travel credit at terminal")
    empty = [0.0] * 64
    assert cosine_similarity(query, related) > cosine_similarity(query, empty)


def test_prompt_contains_both_retrieval_sources():
    prompt = build_grounded_prompt(
        "Where can I eat at RWI?",
        [{"text": "semantic"}],
        {"records": [{"airport": {"code": "RWI"}}]},
        [],
    )
    assert "Semantic retrieval results" in prompt
    assert "Cypher graph retrieval results" in prompt

