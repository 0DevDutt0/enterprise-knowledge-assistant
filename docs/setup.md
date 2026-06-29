# Setup Guide

Full environment setup for the Enterprise Knowledge Assistant. Covers
Python, dependencies, CUDA (optional), Tesseract, and first-run
verification.

---

## 1. Python

The project targets Python 3.11. Use pyenv, conda, or your system
package manager to install it.

```bash
python3.11 --version   # should print Python 3.11.x
```

---

## 2. Clone and create a virtual environment

```bash
git clone <repo>
cd enterprise-knowledge-assistant

python3.11 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
```

---

## 3. Install Python dependencies

### CPU-only (default)

```bash
pip install -r requirements.txt
```

### GPU (CUDA 12.8 -- Blackwell / Ada Lovelace / Ampere)

Install the CUDA 12.8 build of PyTorch first, then install the rest
of the requirements:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```

> **Why CUDA 12.8 and not 13.x?** The BGE models run on sentence-
> transformers, which uses PyTorch. As of the writing of this guide,
> PyTorch's CUDA 13 build was not yet stable enough for the Blackwell
> (sm_120) architecture. The CUDA 12.8 build works. If you are on an
> older GPU (Ampere/Ada), this also works.

After installing, verify CUDA is visible:

```python
import torch
print(torch.cuda.is_available())   # True
print(torch.cuda.get_device_name(0))
```

Set `DEVICE=cuda` in your `.env` to enable GPU inference for the
embedder and reranker.

---

## 4. Tesseract OCR (optional)

Tesseract is only used for scanned PDFs (images with no selectable
text). If all your documents are digital PDFs, you can skip this.

### macOS

```bash
brew install tesseract
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install tesseract-ocr
tesseract --version
```

### Windows

Download the UB-Mannheim installer:
`https://github.com/UB-Mannheim/tesseract/wiki`

After installation, add the install directory to `PATH` or set the
path explicitly in `.env`:

```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Disable OCR entirely

If you do not need OCR and do not want to install Tesseract, set:

```
OCR_ENABLED=false
```

Scanned PDFs will yield zero chunks and a warning instead of an error.

---

## 5. Environment configuration

```bash
cp .env.example .env
```

Open `.env` and fill in:

```
GROQ_API_KEY=gsk_...
```

Everything else has working defaults. See `.env.example` for the full
list with explanations.

**Required field:** `GROQ_API_KEY` -- get one free at
`https://console.groq.com`.

---

## 6. Create data directories

```bash
mkdir -p data/raw data/processed data/vector_store
```

These are gitignored. The API will create them on first run if they are
absent, but creating them manually avoids a startup warning.

---

## 7. Verify the installation

```bash
# Settings load correctly
python -c "from app.config.settings import settings; print('OK:', settings.groq_model)"

# Tests pass (no API key needed, no GPU needed)
pytest

# API boots
uvicorn main:app --reload
# visit http://localhost:8000/docs
```

---

## 8. First run

1. Start the API: `uvicorn main:app --reload`
2. Start the UI: `streamlit run streamlit_app.py`
3. Open `http://localhost:8501`
4. Upload a PDF using the Admin tab
5. Click **Rebuild Index** (this downloads the BGE models on first run
   -- allow a few minutes)
6. Switch to the Ask tab and type a question

> **First-run model download.** The BGE embedding and reranker models
> are downloaded from HuggingFace on first use and cached in
> `~/.cache/huggingface`. On a clean machine this takes a few minutes
> depending on connection speed:
> - `bge-base-en-v1.5`: ~440 MB
> - `bge-reranker-base`: ~360 MB

---

## 9. WSL2 notes (Windows CUDA users)

If running in WSL2 with CUDA:

- Requires WSL2 2.7.0 or later for CUDA graph capture support.
- Install NVIDIA drivers on the Windows host only; do not install
  drivers inside WSL2.
- `nvidia-smi` inside WSL2 should show the GPU.
- The PyTorch CUDA 12.8 install above applies inside WSL2 as well.
