from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import model_predictor
from schemas import SolarAnalysisRequest, SolarAnalysisResponse
from solar_analysis import analyze_solar_polygon


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        predictor = model_predictor.load_predictor()
        print(f"[startup] Loaded model: {predictor.model_name}")
    except FileNotFoundError as exc:
        print(f"[startup] WARNING: {exc}. Falling back to physics formula.")
    yield


app = FastAPI(title="Renewables Solar Analysis API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Renewables Solar Analysis API is running."}


@app.get("/health")
def health() -> dict[str, str]:
    predictor = model_predictor.get_predictor()
    return {
        "status": "ok",
        "model": predictor.model_name if predictor else "physics-fallback",
    }


@app.post("/solar/analyze", response_model=SolarAnalysisResponse)
def solar_analyze(request: SolarAnalysisRequest) -> SolarAnalysisResponse:
    return analyze_solar_polygon(request)
