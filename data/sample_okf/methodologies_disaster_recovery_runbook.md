---
id: methodologies/disaster_recovery_runbook
concept_id: methodologies/disaster_recovery_runbook
type: Methodology
label: Methodology
name: Disaster Recovery Runbook
title: Disaster Recovery Runbook
description: RTO/RPO objectives and failover procedures for mission-critical GCP applications
status: stable
okf_version: '0.2'
tags:
- disaster-recovery
- operations
sources:
- id: '10001000100S0s1001001'
  title: Disaster Recovery Runbook
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

Disaster recovery procedures for cloud workloads.

### 1. Database Failover
- Execute failover for [[architectures/spanner_multi_region_replication|Spanner Multi-Region]].
- Restore caches using [[methodologies/memorystore_resiliency_patterns|Memorystore Resiliency]].

### 2. Network Rerouting
- Reroute traffic via [[architectures/hybrid_cloud_connectivity|Hybrid Connectivity]].

