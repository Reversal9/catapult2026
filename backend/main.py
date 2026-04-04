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
from solar_analysis import analyze_solar_polygon


app = FastAPI(title="Renewables Solar Analysis API")
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
    return {"status": "ok"}


@app.post("/solar/analyze", response_model=SolarAnalysisResponse)
def solar_analyze(request: SolarAnalysisRequest) -> SolarAnalysisResponse:
    return analyze_solar_polygon(request)


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
