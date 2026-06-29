# API Reference

The Enterprise Knowledge Assistant exposes a JSON REST API via FastAPI.
Interactive docs are available at `http://localhost:8000/docs` (Swagger UI)
and `http://localhost:8000/redoc` when the API is running.

This document covers the endpoints, request/response shapes, and example
`curl` commands.

---

## Base URL

```
http://localhost:8000
```

All endpoints return `application/json`. Error responses follow a
consistent shape (see Error responses below).

---

## Endpoints

### POST /ask

Ask a question against the indexed documents.

**Request body:**

```json
{
  "query": "What is the maximum password length?"
}
```

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `query` | string | yes | 1--2000 characters |

**Response:**

```json
{
  "answer": "The maximum password length is 128 characters according to section 4.2.",
  "citations": [
    {
      "document": "it-security-guidelines.pdf",
      "page": 11,
      "section": "Password Policy",
      "chunk_id": "a1b2c3d4"
    }
  ],
  "confidence_band": "High",
  "confidence_percent": 84.2,
  "processing_time_ms": 1340.5,
  "is_refusal": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Generated answer text |
| `citations` | array | Chunks cited by the answer |
| `confidence_band` | string | `High`, `Medium`, or `Low` |
| `confidence_percent` | float | 0--100; derived from rerank + similarity |
| `processing_time_ms` | float | End-to-end latency in milliseconds |
| `is_refusal` | bool | `true` when confidence is below the floor |

**Refusal response (confidence below floor):**

```json
{
  "answer": "I was unable to find relevant information in the indexed documents.",
  "citations": [],
  "confidence_band": "Low",
  "confidence_percent": 0.0,
  "processing_time_ms": 42.1,
  "is_refusal": true
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is the notice period for resignation?"}'
```

---

### POST /rebuild-index

Re-index all PDFs in the raw document directory. Existing index is
cleared first (idempotent).

**Request body:** none.

**Response:**

```json
{
  "total_chunks": 1423,
  "documents": ["employee-handbook.pdf", "it-security-guidelines.pdf"],
  "elapsed_ms": 4820.3
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total_chunks` | int | Total chunks written to the FAISS index |
| `documents` | array | Document filenames that were indexed |
| `elapsed_ms` | float | Time to complete the rebuild |

**Example:**

```bash
curl -X POST http://localhost:8000/rebuild-index
```

---

### GET /health

Shallow health check. Returns the status of the vector store and the
LLM client. Does not make a live Groq API call.

**Response:**

```json
{
  "status": "ok",
  "vector_store": {
    "status": "ok",
    "message": "Index contains 1423 chunks"
  },
  "llm": {
    "status": "ok",
    "message": "Client initialised"
  },
  "timestamp": "2026-06-29T10:00:00+00:00"
}
```

Status values: `ok`, `degraded`, `error`. Overall `status` is the
worst of the component statuses.

**Example:**

```bash
curl http://localhost:8000/health
```

---

### GET /metrics

Request latency metrics for the main API operations.

**Response:**

```json
{
  "ask": {
    "count": 42,
    "p50_ms": 1210.0,
    "p95_ms": 3800.0
  },
  "rebuild": {
    "count": 3,
    "p50_ms": 4500.0,
    "p95_ms": 6200.0
  }
}
```

Metrics are in-memory and reset when the API process restarts.

**Example:**

```bash
curl http://localhost:8000/metrics
```

---

## Error responses

All errors return a JSON body with a `detail` field:

```json
{
  "detail": "Human-readable error description"
}
```

| HTTP status | Meaning |
|-------------|---------|
| 400 | Invalid request (query too long, missing field) |
| 422 | Ingestion failed (malformed PDF, OCR error) |
| 500 | Internal server error (stack trace in logs, not in response) |
| 502 | LLM call failed (Groq error or rate limit) |
| 503 | Index not ready (no documents indexed yet) |

---

## Correlation IDs

Every response includes an `X-Correlation-ID` header. If you supply
your own `X-Correlation-ID` on the request, it is echoed back and
appears in all log entries for that request. Useful for tracing a
specific query through the logs.

```bash
curl -H 'X-Correlation-ID: my-trace-id' \
     -X POST http://localhost:8000/ask \
     -H 'Content-Type: application/json' \
     -d '{"query": "test"}'
```
