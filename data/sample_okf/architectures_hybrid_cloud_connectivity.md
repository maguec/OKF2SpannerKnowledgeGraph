---
id: architectures/hybrid_cloud_connectivity
concept_id: architectures/hybrid_cloud_connectivity
type: Architecture
label: Architecture
name: Hybrid Cloud Connectivity Architecture
title: Hybrid Cloud Connectivity Architecture
description: Connecting on-premises data centers to GCP using Cloud Interconnect and VPN
status: stable
okf_version: '0.2'
tags:
- networking
- hybrid-cloud
sources:
- id: '10001000100S0s1001001'
  title: Hybrid Cloud Connectivity Architecture
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

Hybrid networking topology for enterprise cloud adoption.

### 1. Interconnect Options
- Dedicated Interconnect vs Partner Interconnect.
- Secure using [[methodologies/securing_gcp_workloads|Securing GCP Workloads]].

### 2. Disaster Recovery
- Enable cross-site failover in [[methodologies/disaster_recovery_runbook|Disaster Recovery Runbook]].

