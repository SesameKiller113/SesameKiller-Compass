CREATE CONSTRAINT airport_code IF NOT EXISTS
FOR (a:Airport) REQUIRE a.code IS UNIQUE;

CREATE CONSTRAINT terminal_id IF NOT EXISTS
FOR (t:Terminal) REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT restaurant_id IF NOT EXISTS
FOR (r:Restaurant) REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT benefit_id IF NOT EXISTS
FOR (b:Benefit) REQUIRE b.id IS UNIQUE;

CREATE CONSTRAINT card_name IF NOT EXISTS
FOR (c:CreditCard) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT chunk_id IF NOT EXISTS
FOR (k:KnowledgeChunk) REQUIRE k.id IS UNIQUE;

CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS
FOR (k:KnowledgeChunk) ON (k.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: 64,
  `vector.similarity_function`: 'cosine'
}};

