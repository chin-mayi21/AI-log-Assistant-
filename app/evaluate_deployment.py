"""Run deployment test cases through local normalization, RAG, and Ollama."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ollama_analyzer import OLLAMA_MODEL
from app.rag import COLLECTION_NAME, EMBEDDING_MODEL, EmbeddingUnavailableError, ingest_dataset
from app.test_pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
TEST_CASES_PATH = ROOT / "data" / "test_cases.json"
RESULTS_PATH = ROOT / "data" / "evaluation_results.json"
REPORT_PATH = ROOT / "docs" / "evaluation_report.md"


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    query = case["query"]
    try:
        result = run_pipeline(
            company=query.get("company", "Evaluation Corp"),
            project=query["project"],
            service=query["service"],
            deployment_stage=query.get("deployment_stage"),
            raw_log=query["raw_log"],
            skip_ingest=True,
        )
    except (OSError, ValueError, RuntimeError) as error:
        result = {"status": "PIPELINE_ERROR", "message": str(error)}

    analysis = result.get("analysis", {})
    retrieved = result.get("retrieved_context", [])
    expected = case["expected"]
    actual_category = analysis.get("incident_type", "")
    incident_detected = analysis.get("status") == "INCIDENT_DETECTED"
    context_categories = [example.get("incident_type", "") for example in retrieved]
    in_context = expected["incident_type"] in context_categories
    same_project = all(example.get("project") == query["project"] for example in retrieved)
    cause_text = str(analysis.get("probable_root_cause", "")).lower()
    expected_cause_terms = [
        token.lower()
        for token in expected["probable_root_cause"].replace(",", " ").replace(".", " ").split()
        if len(token) > 4
    ]
    cause_overlap = (
        sum(term in cause_text for term in expected_cause_terms) / len(expected_cause_terms)
        if expected_cause_terms
        else 0.0
    )
    actions = analysis.get("recommended_actions", [])
    enough_evidence = bool(analysis.get("evidence"))
    unknown_case = expected["incident_type"] == "Unknown/Unclassified Failure"
    unknown_handled_cautiously = (
        analysis.get("status") == "INSUFFICIENT_CONTEXT"
        and float(analysis.get("confidence", 1)) <= 0.35
    )
    return {
        "id": case["id"],
        "project": query["project"],
        "service": query["service"],
        "deployment_stage": query.get("deployment_stage", "unknown"),
        "raw_log": query["raw_log"],
        "expected_category": expected["incident_type"],
        "expected_root_cause": expected["probable_root_cause"],
        "pipeline_status": result["status"],
        "retrieved_count": len(retrieved),
        "retrieved_categories": context_categories,
        "retrieved_expected_category": in_context,
        "retrieved_same_project": same_project,
        "analysis_status": analysis.get("status", result.get("status")),
        "actual_category": actual_category or None,
        "category_correct": actual_category == expected["incident_type"],
        "probable_root_cause": analysis.get("probable_root_cause"),
        "expected_cause_term_overlap": round(cause_overlap, 3),
        "evidence_present": enough_evidence,
        "recommended_action_count": len(actions) if isinstance(actions, list) else 0,
        "actions_actionable_shape": isinstance(actions, list) and 2 <= len(actions) <= 5,
        "severity": analysis.get("severity"),
        "confidence": analysis.get("confidence"),
        "unknown_case": unknown_case,
        "unknown_handled_cautiously": unknown_handled_cautiously if unknown_case else None,
        "summary": analysis.get("summary"),
        "recommended_actions": actions,
        "error": result.get("message") if result["status"] != "OK" else None,
    }


def run_evaluation() -> dict[str, Any]:
    cases = json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))
    ingest_dataset()
    results = [_evaluate_case(case) for case in cases]
    count = len(results) or 1
    analyzed = [item for item in results if item["actual_category"]]
    unknown_cases = [item for item in results if item["unknown_case"]]
    metrics = {
        "cases": len(results),
        "category_accuracy": round(sum(item["category_correct"] for item in results) / count, 3),
        "category_accuracy_on_analyzed": round(
            sum(item["category_correct"] for item in analyzed) / (len(analyzed) or 1), 3
        ),
        "expected_category_retrieval_rate": round(
            sum(item["retrieved_expected_category"] for item in results) / count, 3
        ),
        "same_project_context_rate": round(
            sum(item["retrieved_same_project"] for item in results) / count, 3
        ),
        "evidence_presence_rate": round(
            sum(item["evidence_present"] for item in results) / count, 3
        ),
        "actionable_shape_rate": round(
            sum(item["actions_actionable_shape"] for item in results) / count, 3
        ),
        "unknown_cautious_rate": round(
            sum(bool(item["unknown_handled_cautiously"]) for item in unknown_cases)
            / (len(unknown_cases) or 1),
            3,
        ),
        "ai_unavailable_count": sum(item["pipeline_status"] != "OK" for item in results),
        "average_retrieved_count": round(
            sum(item["retrieved_count"] for item in results) / count,
            2,
        ),
    }
    report = {
        "evaluated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ollama_model": OLLAMA_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "collection": COLLECTION_NAME,
        "retrieval_count": 4,
        "metrics": metrics,
        "results": results,
    }
    RESULTS_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Deployment troubleshooting evaluation",
        "",
        f"- Evaluated: {report['evaluated_at']}",
        f"- Cases: {metrics['cases']}",
        f"- Ollama chat model: `{OLLAMA_MODEL}`",
        f"- Ollama embedding model: `{EMBEDDING_MODEL}`",
        f"- ChromaDB collection: `{COLLECTION_NAME}`",
        "- Retrieval limit: 4 records per query",
        "",
        "## Results",
        "",
        "| Measure | Result |",
        "| --- | ---: |",
        f"| Exact incident category accuracy | {metrics['category_accuracy']:.1%} |",
        f"| Category accuracy among analyses with a category | {metrics['category_accuracy_on_analyzed']:.1%} |",
        f"| Expected category present in retrieved context | {metrics['expected_category_retrieval_rate']:.1%} |",
        f"| Retrieved examples stayed in the requested project | {metrics['same_project_context_rate']:.1%} |",
        f"| Analysis included evidence | {metrics['evidence_presence_rate']:.1%} |",
        f"| Analysis returned 2–5 recommended actions | {metrics['actionable_shape_rate']:.1%} |",
        f"| Unknown cases handled with low-confidence insufficient context | {metrics['unknown_cautious_rate']:.1%} |",
        f"| Non-OK/unavailable pipeline results | {metrics['ai_unavailable_count']} |",
        f"| Average retrieved examples | {metrics['average_retrieved_count']:.2f} |",
        "",
        "## Case details",
        "",
        "| ID | Expected | Predicted | Retrieved expected category | Cause overlap | Evidence/actions |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for item in results:
        lines.append(
            f"| {item['id']} | {item['expected_category']} | "
            f"{item['actual_category'] or item['analysis_status']} | "
            f"{'yes' if item['retrieved_expected_category'] else 'no'} | "
            f"{item['expected_cause_term_overlap']:.0%} | "
            f"{'yes' if item['evidence_present'] else 'no'}/"
            f"{item['recommended_action_count']} |"
        )
    lines.extend(
        [
            "",
            "The cause overlap is a lightweight lexical diagnostic, not a semantic judgement. "
            "Review full per-case inputs, retrieved examples, and model outputs in "
            "`data/evaluation_results.json`; category and safety decisions require human review.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    try:
        report = run_evaluation()
    except EmbeddingUnavailableError as error:
        print(f"Evaluation unavailable: {error}")
        return 1
    print(json.dumps({"metrics": report["metrics"], "results_path": str(RESULTS_PATH)}, indent=2))
    return 0 if report["metrics"]["ai_unavailable_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
