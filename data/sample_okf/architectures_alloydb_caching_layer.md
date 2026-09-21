---
id: architectures/alloydb_caching_layer
concept_id: architectures/alloydb_caching_layer
type: Architecture
label: Architecture
name: AlloyDB Caching Layer Architecture
title: AlloyDB Caching Layer Architecture
description: Using Memorystore as a distributed write-through and read-aside cache for AlloyDB
status: stable
okf_version: '0.2'
tags:
- product/alloydb
- product/memorystore
sources:
- id: '10001000100S0s1001001'
  title: AlloyDB Caching Layer Architecture
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

Combining AlloyDB for PostgreSQL with Memorystore caching.

### 1. Read-Aside Pattern
- Cache frequently queried read objects.
- Refer to [[architectures/memorystore_high_availability|Memorystore HA]].

### 2. Columnar Engine
- Offload analytics to [[architectures/alloydb_columnar_engine|AlloyDB Columnar Engine]].
- Avoid anti-patterns from [[methodologies/how_to_use_memorystore|Memorystore Anti Patterns]].

