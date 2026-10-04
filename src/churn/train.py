"""Обучение модели оттока: проверка данных, обучение, запись в MLflow, регистрация и гейт.

  MLFLOW_TRACKING_URI=http://mlflow.localhost C=1.0 uv run python -m churn.train

Новая версия всегда получает алиас challenger. Алиас champion она получает, только если
PR-AUC на отложенной выборке выше, чем у текущего champion, хотя бы на GATE_MIN_GAIN
(или champion ещё нет).
"""
import hashlib
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import pandas as pd
import sklearn
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    PrecisionRecallDisplay,
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DATA_PATH = Path(os.getenv("DATA_PATH", "data/Customer-Churn-Records.csv"))
MODEL_NAME = os.getenv("MODEL_NAME", "bank-churn")
EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "bank-churn")
C = float(os.getenv("C", "1.0"))
# разница PR-AUC двух лгрегрессий на одном тесте шумит с σ≈0.002–0.005 (бутстреп), 0.01 это ≥2σ
MIN_GAIN = float(os.getenv("GATE_MIN_GAIN", "0.01"))
TARGET_RECALL = 0.70
SEED = 42
SKOPS_TRUSTED = ["numpy.dtype"]

TARGET = "exited"
DROP = ["row_number", "customer_id", "surname", "complain"]  # complain почти всегда равен exited, утечка
NUMERIC = ["credit_score", "age", "tenure", "balance", "num_of_products", "has_cr_card",
           "is_active_member", "estimated_salary", "satisfaction_score", "point_earned"]
CATEGORICAL = ["geography", "gender", "card_type"]


def load_and_validate(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = (df.columns.str.strip()
                            .str.replace(" ", "_")
                            .str.replace(r"(?<=[a-z])(?=[A-Z])", "_", regex=True)
                            .str.lower())
    missing = set(NUMERIC + CATEGORICAL + [TARGET]) - set(df.columns)
    if missing:
        raise ValueError(f"в данных нет колонок: {sorted(missing)}")
    if len(df) < 1000:
        raise ValueError(f"слишком мало строк: {len(df)}")
    if not set(df[TARGET].unique()) <= {0, 1}:
        raise ValueError(f"неожиданные значения таргета: {df[TARGET].unique()[:5]}")
    return df


def build_pipeline(c: float) -> Pipeline:
    preprocess = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("scale", StandardScaler())]), NUMERIC),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                          ("onehot", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL),
    ])
    model = LogisticRegression(max_iter=1000, C=c, random_state=SEED)
    return Pipeline([("preprocess", preprocess), ("model", model)])


def pr_curve_figure(y_true, proba, threshold: float):
    fig, ax = plt.subplots(figsize=(6, 5))
    PrecisionRecallDisplay.from_predictions(y_true, proba, ax=ax, name=f"C={C}")
    pred = proba >= threshold
    ax.scatter(recall_score(y_true, pred), precision_score(y_true, pred), color="red", zorder=3,
               label=f"порог {threshold:.3f}")
    ax.axhline(y_true.mean(), ls="--", color="grey", label=f"доля оттока {y_true.mean():.2f}")
    ax.legend()
    return fig


def champion_pr_auc(client: MlflowClient) -> tuple[str | None, float | None]:
    try:
        mv = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException:
        return None, None
    return mv.version, client.get_run(mv.run_id).data.metrics.get("pr_auc")


def main() -> dict:
    df = load_and_validate(DATA_PATH)
    data_md5 = hashlib.md5(DATA_PATH.read_bytes()).hexdigest()
    features = NUMERIC + CATEGORICAL
    x_train, x_test, y_train, y_test = train_test_split(
        df[features], df[TARGET], test_size=0.2, stratify=df[TARGET], random_state=SEED)

    pipeline = build_pipeline(C)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    oof = cross_val_predict(pipeline, x_train, y_train, cv=cv, method="predict_proba")[:, 1]
    _, recall, thresholds = precision_recall_curve(y_train, oof)
    threshold = round(float(thresholds[recall[:-1] >= TARGET_RECALL].max()), 4)

    pipeline.fit(x_train, y_train)
    proba = pipeline.predict_proba(x_test)[:, 1]
    pred = (proba >= threshold).astype(int)
    metrics = {
        "pr_auc": float(average_precision_score(y_test, proba)),
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "precision": float(precision_score(y_test, pred)),
        "recall": float(recall_score(y_test, pred)),
        "f1": float(f1_score(y_test, pred)),
    }

    mlflow.set_experiment(EXPERIMENT)
    client = MlflowClient()
    with mlflow.start_run() as run:
        metadata = {"target": TARGET, "features": features, "numeric_cols": NUMERIC,
                    "categorical_cols": CATEGORICAL, "dropped_cols": DROP,
                    "threshold": threshold,
                    "threshold_rule": f"max threshold with recall >= {TARGET_RECALL} on train OOF",
                    "n_train": len(x_train), "data_rows": len(df), "data_md5": data_md5,
                    "metrics_test": {k: round(v, 4) for k, v in metrics.items()},
                    "sklearn": sklearn.__version__, "mlflow": mlflow.__version__}
        mlflow.log_params({"C": C, "model": "LogisticRegression", "seed": SEED,
                           "threshold": threshold, "data_md5": data_md5, "data_rows": len(df)})
        mlflow.log_metrics(metrics)
        mlflow.log_dict(metadata, "metadata.json")
        fig = pr_curve_figure(y_test, proba, threshold)
        mlflow.log_figure(fig, "pr_curve.png")
        plt.close(fig)
        info = mlflow.sklearn.log_model(pipeline, name="model", registered_model_name=MODEL_NAME,
                                        input_example=x_train.head(3), skops_trusted_types=SKOPS_TRUSTED)
        version = info.registered_model_version

    old_version, old_pr_auc = champion_pr_auc(client)
    promoted = old_pr_auc is None or metrics["pr_auc"] >= old_pr_auc + MIN_GAIN
    client.set_registered_model_alias(MODEL_NAME, "challenger", version)
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, "champion", version)

    result = {"run_id": run.info.run_id, "version": version, "C": C,
              "pr_auc": round(metrics["pr_auc"], 4), "data_md5": data_md5[:8],
              "champion_before": old_version,
              "champion_pr_auc_before": None if old_pr_auc is None else round(old_pr_auc, 4),
              "min_gain": MIN_GAIN, "promoted": promoted}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()