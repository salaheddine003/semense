"""
Apache Kafka — Bus de données / Streaming (simulation Python)
=============================================================
Kafka est un bus de messages distribué orienté log.
Topics simulés :
  - experimental-results  : résultats culturaux de démonstration
  - material-updates      : mises à jour matériel génétique
  - quality-alerts        : alertes qualité données
  - geo-stream            : données géolocalisées (météo/drones - futur)

Architecture :
  Producer → [Topic Kafka] → Consumer → Sink (HDFS / HBase / Reporting)
"""

import os
import json
import threading
import queue
import time
import random
import pandas as pd
from datetime import datetime

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENRICH_DIR = os.path.join(BASE_DIR, "data", "enriched")
KAFKA_DIR  = os.path.join(BASE_DIR, "kafka")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

os.makedirs(KAFKA_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Modèle Kafka
# ─────────────────────────────────────────────────────────────

class KafkaTopic:
    """Simule un topic Kafka avec partitions."""

    def __init__(self, name: str, partitions: int = 3, retention_ms: int = 86400000):
        self.name         = name
        self.partitions   = [queue.Queue() for _ in range(partitions)]
        self.retention_ms = retention_ms
        self.offsets      = [0] * partitions
        self.nb_partitions = partitions
        self._lock        = threading.Lock()
        self.total_produced = 0
        self.total_consumed = 0

    def produce(self, key: str, value: dict, headers: dict = None) -> int:
        """Envoie un message. Retourne le numéro de partition."""
        partition = abs(hash(key)) % self.nb_partitions
        offset    = self.offsets[partition]
        msg = {
            "topic":     self.name,
            "partition": partition,
            "offset":    offset,
            "key":       key,
            "value":     value,
            "headers":   headers or {},
            "timestamp": datetime.now().isoformat(),
        }
        with self._lock:
            self.partitions[partition].put(msg)
            self.offsets[partition] += 1
            self.total_produced += 1
        return partition

    def consume(self, group_id: str, partition: int = None, timeout: float = 0.1) -> dict | None:
        """Lit un message depuis une partition."""
        parts = [self.partitions[partition]] if partition is not None else self.partitions
        for p in parts:
            try:
                msg = p.get(timeout=timeout)
                with self._lock:
                    self.total_consumed += 1
                return msg
            except queue.Empty:
                continue
        return None

    def info(self) -> dict:
        queued = sum(p.qsize() for p in self.partitions)
        return {
            "topic":      self.name,
            "partitions": self.nb_partitions,
            "produced":   self.total_produced,
            "consumed":   self.total_consumed,
            "queued":     queued,
            "offsets":    self.offsets[:],
        }


class KafkaBroker:
    """Simule un broker Kafka."""
    def __init__(self, broker_id: int = 0, host: str = "localhost:9092"):
        self.broker_id = broker_id
        self.host      = host
        self.topics: dict[str, KafkaTopic] = {}

    def create_topic(self, name: str, partitions: int = 3) -> KafkaTopic:
        self.topics[name] = KafkaTopic(name, partitions)
        print(f"  Created topic '{name}' with {partitions} partitions.")
        return self.topics[name]

    def get_topic(self, name: str) -> KafkaTopic:
        return self.topics[name]

    def list_topics(self) -> list:
        return list(self.topics.keys())


# ─────────────────────────────────────────────────────────────
# Producers
# ─────────────────────────────────────────────────────────────

def producer_results(broker: KafkaBroker, fact: pd.DataFrame, n: int, results_log: list):
    """Produit N messages de nouveaux résultats culturaux."""
    topic = broker.get_topic("experimental-results")
    sample = fact[fact["RESULT_NUM"].notna()].sample(min(n, len(fact)))
    for _, row in sample.iterrows():
        key = f"{row['LK_EXPERIMENT_EXPERIMENT_ID']}_{row.get('TRAIT','?')}"
        value = {
            "experiment_id": str(row["LK_EXPERIMENT_EXPERIMENT_ID"]),
            "sl_trial":      str(row.get("SL_TRIAL", "")),
            "trait":         str(row.get("TRAIT", "")),
            "result":        float(row["RESULT_NUM"]),
            "year":          int(row["YEAR"]) if pd.notna(row.get("YEAR")) else None,
            "species":       str(row.get("ESPECE_FR", "")),
            "region":        str(row.get("REGION", "")),
            "event_type":    "NEW_RESULT",
        }
        topic.produce(key, value, headers={"source": "CRISP", "version": "1.0"})
    results_log.append(("producer_results", n))


def producer_quality_alerts(broker: KafkaBroker, fact: pd.DataFrame, results_log: list):
    """Produit des alertes qualité si des anomalies sont détectées."""
    topic   = broker.get_topic("quality-alerts")
    alerts  = 0
    # Outliers extrêmes
    for trait in ["YD15QH", "YD16QH", "%MOIS"]:
        sub = fact[fact["TRAIT"] == trait]["RESULT_NUM"].dropna()
        if len(sub) < 10:
            continue
        q01, q99 = sub.quantile(0.01), sub.quantile(0.99)
        outliers = fact[(fact["TRAIT"] == trait) &
                        ((fact["RESULT_NUM"] < q01) | (fact["RESULT_NUM"] > q99))]
        for _, row in outliers.head(5).iterrows():
            key = f"alert_{row['LK_EXPERIMENT_EXPERIMENT_ID']}_{trait}"
            topic.produce(key, {
                "alert_type":    "OUTLIER",
                "experiment_id": str(row["LK_EXPERIMENT_EXPERIMENT_ID"]),
                "trait":         trait,
                "value":         float(row["RESULT_NUM"]),
                "threshold_min": float(q01),
                "threshold_max": float(q99),
                "severity":      "WARNING",
                "timestamp":     datetime.now().isoformat(),
            })
            alerts += 1
    results_log.append(("producer_quality_alerts", alerts))


def producer_geo_stream(broker: KafkaBroker, fact: pd.DataFrame, results_log: list):
    """Simule un flux géo (futur : drones / météo)."""
    topic   = broker.get_topic("geo-stream")
    essais  = fact.drop_duplicates("LK_EXPERIMENT_EXPERIMENT_ID")
    essais  = essais[essais["LAT"].notna() & essais["LON"].notna()]
    for _, row in essais.head(20).iterrows():
        key = f"geo_{row['LK_EXPERIMENT_EXPERIMENT_ID']}"
        topic.produce(key, {
            "experiment_id": str(row["LK_EXPERIMENT_EXPERIMENT_ID"]),
            "lat":           float(row["LAT"]),
            "lon":           float(row["LON"]),
            "region":        str(row.get("REGION", "")),
            "species":       str(row.get("ESPECE_FR", "")),
            "data_source":   "DRONE_SIM",
            "ndvi":          round(random.uniform(0.3, 0.85), 3),  # simulated NDVI
            "temperature":   round(random.uniform(8, 28), 1),
            "timestamp":     datetime.now().isoformat(),
        })
    results_log.append(("producer_geo_stream", min(20, len(essais))))


# ─────────────────────────────────────────────────────────────
# Consumers
# ─────────────────────────────────────────────────────────────

def consumer_results_sink(broker: KafkaBroker, results_log: list) -> list:
    """Consomme les résultats et les persiste dans un fichier (Sink HDFS)."""
    topic    = broker.get_topic("experimental-results")
    consumed = []
    while True:
        msg = topic.consume("group-analytics", timeout=0.05)
        if msg is None:
            break
        consumed.append(msg["value"])
    sink_path = os.path.join(KAFKA_DIR, "consumed_results.json")
    with open(sink_path, "w", encoding="utf-8") as f:
        json.dump(consumed[:100], f, ensure_ascii=False, indent=2)
    results_log.append(("consumer_results_sink", len(consumed)))
    return consumed


def consumer_alerts_sink(broker: KafkaBroker, results_log: list) -> list:
    """Consomme et log les alertes qualité."""
    topic    = broker.get_topic("quality-alerts")
    alerts   = []
    while True:
        msg = topic.consume("group-quality", timeout=0.05)
        if msg is None:
            break
        alerts.append(msg["value"])
    sink_path = os.path.join(KAFKA_DIR, "quality_alerts.json")
    with open(sink_path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)
    if alerts:
        print(f"  [Consumer] ⚠  {len(alerts)} alertes qualité traitées → kafka/quality_alerts.json")
    results_log.append(("consumer_alerts_sink", len(alerts)))
    return alerts


def consumer_geo_sink(broker: KafkaBroker, results_log: list) -> list:
    """Consomme les données géo (drone/météo simulé)."""
    topic  = broker.get_topic("geo-stream")
    geos   = []
    while True:
        msg = topic.consume("group-geo", timeout=0.05)
        if msg is None:
            break
        geos.append(msg["value"])
    if geos:
        df_geo = pd.DataFrame(geos)
        df_geo.to_csv(os.path.join(KAFKA_DIR, "geo_stream.csv"), index=False, sep=";")
    results_log.append(("consumer_geo_sink", len(geos)))
    return geos


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def run():
    print("=" * 80)
    print("  APACHE KAFKA — Bus de données / Streaming")
    print("  Broker : localhost:9092")
    print("=" * 80)

    fact_path = os.path.join(ENRICH_DIR, "fact_table.parquet")
    if not os.path.exists(fact_path):
        raise FileNotFoundError("Table de faits non disponible; lancer le pipeline complet")
    fact = pd.read_parquet(fact_path)

    # Création du broker et des topics
    broker = KafkaBroker(broker_id=0)
    print("\n  ── Création des Topics ──")
    broker.create_topic("experimental-results", partitions=3)
    broker.create_topic("material-updates",     partitions=2)
    broker.create_topic("quality-alerts",       partitions=1)
    broker.create_topic("geo-stream",           partitions=2)

    results_log = []

    # Phase PRODUCE
    print("\n  ── Producers ──")
    t0 = time.time()
    producer_results(broker, fact, n=500, results_log=results_log)
    producer_quality_alerts(broker, fact, results_log=results_log)
    producer_geo_stream(broker, fact, results_log=results_log)
    prod_time = time.time() - t0

    for tname in broker.list_topics():
        info = broker.get_topic(tname).info()
        print(f"  Topic '{info['topic']}'  partitions={info['partitions']}  "
              f"produced={info['produced']:,}  queued={info['queued']:,}")

    # Phase CONSUME
    print("\n  ── Consumers ──")
    t1 = time.time()
    consumed = consumer_results_sink(broker, results_log)
    alerts   = consumer_alerts_sink(broker, results_log)
    geos     = consumer_geo_sink(broker, results_log)
    cons_time = time.time() - t1

    # Résumé final
    print("\n  ── Résumé Kafka ──")
    total_produced = sum(broker.get_topic(t).total_produced for t in broker.list_topics())
    total_consumed = sum(broker.get_topic(t).total_consumed for t in broker.list_topics())
    print(f"  Total produit  : {total_produced:,} messages  ({prod_time:.2f}s)")
    print(f"  Total consommé : {total_consumed:,} messages  ({cons_time:.2f}s)")
    print(f"  Alertes qualité: {len(alerts)}")
    print(f"  Events géo     : {len(geos)}")

    # Export rapport
    os.makedirs(REPORT_DIR, exist_ok=True)
    report = {
        "broker":  "localhost:9092",
        "topics":  [broker.get_topic(t).info() for t in broker.list_topics()],
        "log":     results_log,
        "summary": {
            "total_produced": total_produced,
            "total_consumed": total_consumed,
            "quality_alerts": len(alerts),
            "geo_events":     len(geos),
        },
        "timestamp": datetime.now().isoformat(),
    }
    with open(os.path.join(REPORT_DIR, "kafka_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Rapport Kafka   : reports/kafka_report.json")
    print(f"  Sink résultats  : kafka/consumed_results.json")
    print(f"  Sink alertes    : kafka/quality_alerts.json")
    print(f"  Sink géo        : kafka/geo_stream.csv")


if __name__ == "__main__":
    run()
