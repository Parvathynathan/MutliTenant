from pathlib import Path


COLLECTION_NAME = "multitenant_rag_kb"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.2"
VECTOR_DIMENSION = 768
STORAGE_DIR = Path(__file__).resolve().parent.parent / "qdrant_test_storage"