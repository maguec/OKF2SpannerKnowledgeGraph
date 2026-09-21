---
id: methodologies/memorystore_resiliency_patterns
concept_id: methodologies/memorystore_resiliency_patterns
type: Methodology
label: Methodology
name: Memorystore Resiliency Patterns
title: Memorystore Resiliency Patterns
description: Best practices for configuring failure domains and cluster persistence in Memorystore
status: stable
okf_version: '0.2'
tags:
- product/memorystore
- resiliency
sources:
- id: '10001000100S0s1001001'
  title: Memorystore Resiliency Patterns
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

Best practices for Memorystore availability and cluster persistence.

### 1. Persistence Options
- RDB snapshots vs AOF persistence.
- Pair with [[architectures/memorystore_high_availability|High Availability Patterns]].

### 2. Multi-Zone Failover
- Ensure automatic failover is enabled.
- Avoid common mistakes in [[methodologies/how_to_use_memorystore|Memorystore Anti Patterns]].
- See [[methodologies/disaster_recovery_runbook|Disaster Recovery Runbook]].

