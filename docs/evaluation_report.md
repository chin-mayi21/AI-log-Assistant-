# Deployment troubleshooting evaluation

- Evaluated: 2026-10-08T14:45:17+05:30
- Cases: 24
- Ollama chat model: `qwen2.5:1.5b`
- Ollama embedding model: `nomic-embed-text`
- ChromaDB collection: `ai_log_assistant_deployment_knowledge`
- Retrieval limit: 4 records per query

## Results

| Measure | Result |
| --- | ---: |
| Exact incident category accuracy | 58.3% |
| Category accuracy among analyses with a category | 63.6% |
| Expected category present in retrieved context | 70.8% |
| Retrieved examples stayed in the requested project | 100.0% |
| Analysis included evidence | 91.7% |
| Analysis returned 2–5 recommended actions | 91.7% |
| Unknown cases handled with low-confidence insufficient context | 0.0% |
| Non-OK/unavailable pipeline results | 2 |
| Average retrieved examples | 4.00 |

## Case details

| ID | Expected | Predicted | Retrieved expected category | Cause overlap | Evidence/actions |
| --- | --- | --- | --- | ---: | --- |
| CASE-001 | Docker/Container Failure | Docker/Container Failure | yes | 14% | yes/3 |
| CASE-002 | Kubernetes Deployment Failure | Kubernetes Deployment Failure | yes | 0% | yes/4 |
| CASE-003 | Image Pull Failure | Image Pull Failure | yes | 43% | yes/3 |
| CASE-004 | Database Migration Failure | AI_UNAVAILABLE | yes | 0% | no/0 |
| CASE-005 | Environment Variable Error | Configuration Error | no | 40% | yes/4 |
| CASE-006 | Network/Connectivity Failure | AI_UNAVAILABLE | yes | 0% | no/0 |
| CASE-007 | Version/Dependency Conflict | Version/Dependency Conflict | yes | 0% | yes/3 |
| CASE-008 | Port Conflict | Service Startup Failure | no | 17% | yes/4 |
| CASE-009 | Health Check Failure | Health Check Failure | yes | 33% | yes/4 |
| CASE-010 | Timeout | Timeout | yes | 11% | yes/3 |
| CASE-011 | Permission Error | Permission Error | yes | 100% | yes/3 |
| CASE-012 | Network/Connectivity Failure | Network/Connectivity Failure | yes | 17% | yes/3 |
| CASE-013 | Network/Connectivity Failure | Image Pull Failure | no | 0% | yes/3 |
| CASE-014 | Resource Exhaustion | Resource Exhaustion | yes | 22% | yes/5 |
| CASE-015 | Authentication/Authorization Failure | Database Migration Failure | no | 0% | yes/3 |
| CASE-016 | Build Failure | Build Failure | yes | 67% | yes/3 |
| CASE-017 | Dependency Failure | Dependency Failure | yes | 33% | yes/3 |
| CASE-018 | CI/CD Pipeline Failure | Image Pull Failure | no | 0% | yes/3 |
| CASE-019 | Configuration Error | Configuration Error | yes | 14% | yes/3 |
| CASE-020 | Kubernetes Deployment Failure | Kubernetes Deployment Failure | yes | 14% | yes/3 |
| CASE-021 | Infrastructure Failure | Resource Exhaustion | no | 0% | yes/3 |
| CASE-022 | Service Startup Failure | Timeout | no | 0% | yes/5 |
| CASE-023 | Timeout | Timeout | yes | 0% | yes/4 |
| CASE-024 | Unknown/Unclassified Failure | CI/CD Pipeline Failure | yes | 0% | yes/3 |

The cause overlap is a lightweight lexical diagnostic, not a semantic judgement. Review full per-case inputs, retrieved examples, and model outputs in `data/evaluation_results.json`; category and safety decisions require human review.
