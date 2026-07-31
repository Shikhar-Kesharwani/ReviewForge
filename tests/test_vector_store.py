"""Tests for ReviewForge Vector Store Abstraction Layer (vector_store.py)."""
import os
import pytest
from reviewforge.vector_store import (
    is_cloud_vector_store,
    get_vector_status,
    LocalVectorStore,
)


class TestVectorStore:
    def test_default_fallback_is_local(self, monkeypatch):
        monkeypatch.delenv("PINECONE_API_KEY", raising=False)
        assert is_cloud_vector_store() is False

    def test_pinecone_cloud_detected(self, monkeypatch):
        monkeypatch.setenv("PINECONE_API_KEY", "mock-pinecone-key-12345")
        assert is_cloud_vector_store() is True

    def test_vector_status(self, monkeypatch):
        monkeypatch.delenv("PINECONE_API_KEY", raising=False)
        status = get_vector_status()
        assert isinstance(status, dict)
        assert status["is_cloud"] is False
        assert "mode" in status

    def test_local_vector_store_add_and_search(self):
        store = LocalVectorStore(persist_directory="./data/test_chroma")
        store.add_texts(["def foo(): pass", "import os"], metadatas=[{"file": "a.py"}, {"file": "b.py"}])
        results = store.similarity_search("function definition", k=1)
        assert isinstance(results, list)
        assert len(results) == 1
        assert "text" in results[0]
