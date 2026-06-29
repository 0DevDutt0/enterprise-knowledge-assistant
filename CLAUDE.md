# CLAUDE.md — Enterprise Knowledge Assistant

This file is the source of truth for Claude Code working on this repo. Read it
fully before touching code. Read the referenced docs (PLAN, ARCHITECTURE, SPEC,
EVALUATION) before starting any module.

---

## 1. What this project is

A production-oriented Enterprise Knowledge Assistant: a Retrieval-Augmented
Generation system over uploaded PDFs that produces grounded, cited answers with
confidence scores. Backend in FastAPI, frontend in Streamlit, retrieval over
FAISS with cross-encoder re-ranking, generation via Groq.

This is **not** a tutorial project. The architecture, code quality, and
documentation must read like an internal enterprise platform an engineering
team would ship.

---

## 2. Required reading order (do not skip)

1. `SPEC.md` — the assignment requirements, distilled into an acceptance checklist.
2. `ARCHITECTURE.md` — module boundaries, data flow, dependency graph.
3. `PLAN.md` — phased build plan with per-module acceptance criteria.
4. `EVALUATION.md` — how the system is measured.

Treat these as authoritative. If a user instruction conflicts with them, stop
and ask before deviating.

---

## 3. Tech stack (locked)

| Layer            | Choice                                |
|------------------|---------------------------------------|
| Language         | Python 3.11                           |
| Orchestration    | LangChain                             |
| LLM              | Groq (latest high-quality free model) |
| Embeddings       | BAAI/bge-base-en-v1.5 (local)         |
| Re-ranker        | BAAI/bge-reranker-base (local)        |
| Vector store     | FAISS (persisted to disk)             |
| PDF parsing      | PyMuPDF (first), Tesseract (fallback) |
| API              | FastAPI                               |
| UI               | Streamlit                             |
| Config           | python-dotenv + pydantic-settings     |
| Validation       | Pydantic v2                           |
| Logging          | stdlib `logging` with JSON formatter  |

Do not introduce new top-level dependencies without flagging it explicitly in
the response and updating `requirements.txt` and `ARCHITECTURE.md`.

---

## 4. Coding conventions (non-negotiable)

These are personal conventions enforced across every file in this repo. Treat
violations as bugs.

1. **File path comment on line 1.** Every Python source file begins with a
   single-line comment containing its repo-relative path, e.g.
   `# app/rag/retrieval/retriever.py`. No blank line before it.
2. **Single quotes everywhere in Python.** Use `'...'` for all strings except
   when the string itself contains a single quote, in which case use `"..."`.
   Docstrings use triple double quotes (`"""..."""`) — this is the only
   exception.
3. **No argparse.** CLI entry points use interactive `input()` inside a
   `while True:` loop with a clear menu. Loop exits on an explicit `quit`
   option, not on Ctrl-C.
4. **ASCII only in source files.** No smart quotes, em dashes, ellipsis
   characters, arrows, or emoji in `.py` files. Markdown docs may use Unicode.
5. **Complete files only.** When asked to modify a file, always emit the full
   file contents. Never emit diffs, partial snippets, or `# ... rest of file
   unchanged` placeholders.
6. **Type hints on every function signature.** Including return types. Use
   `from __future__ import annotations` at the top of every module.
7. **Docstrings on every public function, class, and module.** Google style.
   One-line summary, blank line, then details if needed.
8. **No print() in library code.** Use the configured logger. `print()` is
   allowed only inside Streamlit pages and the CLI menu loops.
9. **No bare except.** Always catch a specific exception class.
10. **Imports grouped and sorted:** stdlib, third-party, local. One blank line
    between groups.

---

## 5. Architectural principles

- **Separation of concerns.** No module imports from a layer above it. Order
  from bottom to top: `utils` → `models` → `config` → domain packages
  (`ingestion`, `rag`, `evaluation`) → `services` → `api` / `ui`.
- **Configuration is injected, never imported globally.** A single
  `Settings` Pydantic model is loaded once at startup and passed down. No
  module reads `os.environ` directly except `config/settings.py`.
- **Pure functions wherever feasible.** Pipeline stages (chunker, embedder,
  retriever, reranker) take inputs and return outputs without mutating shared
  state.
- **Interfaces over implementations.** Vector store, embedder, LLM, and
  reranker each have a thin abstract base class so they can be swapped
  (Qdrant later, OpenAI embeddings later, etc). The factory lives in
  `services/`.
- **Fail loudly at startup, gracefully at runtime.** Missing API keys or
  models → crash on boot with a clear message. Per-request failures → return
  a structured error response, never a 500 stack trace to the user.

---

## 6. Project layout

```
enterprise-knowledge-assistant/
├── app/
│   ├── api/                  # FastAPI routers, schemas, middleware
│   ├── ui/                   # Streamlit pages and components
│   ├── ingestion/
│   │   └── document_processing/  # PyMuPDF, OCR, element classification
│   ├── rag/
│   │   ├── retrieval/        # Embedder, vector store, retriever, reranker
│   │   ├── generation/       # Prompt builder, LLM client, answer assembler
│   │   └── prompts/          # Prompt templates as .md or .txt
│   ├── evaluation/           # Benchmark runner, metrics
│   ├── config/               # Settings, logging config
│   ├── models/               # Pydantic domain models (DocumentElement, Chunk, Answer)
│   ├── services/             # Orchestration, factories, dependency wiring
│   ├── utils/                # Pure helpers (text cleaning, hashing, timing)
│   └── middleware/           # Request logging, error handling
├── scripts/                  # Index rebuild, eval runs, smoke tests
├── tests/                    # Pytest, mirrors app/ structure
├── docs/                     # Architecture diagrams, design notes, ADRs
├── data/
│   ├── raw/                  # Uploaded PDFs (gitignored)
│   ├── processed/            # Extracted elements (gitignored)
│   └── vector_store/         # Persisted FAISS index (gitignored)
├── main.py                   # FastAPI entrypoint
├── streamlit_app.py          # Streamlit entrypoint
├── requirements.txt
├── .env.example
├── README.md
├── CLAUDE.md                 # this file
├── SPEC.md
├── PLAN.md
├── ARCHITECTURE.md
└── EVALUATION.md
```

---

## 7. Working agreement with Claude Code

- **Plan before coding.** For every new module, first state the public
  interface (function signatures, classes, return types), the test plan, and
  the acceptance criteria from `PLAN.md`. Wait for confirmation before
  implementing if the scope is non-trivial.
- **One module at a time.** Do not jump ahead in `PLAN.md`. Finish a phase,
  run its tests, then move on.
- **Tests live with the code.** Every new module ships with at least one
  pytest test. Tests should not require network access or GPU.
- **Documentation is part of done.** When a module is complete, update any
  docs in `docs/` that reference it. If a design decision was made, write an
  ADR (architecture decision record) at `docs/adr/NNNN-title.md`.
- **No silent scope expansion.** If implementing a module requires something
  not in `PLAN.md`, surface it before writing code.

---

## 8. Things to never do

- Never hardcode model names, paths, chunk sizes, or top-K values in code.
  All tunables live in `config/settings.py` and are sourced from `.env`.
- Never write to `data/` from inside `app/`. Ingestion writes; retrieval
  reads. Scripts in `scripts/` are the only place that triggers rebuilds.
- Never call the LLM from `retrieval/`. Generation is a separate stage.
- Never store API keys, file paths from a user's machine, or PII in logs.
  Log message IDs and document hashes, not raw content.
- Never commit `data/` contents, `.env`, or `*.faiss` files.
- Never fabricate a citation in the answer. If retrieval returns nothing
  above the confidence floor, the system answers with the canonical
  unavailable-information message defined in `prompts/system_prompt.md`.

---

## 9. Definition of done (per module)

A module is done when all of the following are true:

1. Code conforms to the conventions in section 4.
2. Public interface matches what was agreed in the planning step.
3. Pytest tests pass and cover the happy path plus at least one failure mode.
4. Module is referenced from `ARCHITECTURE.md` and any new tunables are in
   `.env.example` and `config/settings.py`.
5. A short note added to `PLAN.md` marking the phase complete with the
   commit/branch reference.

---

## 10. Hardware notes (developer machine)

Devdutt's workstation runs an RTX 5090 Laptop (Blackwell, sm_120, 24GB
VRAM) on WSL2. If GPU acceleration is enabled for embeddings or reranking:

- PyTorch must be the CUDA 12.8 build (not 13.x — Blackwell support
  requirements). Document this in `README.md` setup section.
- WSL2 2.7.0+ is required for CUDA graph capture.
- The system must still run end-to-end on CPU. GPU is a speedup, not a
  requirement. Default device in `config/settings.py` is `cpu`; users opt
  into `cuda` via `.env`.
