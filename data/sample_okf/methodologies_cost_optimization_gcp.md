---
id: methodologies/cost_optimization_gcp
concept_id: methodologies/cost_optimization_gcp
type: Methodology
label: Methodology
name: Cost Optimization on GCP
title: Cost Optimization on GCP
description: FinOps strategies and resource right-sizing across Google Cloud services
status: stable
okf_version: '0.2'
tags:
- finops
- cost-optimization
sources:
- id: '10001000100S0s1001001'
  title: Cost Optimization on GCP
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

FinOps guidelines for optimizing cloud spend.

### 1. Resource Sizing
- Right-size Memorystore via [[methodologies/how_to_size_memorystore|Memorystore Sizing]].
- Optimize BigQuery slots using [[methodologies/bigquery_warehouse_optimization|BigQuery Optimization]].

### 2. Serverless Scaling
- Scale down idle services in [[architectures/cloud_run_microservices|Cloud Run Microservices]].

