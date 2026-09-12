"""Regression checks for error propagation and maintained deliverables."""

import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class RegressionTests(unittest.TestCase):
    def test_module_without_run_is_an_error(self):
        main = importlib.import_module("main")
        with patch.dict(sys.modules, {"phase_without_run": types.ModuleType("phase_without_run")}):
            result = main.run_phase((99, "TEST", "phase_without_run", "invalid phase"))
        self.assertTrue(result["status"].startswith("ERREUR:"))

    def test_missing_input_stops_storage_and_queries(self):
        for name in ["08_hbase_store", "09_kafka_streaming", "12_drill_queries"]:
            with self.subTest(module=name):
                module = importlib.import_module(name)
                with tempfile.TemporaryDirectory() as directory:
                    with patch.object(module, "ENRICH_DIR", directory):
                        with self.assertRaises(FileNotFoundError):
                            module.run()

    def test_nifi_missing_input_is_not_success(self):
        nifi = importlib.import_module("07_nifi_flow")
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(nifi, "RAW_DIR", directory):
                with self.assertRaises(RuntimeError):
                    nifi.NiFiPipeline("essai").execute()

    def test_nifi_missing_column_is_rejected(self):
        import pandas as pd
        nifi = importlib.import_module("07_nifi_flow")
        validator = nifi.ValidateRecordProcessor("essai", ["YEAR"])
        result, flow = validator.run({"content": pd.DataFrame({"OTHER": [1]})})
        self.assertEqual(result, "failure")
        self.assertIn("YEAR", flow["error"])

    def test_spark_uses_isolated_process(self):
        main = importlib.import_module("main")
        with patch.object(main.subprocess, "run") as run:
            result = main.run_phase((8, "SPARK", "11_spark_analysis", "isolated Spark"))
        self.assertEqual(result["status"], "OK")
        self.assertEqual(run.call_args.args[0][0], sys.executable)
        self.assertTrue(run.call_args.kwargs["check"])

    def test_deliverable_validation_preserves_deck_and_dashboard(self):
        files = [ROOT / "deliverables/presentation_semences.pptx", ROOT / "reports/dashboard.html"]
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        report = importlib.import_module("17_deliverables").run()
        self.assertGreaterEqual(report["slides"], 20)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in files])

    def test_api_rejects_bad_search_and_payload_then_remains_available(self):
        api = importlib.import_module("platform_api")
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(api, "AUDIT_PATH", str(Path(directory) / "audit.jsonl")):
                server = api.ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                headers = {"X-API-Key": "semences-researcher-demo", "Content-Type": "application/json"}
                try:
                    cases = [("/api/search?q=%22", None), ("/api/predict", b"[]"), ("/api/predict", b"{}")]
                    for route, body in cases:
                        with self.subTest(route=route, body=body):
                            request = urllib.request.Request(base + route, data=body, headers=headers)
                            with self.assertRaises(urllib.error.HTTPError) as error:
                                urllib.request.urlopen(request, timeout=10)
                            self.assertEqual(error.exception.code, 400)
                    with urllib.request.urlopen(base + "/api/health", timeout=10) as response:
                        self.assertEqual(json.load(response)["status"], "UP")
                    payload = {
                        "YEAR": 2018, "REPLICATION_NUM": 1, "ENTRY_NUM": 10,
                        "SPECIES": "W", "SPECIES_SPECIFICITY": "", "REGION": "CENTRE",
                    }
                    request = urllib.request.Request(
                        base + "/api/predict", data=json.dumps(payload).encode(), headers=headers,
                    )
                    with urllib.request.urlopen(request, timeout=30) as response:
                        prediction = json.load(response)
                    self.assertEqual(prediction["trait"], "YD15QH")
                    self.assertGreaterEqual(prediction["high_yield_probability"], 0)
                    self.assertLessEqual(prediction["high_yield_probability"], 1)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
