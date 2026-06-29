# app/config/settings.py
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All tunables live here. The instance is constructed once at startup and
    injected into every module that needs it. No module reads os.environ directly
    except this one.
    """

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # LLM (Groq)
    # ------------------------------------------------------------------
    groq_api_key: str = Field(..., description='Groq API key (required)')
    groq_model: str = Field('llama-3.3-70b-versatile', description='Groq model identifier')
    groq_timeout_seconds: int = Field(30, description='LLM call timeout in seconds')
    groq_max_retries: int = Field(2, description='Retries on transient Groq errors')

    # ------------------------------------------------------------------
    # Embeddings & reranking
    # ------------------------------------------------------------------
    embedding_model: str = Field('BAAI/bge-base-en-v1.5', description='HF embedding model name')
    reranker_model: str = Field('BAAI/bge-reranker-base', description='HF cross-encoder model name')
    device: str = Field('cpu', description='"cpu" or "cuda" for local models')
    embedding_batch_size: int = Field(32, description='Embedder batch size')

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------
    chunk_size: int = Field(800, description='Paragraph chunk size in characters')
    chunk_overlap: int = Field(150, description='Paragraph chunk overlap in characters')

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    top_k_retrieval: int = Field(10, description='Candidates returned from vector search')
    top_k_rerank: int = Field(5, description='Survivors after cross-encoder reranking')
    confidence_floor: float = Field(
        -3.0,
        description='Rerank score below this triggers the canonical refusal instead of the LLM. '
        'CrossEncoder raw logits: positive = relevant, ~0 = uncertain, <-3 = irrelevant.',
    )

    # ------------------------------------------------------------------
    # Retrieval mode
    # ------------------------------------------------------------------
    retrieval_mode: str = Field(
        'semantic',
        description='"semantic" (FAISS only) or "hybrid" (BM25 + FAISS via RRF). '
        'Hybrid improves recall on exact-match queries (names, codes, IDs).',
    )
    rrf_k: int = Field(
        60,
        description='Reciprocal Rank Fusion constant k. Higher values reduce the '
        'advantage of very high-ranked results. Default 60 is standard.',
    )

    # ------------------------------------------------------------------
    # Query rewriting
    # ------------------------------------------------------------------
    query_rewriting_enabled: bool = Field(
        False,
        description='Use the LLM to rewrite queries before retrieval. '
        'Improves recall on vague or pronoun-heavy inputs at the cost of one '
        'extra Groq API call per query. Disable to reduce latency.',
    )
    query_rewrite_template_path: str = Field(
        'app/rag/prompts/query_rewrite_prompt.md',
        description='Path to the query rewrite prompt template (relative to repo root).',
    )

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    prompt_template_path: str = Field(
        'app/rag/prompts/system_prompt.md',
        description='Path to the system prompt template (relative to repo root)',
    )
    max_context_chars: int = Field(
        4000,
        description='Maximum characters of retrieved context included in the LLM prompt',
    )
    max_history_turns: int = Field(
        5,
        description='Maximum number of prior conversation turns injected into the LLM '
        'prompt. Older turns are dropped silently. Set to 0 to disable history injection.',
    )

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------
    ocr_enabled: bool = Field(True, description='Enable Tesseract OCR fallback for scanned PDFs')
    tesseract_cmd: str = Field('', description='Override Tesseract binary path if not on PATH')

    # ------------------------------------------------------------------
    # Storage paths
    # ------------------------------------------------------------------
    data_dir: str = Field('data', description='Root data directory')
    raw_dir: str = Field('data/raw', description='Uploaded PDF storage')
    processed_dir: str = Field('data/processed', description='Extracted element storage')
    vector_store_dir: str = Field('data/vector_store', description='Persisted FAISS index')

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    api_host: str = Field('0.0.0.0', description='FastAPI bind host')
    api_port: int = Field(8000, description='FastAPI bind port')
    cors_origins: str = Field(
        'http://localhost:8501',
        description='Comma-separated CORS origins',
    )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    api_base_url: str = Field('http://localhost:8000', description='API URL used by the Streamlit UI')

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field('INFO', description='DEBUG | INFO | WARNING | ERROR')
    log_format: str = Field('json', description='"json" or "text"')


settings = Settings()
