---
id: architectures/spanner_graph_knowledge_base
concept_id: architectures/spanner_graph_knowledge_base
type: Architecture
label: Architecture
name: Spanner Knowledge Graph Architecture
title: Spanner Knowledge Graph Architecture
description: Building scalable property graph databases with Google Cloud Spanner and OKF v2
status: stable
okf_version: '0.2'
tags:
- product/spanner
- graph-database
sources:
- id: '10001000100S0s1001001'
  title: Spanner Knowledge Graph Architecture
  author: chrism@example.com
  drive_url: https://drive.google.com/open?id=10001000100S0s1001001
  references: []
contributor:
  email: chrism@example.com
  role: Solutions Architect
google_cloud_products: []
external_hybrid_products: []
custom_properties: {}
---

Architectural pattern for building knowledge graphs on Spanner.

### 1. Schema Design
- Interleaved GraphNode and GraphEdge tables.
- Refer to [[methodologies/spanner_schema_best_practices|Spanner Schema Best Practices]].
- Tune queries using [[methodologies/spanner_graph_query_tuning|Query Tuning]].

### 2. AI Integration
- Combine graph structure with [[architectures/vector_search_rag_pipeline|Vector Search RAG Pipeline]].
- Generate embeddings via [[architectures/llm_embeddings_pipeline|LLM Embeddings Pipeline]].

