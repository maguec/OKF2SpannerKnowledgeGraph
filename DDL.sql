CREATE TABLE GraphNode (
  id STRING(36) NOT NULL,
  label STRING(MAX) NOT NULL,
  properties JSON,
  body_tokens TOKENLIST AS (TOKENIZE_FULLTEXT(JSON_VALUE(properties, '$.body'))) HIDDEN,
  embedding ARRAY<FLOAT64>(vector_length=>768),
) PRIMARY KEY (id);

CREATE TABLE GraphEdge (
  id STRING(36) NOT NULL,
  dest_id STRING(36) NOT NULL,
  edge_id STRING(36) NOT NULL,
  label STRING(MAX) NOT NULL,
  properties JSON,
) PRIMARY KEY (id, dest_id, edge_id),
  INTERLEAVE IN PARENT GraphNode;

CREATE PROPERTY GRAPH OKFGraph
  NODE TABLES (
    GraphNode
      DYNAMIC LABEL (label)
      DYNAMIC PROPERTIES (properties)
  )
  EDGE TABLES (
    GraphEdge
      SOURCE KEY (id) REFERENCES GraphNode(id)
      DESTINATION KEY (dest_id) REFERENCES GraphNode(id)
      DYNAMIC LABEL (label)
      DYNAMIC PROPERTIES (properties)
  );

-- Spanner Full Text Search Index
CREATE SEARCH INDEX GraphNodeSearchIndex ON GraphNode(body_tokens);

-- Spanner ScaNN Vector Search Index (Gemini text-embedding-004 768-dim)
CREATE VECTOR INDEX GraphNodeVectorIndex ON GraphNode(embedding) 
WHERE embedding IS NOT NULL 
OPTIONS (distance_type = 'COSINE');
