import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routes import analytics, graph, image, memory, notes, query, recommendations, study, summary, upload, youtube
from services.analytics_service import get_system_status
from services.database import initialize_database

app = FastAPI(
    title="AI Personal Knowledge Engine",
    description="Production-ready Second Brain AI System",
    version="2.0.0"
)


@app.on_event("startup")
def startup():
    initialize_database()


allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
).split(",")

allowed_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX", r"https://.*\.vercel\.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    """Optional shared-secret guard for deployed API endpoints."""
    configured_key = os.getenv("SECOND_BRAIN_API_KEY", "").strip()
    if (
        configured_key
        and request.url.path.startswith("/api")
        and request.url.path != "/api/health"
        and request.method != "OPTIONS"
        and request.headers.get("x-api-key") != configured_key
    ):
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key."})

    return await call_next(request)


@app.get("/health")
@app.get("/api/health")
def health_check():
    return {"status": "ok", "system_status": get_system_status()}


app.include_router(upload.router, prefix="/api")
app.include_router(image.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(youtube.router, prefix="/api")
app.include_router(summary.router, prefix="/api")
app.include_router(study.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")


static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
