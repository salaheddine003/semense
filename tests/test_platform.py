import importlib
import json
import os
import sqlite3
import unittest
import zipfile
import sys
import glob
import tempfile
import threading
import types
import urllib.error
import urllib.request

from pptx import Presentation

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


class PlatformTests(unittest.TestCase):
    def test_source_files_exist(self):
        expected = [
            "ESSAI.csv", "RESULTAT_ESSAIS.csv", "LK_CRISP_MATERIAL_20190108.csv",
            "PARCELLE_SPECIFICATION_20190108.csv", "REF_ESPECES_20190108.csv",
            "TRIAL_QUALIFICATION_20190108.csv",
        ]
        for name in expected:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "CSV", name)), name)

    def test_fact_table_contract(self):
        fact = pd.read_parquet(os.path.join(ROOT, "data", "enriched", "fact_table.parquet"))
        required = {
            "LK_EXPERIMENT_EXPERIMENT_ID", "YEAR", "SPECIES", "TRAIT",
            "RESULT_NUM", "ESPECE_FR",
        }
        self.assertTrue(required.issubset(fact.columns))
        self.assertGreater(len(fact), 100000)
        self.assertGreater(fact["RESULT_NUM"].notna().mean(), 0.99)

    def test_species_mapping_is_traceable(self):
        etl = importlib.import_module("02_etl")
        mapped = etl.map_species(pd.Series(["S", "A", "D", "F"])).tolist()
        self.assertEqual(mapped, ["Soja", "INCONNU_CODE_A", "INCONNU_CODE_D", "INCONNU_CODE_F"])
        fact = pd.read_parquet(os.path.join(ROOT, "data", "enriched", "fact_table.parquet"))
        self.assertTrue((fact.loc[fact["SPECIES"] == "S", "ESPECE_FR"] == "Soja").all())
        self.assertTrue(os.path.exists(os.path.join(ROOT, "reports", "species_mapping.json")))

    def test_prediction_artifacts(self):
        path = os.path.join(ROOT, "reports", "prediction_report.json")
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual(report["status"], "OK")
        self.assertIn("mae", report["metrics"])
        self.assertTrue(os.path.exists(os.path.join(ROOT, report["model_path"])))
        classification = report["classification_evaluation"]
        self.assertEqual(classification["train_test_group_overlap"], 0)
        self.assertIn("GroupKFold", classification["protocol"])
        self.assertNotIn("YD16QH", classification["features"])
        self.assertNotIn("%MOIS", classification["features"])
        self.assertNotIn("SL_TRIAL", classification["features"])
        self.assertGreater(classification["metrics"]["f1_score"], 0)
        self.assertTrue(os.path.exists(
            os.path.join(ROOT, "models", "high_yield_classifier.joblib")
        ))
        predictions = pd.read_csv(
            os.path.join(ROOT, "data", "exposed", "yield_predictions.csv"),
            sep=";",
        )
        self.assertEqual(len(predictions), report["test_rows"])
        self.assertEqual(int(predictions.duplicated().sum()), 0)
        self.assertIn("LK_SL_TRIAL_L2_DATA_ID", predictions.columns)

    def test_catalog_search(self):
        path = os.path.join(ROOT, "catalog", "semences_catalog.db")
        self.assertTrue(os.path.exists(path))
        with sqlite3.connect(path) as con:
            self.assertGreater(con.execute("SELECT COUNT(*) FROM datasets").fetchone()[0], 0)
            self.assertGreater(con.execute(
                "SELECT COUNT(*) FROM search_index WHERE search_index MATCH 'Blé'"
            ).fetchone()[0], 0)

    def test_drill_all_queries_ok(self):
        with open(os.path.join(ROOT, "reports", "drill_report.json"), encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertTrue(all(q["status"] == "OK" for q in report["queries"]))

    def test_hive_all_queries_ok_and_bad_query_raises(self):
        module = importlib.import_module("10_hive_queries")
        fact = os.path.join(ROOT, "data", "enriched", "fact_table.parquet").replace("\\", "/")
        connection = module.HiveConnection("test", ROOT)
        with self.assertRaises(RuntimeError):
            connection.execute("BAD_QUERY_TEST", "SELECT * FROM table_that_does_not_exist", fact)
        self.assertTrue(connection._log[-1]["status"].startswith("ERROR:"))
        connection.close()
        with open(os.path.join(ROOT, "reports", "hive_report.json"), encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertTrue(all(q["status"] == "OK" for q in report["execution"]))

    def test_hbase_counts_and_unique_keys(self):
        report_path = os.path.join(ROOT, "reports", "hbase_summary.json")
        with open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
        stats = report["tables"]["results"]["load"]
        self.assertEqual(stats["received"], stats["inserted"] + stats["rejected"])
        self.assertEqual(stats["collisions"], 0)
        with sqlite3.connect(os.path.join(ROOT, "hbase", "semences_hbase.db")) as con:
            actual, unique = con.execute(
                "SELECT COUNT(*), COUNT(DISTINCT row_key) FROM results"
            ).fetchone()
        self.assertEqual(actual, report["tables"]["results"]["rows"])
        self.assertEqual(actual, unique)

    def test_local_engine_reports(self):
        for filename in ["spark_report.json", "r_report.json", "kafka_report.json"]:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "reports", filename)))
        with open(os.path.join(ROOT, "reports", "spark_report.json"), encoding="utf-8") as handle:
            spark = json.load(handle)
        self.assertIn(spark["engine"], {"PySpark", "pandas-fallback"})
        self.assertTrue(all(step["engine"].startswith(spark["engine"].split("-")[0]) for step in spark["steps"]))
        with open(os.path.join(ROOT, "reports", "r_report.json"), encoding="utf-8") as handle:
            r_report = json.load(handle)
        self.assertEqual(r_report["status"], "OK")
        self.assertEqual(r_report["return_code"], 0)
        for output in r_report["outputs"]:
            self.assertGreater(os.path.getsize(os.path.join(ROOT, output)), 100)

    def test_kafka_topics_and_consumers(self):
        with open(os.path.join(ROOT, "reports", "kafka_report.json"), encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual(report["summary"]["total_produced"], 535)
        self.assertEqual(report["summary"]["total_consumed"], 535)
        self.assertTrue(all(topic["queued"] == 0 for topic in report["topics"]))
        self.assertEqual(len(report["topics"]), 4)
        for filename in ["consumed_results.json", "quality_alerts.json", "geo_stream.csv"]:
            self.assertGreater(os.path.getsize(os.path.join(ROOT, "kafka", filename)), 0)

    def test_api_http_rbac_and_audit(self):
        api = importlib.import_module("platform_api")
        with tempfile.TemporaryDirectory() as directory:
            previous = api.AUDIT_PATH
            api.AUDIT_PATH = os.path.join(directory, "audit.jsonl")
            server = api.ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                health = json.load(urllib.request.urlopen(base + "/api/health"))
                self.assertEqual(health["status"], "UP")
                request = urllib.request.Request(
                    base + "/api/search?q=Soja",
                    headers={"X-API-Key": "semences-researcher-demo"},
                )
                self.assertGreater(len(json.load(urllib.request.urlopen(request))["results"]), 0)
                denied = urllib.request.Request(
                    base + "/api/predict", data=b"{}", method="POST",
                    headers={"X-API-Key": "semences-operator-demo", "Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as context:
                    urllib.request.urlopen(denied)
                self.assertEqual(context.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()
                api.AUDIT_PATH = previous
            with open(os.path.join(directory, "audit.jsonl"), encoding="utf-8") as handle:
                events = [json.loads(line) for line in handle]
            self.assertEqual([event["status"] for event in events], [200, 403])

    def test_map_images_and_powerpoint_content(self):
        with open(os.path.join(ROOT, "reports", "carte_essais.html"), encoding="utf-8") as handle:
            map_html = handle.read()
        self.assertEqual(map_html.count('"id":'), 424)
        self.assertIn("basemaps.cartocdn.com", map_html)
        self.assertIn('id="category"', map_html)
        self.assertIn('id="franceOnly"', map_html)
        self.assertIn("points affichés sur", map_html)
        with open(os.path.join(ROOT, "reports", "dashboard.html"), encoding="utf-8") as handle:
            dashboard = handle.read()
        self.assertIn("nécessite Internet", dashboard)
        images = glob.glob(os.path.join(ROOT, "reports", "images", "*.png"))
        images += glob.glob(os.path.join(ROOT, "reports", "r", "*.png"))
        self.assertEqual(len(images), 9)
        self.assertTrue(all(os.path.getsize(path) > 5000 for path in images))
        presentation = Presentation(os.path.join(ROOT, "deliverables", "presentation_semences.pptx"))
        self.assertGreaterEqual(len(presentation.slides), 20)

    def test_pipeline_error_is_not_ok(self):
        orchestrator = importlib.import_module("main")
        module_name = "audit_failing_phase"
        module = types.ModuleType(module_name)
        module.run = lambda: (_ for _ in ()).throw(RuntimeError("audit failure"))
        sys.modules[module_name] = module
        try:
            result = orchestrator.run_phase((99, "AUDIT", module_name, "failure injection"))
        finally:
            del sys.modules[module_name]
        self.assertTrue(result["status"].startswith("ERREUR:"))

    def test_pipeline_full_run_evidence(self):
        with open(os.path.join(ROOT, "reports", "pipeline_run.json"), encoding="utf-8") as handle:
            run = json.load(handle)
        self.assertEqual(run["status"], "OK")
        self.assertEqual(len(run["phases"]), 17)
        self.assertTrue(all(p["status"] == "OK" and not p.get("resumed") for p in run["phases"]))

    def test_dashboard_is_offline_and_filterable(self):
        with open(os.path.join(ROOT, "reports", "dashboard.html"), encoding="utf-8") as handle:
            html = handle.read()
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)
        self.assertIn('id="tableFilter"', html)
        self.assertIn("Adaptation fonctionnelle locale", html)

    def test_quality_and_quarantine(self):
        path = os.path.join(ROOT, "reports", "data_quality_report.json")
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual(report["status"], "OK")
        self.assertTrue(report["policy"]["source_immutability"])
        self.assertGreater(report["totals"]["quarantined_rows"], 0)
        self.assertTrue(os.path.exists(os.path.join(
            ROOT, "data", "quarantine", "resultats_quarantine.parquet"
        )))

    def test_generated_deliverables(self):
        image = os.path.join(ROOT, "deliverables", "architecture_big_data.png")
        presentation = os.path.join(
            ROOT, "deliverables", "presentation_semences.pptx"
        )
        self.assertGreater(os.path.getsize(image), 10000)
        self.assertTrue(zipfile.is_zipfile(presentation))

    def test_rbac_roles(self):
        api = importlib.import_module("platform_api")
        self.assertIn("researcher", api.ROLE_KEYS.values())
        self.assertIn("breeder", api.ROLE_KEYS.values())
        self.assertIn("operator", api.ROLE_KEYS.values())


if __name__ == "__main__":
    unittest.main()
