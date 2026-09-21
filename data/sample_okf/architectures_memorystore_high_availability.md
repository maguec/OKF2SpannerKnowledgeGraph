---
id: architectures/memorystore_high_availability
concept_id: architectures/memorystore_high_availability
type: Architecture
label: Architecture
name: Memorystore High Availability Architecture
title: Memorystore High Availability Architecture
description: High availability topology and automatic failover design for Memorystore
status: stable
okf_version: '0.2'
tags:
- product/memorystore
- architecture
sources:
- id: '10001000100S0s1001001'
  title: Memorystore High Availability Architecture
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

High availability design for Memorystore instances.

### 1. Replica Management
- Provision cross-zone read replicas.
- Reference [[methodologies/memorystore_resiliency_patterns|Resiliency Patterns]].

### 2. Connection Handling
- Use smart clients to route reads to replicas.
- See [[methodologies/how_to_size_memorystore|Sizing Guide]] for replica memory footprint.

