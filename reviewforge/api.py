"""
Universal FastAPI REST Backend for ReviewForge.
Exposes backward-compatible endpoints (/health, /status, /api/chat) AND
versioned endpoints (/api/v1/chat, /readiness, /liveness) with
OpenAPI /docs documentation, Sentry, Security Headers, and Structured Logging.
"""

import os
import sys
import uuid
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from reviewforge.config_validation import validate_config
from reviewforge.db_config import get_db_status, init_db, get_engine
from reviewforge.vector_store import get_vector_status, get_vector_store
from reviewforge.security import setup_security
from reviewforge.logger import logger
from reviewforge.sentry_integration import init_sentry

# Validate Configuration on Boot
config_status = validate_config(strict=False)

# Initialize Sentry Error Tracking
init_sentry()

app = FastAPI(
    title="ReviewForge API",
    description="Enterprise Universal AI Pair Programming API Server",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Attach Security Headers & Production CORS
setup_security(app)


@app.middleware("http")
async in_logging_middleware(request: Request, call_next):
    """Inject Request ID & Correlation ID, log structured request duration."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    correlation_id = request.headers.get("X-Correlation-ID", request_id)
    
    request.state.request_id = request_id
    request.state.correlation_id = correlation_id
    
    logger.info(f"HTTP {request.method} {request.url.path}", extra={"request_id": request_id, "correlation_id": correlation_id})
    
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.on_event("startup")
def on_startup():
    """Initialize database schema on boot."""
    try:
        init_db()
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.warning(f"Startup DB init notice: {e}")


# ─── HEALTH & DIAGNOSTIC ENDPOINTS ─────────────────────────────────────────────

@app.get("/")
@app.get("/health")
def health_check():
    """Simple Liveness Health Check (100% Backward Compatible)."""
    return {
        "status": "healthy",
        "service": "ReviewForge API",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.get("/liveness")
def liveness_check():
    """Kubernetes / Render Liveness Probe."""
    return {"status": "alive", "timestamp": logger.name}


@app.get("/readiness")
def readiness_check():
    """Kubernetes / Render Readiness Probe."""
    db_stat = get_db_status()
    vec_stat = get_vector_status()
    
    is_ready = db_stat.get("connected", True)
    return {
        "status": "ready" if is_ready else "not_ready",
        "database_connected": is_ready,
        "database_mode": db_stat["mode"],
        "vector_mode": vec_stat["mode"]
    }


@app.get("/status")
def system_status():
    """System Status (100% Backward Compatible)."""
    return {
        "database": get_db_status(),
        "vector_store": get_vector_status(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "config_validation": config_status,
    }


# ─── API MODELS & ROUTING ──────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    prompt: str
    model: Optional[str] = "gemini/gemini-2.0-flash"
    files: Optional[List[str]] = []


@app.post("/api/chat")
@app.post("/api/v1/chat")
def chat_completion(req: ChatRequest):
    """Process user prompt using ReviewForge Coder Engine (Supports both /api/chat & /api/v1/chat)."""
    try:
        from reviewforge.llm import litellm
        
        messages = [
            {"role": "system", "content": "You are ReviewForge, an expert AI pair programmer. Provide clear, accurate code edits."},
            {"role": "user", "content": req.prompt}
        ]
        
        response = litellm.completion(
            model=req.model,
            messages=messages,
            temperature=0,
        )
        content = response.choices[0].message.content
        return {"response": content, "model": req.model, "api_version": "v1"}
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/status")
def api_v1_status():
    """Version 1 System Status."""
    return system_status()


# ─── PROGRAMMATIC PORT BINDING FOR RENDER / CONTAINER ────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"🚀 Starting ReviewForge API Server on port {port}...")
    uvicorn.run("reviewforge.api:app", host="0.0.0.0", port=port, reload=False)
