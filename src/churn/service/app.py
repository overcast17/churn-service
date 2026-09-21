import time 
import uuid
from typing import Literal

from contextlib import asynccontextmanager

import joblib 
import pandas as pd 
from fastapi import BackgroundTasks, FastAPI, HTTPException

from pydantic import BaseModel, Field

from churn import db 
from churn.config import settings

class Features(BaseModel):
    model_config = {"extra": "forbid"}
    credit_score: int = Field(ge=300, le=900)
    geography: Literal["France", "Spain", "Germany"]
    gender: Literal["Male", "Female"]
    age: int = Field(ge=18, le=100)
    tenure: int = Field(ge=0, le=10)
    balance: float = Field(ge=0)
    num_of_products: int = Field(ge=1, le=4)
    has_cr_card: int = Field(ge=0, le=1)
    is_active_member: int = Field(ge=0, le=1)
    estimated_salary: float = Field(ge=0)
    satisfaction_score: int = Field(ge=1, le=5)
    card_type: Literal["SILVER", "GOLD", "PLATINUM", "DIAMOND"]
    point_earned: int = Field(ge=0)


class Prediction(BaseModel):

    score: float
    churn: bool
    model_version: str 
    request_id: str
    latency_ms: float

class BatchRequest(BaseModel):
    model_config = {"extra":"forbid"}
    rows: list[Features] = Field(min_length=1, max_length=1000)

class BatchPrediction(BaseModel):
    scores: list[float]
    churn: list[bool]
    model_version: str
    request_id: str
    latency_ms: float

## Загрузка модели 
@asynccontextmanager
async def lifespan(app: FastAPI):
    bundle = joblib.load(settings.model_path)
    app.state.pipeline = bundle["pipeline"]
    app.state.meta = bundle["metadata"]
    app.state.version = bundle["metadata"]["model_version"]

    db.init()
    yield
    app.state.pipeline = None

## Сам сервис 
app = FastAPI(title= "churn_service", version = "1.0", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status":"ok", "model_version": getattr(app.state, "version", "unknown")}


@app.get("/ready")
def ready():
    if getattr(app.state, "pipeline", None) is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status":"ready"}

@app.post("/v1/predict")
def predict(x: Features, bg: BackgroundTasks) -> Prediction:
    t0 = time.perf_counter()
    request_id = str(uuid.uuid4())
    payload = x.model_dump()
    frame = pd.DataFrame([payload]).reindex(columns=app.state.meta["features"])

    score = float(app.state.pipeline.predict_proba(frame)[0,1])

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    bg.add_task(db.save_prediction, request_id, payload, score, app.state.version, latency_ms, 200)

    churn = score>= app.state.meta['threshold']

    return Prediction(score = score, churn = churn, model_version=app.state.version, request_id= request_id, latency_ms=latency_ms )

@app.post("/v1/predict/batch")
def predict_batch(req: BatchRequest) -> BatchPrediction:
    t0 = time.perf_counter()
    request_id = str(uuid.uuid4())

    frame = pd.DataFrame([r.model_dump() for r in req.rows]).reindex(columns=app.state.meta["features"])

    scores = [float(s) for s in app.state.pipeline.predict_proba(frame)[:, 1]]

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    threshold = app.state.meta["threshold"]
    churn = [s >= threshold for s in scores]

    return BatchPrediction(
        scores=scores,
        churn=churn,
        model_version=app.state.version,
        request_id=request_id,
        n_rows=len(scores),
        latency_ms=latency_ms,
    )