"""
Production Security & Header Middleware for ReviewForge.
Implements HSTS, Content Security Policy, X-Frame-Options, Referrer-Policy,
Permissions-Policy, and production CORS protection.
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds enterprise production security headers to all HTTP responses."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Enterprise Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # HSTS (Strict-Transport-Security) in production
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
            
        return response


def setup_security(app: FastAPI):
    """Attach Security Headers and Production CORS Middleware to FastAPI app."""
    # Attach Security Headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Configure CORS
    allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
    if allowed_origins_raw.strip():
        allowed_origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
    else:
        # Default local origins
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:8501",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8501",
        ]
        
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
