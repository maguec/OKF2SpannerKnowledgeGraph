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

Perform semantic similarity vector search across title, description, and body text using 768-dimensional Gemini embeddings and Spanner ScaNN `GraphNodeVectorIndex`.

```sql
SELECT 
  id AS node_uuid,
  label AS node_type,
  JSON_VALUE(properties, '$.id') AS concept_id,
  JSON_VALUE(properties, '$.name') AS concept_name,
  JSON_VALUE(properties, '$.description') AS description,
  COSINE_DISTANCE(embedding, @query_vec) AS distance
FROM GraphNode
WHERE embedding IS NOT NULL
ORDER BY distance ASC
LIMIT 5;
```

---

## 5. Full Text Search Query (`SEARCH`)

Perform full text keyword search on node body text using Spanner `SEARCH(body_tokens, query)` index.

```sql
SELECT 
  id AS node_uuid,
  label AS node_type,
  JSON_VALUE(properties, '$.id') AS concept_id,
  JSON_VALUE(properties, '$.name') AS concept_name
FROM GraphNode
WHERE SEARCH(body_tokens, 'Memorystore OR Spanner')
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
