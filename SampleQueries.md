# Spanner Graph & Search Sample Queries for OKF Knowledge Graph

This document provides sample **Spanner Graph (GQL)**, **Full Text Search (FTS)**, and **ScaNN Vector Search** queries to inspect, search, and traverse the OKF Knowledge Graph (`OKFGraph`) created in Google Cloud Spanner.

> **Note on Graph Schema & Relationships**:
> - Node Primary Keys: **UUIDv4 (`STRING(36)`)**.
> - Concept Nodes (`Methodology`, `Architecture`, `Specification`, etc.) link to:
>   - **`Tag`** nodes via **`HAS_TAGS`** edges.
>   - **`Source`** nodes via **`HAS_REFERENCE`** edges.
>   - Other **Concept** nodes via **`HAS_LINKS`** edges (from Markdown links & Wikilinks).
> - Full Text Search index: `GraphNodeSearchIndex` on `body_tokens`.
> - Vector Search index: `GraphNodeVectorIndex` (ScaNN index with `COSINE` distance) vectorizing `title` + `description` + `body`.

---

## 1. Query Concept Links (`HAS_LINKS`)

Query all directed links between concept nodes.

```sql
GRAPH OKFGraph
MATCH (source)-[e:HAS_LINKS]->(target)
RETURN 
  JSON_VALUE(source.properties, '$.id') AS source_concept,
  e.label AS relationship,
  JSON_VALUE(target.properties, '$.id') AS target_concept
ORDER BY source_concept;
```

---

## 2. Query Tags Connected to Concepts (`HAS_TAGS`)

Find all `Tag` nodes linked to a specific concept.

```sql
GRAPH OKFGraph
MATCH (c)-[e:HAS_TAGS]->(t:Tag)
WHERE JSON_VALUE(c.properties, '$.id') = 'methodologies/how_to_use_memorystore'
RETURN 
  JSON_VALUE(c.properties, '$.name') AS concept_name,
  e.label AS relationship,
  JSON_VALUE(t.properties, '$.tag') AS tag_name;
```

---

## 3. Query Document References & Sources (`HAS_REFERENCE`)

Find all `Source` reference documents linked to a concept.

```sql
GRAPH OKFGraph
MATCH (c)-[e:HAS_REFERENCE]->(s:Source)
RETURN 
  JSON_VALUE(c.properties, '$.id') AS concept_id,
  JSON_VALUE(s.properties, '$.name') AS source_title,
  JSON_VALUE(s.properties, '$.author') AS author,
  JSON_VALUE(s.properties, '$.drive_url') AS drive_url;
```

---

## 4. ScaNN Vector Search Query (`COSINE_DISTANCE`)

Perform semantic similarity vector search across title, description, and body text using 768-dimensional Gemini embeddings and Spanner ScaNN `GraphNodeVectorIndex`. Supports optional filtering by node `label` and `tags`.

```sql
SELECT 
  id AS node_uuid,
  label AS node_type,
  JSON_VALUE(properties, '$.id') AS concept_id,
  JSON_VALUE(properties, '$.name') AS concept_name,
  JSON_VALUE(properties, '$.description') AS description,
  JSON_VALUE_ARRAY(properties, '$.tags') AS tags,
  COSINE_DISTANCE(embedding, @query_vec) AS distance
FROM GraphNode
WHERE embedding IS NOT NULL
  AND (@label IS NULL OR label = @label)
  AND (
    @tags IS NULL
    OR EXISTS (
      SELECT 1 FROM UNNEST(JSON_VALUE_ARRAY(properties, '$.tags')) AS t
      JOIN UNNEST(@tags) AS search_tag
      ON LOWER(t) = search_tag OR LOWER(t) LIKE CONCAT('%', search_tag)
    )
    OR EXISTS (
      SELECT 1 FROM UNNEST(@tags) AS search_tag
      WHERE LOWER(JSON_VALUE(properties, '$.tag')) = search_tag
         OR LOWER(JSON_VALUE(properties, '$.tag')) LIKE CONCAT('%', search_tag)
    )
  )
ORDER BY distance ASC
LIMIT 5;
```

---

## 5. Full Text Search Query (`SEARCH`)

Perform full text keyword search on node body text using Spanner `SEARCH(body_tokens, query)` index. Supports optional filtering by node `label` and `tags`.

```sql
SELECT 
  id AS node_uuid,
  label AS node_type,
  JSON_VALUE(properties, '$.id') AS concept_id,
  JSON_VALUE(properties, '$.name') AS concept_name,
  JSON_VALUE_ARRAY(properties, '$.tags') AS tags
FROM GraphNode
WHERE SEARCH(body_tokens, 'Memorystore OR Spanner')
  AND (@label IS NULL OR label = @label)
  AND (
    @tags IS NULL
    OR EXISTS (
      SELECT 1 FROM UNNEST(JSON_VALUE_ARRAY(properties, '$.tags')) AS t
      JOIN UNNEST(@tags) AS search_tag
      ON LOWER(t) = search_tag OR LOWER(t) LIKE CONCAT('%', search_tag)
    )
    OR EXISTS (
      SELECT 1 FROM UNNEST(@tags) AS search_tag
      WHERE LOWER(JSON_VALUE(properties, '$.tag')) = search_tag
         OR LOWER(JSON_VALUE(properties, '$.tag')) LIKE CONCAT('%', search_tag)
    )
  )
LIMIT 10;
```

---

## 6. Multi-Hop Graph Path Traversal

Traverse paths (up to 3 hops) across concepts, tags, and sources in the knowledge graph.

```sql
GRAPH OKFGraph
MATCH p = (a)-[e]->{1,3}(b)
WHERE JSON_VALUE(a.properties, '$.id') = 'methodologies/how_to_use_memorystore'
RETURN 
  JSON_VALUE(a.properties, '$.id') AS start_concept,
  JSON_VALUE(b.properties, '$.id') AS end_concept,
  ARRAY_LENGTH(NODES(p)) AS path_node_count;
```

---

## 7. Unified Hybrid Search API (`POST /search`)

The unified search endpoint runs **both Full-Text Search (BM25) and ScaNN Vector Search (Cosine Similarity)** across Gemini node embeddings with optional `label` and `tags` filters in a single request.

### Hybrid Re-Ranking Algorithm: Reciprocal Rank Fusion (RRF+)

Rather than returning separate buckets, results are merged and re-ranked using an enhanced **Reciprocal Rank Fusion (RRF)** algorithm:

1. **Candidate Retrieval**: Fetches top candidate matches from both Spanner Full-Text Search (`SEARCH`) and ScaNN Vector Search (`COSINE_DISTANCE`).
2. **Reciprocal Rank Fusion**:
   $$\text{RRF}(d) = \frac{1}{60 + \text{rank}_{\text{vec}}(d)} + \frac{1}{60 + \text{rank}_{\text{fts}}(d)}$$
   Normalized to $[0.0, 1.0]$.
3. **Multi-Modal Score Fusion**: Blends normalized RRF ($50\%$), vector cosine similarity ($30\%$), and full-text relevance score ($20\%$).
4. **Cross-Modal Consensus Boost**: Items confirmed by **both** vector semantic search and full-text keyword search receive a $15\%$ synergy boost.
5. **Final Output**: Top `limit` items ordered by final `score` descending with 1-based `rank`.

### Request

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "search_string": "memorystore caching best practices",
    "label": "Methodology",
    "tags": ["caching", "database"],
    "limit": 5
  }'
```

> **Note**: Both `"tags": ["caching"]` (array) or `"tags": "caching"` (string) or `"tag": "caching"` are supported.

### Response

```json
{
  "search_string": "memorystore caching best practices",
  "label": "Methodology",
  "tags": ["caching", "database"],
  "total_results": 2,
  "rerank_algorithm": "reciprocal_rank_fusion_hybrid",
  "results": [
    {
      "id": "1aecf31e-3a61-280c-0ae0-e5d38ebc51dd",
      "label": "Methodology",
      "concept_id": "methodologies/how_to_use_memorystore",
      "name": "How to Use Memorystore",
      "description": "Best practices for deploying and configuring Google Cloud Memorystore for Redis.",
      "contributor": {
        "name": "Cloud Architecture Team",
        "email": "architecture@example.com"
      },
      "sources": [
        "https://cloud.google.com/memorystore/docs/redis"
      ],
      "tags": ["caching", "memorystore"],
      "score": 0.9421,
      "rank": 1,
      "matched_by": ["vector", "fulltext"],
      "vector_distance": 0.084,
      "fts_score": 1.54
    },
    {
      "id": "2c8d486a-e964-864d-aaae-2cfe564ba3c3",
      "label": "Methodology",
      "concept_id": "methodologies/how_to_size_memorystore",
      "name": "How to Size Memorystore",
      "description": "Sizing and memory management guide for Memorystore instances.",
      "contributor": {
        "name": "Cloud Architecture Team"
      },
      "sources": [],
      "tags": ["caching", "memorystore"],
      "score": 0.7812,
      "rank": 2,
      "matched_by": ["vector"],
      "vector_distance": 0.142,
      "fts_score": null
    }
  ]
}
```


