# Deployment Guide

Options for running the Enterprise Knowledge Assistant beyond local
development.

---

## Local development (default)

See `docs/setup.md` for the full environment setup.

```bash
# Terminal 1 -- API
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 -- UI
streamlit run streamlit_app.py
```

The `--reload` flag restarts the API on code changes. Do not use it in
production.

---

## Production local (no reload)

```bash
# API with multiple workers
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2

# UI (Streamlit manages its own workers)
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

> **Note on workers:** the FAISS index is held in memory. With multiple
> Uvicorn workers, each worker loads its own copy of the index.
> If you rebuild the index from one worker, the other workers continue
> serving the old index until they restart. For a single-machine
> deployment, `--workers 1` avoids this inconsistency.

---

## Docker (sketch)

A `Dockerfile` is not included in the current release. The following
sketch is provided for teams that want to containerise the API.

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download the BGE models at build time to avoid cold starts
RUN python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer('BAAI/bge-base-en-v1.5')
CrossEncoder('BAAI/bge-reranker-base')
"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`docker-compose.yml` (API + UI):**

```yaml
version: "3.9"
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/app/data

  ui:
    build: .
    command: streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
    ports:
      - "8501:8501"
    environment:
      - API_BASE_URL=http://api:8000
    depends_on:
      - api
```

Mount `./data` as a volume so the FAISS index and raw PDFs persist
across container restarts.

---

## Cloud deployment (notes)

The API and UI are stateless except for the persisted FAISS index in
`data/vector_store/`. The main deployment consideration is how to share
that directory.

### Single VM

The simplest path: deploy API and UI on one VM, store `data/` on the
local disk. Use `systemd` or `supervisord` to keep the processes alive.

### Separate API and UI containers

Mount `data/` from a shared network volume (NFS, EFS on AWS, Azure
Files). Both services see the same index.

### Model download at startup

If the HuggingFace model cache (`~/.cache/huggingface`) is not
pre-populated, the first startup will download ~800 MB of model weights.
Bake them into the Docker image (see the `RUN python -c` step above)
to avoid cold-start delays.

### Environment variables

All configuration is injected via environment variables. Most cloud
platforms (AWS ECS, Google Cloud Run, Azure Container Apps, Fly.io)
support environment variable injection directly or via secrets managers.
Do not bake `.env` into the Docker image.

### GROQ_API_KEY security

Store `GROQ_API_KEY` in the platform's secrets manager (AWS Secrets
Manager, GCP Secret Manager, HashiCorp Vault) and inject it at runtime.
Never hardcode it in source or image layers.

---

## Reverse proxy (nginx)

If you expose the API behind nginx:

```nginx
server {
    listen 80;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;   # LLM calls can be slow
    }

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Set `CORS_ORIGINS` in `.env` to the public-facing domain instead of
`http://localhost:8501`.

Set `API_BASE_URL` in `.env` to the public API URL so the Streamlit
process reaches the correct endpoint.
