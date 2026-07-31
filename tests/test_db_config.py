"""Tests for ReviewForge Database Abstraction Layer (db_config.py)."""
import os
import pytest
from reviewforge.db_config import get_database_url, is_cloud_db, get_db_status


class TestDBConfig:
    def test_default_fallback_is_sqlite(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert is_cloud_db() is False
        url = get_database_url()
        assert url.startswith("sqlite:///")

    def test_cloud_postgres_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/reviewforgedb")
        assert is_cloud_db() is True
        url = get_database_url()
        assert url.startswith("postgresql://")

    def test_legacy_postgres_prefix_fix(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/reviewforgedb")
        url = get_database_url()
        assert url.startswith("postgresql://")

    def test_db_status_dict(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        status = get_db_status()
        assert isinstance(status, dict)
        assert "mode" in status
        assert status["is_cloud"] is False
