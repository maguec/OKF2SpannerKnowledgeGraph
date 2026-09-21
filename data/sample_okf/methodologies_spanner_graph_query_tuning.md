---
id: methodologies/spanner_graph_query_tuning
concept_id: methodologies/spanner_graph_query_tuning
type: Methodology
label: Methodology
name: Spanner Graph Query Tuning
title: Spanner Graph Query Tuning
description: Optimizing GQL graph pattern matching queries and execution plans in Spanner
status: stable
okf_version: '0.2'
tags:
- product/spanner
- gql
- query-tuning
sources:
- id: '10001000100S0s1001001'
  title: Spanner Graph Query Tuning
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

Tuning GQL query performance in Spanner.

### 1. Path Filtering
- Use JSON_VALUE index hints and dynamic label filtering.
- Applied in [[architectures/spanner_graph_knowledge_base|Spanner Knowledge Graph]].

### 2. Schema Optimization
- Align with [[methodologies/spanner_schema_best_practices|Spanner Schema Best Practices]].

