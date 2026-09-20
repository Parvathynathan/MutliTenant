import uuid
from typing import Annotated

import ollama
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .chunking import chunk_text
from .config import LLM_MODEL, STORAGE_DIR
from .embedding import embed_texts
from .ingestion import extract_text
from .qdrant_store import QdrantStore

app = FastAPI(title="Multi-Tenant RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

qdrant_store = QdrantStore(STORAGE_DIR)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=10)


class QueryResponse(BaseModel):
    tenant_id: str
    query: str
    answer: str
    sources: list[str]


def get_tenant_id(x_tenant_id: Annotated[str | None, Header()] = None) -> str:
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(status_code=401, detail="A tenant is required.")
    return x_tenant_id.strip()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ingest")
def ingest_files(
    uploads: Annotated[list[UploadFile], File(alias="upload")],
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, int | str | list[dict[str, int | str]]]:
    if not uploads:
        raise HTTPException(status_code=422, detail="Select at least one document.")

    indexing_id = str(uuid.uuid4())
    results: list[dict[str, int | str]] = []
    for upload in uploads:
        filename = upload.filename or "Untitled document"
        raw_text = extract_text(upload)
        if not raw_text.strip():
            results.append({"filename": filename, "indexed_chunks": 0, "status": "skipped"})
            continue

        chunks = chunk_text(raw_text)
        embeddings = embed_texts(chunks)
        indexed_chunks = qdrant_store.upsert_chunks(
            tenant_id=tenant_id,
            filename=filename,
            chunks=chunks,
            embeddings=embeddings,
        )
        results.append({"filename": filename, "indexed_chunks": indexed_chunks, "status": "indexed"})

    return {
        "tenant_id": tenant_id,
        "indexing_id": indexing_id,
        "documents": len(results),
        "indexed_chunks": sum(int(result["indexed_chunks"]) for result in results),
        "results": results,
    }


@app.post("/api/query", response_model=QueryResponse)
def query_rag(
    payload: QueryRequest,
    tenant_id: str = Depends(get_tenant_id),
) -> QueryResponse:
    query_vector = embed_texts([payload.query])[0]
    results = qdrant_store.search(tenant_id, query_vector, payload.top_k)
    contexts = [hit.payload["text"] for hit in results if hit.payload and "text" in hit.payload]
    sources = sorted({
        hit.payload.get("filename", "Unknown")
        for hit in results
        if hit.payload
    })

    if not contexts:
        return QueryResponse(
            tenant_id=tenant_id,
            query=payload.query,
            answer="No relevant context found for this tenant.",
            sources=[],
        )

    prompt = (
        "Answer strictly from the context below. If the answer is not present, say you do not know.\n\n"
        f"Context:\n{chr(10).join(contexts)}\n\nQuestion: {payload.query}"
    )
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.0},
    )
    return QueryResponse(
        tenant_id=tenant_id,
        query=payload.query,
        answer=response["message"]["content"],
        sources=sources,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
