# Spanner Graph Sample Queries for OKF Knowledge Graph

This document provides sample **Spanner Graph (GQL)** queries to inspect, traverse, and visualize the OKF Knowledge Graph (`OKFGraph`) created in Google Cloud Spanner.

> **Note on Schema & Primary Keys**:
> - `GraphNode.id`, `GraphEdge.id`, `GraphEdge.dest_id`, and `GraphEdge.edge_id` are formatted as **UUIDv4 (`STRING(36)`)**.
> - Human-readable concept strings (e.g. `'spanner-graph'`), concept names, and metadata remain accessible inside the `properties` JSON column.

---

## 1. List All Nodes in the Knowledge Graph

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

## 2. Retrieve All Relationships / Edges

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

## 3. Find Outgoing and Incoming Links for a Specific Concept

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

## 4. Multi-Hop Graph Path Traversal

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

## 5. Most Connected Concepts (Out-Degree Aggregation)

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

---

## 6. Standard SQL Query Fallback

You can also run standard relational Spanner SQL directly on the underlying `GraphNode` and `GraphEdge` tables:

```sql
SELECT 
  n.id AS node_uuid,
  n.label AS node_type,
  JSON_VALUE(n.properties, '$.id') AS concept_id,
  JSON_VALUE(n.properties, '$.name') AS concept_name
FROM GraphNode n;

SELECT 
  e.id AS source_node_uuid,
  e.dest_id AS target_node_uuid,
  e.edge_id AS edge_uuid,
  e.label AS relationship,
  JSON_VALUE(e.properties, '$.type') AS link_type,
  JSON_VALUE(e.properties, '$.text') AS link_text
FROM GraphEdge e;
```
