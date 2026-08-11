from typing import Any, Dict, List


class MissingOpenAIKeyError(RuntimeError):
    pass


class AnswerGenerator:
    def __init__(self, openai_api_key: str, model_name: str):
        self.openai_api_key = openai_api_key
        self.model_name = model_name

    def generate(
        self,
        question: str,
        semantic_results: List[Dict[str, Any]],
        graph_results: Dict[str, Any],
        chat_history: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        if not self.openai_api_key:
            raise MissingOpenAIKeyError(
                "OPENAI_API_KEY is required for answer generation. Retrieval completed, but no LLM call was made."
            )

        return self._generate_with_openai(question, semantic_results, graph_results, chat_history)

    def _generate_with_openai(
        self,
        question: str,
        semantic_results: List[Dict[str, Any]],
        graph_results: Dict[str, Any],
        chat_history: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=self.model_name, api_key=self.openai_api_key, temperature=0.2)
        recent_history = chat_history[-6:]
        prompt = build_grounded_prompt(question, semantic_results, graph_results, recent_history)
        result = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a travel-domain Q&A assistant. Use only the provided graph and semantic "
                        "retrieval context. If the context is insufficient, say what is missing."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )
        return {
            "mode": "openai",
            "answer": result.content,
            "promptPreview": prompt[:1200],
        }


def build_grounded_prompt(
    question: str,
    semantic_results: List[Dict[str, Any]],
    graph_results: Dict[str, Any],
    chat_history: List[Dict[str, str]],
) -> str:
    return (
        "Conversation history:\n"
        f"{chat_history}\n\n"
        "User question:\n"
        f"{question}\n\n"
        "Semantic retrieval results:\n"
        f"{semantic_results}\n\n"
        "Cypher graph retrieval results:\n"
        f"{graph_results}\n\n"
        "Answer with a concise, structured response grounded in the retrieved context."
    )
