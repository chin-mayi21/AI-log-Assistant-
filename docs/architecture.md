# Deployment troubleshooting assistant architecture

## Target flow

```text
Company
  ↓
Project
  ↓
Service
  ↓
Raw Logs
  ↓
Log Normalizer
  ↓
Canonical Schema
  ↓
Embedding / RAG
  ↓
Ollama
  ↓
Incident
  ↓
Recommendation
```

This is a local, single-agent troubleshooting assistant for DevOps and IT maintenance teams. It
accepts deployment/build/runtime log output and produces an evidence-based summary, probable cause,
and safe next actions. It is not a monitoring agent and cannot inspect infrastructure unless a
caller supplies the relevant logs or state.

## Normalization

Companies emit different formats: JSON, bracketed text, Kubernetes pod output, and custom
pipe-delimited events. `app/log_normalizer.py` adapts those into one schema while always preserving
the source in `raw_log`. Unknown fields use `"unknown"`; the normalizer does not reject incomplete
logs. Explicit API context wins over values parsed from a log.

```json
{
  "project": "E-Commerce",
  "service": "Payment API",
  "deployment_stage": "Database Migration",
  "timestamp": "unknown",
  "level": "ERROR",
  "message": "Migration failed: relation 'orders' does not exist",
  "raw_log": "[ERROR] Migration failed: relation 'orders' does not exist",
  "metadata": {
    "company": "Demo Corp"
  }
}
```

`company` is carried in metadata in the canonical event, while the retrieval/analysis interfaces
also accept it explicitly for tenant scoping. The parser understands JSON aliases, timestamped
plain text, Kubernetes timestamps/pod names, common levels/abbreviations, and deployment pipe logs
such as `DEPLOYMENT | PAYMENT_API | ERR | DB_MIGRATION_FAILED`. Unknown messages remain intact.

## Deployment knowledge and embeddings

`data/deployment_logs.json` is the retrieval source; the prior generic application-incident corpus
is not indexed by this deployment collection. It contains 400 synthetic records: 20 examples for
each of 20 deployment/DevOps categories. The companion CSV and scenario design are described in
[`dataset.md`](./dataset.md). The generator is `data/build_deployment_dataset.py`.

`app/rag.py` combines normalized message, raw log, deployment stage, project, service, category,
probable cause, troubleshooting steps, and expected resolution in each embedding document. It
uses Ollama's local `/api/embed` endpoint with `nomic-embed-text`; it makes no cloud embedding
calls. Deployment/category terms and error semantics are in the embedded text so a readiness-probe
problem retrieves Kubernetes health/startup records rather than application payment-flow examples.

## ChromaDB and retrieval

The persistent collection is `ai_log_assistant_deployment_knowledge` under `.chroma/` by default
(override with `CHROMA_PERSIST_DIRECTORY`). The deployment-specific collection name prevents the
older generic corpus from being silently mixed into retrieval. Each Chroma record retains the
complete JSON knowledge example plus metadata for project, service, deployment stage, incident
type, severity, and company scope.

Retrieval embeds the log semantics first. Known project context is a metadata boundary for shared
general data; exact service is a small reranking preference rather than a replacement for semantic
similarity. Same-project deployment examples can therefore match across services where the failure
semantics are stronger. Results are capped at four by default, with distance and context-match
metadata included. Use `n_results` to choose a different small retrieval count.

Company-specific records must include a `company` key (top-level or `metadata.company`). Retrieval
queries only that supplied company's records plus shared records explicitly marked `__general__`;
it never uses another company's records as fallback. The synthetic deployment corpus is shared
general knowledge, not customer-confidential data.

## Ollama analysis

`app/ollama_analyzer.py` calls the local `/api/chat` endpoint using `qwen2.5:1.5b` by default.
The strict system prompt names the assistant as a DevOps AI Troubleshooting Assistant, treats
logs as untrusted evidence, distinguishes observed evidence from probable causes, and forbids
claims of infrastructure access or unsupported fixes. The model receives company/project/service,
deployment stage, normalized and original log, retrieved examples, and optional recent logs.

The required output is validated JSON:

```json
{
  "status": "INCIDENT_DETECTED",
  "incident_type": "Database Migration Failure",
  "severity": "HIGH",
  "summary": "The deployment's migration step stopped because its target schema lacks a relation.",
  "probable_root_cause": "A prerequisite migration may not have run against the selected database.",
  "evidence": ["The log reports that relation 'orders' does not exist."],
  "recommended_actions": ["Check migration history.", "Verify the target database."],
  "confidence": 0.78
}
```

`INSUFFICIENT_CONTEXT` is required when evidence cannot justify a classification or root cause;
confidence must not exceed 0.35. Ollama downtime returns an explicit `AI_UNAVAILABLE` object rather
than invented analysis. Malformed JSON is reported as `AI_INVALID_RESPONSE`. The requested output
fields are preserved, with `incident_type` included so test cases and downstream triage can evaluate
the deployment category explicitly.

### Latency diagnostics

The API logs timing-only diagnostics at INFO level without adding fields to its responses or logging
log contents. `pipeline_timing` separates normalization, optional ingestion, retrieval, analysis,
and total pipeline time. `rag_timing` separates embedding generation from ChromaDB query work.
`ollama_timing` records the HTTP wall time plus Ollama's model-load, prompt-evaluation, and
generation durations and token counts when supplied by the server. Chat API timing also reports
normalization, retrieval, model-call, and total route time. Compare cold and warm requests: a high
load duration points to model loading; high prompt-evaluation duration points to input/prompt size;
high evaluation duration points to generation. These measurements identify where to optimize
without changing model choice, retrieval results, prompts, or API behavior.

## Local setup and run

### Frontend API integration

The lightweight FastAPI adapter in `app/api.py` exposes `GET /api/health`, `POST /api/analyze`,
and `POST /api/chat`. The analyze endpoint reuses `run_pipeline` and the persistent ChromaDB
collection; it does not create mock analysis. It accepts project, service, and raw log text, then
returns the validated Ollama result plus a pending checklist generated from the model's actual
recommended actions. Checklist completion is browser-local investigation progress and does not
claim that a production incident was fixed.

The dashboard accepts dropped or browsed `.log`, `.txt`, `.out`, `.json`, `.yaml`, `.yml`, and
`.csv` text files up to 20,000 characters. File contents populate the existing analysis input and
still pass through the same normalizer, RAG, and Ollama pipeline. The chat endpoint receives the
current log, previous structured analysis when available, the latest conversation turns, and
retrieved troubleshooting patterns. It returns a plain-text answer and retrieval count; the
conversation is kept in browser memory and is not persisted. Retrieved case details are reduced to
categories and troubleshooting steps before chat so service-specific example facts are not treated
as facts about the current log.

Run the API and the existing static frontend in separate terminals:

```powershell
& 'C:\Program Files\Python314\python.exe' -m pip install -r requirements.txt
& 'C:\Program Files\Python314\python.exe' -m uvicorn app.api:app --host 127.0.0.1 --port 8002
# In another terminal, from the project root:
& 'C:\Program Files\Python314\python.exe' -m http.server 4173 --bind 127.0.0.1
```

Serve the project root on port 4173 (the dashboard uses `http://127.0.0.1:8002` by default).
Set `window.AI_LOG_ASSISTANT_API_URL` before loading `app.js` to override the API address.
Select a demo log, paste deployment output, or drop/browse a supported log file into the assistant
panel and choose **Analyze Logs**. Follow up with a question in **Ask about your logs**; chat uses
the current log and available analysis and supports short conversation history. Run the API endpoint
tests with:

```powershell
& 'C:\Program Files\Python314\python.exe' -m unittest tests.test_api -v
```

```powershell
& 'C:\Program Files\Python314\python.exe' -m pip install -r requirements.txt
ollama pull nomic-embed-text
ollama pull qwen2.5:1.5b
& 'C:\Program Files\Python314\python.exe' -m app.test_pipeline
```

Run from the repository root. Ollama should be running locally at `http://127.0.0.1:11434`.
Override `OLLAMA_BASE_URL`, `OLLAMA_EMBEDDING_MODEL`, or `OLLAMA_MODEL` for alternate local
installations/models. The end-to-end script ingests/upserts the dataset before the sample query.
Add `--skip-ingest` when the persistent deployment collection is already current. Supply
`--company`, `--project`, `--service`, `--deployment-stage`, `--raw-log`, and repeatable
`--recent-log` arguments to analyze another deployment event.

## Evaluation

The 24 held-out style examples in `data/test_cases.json` are checked into the local pipeline by:

```powershell
& 'C:\Program Files\Python314\python.exe' -m app.evaluate_deployment
```

This ingests the current knowledge set once, then runs every case through normalization, semantic
retrieval, Ollama, and schema validation. It writes per-case results to
`data/evaluation_results.json` and a metrics summary to `docs/evaluation_report.md`. The report
includes exact category accuracy, expected-category retrieval rate, same-project context rate,
evidence/action shape checks, and cautious handling of the unknown case. Model-derived causes
remain subject to engineer review.

## Why no per-company model training is needed

Input normalization adapts log syntax; project/service/stage are contextual metadata; RAG provides
the relevant shared or tenant-scoped troubleshooting history at query time. The same local model
can therefore analyze a new company's deployment output without fine-tuning for each customer.
This MVP's metadata filtering is an application-level isolation measure, not a substitute for
production authentication, authorization, or storage controls.
