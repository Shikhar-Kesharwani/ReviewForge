"""
Database Abstraction Layer for ReviewForge.
Dynamically switches between Cloud PostgreSQL (if DATABASE_URL is set)
and local SQLite (default fallback).
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


def get_database_url() -> str:
    """Determine the active database URL based on environment variables."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Fix legacy postgres:// URIs if provided by Heroku/Render
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return db_url
    
    # Fallback to local SQLite in ./data directory
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    local_sqlite_path = data_dir / "local.db"
    return f"sqlite:///{local_sqlite_path.absolute()}"


def is_cloud_db() -> bool:
    """Returns True if connected to Cloud PostgreSQL, False if using local SQLite."""
    return bool(os.getenv("DATABASE_URL"))


# Global Engine & Session Factory
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        db_url = get_database_url()
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        _engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal()


def init_db():
    """Initialize database tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def get_db_status() -> dict:
    """Return status metadata about the current database connection."""
    cloud = is_cloud_db()
    db_url = get_database_url()
    
    status = {
        "mode": "Cloud PostgreSQL" if cloud else "Local SQLite",
        "is_cloud": cloud,
        "connected": False,
        "url_masked": db_url.split("@")[-1] if "@" in db_url else db_url,
    }
    
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            status["connected"] = True
    except Exception as e:
        status["error"] = str(e)

    return status
