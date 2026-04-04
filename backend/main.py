from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from schemas import SolarAnalysisRequest, SolarAnalysisResponse
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