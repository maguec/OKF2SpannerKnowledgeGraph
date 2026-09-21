---
id: methodologies/how_to_size_memorystore
concept_id: methodologies/how_to_size_memorystore
type: Methodology
label: Methodology
name: How to Size Memorystore Instances
title: How to Size Memorystore Instances
description: Capacity planning and memory sizing guidelines for Memorystore Redis and Valkey
status: stable
okf_version: '0.2'
tags:
- product/memorystore
- capacity-planning
sources:
- id: '10001000100S0s1001001'
  title: How to Size Memorystore Instances
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

Guidelines for sizing Memorystore instances.

### 1. Memory Overhead
- Account for maxmemory policy and fragmentation.
- Avoid OOM issues listed in [[methodologies/how_to_use_memorystore|Memorystore Anti Patterns]].

### 2. Throughput Sizing
- Evaluate network throughput and CPU bounds.
- Check [[methodologies/cost_optimization_gcp|Cost Optimization Guidelines]].

