"""Leakage-safe training and evaluation for cultural yield prediction."""

import json
import os
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, mean_absolute_error,
    mean_squared_error, precision_score, r2_score, recall_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACT_PATH = os.path.join(BASE_DIR, "data", "enriched", "fact_table.parquet")
MODEL_DIR = os.path.join(BASE_DIR, "models")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
PREDICTION_DIR = os.path.join(BASE_DIR, "data", "exposed")

TARGET_TRAIT = "YD15QH"
TARGET = "RESULT_NUM"
HIGH_YIELD_THRESHOLD = 80.0
NUMERIC_FEATURES = ["YEAR", "REPLICATION_NUM", "ENTRY_NUM"]
CATEGORICAL_FEATURES = ["SPECIES", "SPECIES_SPECIFICITY", "REGION"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
CLASSIFICATION_NUMERIC = NUMERIC_FEATURES
CLASSIFICATION_CATEGORICAL = CATEGORICAL_FEATURES
CLASSIFICATION_FEATURES = CLASSIFICATION_NUMERIC + CLASSIFICATION_CATEGORICAL
GROUP_COLUMN = "LK_EXPERIMENT_EXPERIMENT_ID"
SOURCE_ROW_COLUMN = "LK_SL_TRIAL_L2_DATA_ID"


def prepare_dataset(fact):
    columns = FEATURES + [TARGET, GROUP_COLUMN, SOURCE_ROW_COLUMN]
    data = fact.loc[
        (fact["TRAIT"] == TARGET_TRAIT) & fact[TARGET].notna(), columns
    ].copy()
    data["YEAR"] = pd.to_numeric(data["YEAR"], errors="coerce")
    return data[data[TARGET].between(0, 250)].copy()


def _preprocessor():
    return ColumnTransformer([
        ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
        ("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OrdinalEncoder(
                handle_unknown="use_encoded_value", unknown_value=-1
            )),
        ]), CATEGORICAL_FEATURES),
    ])


def build_model():
    regressor = HistGradientBoostingRegressor(
        learning_rate=0.07, max_iter=250, max_leaf_nodes=25,
        l2_regularization=1.0, random_state=42,
    )
    return Pipeline([("preprocess", _preprocessor()), ("regressor", regressor)])


def build_classifier(params=None):
    config = {
        "learning_rate": 0.08, "max_iter": 150, "max_leaf_nodes": 15,
        "l2_regularization": 1.0, "random_state": 42,
    }
    config.update(params or {})
    return Pipeline([
        ("preprocess", _preprocessor()),
        ("classifier", HistGradientBoostingClassifier(**config)),
    ])


def binary_metrics(actual, probability, threshold):
    classified = probability >= threshold
    tn, fp, fn, tp = confusion_matrix(
        actual, classified, labels=[False, True]
    ).ravel()
    return {
        "yield_threshold_q_ha": HIGH_YIELD_THRESHOLD,
        "decision_probability_threshold": round(float(threshold), 4),
        "accuracy": round(float(accuracy_score(actual, classified)), 4),
        "precision": round(float(precision_score(
            actual, classified, zero_division=0)), 4),
        "recall": round(float(recall_score(
            actual, classified, zero_division=0)), 4),
        "f1_score": round(float(f1_score(
            actual, classified, zero_division=0)), 4),
        "confusion_matrix": {
            "true_negative": int(tn), "false_positive": int(fp),
            "false_negative": int(fn), "true_positive": int(tp),
        },
    }


def tune_classifier(train):
    labels = train[TARGET] >= HIGH_YIELD_THRESHOLD
    groups = train[GROUP_COLUMN].astype(str)
    configurations = [
        {"learning_rate": 0.08, "max_iter": 150,
         "max_leaf_nodes": 15, "l2_regularization": 1.0},
        {"learning_rate": 0.06, "max_iter": 350,
         "max_leaf_nodes": 31, "l2_regularization": 2.0},
        {"learning_rate": 0.05, "max_iter": 400,
         "max_leaf_nodes": 31, "l2_regularization": 10.0},
    ]
    cv = GroupKFold(n_splits=3)
    tuning = []
    best = None
    for config in configurations:
        oof_probability = np.zeros(len(train))
        for fit_idx, validation_idx in cv.split(train, labels, groups):
            fold_model = build_classifier(config)
            fold_model.fit(
                train.iloc[fit_idx][CLASSIFICATION_FEATURES],
                labels.iloc[fit_idx],
            )
            oof_probability[validation_idx] = fold_model.predict_proba(
                train.iloc[validation_idx][CLASSIFICATION_FEATURES]
            )[:, 1]

        candidates = []
        for threshold in np.arange(0.10, 0.901, 0.01):
            score = f1_score(
                labels, oof_probability >= threshold, zero_division=0
            )
            candidates.append((float(score), float(threshold)))
        cv_f1, threshold = max(candidates)
        tuning.append({
            "params": config, "group_cv_f1": round(cv_f1, 4),
            "threshold": round(threshold, 4),
        })
        if best is None or cv_f1 > best[0]:
            best = (cv_f1, threshold, config)
    return best[2], best[1], tuning


def metrics_by_species(test, actual, classified):
    frame = test[["SPECIES"]].copy()
    frame["actual"] = np.asarray(actual)
    frame["classified"] = np.asarray(classified)
    rows = []
    for species, group in frame.groupby("SPECIES"):
        rows.append({
            "species": str(species),
            "rows": int(len(group)),
            "positive_rate": round(float(group["actual"].mean()), 4),
            "accuracy": round(float(accuracy_score(
                group["actual"], group["classified"])), 4),
            "precision": round(float(precision_score(
                group["actual"], group["classified"], zero_division=0)), 4),
            "recall": round(float(recall_score(
                group["actual"], group["classified"], zero_division=0)), 4),
            "f1_score": round(float(f1_score(
                group["actual"], group["classified"], zero_division=0)), 4),
        })
    return rows


def evaluate_classifier(data):
    test_year = int(data["YEAR"].max())
    train = data[data["YEAR"] < test_year].reset_index(drop=True)
    test = data[data["YEAR"] == test_year].reset_index(drop=True)
    train_labels = train[TARGET] >= HIGH_YIELD_THRESHOLD
    test_labels = test[TARGET] >= HIGH_YIELD_THRESHOLD

    train_groups = set(train[GROUP_COLUMN].astype(str))
    test_groups = set(test[GROUP_COLUMN].astype(str))
    overlap = len(train_groups & test_groups)
    if overlap:
        raise RuntimeError(f"Fuite de groupes détectée: {overlap} essais partagés")

    selected_params, threshold, tuning = tune_classifier(train)
    model = build_classifier(selected_params)
    model.fit(train[CLASSIFICATION_FEATURES], train_labels)
    probability = model.predict_proba(test[CLASSIFICATION_FEATURES])[:, 1]
    metrics = binary_metrics(test_labels, probability, threshold)
    classified = probability >= threshold

    importance = permutation_importance(
        model, test[CLASSIFICATION_FEATURES], test_labels,
        scoring="roc_auc", n_repeats=5, random_state=42, n_jobs=1,
    )
    importance_rows = sorted([
        {
            "feature": feature,
            "importance_mean": round(float(mean), 6),
            "importance_std": round(float(std), 6),
        }
        for feature, mean, std in zip(
            CLASSIFICATION_FEATURES,
            importance.importances_mean,
            importance.importances_std,
        )
    ], key=lambda row: row["importance_mean"], reverse=True)

    annual_rates = {
        str(int(year)): round(float(
            (group[TARGET] >= HIGH_YIELD_THRESHOLD).mean()), 4)
        for year, group in data.groupby("YEAR")
    }
    quality = {
        "rows": int(len(data)),
        "experiments": int(data[GROUP_COLUMN].nunique()),
        "full_duplicates": int(data.duplicated().sum()),
        "missing_rates": {
            column: round(float(data[column].isna().mean()), 4)
            for column in CLASSIFICATION_FEATURES
        },
    }
    report = {
        "protocol": "GroupKFold 2015-2017; test temporel final 2018 intact",
        "features": CLASSIFICATION_FEATURES,
        "excluded_leakage_features": [
            "%MOIS", "YD16QH", "SL_TRIAL",
            "LK_STOCK_S1_DATA_ID", "MAIN_NAME",
        ],
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_years": sorted(train["YEAR"].astype(int).unique().tolist()),
        "test_year": test_year,
        "group_column": GROUP_COLUMN,
        "train_test_group_overlap": overlap,
        "hyperparameter_search": tuning,
        "selected_params": selected_params,
        "metrics": metrics,
        "metrics_by_species": metrics_by_species(
            test, test_labels, classified
        ),
        "annual_positive_rates": annual_rates,
        "permutation_importance": importance_rows,
        "data_quality": quality,
        "limitations": [
            "Les données météo, sol et conduite culturale ne sont pas disponibles",
            "Le seuil de 80 q/ha doit être validé par espèce avec un agronome",
            "Les espèces peu représentées nécessitent davantage de données",
        ],
    }
    return model, metrics, report


def run():
    print("=" * 80)
    print("  PREDICTION CULTURALE - validation sans fuite")
    print("=" * 80)
    fact = pd.read_parquet(FACT_PATH)
    data = prepare_dataset(fact)
    years = [int(year) for year in sorted(
        data["YEAR"].dropna().astype(int).unique()
    )]
    test_year = int(years[-1])
    train = data[data["YEAR"] < test_year]
    test = data[data["YEAR"] == test_year]

    regressor = build_model()
    regressor.fit(train[FEATURES], train[TARGET])
    predicted = regressor.predict(test[FEATURES])
    baseline = np.repeat(train[TARGET].mean(), len(test))
    regression_metrics = {
        "mae": round(float(mean_absolute_error(test[TARGET], predicted)), 4),
        "rmse": round(float(mean_squared_error(test[TARGET], predicted) ** 0.5), 4),
        "r2": round(float(r2_score(test[TARGET], predicted)), 4),
        "baseline_mae": round(float(mean_absolute_error(
            test[TARGET], baseline)), 4),
        "baseline_rmse": round(float(mean_squared_error(
            test[TARGET], baseline) ** 0.5), 4),
    }
    classifier, classification_metrics, classification_report = (
        evaluate_classifier(data)
    )

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(PREDICTION_DIR, exist_ok=True)
    regressor_path = os.path.join(MODEL_DIR, "yield_yd15qh.joblib")
    classifier_path = os.path.join(MODEL_DIR, "high_yield_classifier.joblib")
    joblib.dump(regressor, regressor_path)
    joblib.dump(classifier, classifier_path)

    output = test[
        [SOURCE_ROW_COLUMN, GROUP_COLUMN, "YEAR", "SPECIES", "REGION", TARGET]
    ].copy()
    output["PREDICTION"] = np.round(predicted, 3)
    output["ERREUR_ABS"] = np.round(
        np.abs(output[TARGET] - output["PREDICTION"]), 3
    )
    output.to_csv(
        os.path.join(PREDICTION_DIR, "yield_predictions.csv"),
        index=False, sep=";",
    )
    if output.duplicated().any():
        raise RuntimeError("Doublons complets détectés dans l'export de prédictions")

    report = {
        "status": "OK",
        "objective": "Prédire YD15QH avant sa mesure",
        "target": TARGET,
        "target_trait": TARGET_TRAIT,
        "features": FEATURES,
        "validation": "Dernière année réservée au test; groupes isolés",
        "train_years": years[:-1],
        "test_year": test_year,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "prediction_rows": int(len(output)),
        "prediction_full_duplicates": int(output.duplicated().sum()),
        "quality_filter": "0 <= YD15QH <= 250",
        "metrics": regression_metrics,
        "classification_evaluation": classification_report,
        "model": "HistGradientBoostingRegressor",
        "model_path": "models/yield_yd15qh.joblib",
        "classifier_path": "models/high_yield_classifier.joblib",
        "timestamp": datetime.now().isoformat(),
    }
    with open(
        os.path.join(REPORT_DIR, "prediction_report.json"),
        "w", encoding="utf-8",
    ) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print(
        f"  Régression test {test_year}: MAE={regression_metrics['mae']} "
        f"RMSE={regression_metrics['rmse']} R²={regression_metrics['r2']}"
    )
    print(
        f"  Classification test {test_year}: "
        f"accuracy={classification_metrics['accuracy']} "
        f"precision={classification_metrics['precision']} "
        f"recall={classification_metrics['recall']} "
        f"F1={classification_metrics['f1_score']}"
    )
    print("  Fuite groupes train/test: 0")
    return report


if __name__ == "__main__":
    run()
