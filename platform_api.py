"""Local administration API for health, catalog search and yield prediction."""

import importlib
import json
import os
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROLE_KEYS = {
    os.environ.get("SEMENCES_RESEARCHER_KEY", "semences-researcher-demo"): "researcher",
    os.environ.get("SEMENCES_BREEDER_KEY", "semences-breeder-demo"): "breeder",
    os.environ.get("SEMENCES_OPERATOR_KEY", "semences-operator-demo"): "operator",
}
LEGACY_KEY = os.environ.get("SEMENCES_API_KEY")
if LEGACY_KEY:
    ROLE_KEYS[LEGACY_KEY] = "operator"
AUDIT_PATH = os.path.join(BASE_DIR, "reports", "api_audit.jsonl")
MODEL_PATH = os.path.join(BASE_DIR, "models", "yield_yd15qh.joblib")
CLASSIFIER_PATH = os.path.join(BASE_DIR, "models", "high_yield_classifier.joblib")
CATALOG_PATH = os.path.join(BASE_DIR, "catalog", "semences_catalog.db")


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def role(self):
        return ROLE_KEYS.get(self.headers.get("X-API-Key"))

    def audit(self, role, action, status):
        event = {
            "timestamp": datetime.now().isoformat(),
            "role": role or "anonymous",
            "action": action,
            "status": status,
            "client": self.client_address[0],
        }
        os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
        with open(AUDIT_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def require_role(self, allowed):
        role = self.role()
        if role not in allowed:
            self.audit(role, self.path, 403)
            json_response(self, 403, {
                "error": "Accès interdit",
                "required_roles": sorted(allowed),
            })
            return None
        return role

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            run_path = os.path.join(BASE_DIR, "reports", "pipeline_run.json")
            run = {}
            if os.path.exists(run_path):
                with open(run_path, encoding="utf-8") as handle:
                    run = json.load(handle)
            return json_response(self, 200, {
                "status": "UP", "pipeline": run,
                "model_ready": os.path.exists(MODEL_PATH),
                "catalog_ready": os.path.exists(CATALOG_PATH),
            })
        if parsed.path == "/api/search":
            role = self.require_role({"researcher", "breeder", "operator"})
            if not role:
                return
            query = parse_qs(parsed.query).get("q", [""])[0].strip()
            if not query:
                return json_response(self, 400, {"error": "Paramètre q obligatoire"})
            with sqlite3.connect(CATALOG_PATH) as con:
                con.row_factory = sqlite3.Row
                rows = con.execute(
                    "SELECT entity_type, entity_id, title, description "
                    "FROM search_index WHERE search_index MATCH ? LIMIT 25", (query,)
                ).fetchall()
            self.audit(role, "search", 200)
            return json_response(self, 200, {
                "query": query, "role": role, "results": [dict(r) for r in rows]
            })
        if parsed.path == "/api/catalog":
            role = self.require_role({"researcher", "breeder", "operator"})
            if not role:
                return
            with sqlite3.connect(CATALOG_PATH) as con:
                con.row_factory = sqlite3.Row
                rows = con.execute("SELECT * FROM datasets ORDER BY name").fetchall()
            self.audit(role, "catalog", 200)
            return json_response(self, 200, {
                "role": role, "datasets": [dict(r) for r in rows]
            })
        return json_response(self, 404, {"error": "Route inconnue"})

    def do_POST(self):
        role = self.require_role({"researcher", "breeder"})
        if not role:
            return
        if urlparse(self.path).path != "/api/predict":
            return json_response(self, 404, {"error": "Route inconnue"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            features = importlib.import_module("src.13_prediction").FEATURES
            row = pd.DataFrame([{key: payload.get(key) for key in features}])
            prediction = float(joblib.load(MODEL_PATH).predict(row)[0])
            classifier = joblib.load(CLASSIFIER_PATH)
            high_yield_probability = float(classifier.predict_proba(row)[0, 1])
            report_path = os.path.join(BASE_DIR, "reports", "prediction_report.json")
            with open(report_path, encoding="utf-8") as handle:
                report = json.load(handle)
            threshold = report["classification_evaluation"]["metrics"][
                "decision_probability_threshold"
            ]
            self.audit(role, "predict", 200)
            json_response(self, 200, {
                "role": role,
                "trait": "YD15QH",
                "prediction": round(prediction, 3),
                "high_yield_threshold_q_ha": 80,
                "high_yield_probability": round(high_yield_probability, 4),
                "high_yield": high_yield_probability >= threshold,
                "decision_probability_threshold": threshold,
                "model_validation": "GroupKFold + test temporel 2018",
            })
        except Exception as exc:
            self.audit(role, "predict", 400)
            json_response(self, 400, {"error": str(exc)})

    def log_message(self, fmt, *args):
        print(f"[API] {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    host = os.environ.get("SEMENCES_HOST", "127.0.0.1")
    port = int(os.environ.get("SEMENCES_PORT", "8080"))
    print(f"API Semences: http://{host}:{port}/api/health")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
