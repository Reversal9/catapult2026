"""
Catapult 2026 - Renewables Analysis Backend

FastAPI application providing REST endpoints for analyzing renewable energy potential:
- Solar suitability analysis for user-drawn regions
- Asset-based infrastructure analysis
- Multi-use infrastructure site evaluation

The backend supports graceful degradation when optional ML dependencies are unavailable,
falling back to physics-based calculations for energy prediction.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from asset_analysis import analyze_asset_polygon
from infrastructure_pipeline import analyze_infrastructure_polygon

try:
    import model_predictor
except Exception:  # pragma: no cover - optional ML dependency missing in tests
    # Fallback when model_predictor module can't be loaded (missing numpy, torch, etc.)
    class _FallbackPredictorModule:
        """Stub module providing no-op methods when ML dependencies aren't available."""
        @staticmethod
        def load_predictor():
            return None

        @staticmethod
        def get_predictor():
            return None

    model_predictor = _FallbackPredictorModule()

from schemas import (
    AssetAnalysisRequest,
    AssetAnalysisResponse,
    InfrastructureAnalysisRequest,
    InfrastructureAnalysisResponse,
    SolarAnalysisRequest,
    SolarAnalysisResponse,
)
from solar_analysis import analyze_solar_polygon


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown.
    
    At startup:
    - Attempts to load the ML model predictor
    - Falls back gracefully if model files are missing
    - Logs model availability status
    """
    try:
        predictor = model_predictor.load_predictor()
        print(f"[startup] Loaded model: {predictor.model_name}")
    except FileNotFoundError as exc:
        print(f"[startup] WARNING: {exc}. Falling back to physics formula.")
    yield


# Initialize FastAPI application with CORS middleware
app = FastAPI(title="Renewables Solar Analysis API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from all origins (frontend, testing)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


@app.get("/")
def root() -> dict[str, str]:
    """
    Health check endpoint - displays API status.
    
    Returns:
        Status message indicating API is running
    """
    return {"message": "Renewables Solar Analysis API is running."}


@app.get("/health")
def health() -> dict[str, str]:
    """
    Detailed health check - shows model availability.
    
    Returns:
        Status and current model source (ML model name or "physics-fallback")
    """
    predictor = model_predictor.get_predictor()
    return {
        "status": "ok",
        "model": predictor.model_name if predictor else "physics-fallback",
    }


@app.post("/solar/analyze", response_model=SolarAnalysisResponse)
def solar_analyze(request: SolarAnalysisRequest) -> SolarAnalysisResponse:
    """
    Analyze solar potential for a user-drawn polygon region.
    
    Process:
    1. Calculate polygon area and centroid
    2. Fetch annual solar irradiance (GHI) from Open-Meteo
    3. Estimate panel count and installed capacity
    4. Predict annual energy output (ML model or physics formula)
    5. Calculate project cost
    6. Generate suitability score
    
    Args:
        request: SolarAnalysisRequest with polygon points and panel specifications
        
    Returns:
        SolarAnalysisResponse with energy output, cost, and suitability metrics
    """
    return analyze_solar_polygon(request)


@app.post("/asset/analyze", response_model=AssetAnalysisResponse)
def asset_analyze(request: AssetAnalysisRequest) -> AssetAnalysisResponse:
    """
    Analyze solar assets within a region based on facility specifications.
    
    Process:
    1. Validate polygon geometry
    2. Query for existing solar infrastructure
    3. Estimate energy generation based on asset characteristics
    4. Calculate project feasibility and cost
    
    Args:
        request: AssetAnalysisRequest with polygon and asset filter criteria
        
    Returns:
        AssetAnalysisResponse with discovered assets and analysis results
        
    Raises:
        HTTPException: If polygon is invalid or analysis fails
    """
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
    """
    Analyze multi-use infrastructure potential in a region.
    
    This endpoint evaluates a region for:
    - Solar farm siting (with water/terrain analysis)
    - Wind farm potential
    - Data center infrastructure
    - Combined multi-use scenarios
    
    Process:
    1. Grid the region into smaller cells
    2. For each cell, evaluate use type viability
    3. Extract natural/built features (water, buildings, roads)
    4. Score candidates by solar validity, buildability, infrastructure
    5. Merge adjacent high-value cells
    6. Return ranked infrastructure sites
    
    Args:
        request: InfrastructureAnalysisRequest with region, use types, and cell size
        
    Returns:
        InfrastructureAnalysisResponse with candidate infrastructure sites
        
    Raises:
        HTTPException: If polygon is invalid or analysis fails
    """
    try:
        return analyze_infrastructure_polygon(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
