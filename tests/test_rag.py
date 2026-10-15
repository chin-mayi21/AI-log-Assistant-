import hashlib
import json
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

import chromadb

from app.rag import COLLECTION_NAME, ingest_dataset, retrieve_context

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "deployment_logs.json"

SYNONYMS = {
    "restarting": "restart",
    "restarts": "restart",
    "failed": "failure",
    "failing": "failure",
    "failure": "failure",
    "probe": "healthcheck",
    "readiness": "healthcheck",
    "liveness": "healthcheck",
    "pod": "container",
    "pods": "container",
    "pull": "image",
    "pulled": "image",
    "fetch": "image",
    "refused": "connectivity",
    "refused,": "connectivity",
    "connection": "connectivity",
}


def deterministic_test_embeddings(texts):
    vectors = []
    for text in texts:
        vector = [0.0] * 512
        tokens = text.lower().replace("-", " ").replace("_", " ").split()
        for token in tokens:
            normalized = SYNONYMS.get(token.strip(".,:;()[]'\""), token.strip(".,:;()[]'\""))
            position = int.from_bytes(hashlib.sha256(normalized.encode()).digest()[:2], "big") % len(vector)
            vector[position] += 1
        vectors.append(vector)
    return vectors


class RagTests(unittest.TestCase):
    def setUp(self):
        self.client = chromadb.EphemeralClient()
        self.embedding_provider = deterministic_test_embeddings
        self.collection_name = COLLECTION_NAME + "_test"
        self.assertEqual(
            ingest_dataset(
                DATASET,
                client=self.client,
                embedding_provider=self.embedding_provider,
                collection_name=self.collection_name,
            ),
            400,
        )

    def tearDown(self):
        del self.client

    def retrieve(self, project, service, log, stage="Deployment Verification", company="Demo Corp"):
        return retrieve_context(
            company,
            project,
            service,
            log,
            deployment_stage=stage,
            client=self.client,
            embedding_provider=self.embedding_provider,
            collection_name=self.collection_name,
        )

    def test_retrieves_payment_migration_context(self):
        with self.assertLogs("app.rag", level="INFO") as captured:
            results = self.retrieve(
                "E-Commerce",
                "Payment API",
                "Migration failed: relation orders does not exist",
                "Database Migration",
            )
        timing_log = "\n".join(captured.output)
        self.assertIn("rag_timing embedding_ms=", timing_log)
        self.assertIn("query_ms=", timing_log)
        self.assertIn("returned_count=4", timing_log)
        self.assertTrue(results)
        self.assertEqual(len(results), 4)
        self.assertIn("Database Migration Failure", {record["incident_type"] for record in results})
        self.assertTrue(all(record["project"] == "E-Commerce" for record in results))

    def test_retrieves_kubernetes_health_and_startup_not_payment_transactions(self):
        results = self.retrieve(
            "E-Commerce",
            "Payment API",
            "Pod payment-api keeps restarting and readiness probe failed",
            "Kubernetes Deployment",
        )
        categories = {record["incident_type"] for record in results}
        self.assertTrue(
            categories
            & {
                "Kubernetes Deployment Failure",
                "Health Check Failure",
                "Service Startup Failure",
                "Docker/Container Failure",
            }
        )
        self.assertNotIn("Payment Failure", categories)
        self.assertTrue(all(record["project"] == "E-Commerce" for record in results))

    def test_retrieves_dependency_conflict_examples(self):
        results = self.retrieve(
            "Platform Infrastructure",
            "Build Runner",
            "CI build fails because resolved package versions are incompatible",
            "Dependency Installation",
        )
        self.assertIn(
            "Version/Dependency Conflict",
            {record["incident_type"] for record in results},
        )

    def test_connection_refused_retrieves_network_troubleshooting(self):
        results = self.retrieve(
            "E-Commerce",
            "Payment API",
            "payment-api startup error: connection refused by postgres.internal on port 5432",
            "Service Connectivity",
        )
        self.assertIn(
            "Network/Connectivity Failure",
            {record["incident_type"] for record in results},
        )

    def test_company_scoped_records_never_leak_between_companies(self):
        records = json.loads(DATASET.read_text(encoding="utf-8"))
        base = next(record for record in records if record["incident_type"] == "Build Failure")
        company_record = {**base, "id": "COMPANY-ONLY", "metadata": {"company": "Company A"}}
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as stream:
            json.dump([company_record], stream)
            path = Path(stream.name)
        try:
            ingest_dataset(
                path,
                client=self.client,
                embedding_provider=self.embedding_provider,
                collection_name=self.collection_name,
            )
        finally:
            path.unlink()

        other_company = self.retrieve(
            base["project"],
            base["service"],
            base["raw_log"],
            company="Company B",
        )
        self.assertNotIn("COMPANY-ONLY", {record["id"] for record in other_company})
        owner = self.retrieve(
            base["project"],
            base["service"],
            base["raw_log"],
            company="Company A",
        )
        self.assertIn("COMPANY-ONLY", {record["id"] for record in owner})
        self.assertIn("company", {record["_retrieval"]["scope"] for record in owner})

    def test_returns_small_context_and_keeps_metadata(self):
        results = self.retrieve(
            "E-Commerce",
            "Payment API",
            "Payment API container cannot bind its port",
            "Container Startup",
            company="Demo Corp",
        )
        self.assertLessEqual(len(results), 4)
        self.assertTrue(results)
        for record in results:
            self.assertTrue(record["probable_root_cause"])
            self.assertTrue(record["troubleshooting_steps"])
            self.assertIn("deployment_stage", record["_retrieval"])
            self.assertIn("distance", record["_retrieval"])

    def test_empty_collection_returns_no_examples(self):
        results = retrieve_context(
            "Demo Corp",
            "Unknown Project",
            "Unknown Service",
            "an unstructured event",
            client=self.client,
            embedding_provider=self.embedding_provider,
            collection_name="empty_deployment_test",
        )
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
