---
id: methodologies/how_to_use_memorystore
concept_id: methodologies/how_to_use_memorystore
type: Methodology
label: Methodology
name: Memorystore Anti Patterns
title: Memorystore Anti Patterns
description: Things not to do in Memorystore or issues that many customers run into
status: stable
okf_version: '0.2'
tags:
- product/memorystore
- product/alloydb
sources:
- id: '10001000100S0s1001001'
  title: Memorystore Anti Patterns
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

This document describes Memorystore Anti Patterns.

### 1. Expensive Operations
These are killers:
- KEYS
- SCAN
- See [[methodologies/how_to_size_memorystore|Memory Sizing Guide]] for memory impact.

### 2. Architecture
Architecture recommendations:
- Running standalone without [[architectures/memorystore_high_availability|High Availability]]
- Migrate to Valkey via [[methodologies/redis_to_valkey_migration|Redis to Valkey Migration]]

### 3. Client Level Issues
- Not using connection pooling
- For database integration, check [[architectures/alloydb_caching_layer|AlloyDB Caching Layer]].

