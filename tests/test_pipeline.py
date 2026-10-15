import unittest
from unittest.mock import patch

from app.rag import EmbeddingUnavailableError
from app.test_pipeline import run_pipeline


class PipelineTests(unittest.TestCase):
    @patch(
        "app.test_pipeline.ingest_dataset",
        side_effect=EmbeddingUnavailableError("local embeddings offline"),
    )
    def test_pipeline_returns_unavailable_without_fabricated_analysis(self, _ingest):
        result = run_pipeline(
            company="Demo Corp",
            project="E-Commerce",
            service="Payment API",
            deployment_stage="Database Migration",
            raw_log="DB_MIGRATION_FAILED",
        )
        self.assertEqual(result["status"], "AI_UNAVAILABLE")
        self.assertIn("normalized_log", result)
        self.assertNotIn("analysis", result)
        self.assertEqual(result["normalized_log"]["metadata"]["company"], "Demo Corp")

    @patch("app.test_pipeline.analyze_log")
    @patch("app.test_pipeline.retrieve_context")
    @patch("app.test_pipeline.ingest_dataset")
    def test_pipeline_passes_normalized_context_and_retrieved_examples(
        self, ingest, retrieve, analyze
    ):
        examples = [{"id": "DEP-0001", "incident_type": "Database Migration Failure"}]
        expected_analysis = {
            "status": "INCIDENT_DETECTED",
            "incident_type": "Database Migration Failure",
            "severity": "HIGH",
            "summary": "A migration failed.",
            "probable_root_cause": "A prerequisite schema is missing.",
            "evidence": ["The raw output names the missing relation."],
            "recommended_actions": ["Check migration history.", "Verify database target."],
            "confidence": 0.8,
        }
        retrieve.return_value = examples
        analyze.return_value = expected_analysis
        with self.assertLogs("app.test_pipeline", level="INFO") as captured:
            result = run_pipeline(
                company="Demo Corp",
                project="E-Commerce",
                service="Payment API",
                deployment_stage="Database Migration",
                raw_log="[ERROR] Migration failed: relation 'orders' does not exist",
            )
        self.assertEqual(result["status"], "OK")
        timing_log = "\n".join(captured.output)
        self.assertIn("pipeline_timing status=OK", timing_log)
        self.assertIn("normalize_ms=", timing_log)
        self.assertIn("retrieval_ms=", timing_log)
        self.assertIn("analysis_ms=", timing_log)
        self.assertIn("total_ms=", timing_log)
        self.assertEqual(result["analysis"], expected_analysis)
        self.assertEqual(result["retrieved_context"], examples)
        retrieve.assert_called_once()
        self.assertEqual(retrieve.call_args.kwargs["deployment_stage"], "Database Migration")
        self.assertEqual(analyze.call_args.args[1], examples)
        self.assertEqual(analyze.call_args.kwargs["company"], "Demo Corp")
        ingest.assert_called_once()


if __name__ == "__main__":
    unittest.main()
