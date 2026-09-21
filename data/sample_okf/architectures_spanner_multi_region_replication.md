---
id: architectures/spanner_multi_region_replication
concept_id: architectures/spanner_multi_region_replication
type: Architecture
label: Architecture
name: Spanner Multi-Region Replication Architecture
title: Spanner Multi-Region Replication Architecture
description: Global consistency and multi-region replication setup for Cloud Spanner
status: stable
okf_version: '0.2'
tags:
- product/spanner
- multi-region
sources:
- id: '10001000100S0s1001001'
  title: Spanner Multi-Region Replication Architecture
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

Multi-region deployment architecture for Cloud Spanner.

### 1. Leader Placement
- Configure read-write leaders and read-only replicas.
- Follow [[methodologies/spanner_schema_best_practices|Spanner Schema Guidelines]].

### 2. Disaster Recovery
- Pair with [[methodologies/disaster_recovery_runbook|Disaster Recovery Runbook]].

