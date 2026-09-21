# Spanner Graph & Search Sample Queries for OKF Knowledge Graph

This document provides sample **Spanner Graph (GQL)**, **Full Text Search (FTS)**, and **ScaNN Vector Search** queries to inspect, search, and traverse the OKF Knowledge Graph (`OKFGraph`) created in Google Cloud Spanner.

> **Note on Schema & Primary Keys**:
> - `GraphNode.id`, `GraphEdge.id`, `GraphEdge.dest_id`, and `GraphEdge.edge_id` are formatted as **UUIDv4 (`STRING(36)`)**.
> - Full Text Search index: `GraphNodeSearchIndex` on `body_tokens` (`TOKENLIST`).
> - Vector Search index: `GraphNodeVectorIndex` (ScaNN index with `COSINE` distance) on `embedding` (`ARRAY<FLOAT64>(vector_length=>768)` generated via Gemini `text-embedding-004`).

---

## 1. Full Text Search Query (`SEARCH`)

Perform full text keyword search on node body text using Spanner `SEARCH(body_tokens, query)` index.

```sql
SELECT 
  id AS node_uuid,
  label AS node_type,
  JSON_VALUE(properties, '$.id') AS concept_id,
  JSON_VALUE(properties, '$.name') AS concept_name
FROM GraphNode
WHERE SEARCH(body_tokens, 'Spanner OR Graph')
LIMIT 10;
```

---

## 2. ScaNN Vector Search Query (`COSINE_DISTANCE`)

Perform semantic similarity vector search using 768-dimensional Gemini embeddings and Spanner ScaNN `GraphNodeVectorIndex`.

```sql
SELECT 
  id AS node_uuid,
  label AS node_type,
  JSON_VALUE(properties, '$.id') AS concept_id,
  JSON_VALUE(properties, '$.name') AS concept_name,
  COSINE_DISTANCE(embedding, @query_vec) AS distance
FROM GraphNode
WHERE embedding IS NOT NULL
ORDER BY distance ASC
LIMIT 5;
```

---

## 3. List All Nodes in the Knowledge Graph

Fetch all graph nodes with their UUIDv4 primary keys, dynamic labels, and concept properties.

```sql
GRAPH OKFGraph
MATCH (n)
RETURN 
  n.id AS node_uuid,
  n.label AS node_type,
  JSON_VALUE(n.properties, '$.id') AS concept_id,
  JSON_VALUE(n.properties, '$.name') AS concept_name
ORDER BY concept_id;
```

---

## 4. Retrieve All Relationships / Edges

Query all directed edges (`LINKS_TO`) between source and destination concepts.

```sql
GRAPH OKFGraph
MATCH (source)-[e]->(target)
WHERE e.label = 'LINKS_TO'
RETURN 
  JSON_VALUE(source.properties, '$.id') AS source_concept,
  e.label AS relationship,
  JSON_VALUE(e.properties, '$.type') AS link_format,
  JSON_VALUE(e.properties, '$.text') AS link_text,
  JSON_VALUE(target.properties, '$.id') AS target_concept
ORDER BY source_concept;
```

---

## 5. Find Outgoing and Incoming Links for a Specific Concept

Search for all outgoing links from `spanner-graph` or incoming backlinks to `kg-architecture`.

### Outgoing Links:
```sql
GRAPH OKFGraph
MATCH (c)-[e]->(target)
WHERE JSON_VALUE(c.properties, '$.id') = 'spanner-graph' AND e.label = 'LINKS_TO'
RETURN 
  JSON_VALUE(c.properties, '$.name') AS source_name,
  JSON_VALUE(e.properties, '$.type') AS link_type,
  JSON_VALUE(target.properties, '$.name') AS linked_concept;
```

### Incoming Links (Backlinks):
```sql
GRAPH OKFGraph
MATCH (source)-[e]->(c)
WHERE JSON_VALUE(c.properties, '$.id') = 'kg-architecture' AND e.label = 'LINKS_TO'
RETURN 
  JSON_VALUE(source.properties, '$.name') AS referencing_concept,
  JSON_VALUE(e.properties, '$.type') AS link_type,
  JSON_VALUE(c.properties, '$.name') AS target_name;
```

---

## 6. Multi-Hop Graph Path Traversal

Traverse connected paths (up to 3 hops) between concepts in the knowledge graph.

```sql
GRAPH OKFGraph
MATCH p = (a)-[e]->{1,3}(b)
RETURN 
  JSON_VALUE(a.properties, '$.id') AS start_concept,
  JSON_VALUE(b.properties, '$.id') AS end_concept,
  ARRAY_LENGTH(NODES(p)) AS path_node_count;
```

---

## 7. Most Connected Concepts (Out-Degree Aggregation)

Count the number of outgoing links per concept to identify central node hubs in the graph.

```sql
GRAPH OKFGraph
MATCH (n)-[e]->(m)
WHERE e.label = 'LINKS_TO'
RETURN 
  JSON_VALUE(n.properties, '$.id') AS concept_id,
  JSON_VALUE(n.properties, '$.name') AS concept_name,
  COUNT(e) AS outgoing_links_count
GROUP BY concept_id, concept_name
ORDER BY outgoing_links_count DESC;
```
