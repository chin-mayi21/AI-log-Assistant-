# Deployment troubleshooting knowledge dataset

## Focus and categories

`data/deployment_logs.json` prioritizes build, deployment, container, Kubernetes, CI/CD, migration,
configuration, and infrastructure troubleshooting instead of generic application incidents.
There are 20 labeled records for each category:

1. Build Failure
2. Dependency Failure
3. Docker/Container Failure
4. Kubernetes Deployment Failure
5. CI/CD Pipeline Failure
6. Database Migration Failure
7. Configuration Error
8. Environment Variable Error
9. Authentication/Authorization Failure
10. Network/Connectivity Failure
11. Port Conflict
12. Service Startup Failure
13. Health Check Failure
14. Resource Exhaustion
15. Timeout
16. Image Pull Failure
17. Version/Dependency Conflict
18. Permission Error
19. Infrastructure Failure
20. Unknown/Unclassified Failure

All examples are synthetic and authored for this MVP. No external log dataset is copied. Each
category has four scenarios and each scenario has five temporally adjacent events to preserve a
small symptom → failure → impact progression. `metadata.scenario_id` and
`metadata.sequence_index` retain that relationship. These timestamps and sequences are illustrative,
not production chronology.

## Projects and services

| Project | Example deployment services |
| --- | --- |
| E-Commerce | Payment API, Order Service, Product Service, Database Service |
| HR Portal | Employee Service, Payroll Service, Notification Service, Database Service |
| Banking Platform | Account Service, Transaction Service, Payment Service, Database Service |
| Platform Infrastructure | Build Runner, Container Registry, Kubernetes Cluster, Deployment Controller, Database Service |

Service names can recur across projects; project/service context must remain attached. The
Platform Infrastructure project is included for shared deployment concerns that do not belong
exclusively to one business application.

## Record schema

The JSON file is a UTF-8 array with these fields:

| Field | Type | Use |
| --- | --- | --- |
| `id` | string | Unique `DEP-0001`-style training-example identifier. |
| `project` | string | Project context for the log. |
| `service` | string | Service or infrastructure component. |
| `deployment_stage` | string | Build, migration, rollout, startup, verification, and related stage. |
| `timestamp` | string | Synthetic ISO-8601 local timestamp. |
| `level` | string | Event level (`WARN` or `ERROR` in this incident-focused corpus). |
| `raw_log` | string | Synthetic source-format log text. |
| `normalized_message` | string | Message text for semantic indexing. |
| `incident_type` | string | One of the 20 categories listed above. |
| `severity` | string | Operational impact (`LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`). |
| `probable_root_cause` | string | Evidence-aligned probable cause, not a claim of infrastructure inspection. |
| `troubleshooting_steps` | array[string] | Practical, safe investigation steps. |
| `expected_resolution` | string | Expected corrective outcome once evidence confirms it. |
| `metadata` | object | Correlation keys, impact context, or tenant metadata. |

The CSV uses the same records and columns in JSON-file order. Array and object fields
(`troubleshooting_steps` and `metadata`) are JSON-encoded within quoted CSV cells.

## Severity

- **LOW:** isolated tooling issue, optional step, or safe fallback with no known user impact.
- **MEDIUM:** a limited stage/component is delayed or degraded.
- **HIGH:** a service/release is blocked or materially degraded.
- **CRITICAL:** a high-impact release or workload is unavailable, data/financial state is uncertain,
  or recovery needs careful validation.

Severity follows the example's described impact, not a random label. It is contextual; a warning
about an optional documentation job is not treated like an unavailable transaction service.

## Test cases and evaluation

`data/test_cases.json` contains 24 new deployment log inputs, distinct from training `raw_log`
strings. It covers Docker exits, CrashLoopBackOff, image pulls, migrations, missing environment,
connectivity, dependency/version conflict, port binding, health checks, timeouts, permissions, DNS,
TLS, memory, database credentials, build/CI, configuration, scheduling, storage, startup, and an
unknown failure. Each case records expected category and probable cause.

`app.evaluate_deployment` sends those inputs through normalizer → Chroma retrieval → Ollama → JSON
validation, then writes `data/evaluation_results.json` and `docs/evaluation_report.md`. Results
include exact category accuracy, whether the expected category was retrieved, project-context
isolation, evidence/actions shape, and cautious unknown handling. Cause token overlap is only a
lightweight diagnostic; the full context and output are retained for engineer review. The cases
are a small MVP smoke-test set, not a statistically representative benchmark.

## Rebuilding the files

```powershell
& 'C:\Program Files\Python314\python.exe' data\build_deployment_dataset.py
```
