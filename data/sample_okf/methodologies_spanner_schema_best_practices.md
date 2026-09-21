---
id: methodologies/spanner_schema_best_practices
concept_id: methodologies/spanner_schema_best_practices
type: Methodology
label: Methodology
name: Spanner Schema Best Practices
title: Spanner Schema Best Practices
description: Avoiding hotspots and optimizing primary key selection in Cloud Spanner
status: stable
okf_version: '0.2'
tags:
- product/spanner
- database-design
sources:
- id: '10001000100S0s1001001'
  title: Spanner Schema Best Practices
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

Schema design patterns for Cloud Spanner.

### 1. Primary Keys
- Use UUIDv4 or bit-reversed sequence primary keys to prevent hotspots.
- Used in [[architectures/spanner_graph_knowledge_base|Spanner Knowledge Graph]].

### 2. Multi-Region Topologies
- Align schema with [[architectures/spanner_multi_region_replication|Multi-Region Replication]].

