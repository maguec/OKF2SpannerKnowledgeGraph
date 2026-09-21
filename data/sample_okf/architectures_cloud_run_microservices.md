---
id: architectures/cloud_run_microservices
concept_id: architectures/cloud_run_microservices
type: Architecture
label: Architecture
name: Cloud Run Microservices Architecture
title: Cloud Run Microservices Architecture
description: Deploying serverless containerized REST microservices on Cloud Run
status: stable
okf_version: '0.2'
tags:
- product/cloud-run
- microservices
sources:
- id: '10001000100S0s1001001'
  title: Cloud Run Microservices Architecture
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

Serverless container architecture on Cloud Run.

### 1. API Gateway Integration
- Secure endpoints with [[methodologies/securing_gcp_workloads|Securing GCP Workloads]].

### 2. Cache & Database
- Connect to [[architectures/alloydb_caching_layer|AlloyDB Caching Layer]].
- Access [[architectures/spanner_graph_knowledge_base|Spanner Graph]].

