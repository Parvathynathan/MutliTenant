import os
import uuid
from pathlib import Path
from typing import Annotated

import ollama
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http import models


COLLECTION_NAME = "multitenant_rag_kb"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.2"
VECTOR_DIMENSION = 768
STORAGE_DIR = Path(__file__).resolve().parent.parent / "qdrant_test_storage"

app = FastAPI(title="Multi-Tenant RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

qdrant = QdrantClient(path=str(STORAGE_DIR))
if not qdrant.collection_exists(COLLECTION_NAME):
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=VECTOR_DIMENSION,
            distance=models.Distance.COSINE,
        ),
    )
    qdrant.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="tenant_id",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )


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


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [
        ollama.embeddings(model=EMBEDDING_MODEL, prompt=text)["embedding"]
        for text in texts
    ]


def extract_text(upload: UploadFile) -> str:
    if upload.filename and upload.filename.lower().endswith(".pdf"):
        return "".join(page.extract_text() or "" for page in PdfReader(upload.file).pages)
    return upload.file.read().decode("utf-8", errors="replace")


def tenant_filter(tenant_id: str) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value=tenant_id),
            )
        ]
    )


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
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    results: list[dict[str, int | str]] = []
    for upload in uploads:
        filename = upload.filename or "Untitled document"
        raw_text = extract_text(upload)
        if not raw_text.strip():
            results.append({"filename": filename, "indexed_chunks": 0, "status": "skipped"})
            continue

        chunks = splitter.split_text(raw_text)
        embeddings = embed_texts(chunks)
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "tenant_id": tenant_id,
                    "filename": filename,
                    "text": chunk,
                },
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        results.append({"filename": filename, "indexed_chunks": len(points), "status": "indexed"})

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
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=tenant_filter(tenant_id),
        limit=payload.top_k,
    ).points
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
