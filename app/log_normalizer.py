"""Normalize common application log formats into a stable canonical record."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

UNKNOWN = "unknown"

_LEVEL_ALIASES = {
    "TRACE": "DEBUG",
    "DBG": "DEBUG",
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "INFORMATION": "INFO",
    "NOTICE": "INFO",
    "WARN": "WARN",
    "WARNING": "WARN",
    "ERR": "ERROR",
    "ERROR": "ERROR",
    "CRIT": "CRITICAL",
    "FATAL": "CRITICAL",
    "CRITICAL": "CRITICAL",
}
_LEVEL_PATTERN = re.compile(
    r"(?<![A-Z])(?:TRACE|DBG|DEBUG|INFO|INFORMATION|NOTICE|WARN|WARNING|ERR|ERROR|CRIT|FATAL|CRITICAL)(?![A-Z])",
    re.IGNORECASE,
)
_TIMESTAMP_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_PLAIN_PATTERN = re.compile(
    r"^\s*\[(?P<level>[A-Z]+)\]\s+"
    r"(?:(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+)?"
    r"(?P<service>[^:|]+):\s*(?P<message>.*)$",
    re.IGNORECASE,
)
_KUBERNETES_PATTERN = re.compile(
    r"^\s*(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+"
    r"(?P<level>[A-Z]+)\s+(?P<pod>[A-Za-z0-9][A-Za-z0-9_.-]*)\s+(?P<message>.*)$",
    re.IGNORECASE,
)


def _text(value: Any) -> str:
    if value is None or value == "":
        return UNKNOWN
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _normalize_level(value: Any) -> str:
    if value is None or value == "":
        return UNKNOWN
    level = str(value).strip().upper()
    return _LEVEL_ALIASES.get(level, level)


def _parse_timestamp(value: Any) -> str:
    if value is None or value == "":
        return UNKNOWN
    raw = str(value).strip()
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return raw
    return parsed.isoformat(timespec="seconds")


def _clean_service(value: Any) -> str:
    if value is None or not str(value).strip():
        return UNKNOWN
    service = str(value).strip()
    service = re.sub(r"-[a-f0-9]{4,10}(?:-[a-z0-9]{4,6})?$", "", service, flags=re.IGNORECASE)
    service = re.sub(r"[-_]+", " ", service).strip()
    service = re.sub(
        r"\bSVC\b",
        "Service",
        service,
        flags=re.IGNORECASE,
    )
    acronyms = {"api": "API", "db": "DB", "hr": "HR", "http": "HTTP", "sql": "SQL"}
    return " ".join(acronyms.get(word.lower(), word.capitalize()) for word in service.split())


def _context_value(context_value: str | None, extracted_value: Any) -> str:
    if context_value is not None and str(context_value).strip():
        return str(context_value).strip()
    return _text(extracted_value)


def normalize_log(
    raw_log: str | Mapping[str, Any],
    *,
    company: str | None = None,
    project: str | None = None,
    service: str | None = None,
    deployment_stage: str | None = None,
) -> dict[str, Any]:
    """Return a canonical record; supplied context takes precedence over parsed fields.

    Unknown or missing raw fields are retained as ``"unknown"``. The original input is
    always serialized into ``raw_log`` so downstream consumers can inspect it.
    """
    raw_text = raw_log if isinstance(raw_log, str) else json.dumps(raw_log, ensure_ascii=False)
    timestamp: Any = None
    level: Any = None
    parsed_service: Any = None
    parsed_stage: Any = None
    message: Any = None
    metadata: dict[str, Any] = {}

    payload: Mapping[str, Any] | None = None
    if isinstance(raw_log, Mapping):
        payload = raw_log
    elif isinstance(raw_log, str):
        try:
            parsed = json.loads(raw_log)
            if isinstance(parsed, Mapping):
                payload = parsed
        except json.JSONDecodeError:
            pass

    if payload is not None:
        timestamp = payload.get("timestamp", payload.get("time", payload.get("@timestamp")))
        level = payload.get("level", payload.get("severity", payload.get("log_level")))
        parsed_service = payload.get(
            "service",
            payload.get("service_name", payload.get("app", payload.get("container"))),
        )
        parsed_stage = payload.get("deployment_stage", payload.get("stage"))
        message = payload.get("message", payload.get("msg", payload.get("log")))
        known = {
            "timestamp", "time", "@timestamp", "level", "severity", "log_level",
            "service", "service_name", "app", "container", "message", "msg", "log",
            "project", "company", "deployment_stage", "stage",
        }
        metadata = {key: value for key, value in payload.items() if key not in known}
        embedded_project = payload.get("project")
        embedded_company = payload.get("company")
        if project is None and embedded_project:
            project = str(embedded_project)
        if company is None and embedded_company:
            company = str(embedded_company)
    else:
        plain_match = _PLAIN_PATTERN.match(raw_text)
        kube_match = _KUBERNETES_PATTERN.match(raw_text)
        if plain_match:
            timestamp = plain_match.group("timestamp")
            level = plain_match.group("level")
            content_after_level = re.sub(r"^\s*\[[A-Z]+\]\s*", "", raw_text, flags=re.IGNORECASE)
            if timestamp is None and service is not None:
                message = content_after_level
            elif timestamp is None and not re.search(
                r"\b(?:API|SERVICE|WORKER|POD|CONTAINER|DATABASE|DB)\b",
                plain_match.group("service"),
                re.IGNORECASE,
            ):
                message = content_after_level
            else:
                parsed_service = plain_match.group("service").strip()
                message = plain_match.group("message").strip()
        elif kube_match:
            timestamp = kube_match.group("timestamp")
            level = kube_match.group("level")
            parsed_service = kube_match.group("pod")
            message = kube_match.group("message").strip()
            metadata["pod"] = kube_match.group("pod")
        elif "|" in raw_text:
            parts = [part.strip() for part in raw_text.split("|")]
            if len(parts) == 4 and parts[2].upper() in _LEVEL_ALIASES:
                _, parsed_service, raw_level, event_code = parts
                level = raw_level
                metadata["event_code"] = event_code
                message = event_code
                parsed_stage = "Deployment"
                metadata["source"] = "deployment"
            elif len(parts) == 4:
                parsed_service, raw_level, event_code, message = parts
                level = raw_level
                metadata["event_code"] = event_code
                message = f"{event_code}: {message}"
            else:
                message = raw_text.strip()
        else:
            message = raw_text.strip()

        if timestamp is None:
            timestamp_match = _TIMESTAMP_PATTERN.search(raw_text)
            if timestamp_match:
                timestamp = timestamp_match.group()
        if level is None:
            level_match = _LEVEL_PATTERN.search(raw_text)
            if level_match:
                level = level_match.group()

    embedded_service = _clean_service(parsed_service)
    service_aliases = {
        "Payment Api": "Payment API",
        "Auth Service": "Authentication Service",
        "Payment Svc": "Payment Service",
        "Payment Api Service": "Payment API",
    }
    if service is None and embedded_service != UNKNOWN:
        embedded_service = service_aliases.get(embedded_service, embedded_service)
    resolved_service = _context_value(service, embedded_service)
    resolved_level = _normalize_level(level)
    resolved_message = _text(message)
    if resolved_message == UNKNOWN and raw_text.strip():
        resolved_message = raw_text.strip()
    resolved_stage = deployment_stage or _text(parsed_stage)
    if resolved_stage == UNKNOWN:
        resolved_stage = "unknown"
    if company is not None and str(company).strip():
        metadata.setdefault("company", str(company).strip())
    return {
        "project": _context_value(project, UNKNOWN),
        "service": resolved_service,
        "deployment_stage": resolved_stage,
        "timestamp": _parse_timestamp(timestamp),
        "level": resolved_level,
        "message": resolved_message,
        "raw_log": raw_text,
        "metadata": metadata,
    }
