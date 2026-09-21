---
id: methodologies/bigquery_warehouse_optimization
concept_id: methodologies/bigquery_warehouse_optimization
type: Methodology
label: Methodology
name: BigQuery Warehouse Optimization
title: BigQuery Warehouse Optimization
description: Partitioning, clustering, and slot management for BigQuery data warehouses
status: stable
okf_version: '0.2'
tags:
- product/bigquery
- optimization
sources:
- id: '10001000100S0s1001001'
  title: BigQuery Warehouse Optimization
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

Optimizing query performance and cost in BigQuery.

### 1. Partitioning & Clustering
- Partition by date/timestamp and cluster by frequent query keys.
- Review [[methodologies/cost_optimization_gcp|Cost Optimization GCP]].

### 2. Ingestion
- Stream data from [[methodologies/gcs_data_ingestion_patterns|GCS Ingestion Patterns]].

