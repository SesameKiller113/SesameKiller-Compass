from flask import Flask, jsonify, request
from flask_cors import CORS

from .config import get_settings
from .embeddings import create_embedding_model
from .llm import AnswerGenerator, MissingOpenAIKeyError, build_grounded_prompt
from .neo4j_client import GraphRepository


def create_app() -> Flask:
    settings = get_settings()
    embeddings = create_embedding_model(settings.embedding_provider, settings.openai_api_key)
    graph = GraphRepository(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password, embeddings)
    answer_generator = AnswerGenerator(settings.openai_api_key, settings.openai_model)

    graph.wait_until_ready()
    graph.ensure_schema()
    if settings.auto_seed:
        graph.seed_if_empty(settings.seed_path)

    app = Flask(__name__)
    CORS(app)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "rag-service"})

    @app.get("/catalog")
    def catalog():
        return jsonify({"airports": graph.catalog()})

    @app.post("/query")
    def query():
        payload = request.get_json(force=True) or {}
        question = (payload.get("question") or "").strip()
        chat_history = payload.get("chatHistory") or []
        if not question:
            return jsonify({"error": "question is required"}), 400

        semantic_results = graph.semantic_search(question, top_k=int(payload.get("topK", 5)))
        graph_results = graph.structured_search(question)
        try:
            generated = answer_generator.generate(question, semantic_results, graph_results, chat_history)
        except MissingOpenAIKeyError as error:
            return (
                jsonify(
                    {
                        "error": str(error),
                        "mode": "missing-openai-key",
                        "retrieval": {
                            "semantic": semantic_results,
                            "graph": graph_results,
                            "promptPreview": build_grounded_prompt(
                                question, semantic_results, graph_results, chat_history[-6:]
                            )[:1200],
                        },
                    }
                ),
                503,
            )
        except Exception as error:
            return (
                jsonify(
                    {
                        "error": f"LLM answer generation failed: {error}",
                        "mode": "llm-error",
                        "retrieval": {
                            "semantic": semantic_results,
                            "graph": graph_results,
                            "promptPreview": build_grounded_prompt(
                                question, semantic_results, graph_results, chat_history[-6:]
                            )[:1200],
                        },
                    }
                ),
                502,
            )

        return jsonify(
            {
                "answer": generated["answer"],
                "mode": generated["mode"],
                "retrieval": {
                    "semantic": semantic_results,
                    "graph": graph_results,
                    "promptPreview": generated["promptPreview"],
                },
            }
        )

    @app.teardown_appcontext
    def close_driver(_exception=None):
        pass

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=get_settings().port)
