# Multi-Tenant RAG

A local multi-tenant knowledge assistant with a FastAPI backend, Qdrant local storage, Ollama embeddings/chat, and a React frontend.

## Structure

- `backend/main.py` - tenant-scoped ingest and query API
- `frontend/` - Vite + React TypeScript workspace UI
- `qdrant_test_storage/` - local vector data

## Run

Start Ollama first and make sure these models are available:

```powershell
ollama pull nomic-embed-text
ollama pull llama3.2
```

In one terminal from the repository root:

```powershell
.\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location frontend
npm run dev
```

Open `http://localhost:5173`. The API uses the `X-Tenant-ID` header to keep every query and upload isolated to the selected tenant.
