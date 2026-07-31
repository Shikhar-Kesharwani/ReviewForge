"""
Universal FastAPI REST Backend for ReviewForge.
Exposes endpoints for status, health check, chat completion, and system capabilities.
Can be deployed to Render, Railway, Vercel, or run inside Docker Compose.
"""

import os
import sys
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from reviewforge.db_config import get_db_status, init_db
from reviewforge.vector_store import get_vector_status, get_vector_store

app = FastAPI(
    title="ReviewForge API",
    description="Universal AI Pair Programming API Server",
    version="0.1.0",
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initialize system resources on boot."""
    try:
        init_db()
    except Exception as e:
        print(f"Startup DB Init Notice: {e}")


@app.get("/")
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ReviewForge API",
        "version": "0.1.0"
    }


@app.get("/status")
def system_status():
    """Return active execution mode & database/vector configurations."""
    return {
        "database": get_db_status(),
        "vector_store": get_vector_status(),
        "environment": "Render/Cloud" if os.getenv("PORT") else "Local/Docker",
    }


class ChatRequest(BaseModel):
    prompt: str
    model: Optional[str] = "gemini/gemini-2.0-flash"
    files: Optional[List[str]] = []


@app.post("/api/chat")
def chat_completion(req: ChatRequest):
    """Process user prompt using ReviewForge Coder Engine."""
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
        return {"response": content, "model": req.model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── CRUCIAL RENDER RULE ───────────────────────────────────────────────────────
# Programmatically bind to Render/Cloud dynamic PORT variable at startup
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting ReviewForge API Server on port {port}...")
    uvicorn.run("reviewforge.api:app", host="0.0.0.0", port=port, reload=False)
