"""Run the normalize → deployment retrieval → Ollama analysis MVP pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import Any

import chromadb

from app.log_normalizer import normalize_log
from app.ollama_analyzer import analyze_log
from app.rag import EmbeddingUnavailableError, ingest_dataset, retrieve_context

logger = logging.getLogger(__name__)


def run_pipeline(
    *,
    company: str,
    project: str,
    service: str,
    raw_log: str,
    deployment_stage: str | None = None,
    recent_logs: list[str] | None = None,
    skip_ingest: bool = False,
) -> dict[str, Any]:
    pipeline_started = time.perf_counter()
    normalize_started = time.perf_counter()
    normalized = normalize_log(
        raw_log,
        company=company,
        project=project,
        service=service,
        deployment_stage=deployment_stage,
    )
    normalize_ms = (time.perf_counter() - normalize_started) * 1000
    ingest_ms = 0.0
    if not skip_ingest:
        ingest_started = time.perf_counter()
        try:
            ingest_dataset()
        except EmbeddingUnavailableError as error:
            ingest_ms = (time.perf_counter() - ingest_started) * 1000
            _log_pipeline_timing(
                "AI_UNAVAILABLE", pipeline_started, normalize_ms, ingest_ms, 0.0, 0.0
            )
            return {
                "status": "AI_UNAVAILABLE",
                "message": "Ollama is not reachable for local embeddings.",
                "detail": str(error),
                "normalized_log": normalized,
                "retrieved_context": [],
            }
        except (chromadb.errors.ChromaError, OSError) as error:
            ingest_ms = (time.perf_counter() - ingest_started) * 1000
            _log_pipeline_timing(
                "RAG_UNAVAILABLE", pipeline_started, normalize_ms, ingest_ms, 0.0, 0.0
            )
            return {
                "status": "RAG_UNAVAILABLE",
                "message": "The local troubleshooting knowledge base is unavailable.",
                "detail": str(error),
                "normalized_log": normalized,
                "retrieved_context": [],
            }
        ingest_ms = (time.perf_counter() - ingest_started) * 1000
    related = [
        normalize_log(log, company=company, project=project, service=service)
        for log in (recent_logs or [])
    ]
    retrieval_started = time.perf_counter()
    try:
        context = retrieve_context(
            company=company,
            project=project,
            service=service,
            deployment_stage=normalized["deployment_stage"],
            new_log=normalized["message"],
        )
    except EmbeddingUnavailableError as error:
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        _log_pipeline_timing(
            "AI_UNAVAILABLE", pipeline_started, normalize_ms, ingest_ms, retrieval_ms, 0.0
        )
        return {
            "status": "AI_UNAVAILABLE",
            "message": "Ollama is not reachable for local embeddings.",
            "detail": str(error),
            "normalized_log": normalized,
            "retrieved_context": [],
        }
    except (chromadb.errors.ChromaError, OSError) as error:
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        _log_pipeline_timing(
            "RAG_UNAVAILABLE", pipeline_started, normalize_ms, ingest_ms, retrieval_ms, 0.0
        )
        return {
            "status": "RAG_UNAVAILABLE",
            "message": "The local troubleshooting knowledge base is unavailable.",
            "detail": str(error),
            "normalized_log": normalized,
            "retrieved_context": [],
        }
    retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
    analysis_started = time.perf_counter()
    analysis = analyze_log(
        normalized,
        context,
        recent_logs=related,
        company=company,
    )
    analysis_ms = (time.perf_counter() - analysis_started) * 1000
    status = (
        "OK"
        if analysis.get("status") in {"INCIDENT_DETECTED", "INSUFFICIENT_CONTEXT"}
        else analysis.get("status", "OK")
    )
    _log_pipeline_timing(
        status, pipeline_started, normalize_ms, ingest_ms, retrieval_ms, analysis_ms
    )
    return {
        "status": status,
        "normalized_log": normalized,
        "retrieved_context": context,
        "analysis": analysis,
    }


def _log_pipeline_timing(
    status: str,
    started: float,
    normalize_ms: float,
    ingest_ms: float,
    retrieval_ms: float,
    analysis_ms: float,
) -> None:
    total_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "pipeline_timing status=%s normalize_ms=%.1f ingest_ms=%.1f "
        "retrieval_ms=%.1f analysis_ms=%.1f total_ms=%.1f",
        status,
        normalize_ms,
        ingest_ms,
        retrieval_ms,
        analysis_ms,
        total_ms,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", default="Demo Corp")
    parser.add_argument("--project", default="E-Commerce")
    parser.add_argument("--service", default="Payment API")
    parser.add_argument("--deployment-stage", default="Database Migration")
    parser.add_argument(
        "--raw-log",
        default="[ERROR] Migration failed: relation 'orders' does not exist",
    )
    parser.add_argument("--recent-log", action="append", default=[])
    parser.add_argument("--skip-ingest", action="store_true")
    args = parser.parse_args()
    try:
        result = run_pipeline(
            company=args.company,
            project=args.project,
            service=args.service,
            deployment_stage=args.deployment_stage,
            raw_log=args.raw_log,
            recent_logs=args.recent_log,
            skip_ingest=args.skip_ingest,
        )
    except (OSError, ValueError, RuntimeError) as error:
        result = {
            "status": "PIPELINE_ERROR",
            "message": str(error),
        }
    print("Normalized Log:")
    print(json.dumps(result.get("normalized_log"), indent=2, ensure_ascii=False))
    print("\nRetrieved Context:")
    print(json.dumps(result.get("retrieved_context", []), indent=2, ensure_ascii=False))
    print("\nAI Analysis:")
    print(json.dumps(result.get("analysis", result), indent=2, ensure_ascii=False))
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
