"""FastAPI adapter for the local deployment troubleshooting pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

import chromadb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from app.log_normalizer import normalize_log
from app.ollama_analyzer import OLLAMA_MODEL, chat_about_logs
from app.rag import COLLECTION_NAME, EmbeddingUnavailableError, retrieve_context
from app.test_pipeline import run_pipeline

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Log Assistant API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class AnalyzeRequest(BaseModel):
    project: str = Field(min_length=1, max_length=120)
    service: str = Field(min_length=1, max_length=120)
    log: str = Field(min_length=1, max_length=20000)
    company: str = Field(default="Demo Corp", min_length=1, max_length=120)

    @field_validator("project", "service", "log", "company")
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ChatRequest(BaseModel):
    project: str = Field(min_length=1, max_length=120)
    service: str = Field(min_length=1, max_length=120)
    log: str = Field(min_length=1, max_length=20000)
    question: str = Field(min_length=1, max_length=2000)
    company: str = Field(default="Demo Corp", min_length=1, max_length=120)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    analysis: dict[str, Any] | None = None

    @field_validator("project", "service", "log", "question", "company")
    @classmethod
    def reject_blank_chat_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


def _build_checklist(analysis: dict[str, Any]) -> list[dict[str, str]]:
    actions = analysis["recommended_actions"]
    cause = analysis["probable_root_cause"].strip()
    checklist = []
    for index, action in enumerate(actions, start=1):
        title = action.strip().rstrip(".")
        if len(title) > 84:
            title = title[:81].rsplit(" ", 1)[0] + "..."
        checklist.append(
            {
                "id": f"step-{index}",
                "title": title,
                "description": action.strip(),
                "reason": f"This helps verify the probable cause: {cause}"[:240],
                "status": "pending",
            }
        )
    return checklist


@app.get("/api/health")
def health() -> dict[str, str]:
    """Report API configuration without depending on Ollama being online."""
    return {
        "status": "ok",
        "service": "AI Log Assistant API",
        "ollama_model": OLLAMA_MODEL,
        "rag_collection": COLLECTION_NAME,
    }


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    """Normalize, retrieve context, and analyze one supplied log with Ollama."""
    request_started = time.perf_counter()
    try:
        result = run_pipeline(
            company=request.company,
            project=request.project,
            service=request.service,
            raw_log=request.log,
            skip_ingest=True,
        )
    except EmbeddingUnavailableError as error:
        raise HTTPException(
            status_code=503,
            detail={"status": "AI_UNAVAILABLE", "message": str(error)},
        ) from error
    except (chromadb.errors.ChromaError, OSError) as error:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "RAG_UNAVAILABLE",
                "message": "The local troubleshooting knowledge base is unavailable.",
                "detail": str(error),
            },
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"status": "INVALID_LOG", "message": str(error)},
        ) from error

    analysis = result.get("analysis")
    if result.get("status") != "OK" or not isinstance(analysis, dict):
        status = result.get("status", "AI_UNAVAILABLE")
        if status == "AI_INVALID_RESPONSE":
            http_status = 502
            message = (analysis or {}).get("message", "Ollama returned an invalid analysis.")
        else:
            http_status = 503
            message = result.get("message") or (
                analysis.get("message") if isinstance(analysis, dict) else None
            ) or "The local analysis pipeline is unavailable."
        raise HTTPException(
            status_code=http_status,
            detail={"status": status, "message": message},
        )

    required_keys = {
        "status",
        "incident_type",
        "severity",
        "summary",
        "probable_root_cause",
        "evidence",
        "recommended_actions",
        "confidence",
    }
    if not required_keys.issubset(analysis):
        raise HTTPException(
            status_code=502,
            detail={
                "status": "AI_INVALID_RESPONSE",
                "message": "Ollama returned an invalid analysis payload.",
            },
        )

    normalized_log = result.get("normalized_log") or {}
    observed_message = normalized_log.get("message")
    observed_evidence = [observed_message] if isinstance(observed_message, str) and observed_message.strip() else []
    response = {
        "status": analysis["status"],
        "incident_type": analysis["incident_type"],
        "severity": analysis["severity"],
        "summary": analysis["summary"],
        "probable_root_cause": analysis["probable_root_cause"],
        "evidence": analysis["evidence"],
        "observed_evidence": observed_evidence,
        "recommended_actions": analysis["recommended_actions"],
        "confidence": analysis["confidence"],
        "checklist": _build_checklist(analysis),
        "normalized_log": normalized_log,
        "retrieved_count": len(result.get("retrieved_context", [])),
    }
    logger.info(
        "api_timing endpoint=analyze total_ms=%.1f retrieved_count=%d",
        (time.perf_counter() - request_started) * 1000,
        response["retrieved_count"],
    )
    return response


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    """Answer follow-up questions using the current log and deployment RAG context."""
    request_started = time.perf_counter()
    normalize_started = time.perf_counter()
    try:
        normalized = normalize_log(
            request.log,
            company=request.company,
            project=request.project,
            service=request.service,
        )
        normalize_ms = (time.perf_counter() - normalize_started) * 1000
        retrieval_started = time.perf_counter()
        context = retrieve_context(
            company=request.company,
            project=request.project,
            service=request.service,
            deployment_stage=normalized["deployment_stage"],
            new_log=normalized["message"],
        )
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        chat_started = time.perf_counter()
        result = chat_about_logs(
            normalized,
            context,
            request.question,
            history=[message.model_dump() for message in request.history],
            analysis=request.analysis,
        )
        chat_ms = (time.perf_counter() - chat_started) * 1000
    except EmbeddingUnavailableError as error:
        raise HTTPException(
            status_code=503,
            detail={"status": "AI_UNAVAILABLE", "message": str(error)},
        ) from error
    except (chromadb.errors.ChromaError, OSError) as error:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "RAG_UNAVAILABLE",
                "message": "The local troubleshooting knowledge base is unavailable.",
                "detail": str(error),
            },
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"status": "INVALID_LOG", "message": str(error)},
        ) from error

    if result.get("status") != "OK" or not result.get("answer"):
        status = result.get("status", "AI_UNAVAILABLE")
        http_status = 502 if status == "AI_INVALID_RESPONSE" else 503
        raise HTTPException(
            status_code=http_status,
            detail={
                "status": status,
                "message": result.get("message", "The local chat assistant is unavailable."),
            },
        )
    response = {"answer": result["answer"], "retrieved_count": len(context)}
    logger.info(
        "api_timing endpoint=chat normalize_ms=%.1f retrieval_ms=%.1f "
        "chat_ms=%.1f total_ms=%.1f retrieved_count=%d",
        normalize_ms,
        retrieval_ms,
        chat_ms,
        (time.perf_counter() - request_started) * 1000,
        len(context),
    )
    return response
