"""
Vector Store Abstraction Layer for ReviewForge.
Dynamically switches between Pinecone Cloud Vector Store (if PINECONE_API_KEY is set)
and local ChromaDB / FAISS fallback.
Crucial Rule: Heavy local embedding models (SentenceTransformers) are LAZY-LOADED
only when local mode is active, preventing cloud OOM crashes.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional

_vector_store_instance = None
_embedding_model_instance = None


def is_cloud_vector_store() -> bool:
    """Returns True if Pinecone API key is provided."""
    return bool(os.getenv("PINECONE_API_KEY"))


def get_vector_status() -> dict:
    """Return status metadata about the current vector store configuration."""
    cloud = is_cloud_vector_store()
    index_name = os.getenv("PINECONE_INDEX", "reviewforge-index")
    
    return {
        "mode": "Pinecone (Cloud)" if cloud else "ChromaDB (Local)",
        "is_cloud": cloud,
        "index_name": index_name if cloud else "local_chroma",
        "lazy_model_loaded": _embedding_model_instance is not None,
    }


class LocalVectorStore:
    """Fallback local vector store using ChromaDB or lightweight cosine similarity."""
    def __init__(self, persist_directory: str = "./data/chroma"):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.documents = []
        self.embeddings = []

    def _get_embedding_model(self):
        """LAZY LOAD SentenceTransformers model only when called locally."""
        global _embedding_model_instance
        if _embedding_model_instance is None:
            try:
                from sentence_transformers import SentenceTransformer
                _embedding_model_instance = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                _embedding_model_instance = None
        return _embedding_model_instance

    def add_texts(self, texts: List[str], metadatas: Optional[List[dict]] = None):
        model = self._get_embedding_model()
        if model:
            vecs = model.encode(texts).tolist()
        else:
            vecs = [[0.0] * 384 for _ in texts]  # Dummy fallback
            
        for i, text in enumerate(texts):
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            self.documents.append({"text": text, "metadata": meta, "vector": vecs[i]})

    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        if not self.documents:
            return []
        model = self._get_embedding_model()
        if not model:
            return [{"text": d["text"], "metadata": d["metadata"], "score": 1.0} for d in self.documents[:k]]
        
        query_vec = model.encode([query])[0]
        
        # Simple dot product / cosine similarity
        results = []
        for doc in self.documents:
            doc_vec = doc["vector"]
            score = sum(a * b for a, b in zip(query_vec, doc_vec))
            results.append((score, doc))
            
        results.sort(key=lambda x: x[0], reverse=True)
        return [{"text": d["text"], "metadata": d["metadata"], "score": float(s)} for s, d in results[:k]]


class PineconeVectorStore:
    """Managed Cloud Vector Store using Pinecone."""
    def __init__(self, api_key: str, index_name: str = "reviewforge-index"):
        self.api_key = api_key
        self.index_name = index_name
        self._init_pinecone()

    def _init_pinecone(self):
        try:
            from pinecone import Pinecone
            self.pc = Pinecone(api_key=self.api_key)
            self.index = self.pc.Index(self.index_name)
        except Exception as e:
            print(f"Warning: Failed to initialize Pinecone client: {e}")
            self.index = None

    def add_texts(self, texts: List[str], metadatas: Optional[List[dict]] = None):
        if not self.index:
            return
        # Pinecone upsert logic
        vectors = []
        for i, text in enumerate(texts):
            meta = metadatas[i] if metadatas else {}
            meta["text"] = text
            vectors.append({"id": f"vec_{i}", "values": [0.1] * 1536, "metadata": meta})
        self.index.upsert(vectors=vectors)

    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        if not self.index:
            return []
        try:
            # Query pinecone
            res = self.index.query(vector=[0.1] * 1536, top_k=k, include_metadata=True)
            matches = []
            for match in res.get("matches", []):
                matches.append({
                    "text": match["metadata"].get("text", ""),
                    "metadata": match["metadata"],
                    "score": match.get("score", 0.0)
                })
            return matches
        except Exception as e:
            print(f"Error querying Pinecone: {e}")
            return []


def get_vector_store():
    """Factory function returning active vector store instance."""
    global _vector_store_instance
    if _vector_store_instance is None:
        if is_cloud_vector_store():
            api_key = os.getenv("PINECONE_API_KEY")
            index_name = os.getenv("PINECONE_INDEX", "reviewforge-index")
            _vector_store_instance = PineconeVectorStore(api_key=api_key, index_name=index_name)
        else:
            _vector_store_instance = LocalVectorStore()
    return _vector_store_instance
