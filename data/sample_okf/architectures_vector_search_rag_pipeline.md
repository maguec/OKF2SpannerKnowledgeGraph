---
id: architectures/vector_search_rag_pipeline
concept_id: architectures/vector_search_rag_pipeline
type: Architecture
label: Architecture
name: Vector Search RAG Pipeline
title: Vector Search RAG Pipeline
description: Building Retrieval-Augmented Generation using Vector Search and Knowledge Graphs
status: stable
okf_version: '0.2'
tags:
- ai/rag
- product/vector-search
sources:
- id: '10001000100S0s1001001'
  title: Vector Search RAG Pipeline
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

RAG pipeline architecture integrating vector search and graph knowledge.

### 1. Hybrid Retrieval
- Combine vector similarity search with [[architectures/spanner_graph_knowledge_base|Spanner Graph]].
- Feed embeddings from [[architectures/llm_embeddings_pipeline|Embeddings Pipeline]].

### 2. Backend API
- Expose via [[architectures/cloud_run_microservices|Cloud Run Microservices]].

