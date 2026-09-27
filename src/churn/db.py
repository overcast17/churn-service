import psycopg
from psycopg.types.json import Json

from churn.config import settings

DDL = """
CREATE TABLE IF NOT EXISTS predictions (

    request_id      uuid Primary KEY,
    ts      timestamptz NOT NULL DEFAULT now(),
    model_version       text NOT NULL,
    features        jsonb ,
    score       double precision ,
    latency_ms    real,
    status_code     int NOT NULL 
)
"""

def init() -> None:
    if not settings.database_url:
        return 
    with psycopg.connect(settings.database_url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7001)")
        conn.execute(DDL)


def save_prediction(request_id : str, features : dict, score : float | None, model_version : str, latency_ms : float | None, status_code : int):
    if not settings.database_url:
            return 
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "INSERT INTO predictions (request_id, model_version, features, score, latency_ms, status_code) " \
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (request_id, model_version, Json(features), score, latency_ms, status_code)
        )

    
