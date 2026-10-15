import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from app.ollama_analyzer import analyze_log, chat_about_logs


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


class OllamaAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.normalized = {
            "project": "E-Commerce",
            "service": "Payment API",
            "deployment_stage": "Database Migration",
            "timestamp": "unknown",
            "level": "ERROR",
            "message": "relation orders does not exist",
            "metadata": {"company": "Demo Corp"},
            "raw_log": "[ERROR] relation orders does not exist",
        }
        self.example = {
            "id": "DEP-0001",
            "project": "E-Commerce",
            "service": "Payment API",
            "deployment_stage": "Database Migration",
            "incident_type": "Database Migration Failure",
            "severity": "HIGH",
            "raw_log": "relation orders does not exist",
            "normalized_message": "relation orders does not exist",
            "probable_root_cause": "The required migration was not executed.",
            "troubleshooting_steps": ["Check migration status", "Verify database target"],
            "expected_resolution": "Apply the approved missing migration.",
            "_retrieval": {"scope": "general", "context_match": "service", "distance": 0.2},
        }
        self.analysis = {
            "status": "INCIDENT_DETECTED",
            "incident_type": "Database Migration Failure",
            "severity": "HIGH",
            "summary": "Migration stopped because the target schema lacks a required relation.",
            "probable_root_cause": "A prerequisite migration may not have run against this database.",
            "evidence": ["The log says relation orders does not exist."],
            "recommended_actions": ["Check migration history.", "Verify the target database."],
            "confidence": 0.78,
        }

    @patch("app.ollama_analyzer.urllib.request.urlopen")
    def test_sends_context_and_returns_valid_analysis(self, urlopen):
        urlopen.return_value = FakeResponse(
            {
                "message": {"content": json.dumps(self.analysis)},
                "load_duration": 12_500_000,
                "prompt_eval_duration": 30_000_000,
                "eval_duration": 75_000_000,
                "prompt_eval_count": 120,
                "eval_count": 48,
            }
        )
        with self.assertLogs("app.ollama_analyzer", level="INFO") as captured:
            result = analyze_log(
                self.normalized,
                [self.example],
                recent_logs=[{"message": "Migration runner failed"}],
                company="Demo Corp",
                model="test-model",
            )
        self.assertEqual(result, self.analysis)
        timing_log = "\n".join(captured.output)
        self.assertIn("ollama_timing operation=analysis", timing_log)
        self.assertIn("load_ms=12.5", timing_log)
        self.assertIn("prompt_eval_ms=30.0", timing_log)
        self.assertIn("eval_ms=75.0", timing_log)
        self.assertIn("prompt_tokens=120", timing_log)
        self.assertIn("generated_tokens=48", timing_log)
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["format"]["type"], "object")
        self.assertFalse(body["format"]["additionalProperties"])
        self.assertIn("DevOps AI Troubleshooting Assistant", body["messages"][0]["content"])
        self.assertIn("Demo Corp", body["messages"][1]["content"])
        self.assertIn("DEP-0001", body["messages"][1]["content"])
        self.assertIn("Migration runner failed", body["messages"][1]["content"])
        self.assertIn("raw_log", body["messages"][1]["content"])

    @patch("app.ollama_analyzer.urllib.request.urlopen", side_effect=URLError("offline"))
    def test_unavailable_ollama_returns_status_without_fabricated_analysis(self, _urlopen):
        result = analyze_log(self.normalized, [self.example])
        self.assertEqual(result["status"], "AI_UNAVAILABLE")
        self.assertIn("not reachable", result["message"])
        self.assertNotIn("probable_root_cause", result)

    @patch("app.ollama_analyzer.urllib.request.urlopen")
    def test_invalid_model_json_is_rejected(self, urlopen):
        invalid = {**self.analysis, "confidence": 4.0}
        urlopen.return_value = FakeResponse({"message": {"content": json.dumps(invalid)}})
        result = analyze_log(self.normalized, [self.example])
        self.assertEqual(result["status"], "AI_INVALID_RESPONSE")
        self.assertIn("confidence", result["message"])

    def test_insufficient_context_confidence_is_bounded(self):
        from app.ollama_analyzer import validate_analysis

        insufficient = {
            "status": "INSUFFICIENT_CONTEXT",
            "incident_type": "Unknown/Unclassified Failure",
            "severity": "LOW",
            "summary": "The event does not identify a failing component.",
            "probable_root_cause": "Insufficient evidence to determine a cause.",
            "evidence": ["No deployment stage or error detail was supplied."],
            "recommended_actions": ["Collect the complete error output.", "Include the affected deployment stage."],
            "confidence": 0.2,
        }
        self.assertEqual(validate_analysis(insufficient), insufficient)
        insufficient["confidence"] = 0.8
        with self.assertRaises(ValueError):
            validate_analysis(insufficient)

    @patch("app.ollama_analyzer.urllib.request.urlopen")
    def test_chat_uses_log_history_and_generic_retrieval_patterns(self, urlopen):
        answer = "Check whether the host and port in the log are reachable from the workload."
        urlopen.return_value = FakeResponse({"message": {"content": answer}})
        with self.assertLogs("app.ollama_analyzer", level="INFO") as captured:
            result = chat_about_logs(
                self.normalized,
                [self.example],
                "What should I check first?",
                history=[{"role": "user", "content": "What failed?"}],
                analysis=self.analysis,
                model="test-model",
            )
        self.assertEqual(result, {"status": "OK", "answer": answer})
        self.assertIn("ollama_timing operation=chat", "\n".join(captured.output))
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertIn("DevOps AI Troubleshooting Assistant", body["messages"][0]["content"])
        sent_messages = json.dumps(body["messages"], ensure_ascii=False)
        self.assertIn("relation orders does not exist", sent_messages)
        self.assertIn("What failed?", sent_messages)
        self.assertIn("Database Migration Failure", sent_messages)
        self.assertIn("Check migration status", sent_messages)
        self.assertNotIn("expected_resolution", sent_messages)
        self.assertNotIn("The required migration was not executed.", sent_messages)


if __name__ == "__main__":
    unittest.main()
