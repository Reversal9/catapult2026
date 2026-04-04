<<<<<<< HEAD
from asset_analysis import analyze_asset_polygon
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from infrastructure_pipeline import analyze_infrastructure_polygon
from schemas import (
    AssetAnalysisRequest,
    AssetAnalysisResponse,
    InfrastructureAnalysisRequest,
    InfrastructureAnalysisResponse,
    SolarAnalysisRequest,
    SolarAnalysisResponse,
)
=======
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import model_predictor
from schemas import SolarAnalysisRequest, SolarAnalysisResponse
>>>>>>> 8170744edd493d09388cddaeb55063072d9771b7
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
<<<<<<< HEAD


@app.post("/asset/analyze", response_model=AssetAnalysisResponse)
def asset_analyze(request: AssetAnalysisRequest) -> AssetAnalysisResponse:
    try:
        return analyze_asset_polygon(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post(
    "/infrastructure/analyze",
    response_model=InfrastructureAnalysisResponse,
)
def infrastructure_analyze(
    request: InfrastructureAnalysisRequest,
) -> InfrastructureAnalysisResponse:
    try:
        return analyze_infrastructure_polygon(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
=======
>>>>>>> 8170744edd493d09388cddaeb55063072d9771b7
