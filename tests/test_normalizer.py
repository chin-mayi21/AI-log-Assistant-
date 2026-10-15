import unittest

from app.log_normalizer import UNKNOWN, normalize_log


class NormalizeLogTests(unittest.TestCase):
    def assert_canonical(self, result, raw_log):
        self.assertEqual(
            set(result),
            {
                "project",
                "service",
                "deployment_stage",
                "timestamp",
                "level",
                "message",
                "raw_log",
                "metadata",
            },
        )
        self.assertEqual(result["raw_log"], raw_log)
        self.assertIsInstance(result["metadata"], dict)

    def test_plain_text_error_without_service_name(self):
        raw = "[ERROR] Migration failed: relation 'orders' does not exist"
        result = normalize_log(
            raw,
            company="Acme Corp",
            project="E-Commerce",
            service="Payment API",
            deployment_stage="Database Migration",
        )
        self.assert_canonical(result, raw)
        self.assertEqual(result["project"], "E-Commerce")
        self.assertEqual(result["service"], "Payment API")
        self.assertEqual(result["deployment_stage"], "Database Migration")
        self.assertEqual(result["level"], "ERROR")
        self.assertEqual(result["message"], raw.replace("[ERROR] ", ""))
        self.assertEqual(result["metadata"]["company"], "Acme Corp")

    def test_json_log(self):
        raw = (
            '{"timestamp":"2026-10-08T12:31:42","level":"ERROR",'
            '"service":"payment-api","deployment_stage":"Build",'
            '"message":"image build failed","request_id":"req-123"}'
        )
        result = normalize_log(raw, project="E-Commerce")
        self.assert_canonical(result, raw)
        self.assertEqual(result["timestamp"], "2026-10-08T12:31:42")
        self.assertEqual(result["service"], "Payment API")
        self.assertEqual(result["deployment_stage"], "Build")
        self.assertEqual(result["message"], "image build failed")
        self.assertEqual(result["metadata"], {"request_id": "req-123"})

    def test_kubernetes_style_log(self):
        raw = "2026-10-08T12:31:42Z ERROR payment-api-7f8d CrashLoopBackOff"
        result = normalize_log(raw, project="E-Commerce")
        self.assert_canonical(result, raw)
        self.assertEqual(result["timestamp"], "2026-10-08T12:31:42+00:00")
        self.assertEqual(result["level"], "ERROR")
        self.assertEqual(result["service"], "Payment API")
        self.assertEqual(result["message"], "CrashLoopBackOff")
        self.assertEqual(result["metadata"]["pod"], "payment-api-7f8d")

    def test_custom_deployment_pipe_log(self):
        raw = "DEPLOYMENT | PAYMENT_API | ERR | DB_MIGRATION_FAILED"
        result = normalize_log(raw, project="E-Commerce", deployment_stage="Database Migration")
        self.assert_canonical(result, raw)
        self.assertEqual(result["level"], "ERROR")
        self.assertEqual(result["service"], "Payment API")
        self.assertEqual(result["message"], "DB_MIGRATION_FAILED")
        self.assertEqual(result["metadata"]["event_code"], "DB_MIGRATION_FAILED")

    def test_missing_timestamp_and_stage(self):
        raw = "[WARN] Payment API: Retry attempt 2"
        result = normalize_log(raw)
        self.assert_canonical(result, raw)
        self.assertEqual(result["timestamp"], UNKNOWN)
        self.assertEqual(result["deployment_stage"], UNKNOWN)
        self.assertEqual(result["level"], "WARN")
        self.assertEqual(result["service"], "Payment API")
        self.assertEqual(result["message"], "Retry attempt 2")

    def test_missing_service_uses_supplied_context(self):
        raw = '{"timestamp":"2026-10-08T12:31:42","level":"INFO","message":"Build completed"}'
        result = normalize_log(
            raw,
            company="Acme Corp",
            project="Platform Infrastructure",
            service="Build Runner",
        )
        self.assert_canonical(result, raw)
        self.assertEqual(result["service"], "Build Runner")
        self.assertEqual(result["metadata"]["company"], "Acme Corp")

    def test_unknown_unstructured_log_is_not_rejected(self):
        raw = "job ended with exit marker 0xA17"
        result = normalize_log(raw)
        self.assert_canonical(result, raw)
        self.assertEqual(result["timestamp"], UNKNOWN)
        self.assertEqual(result["level"], UNKNOWN)
        self.assertEqual(result["service"], UNKNOWN)
        self.assertEqual(result["project"], UNKNOWN)
        self.assertEqual(result["message"], raw)

    def test_context_overrides_embedded_project_and_service(self):
        raw = '{"project":"wrong","service":"wrong-service","message":"probe failed"}'
        result = normalize_log(
            raw,
            project="E-Commerce",
            service="Payment API",
            deployment_stage="Kubernetes Health Check",
        )
        self.assertEqual(result["project"], "E-Commerce")
        self.assertEqual(result["service"], "Payment API")
        self.assertEqual(result["raw_log"], raw)


if __name__ == "__main__":
    unittest.main()
