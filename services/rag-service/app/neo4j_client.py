import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from .embeddings import cosine_similarity, embedding_dimensions

TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


CONSTRAINTS = [
    "CREATE CONSTRAINT airport_code IF NOT EXISTS FOR (a:Airport) REQUIRE a.code IS UNIQUE",
    "CREATE CONSTRAINT terminal_id IF NOT EXISTS FOR (t:Terminal) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT restaurant_id IF NOT EXISTS FOR (r:Restaurant) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT benefit_id IF NOT EXISTS FOR (b:Benefit) REQUIRE b.id IS UNIQUE",
    "CREATE CONSTRAINT card_name IF NOT EXISTS FOR (c:CreditCard) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (k:KnowledgeChunk) REQUIRE k.id IS UNIQUE",
]


class GraphRepository:
    def __init__(self, uri: str, user: str, password: str, embeddings):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.embeddings = embeddings
        self.vector_index_name = "chunk_embedding_index"

    def close(self) -> None:
        self.driver.close()

    def wait_until_ready(self, attempts: int = 30, delay_seconds: float = 2.0) -> None:
        last_error: Optional[Exception] = None
        for _ in range(attempts):
            try:
                with self.driver.session() as session:
                    session.run("RETURN 1").consume()
                return
            except ServiceUnavailable as exc:
                last_error = exc
                time.sleep(delay_seconds)
        raise RuntimeError(f"Neo4j was not ready after {attempts} attempts: {last_error}")

    def ensure_schema(self) -> None:
        vector_dimensions = embedding_dimensions(self.embeddings)
        vector_index = f"""
        CREATE VECTOR INDEX {self.vector_index_name} IF NOT EXISTS
        FOR (k:KnowledgeChunk) ON (k.embedding)
        OPTIONS {{ indexConfig: {{
          `vector.dimensions`: {vector_dimensions},
          `vector.similarity_function`: 'cosine'
        }}}}
        """

        with self.driver.session() as session:
            for statement in CONSTRAINTS:
                session.run(statement).consume()
            session.run(vector_index).consume()

    def seed_if_empty(self, seed_path: str) -> int:
        with self.driver.session() as session:
            count = session.run("MATCH (a:Airport) RETURN count(a) AS count").single()["count"]
        if count:
            return int(count)
        return self.seed_dataset(seed_path, reset=False)

    def seed_dataset(self, seed_path: str, reset: bool = False) -> int:
        data = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        with self.driver.session() as session:
            if reset:
                session.run("MATCH (n) DETACH DELETE n").consume()
            for airport in data:
                session.execute_write(self._upsert_airport, airport)
                chunks = self._chunks_for_airport(airport)
                for chunk in chunks:
                    embedding = self.embeddings.embed_query(chunk["text"])
                    session.execute_write(self._upsert_chunk, chunk, embedding)
        return len(data)

    @staticmethod
    def _upsert_airport(tx, airport: Dict[str, Any]) -> None:
        tx.run(
            """
            MERGE (a:Airport {code: $code})
            SET a.name = $name, a.city = $city, a.country = $country
            """,
            code=airport["code"],
            name=airport["name"],
            city=airport["city"],
            country=airport["country"],
        )

        for terminal in airport["terminals"]:
            tx.run(
                """
                MATCH (a:Airport {code: $airportCode})
                MERGE (t:Terminal {id: $id})
                SET t.name = $name, t.gateRange = $gateRange
                MERGE (a)-[:HAS_TERMINAL]->(t)
                """,
                airportCode=airport["code"],
                id=terminal["id"],
                name=terminal["name"],
                gateRange=terminal["gateRange"],
            )
            for restaurant in terminal["restaurants"]:
                tx.run(
                    """
                    MATCH (t:Terminal {id: $terminalId})
                    MERGE (r:Restaurant {id: $id})
                    SET r.name = $name,
                        r.cuisine = $cuisine,
                        r.priceLevel = $priceLevel,
                        r.hours = $hours
                    MERGE (t)-[:HAS_RESTAURANT]->(r)
                    """,
                    terminalId=terminal["id"],
                    **restaurant,
                )

        for benefit in airport["benefits"]:
            tx.run(
                """
                MERGE (card:CreditCard {name: $card})
                SET card.issuer = $issuer, card.tier = $tier
                MERGE (b:Benefit {id: $id})
                SET b.type = $type,
                    b.description = $description,
                    b.eligibility = $eligibility
                MERGE (card)-[:OFFERS]->(b)
                """,
                **benefit,
            )
            for terminal_id in benefit["terminalIds"]:
                tx.run(
                    """
                    MATCH (b:Benefit {id: $benefitId})
                    MATCH (t:Terminal {id: $terminalId})
                    MERGE (b)-[:VALID_IN]->(t)
                    """,
                    benefitId=benefit["id"],
                    terminalId=terminal_id,
                )
            for restaurant_id in benefit["restaurantIds"]:
                tx.run(
                    """
                    MATCH (b:Benefit {id: $benefitId})
                    MATCH (r:Restaurant {id: $restaurantId})
                    MERGE (b)-[:VALID_AT]->(r)
                    """,
                    benefitId=benefit["id"],
                    restaurantId=restaurant_id,
                )

    @staticmethod
    def _upsert_chunk(tx, chunk: Dict[str, Any], embedding: List[float]) -> None:
        tx.run(
            """
            MERGE (k:KnowledgeChunk {id: $id})
            SET k.text = $text,
                k.sourceType = $sourceType,
                k.sourceId = $sourceId,
                k.embedding = $embedding
            """,
            **chunk,
            embedding=embedding,
        )

    def _chunks_for_airport(self, airport: Dict[str, Any]) -> List[Dict[str, str]]:
        chunks: List[Dict[str, str]] = []
        terminal_names = ", ".join(t["name"] for t in airport["terminals"])
        benefit_text = "; ".join(
            f"{b['card']} offers {b['type']}: {b['description']} ({b['eligibility']})"
            for b in airport["benefits"]
        )
        chunks.append(
            {
                "id": f"airport-{airport['code']}",
                "sourceType": "Airport",
                "sourceId": airport["code"],
                "text": f"{airport['name']} ({airport['code']}) in {airport['city']} has terminals {terminal_names}. Benefits: {benefit_text}.",
            }
        )

        for terminal in airport["terminals"]:
            restaurants = ", ".join(
                f"{r['name']} serving {r['cuisine']} from {r['hours']}" for r in terminal["restaurants"]
            )
            chunks.append(
                {
                    "id": f"terminal-{terminal['id']}",
                    "sourceType": "Terminal",
                    "sourceId": terminal["id"],
                    "text": f"{terminal['name']} at {airport['code']} covers gates {terminal['gateRange']} and includes restaurants: {restaurants}.",
                }
            )
            for restaurant in terminal["restaurants"]:
                chunks.append(
                    {
                        "id": f"restaurant-{restaurant['id']}",
                        "sourceType": "Restaurant",
                        "sourceId": restaurant["id"],
                        "text": f"{restaurant['name']} is a {restaurant['priceLevel']} {restaurant['cuisine']} restaurant in {terminal['name']} at {airport['code']}, open {restaurant['hours']}.",
                    }
                )

        for benefit in airport["benefits"]:
            chunks.append(
                {
                    "id": f"benefit-{benefit['id']}",
                    "sourceType": "Benefit",
                    "sourceId": benefit["id"],
                    "text": f"{benefit['card']} from {benefit['issuer']} provides {benefit['type']} at {airport['code']}: {benefit['description']}. Eligibility: {benefit['eligibility']}.",
                }
            )
        return chunks

    def semantic_search(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        embedding = self.embeddings.embed_query(question)
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    CALL db.index.vector.queryNodes($indexName, $topK, $embedding)
                    YIELD node, score
                    RETURN node.id AS id,
                           node.text AS text,
                           node.sourceType AS sourceType,
                           node.sourceId AS sourceId,
                           score
                    ORDER BY score DESC
                    """,
                    indexName=self.vector_index_name,
                    topK=top_k,
                    embedding=embedding,
                )
                return self._rerank_semantic(question, [dict(record) for record in result], top_k)
        except Neo4jError:
            return self._semantic_search_brute_force(question, embedding, top_k)

    def _semantic_search_brute_force(
        self, question: str, query_embedding: List[float], top_k: int
    ) -> List[Dict[str, Any]]:
        with self.driver.session() as session:
            records = session.run(
                """
                MATCH (k:KnowledgeChunk)
                RETURN k.id AS id,
                       k.text AS text,
                       k.sourceType AS sourceType,
                       k.sourceId AS sourceId,
                       k.embedding AS embedding
                """
            )
            scored = []
            for record in records:
                item = dict(record)
                item["score"] = cosine_similarity(query_embedding, item.pop("embedding"))
                scored.append(item)
            return self._rerank_semantic(question, scored, top_k)

    def _rerank_semantic(
        self, question: str, results: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        question_tokens = {
            token for token in TOKEN_RE.findall(question.lower()) if len(token) > 2
        }
        for item in results:
            vector_score = float(item.get("score") or 0.0)
            text_tokens = {
                token for token in TOKEN_RE.findall(str(item.get("text", "")).lower()) if len(token) > 2
            }
            overlap = len(question_tokens.intersection(text_tokens))
            lexical_boost = min(0.25, overlap * 0.05)
            item["vectorScore"] = vector_score
            item["score"] = min(1.0, vector_score + lexical_boost)
        results.sort(key=lambda row: row["score"], reverse=True)
        return results[:top_k]

    def structured_search(self, question: str) -> Dict[str, Any]:
        codes = self._resolve_airport_codes(question)
        terminal_ids = self._resolve_terminal_ids(question)
        card_names = self._resolve_card_names(question)
        if codes:
            cypher = AIRPORT_DETAIL_QUERY
            params = {"codes": codes}
            strategy = "airport-detail"
        elif terminal_ids:
            cypher = TERMINAL_DETAIL_QUERY
            params = {"terminalIds": terminal_ids}
            strategy = "terminal-detail"
        elif card_names:
            cypher = CARD_BENEFIT_QUERY
            params = {"cards": card_names}
            strategy = "card-benefit"
        else:
            cypher = AIRPORT_OVERVIEW_QUERY
            params = {"limit": 6}
            strategy = "airport-overview"

        with self.driver.session() as session:
            records = [dict(record) for record in session.run(cypher, **params)]

        return {
            "strategy": strategy,
            "codes": codes,
            "terminalIds": terminal_ids,
            "cardNames": card_names,
            "cypher": cypher.strip(),
            "records": [self._clean_record(record) for record in records],
        }

    def _resolve_airport_codes(self, question: str) -> List[str]:
        normalized = question.lower()
        with self.driver.session() as session:
            records = session.run("MATCH (a:Airport) RETURN a.code AS code, a.name AS name, a.city AS city")
            matches = []
            for record in records:
                code = record["code"]
                name = record["name"].lower()
                city = record["city"].lower()
                if code.lower() in normalized or name in normalized or city in normalized:
                    matches.append(code)
            return matches

    def _resolve_terminal_ids(self, question: str) -> List[str]:
        normalized = question.lower()
        with self.driver.session() as session:
            records = session.run("MATCH (t:Terminal) RETURN t.id AS id, t.name AS name")
            matches = []
            for record in records:
                terminal_id = record["id"]
                name = record["name"].lower()
                if terminal_id.lower() in normalized or name in normalized:
                    matches.append(terminal_id)
            return matches

    def _resolve_card_names(self, question: str) -> List[str]:
        normalized = question.lower()
        with self.driver.session() as session:
            records = session.run("MATCH (c:CreditCard) RETURN c.name AS name")
            matches = []
            for record in records:
                name = record["name"]
                if name.lower() in normalized:
                    matches.append(name)
            return matches

    @staticmethod
    def _clean_record(record: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(record)
        for key, value in cleaned.items():
            if isinstance(value, list):
                cleaned[key] = [item for item in value if item and not _all_values_null(item)]
        return cleaned

    def catalog(self) -> List[Dict[str, Any]]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a:Airport)
                OPTIONAL MATCH (a)-[:HAS_TERMINAL]->(t)
                RETURN a.code AS code,
                       a.name AS name,
                       a.city AS city,
                       count(t) AS terminalCount
                ORDER BY a.code
                """
            )
            return [dict(record) for record in result]


def _all_values_null(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return all(item is None for item in value.values())


AIRPORT_DETAIL_QUERY = """
MATCH (a:Airport)
WHERE a.code IN $codes
OPTIONAL MATCH (a)-[:HAS_TERMINAL]->(t)
OPTIONAL MATCH (t)-[:HAS_RESTAURANT]->(r)
OPTIONAL MATCH (card:CreditCard)-[:OFFERS]->(b)-[:VALID_IN]->(t)
OPTIONAL MATCH (b)-[:VALID_AT]->(benefitRestaurant)
RETURN a { .code, .name, .city, .country } AS airport,
       collect(DISTINCT t { .id, .name, .gateRange }) AS terminals,
       collect(DISTINCT r { .id, .name, .cuisine, .priceLevel, .hours }) AS restaurants,
       collect(DISTINCT {
         card: card.name,
         issuer: card.issuer,
         tier: card.tier,
         type: b.type,
         description: b.description,
         eligibility: b.eligibility,
         terminalId: t.id,
         restaurant: benefitRestaurant.name
       }) AS benefits
ORDER BY airport.code
"""


TERMINAL_DETAIL_QUERY = """
MATCH (a:Airport)-[:HAS_TERMINAL]->(t:Terminal)
WHERE t.id IN $terminalIds
OPTIONAL MATCH (t)-[:HAS_RESTAURANT]->(r)
OPTIONAL MATCH (card:CreditCard)-[:OFFERS]->(b)-[:VALID_IN]->(t)
OPTIONAL MATCH (b)-[:VALID_AT]->(benefitRestaurant)
RETURN a { .code, .name, .city, .country } AS airport,
       collect(DISTINCT t { .id, .name, .gateRange }) AS terminals,
       collect(DISTINCT r { .id, .name, .cuisine, .priceLevel, .hours }) AS restaurants,
       collect(DISTINCT {
         card: card.name,
         issuer: card.issuer,
         tier: card.tier,
         type: b.type,
         description: b.description,
         eligibility: b.eligibility,
         terminalId: t.id,
         restaurant: benefitRestaurant.name
       }) AS benefits
ORDER BY airport.code
"""


CARD_BENEFIT_QUERY = """
MATCH (card:CreditCard)
WHERE card.name IN $cards
MATCH (card)-[:OFFERS]->(b)
OPTIONAL MATCH (b)-[:VALID_IN]->(t)<-[:HAS_TERMINAL]-(a)
OPTIONAL MATCH (b)-[:VALID_AT]->(benefitRestaurant)
RETURN a { .code, .name, .city, .country } AS airport,
       collect(DISTINCT t { .id, .name, .gateRange }) AS terminals,
       collect(DISTINCT benefitRestaurant { .id, .name, .cuisine, .priceLevel, .hours }) AS restaurants,
       collect(DISTINCT {
         card: card.name,
         issuer: card.issuer,
         tier: card.tier,
         type: b.type,
         description: b.description,
         eligibility: b.eligibility,
         terminalId: t.id,
         restaurant: benefitRestaurant.name
       }) AS benefits
ORDER BY airport.code
"""


AIRPORT_OVERVIEW_QUERY = """
MATCH (a:Airport)-[:HAS_TERMINAL]->(t)
OPTIONAL MATCH (t)-[:HAS_RESTAURANT]->(r)
RETURN a { .code, .name, .city, .country } AS airport,
       collect(DISTINCT t { .id, .name, .gateRange }) AS terminals,
       collect(DISTINCT r { .id, .name, .cuisine, .priceLevel, .hours }) AS restaurants,
       [] AS benefits
ORDER BY airport.code
LIMIT $limit
"""
