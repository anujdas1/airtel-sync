"""
main.py — FastAPI Application Entrypoint for Accel SYNC (Project Udyam Digital).
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from db import Base, engine
from routers import advisor, catalogue, kyc, leads, orders, scoring
from services import gstin_service, propensity_model, udyam_service

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("accel_sync")

DATA_DIR = BASE_DIR.parent / "Data"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = BASE_DIR.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & Shutdown lifecycle events."""
    logger.info("Starting up Accel SYNC Backend...")
    
    # 1. Initialize SQLite Database
    Base.metadata.create_all(bind=engine)
    logger.info("SQLite database tables verified/created.")

    # 2. Train / warm up ML Propensity Model
    leads_csv = DATA_DIR / "smb_leads.csv"
    if leads_csv.exists():
        logger.info("Training Lead Propensity Model from %s...", leads_csv)
        try:
            metrics = propensity_model.train_model(str(leads_csv))
            logger.info("ML Propensity Model ready! Metrics: %s", metrics)
        except Exception as e:
            logger.warning("Could not train propensity model on startup: %s", e)

    yield
    logger.info("Shutting down Accel SYNC Backend...")


app = FastAPI(
    title="Accel SYNC — MSME Digital Acquisition & Onboarding API",
    description="Full-stack digital journey engine for Airtel SYNC (Enterprise Track A - Project Udyam Digital)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup for mobile and web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(catalogue.router)
app.include_router(advisor.router)
app.include_router(kyc.router)
app.include_router(orders.router)
app.include_router(leads.router)
app.include_router(scoring.router)

# Aliases for scoring endpoints
@app.get("/api/features", tags=["Scoring"])
def features_alias():
    return scoring.get_features()

@app.post("/api/predict", tags=["Scoring"])
def predict_alias(req: scoring.LeadPredictionRequest):
    return scoring.predict_propensity(req)

# Mount uploads directory
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/api/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": "Accel SYNC",
        "version": "1.0.0",
        "platform": "Enterprise Track A - Project Udyam Digital",
        "reference_date": "2026-07-15",
    }


# Serve Frontend index.html if frontend directory exists
@app.get("/", tags=["Frontend"])
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "message": "Accel SYNC API is running. Open /docs for Swagger interactive documentation."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

