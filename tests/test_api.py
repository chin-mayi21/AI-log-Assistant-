import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import app
from app.rag import EmbeddingUnavailableError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_does_not_require_ollama(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("ollama_model", response.json())

    @patch("app.api.run_pipeline")
    def test_analyze_returns_structured_result_and_recommendation_checklist(self, run_pipeline):
        analysis = {
            "status": "INCIDENT_DETECTED",
            "incident_type": "Kubernetes Deployment Failure",
            "severity": "HIGH",
            "summary": "The pod is restarting after a failed readiness probe.",
            "probable_root_cause": "The container may not be becoming ready within the configured probe window.",
            "evidence": ["The log reports CrashLoopBackOff and repeated readiness probe failures."],
            "recommended_actions": [
                "Inspect previous container logs and termination details.",
                "Verify the readiness endpoint and probe timing.",
            ],
            "confidence": 0.87,
        }
        run_pipeline.return_value = {
            "status": "OK",
            "normalized_log": {"raw_log": "CrashLoopBackOff", "message": "CrashLoopBackOff"},
            "retrieved_context": [{"id": "DEP-0001"}],
            "analysis": analysis,
        }
        response = self.client.post(
            "/api/analyze",
            json={
                "project": "E-Commerce",
                "service": "Payment API",
                "log": "payment-api pod repeatedly enters CrashLoopBackOff after readiness failures",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "INCIDENT_DETECTED")
        self.assertEqual(payload["recommended_actions"], analysis["recommended_actions"])
        self.assertEqual(payload["retrieved_count"], 1)
        self.assertEqual(payload["observed_evidence"], ["CrashLoopBackOff"])
        self.assertEqual(len(payload["checklist"]), 2)
        self.assertEqual(payload["checklist"][0]["id"], "step-1")
        self.assertEqual(payload["checklist"][0]["status"], "pending")
        self.assertIn("probable cause", payload["checklist"][0]["reason"])
        self.assertEqual(run_pipeline.call_args.kwargs["skip_ingest"], True)

    def test_analyze_rejects_blank_log(self):
        response = self.client.post(
            "/api/analyze",
            json={"project": "E-Commerce", "service": "Payment API", "log": "   "},
        )
        self.assertEqual(response.status_code, 422)

    @patch("app.api.run_pipeline")
    def test_analyze_reports_unavailable_pipeline_without_fabricated_result(self, run_pipeline):
        run_pipeline.return_value = {
            "status": "AI_UNAVAILABLE",
            "message": "Ollama is not reachable for local embeddings.",
            "normalized_log": {},
            "retrieved_context": [],
        }
        response = self.client.post(
            "/api/analyze",
            json={"project": "E-Commerce", "service": "Payment API", "log": "connection refused"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["status"], "AI_UNAVAILABLE")

    @patch("app.api.chat_about_logs")
    @patch("app.api.retrieve_context")
    def test_chat_returns_contextual_answer_and_preserves_history(
        self, retrieve_context, chat_about_logs
    ):
        retrieve_context.return_value = [{"id": "DEP-0002"}]
        chat_about_logs.return_value = {
            "status": "OK",
            "answer": "The readiness probe failure is directly observed. Check the endpoint and timing first.",
        }
        response = self.client.post(
            "/api/chat",
            json={
                "project": "E-Commerce",
                "service": "Payment API",
                "log": "payment-api readiness probe failed and pod restarted",
                "question": "What should I check first?",
                "history": [{"role": "user", "content": "What does this log say?"}],
                "analysis": {"probable_root_cause": "Probe configuration may not match startup time."},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], chat_about_logs.return_value["answer"])
        self.assertEqual(response.json()["retrieved_count"], 1)
        self.assertEqual(chat_about_logs.call_args.args[1], retrieve_context.return_value)
        self.assertEqual(chat_about_logs.call_args.args[2], "What should I check first?")
        self.assertEqual(chat_about_logs.call_args.kwargs["history"][0]["role"], "user")
        self.assertEqual(
            chat_about_logs.call_args.kwargs["analysis"]["probable_root_cause"],
            "Probe configuration may not match startup time.",
        )

    @patch("app.api.retrieve_context")
    def test_chat_reports_unavailable_rag(self, retrieve_context):
        retrieve_context.side_effect = EmbeddingUnavailableError("Embedding model unavailable.")
        response = self.client.post(
            "/api/chat",
            json={
                "project": "E-Commerce",
                "service": "Payment API",
                "log": "database connection refused",
                "question": "What can I investigate?",
            },
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["status"], "AI_UNAVAILABLE")

    def test_chat_rejects_blank_question(self):
        response = self.client.post(
            "/api/chat",
            json={
                "project": "E-Commerce",
                "service": "Payment API",
                "log": "database connection refused",
                "question": "   ",
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
