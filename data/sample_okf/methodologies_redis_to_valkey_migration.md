---
id: methodologies/redis_to_valkey_migration
concept_id: methodologies/redis_to_valkey_migration
type: Methodology
label: Methodology
name: Redis to Valkey Migration Guide
title: Redis to Valkey Migration Guide
description: Step-by-step guide for migrating Memorystore Redis instances to Valkey
status: stable
okf_version: '0.2'
tags:
- product/memorystore
- migration
sources:
- id: '10001000100S0s1001001'
  title: Redis to Valkey Migration Guide
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

Migrating from Redis to Valkey engine on Memorystore.

### 1. Compatibility Check
- Verify API compatibility and client library support.
- Review [[methodologies/how_to_use_memorystore|Memorystore Anti Patterns]].

### 2. Zero-Downtime Migration
- Use dual-writing and replication failover.
- Reference [[architectures/memorystore_high_availability|Memorystore HA]].

