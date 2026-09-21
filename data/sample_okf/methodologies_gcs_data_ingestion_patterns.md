---
id: methodologies/gcs_data_ingestion_patterns
concept_id: methodologies/gcs_data_ingestion_patterns
type: Methodology
label: Methodology
name: GCS Data Ingestion Patterns
title: GCS Data Ingestion Patterns
description: Batch and streaming data ingestion patterns using Google Cloud Storage
status: stable
okf_version: '0.2'
tags:
- product/gcs
- data-ingestion
sources:
- id: '10001000100S0s1001001'
  title: GCS Data Ingestion Patterns
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

Data ingestion architectures using Cloud Storage.

### 1. Event Notifications
- Trigger pipelines using [[architectures/event_driven_pubsub_pipeline|Event Driven PubSub Pipeline]].

### 2. Data Warehouse Loading
- Direct ingestion into [[methodologies/bigquery_warehouse_optimization|BigQuery Warehouse]].

