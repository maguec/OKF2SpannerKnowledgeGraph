---
id: architectures/llm_embeddings_pipeline
concept_id: architectures/llm_embeddings_pipeline
type: Architecture
label: Architecture
name: LLM Embeddings Pipeline Architecture
title: LLM Embeddings Pipeline Architecture
description: Generating and storing text embeddings at scale using Gemini and Vertex AI
status: stable
okf_version: '0.2'
tags:
- ai/embeddings
- product/vertex-ai
sources:
- id: '10001000100S0s1001001'
  title: LLM Embeddings Pipeline Architecture
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

Pipeline for generating and serving text embeddings.

### 1. Model Serving
- Use Gemini text-embedding-004 model.
- Store embeddings in [[architectures/vector_search_rag_pipeline|Vector Search RAG Pipeline]].

### 2. Knowledge Ingestion
- Extract metadata from [[architectures/spanner_graph_knowledge_base|Spanner Graph]].

