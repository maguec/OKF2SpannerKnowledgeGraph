---
id: architectures/event_driven_pubsub_pipeline
concept_id: architectures/event_driven_pubsub_pipeline
type: Architecture
label: Architecture
name: Event Driven PubSub Pipeline
title: Event Driven PubSub Pipeline
description: Asynchronous event streaming and message processing with Cloud Pub/Sub
status: stable
okf_version: '0.2'
tags:
- product/pubsub
- event-driven
sources:
- id: '10001000100S0s1001001'
  title: Event Driven PubSub Pipeline
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

Event-driven streaming pipeline design.

### 1. Message Distribution
- Pub/Sub topics and push/pull subscriptions.
- Integrate with [[methodologies/gcs_data_ingestion_patterns|GCS Ingestion]].

### 2. Processing Engine
- Process events with [[architectures/cloud_run_microservices|Cloud Run Microservices]].

