"""
Ingestion script: fetches ROCm doc pages, chunks them, embeds via Ollama,
and writes to document_chunks. Run manually whenever the source list changes.

Usage:
    python scripts/ingest.py

Requires: httpx, beautifulsoup4, sqlalchemy, pgvector, psycopg2-binary
Run from a context where DATABASE_URL and OLLAMA_BASE_URL are set (source
your .env, or run inside the backend container).
"""

import os
import re
import sys

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# --- fill this in with your final page list ---
SOURCES = [
    "https://rocm.docs.amd.com/projects/HIP/en/docs-7.2.0/how-to/hip_porting_guide.html",
    "https://rocm.docs.amd.com/projects/HIP/en/latest/understand/programming_model.html",
    "https://rocm.docs.amd.com/projects/HIP/en/latest/how-to/hip_runtime_api/memory_management/coherence_control.html",
    "https://rocm.docs.amd.com/projects/HIP/en/latest/how-to/hip_runtime_api/memory_management/host_memory.html",
    "https://rocm.docs.amd.com/projects/HIP/en/latest/how-to/hip_runtime_api/memory_management/device_memory.html",
    "https://rocm.docs.amd.com/projects/HIP/en/latest/how-to/hip_runtime_api/memory_management/unified_memory.html",
    "https://rocm.docs.amd.com/projects/HIP/en/latest/how-to/hip_runtime_api/memory_management/virtual_memory.html",
]
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://ara:ara_dev_pw@localhost:5433/ara_db"
)
# psycopg2 driver, not asyncpg, since this script runs sync/standalone
SYNC_DB_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"

CHUNK_SIZE = 800   # chars, not tokens -- rough approximation, fine for this scope
CHUNK_OVERLAP = 150


def fetch_and_clean(url: str) -> str:
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # strip nav/sidebar/footer chrome, keep main article content
    for tag in soup.select("nav, header, footer, script, style, .sidebar, .toctree-wrapper"):
        tag.decompose()

    main = soup.select_one("main, article, div[role='main'], .document") or soup
    text_content = main.get_text(separator="\n")
    text_content = re.sub(r"\n{3,}", "\n\n", text_content).strip()
    return text_content


def chunk_text(text_content: str, size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text_content):
        end = start + size
        chunks.append(text_content[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if len(c.strip()) > 50]


def embed(text_chunk: str) -> list[float]:
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text_chunk},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def main():
    if not SOURCES:
        print("SOURCES list is empty -- add page URLs before running.")
        sys.exit(1)

    engine = create_engine(SYNC_DB_URL)

    # create table if missing, matches db/models.py DocumentChunk schema
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id SERIAL PRIMARY KEY,
                source VARCHAR(512) NOT NULL,
                text TEXT NOT NULL,
                embedding VECTOR(768)
            )
        """))

    total_chunks = 0
    with Session(engine) as session:
        total_chunks = 0
    with Session(engine) as session:
        for url in SOURCES:
            existing = session.execute(
                text("SELECT COUNT(*) FROM document_chunks WHERE source = :source"),
                {"source": url},
            ).scalar()
            if existing:
                print(f"Skipping {url} ({existing} chunks already exist)")
                continue

            print(f"Fetching {url}")
            try:
                page_text = fetch_and_clean(url)
            except Exception as e:
                print(f"  FAILED to fetch: {e}")
                continue
        for url in SOURCES:
            print(f"Fetching {url}")
            try:
                page_text = fetch_and_clean(url)
            except Exception as e:
                print(f"  FAILED to fetch: {e}")
                continue

            chunks = chunk_text(page_text, CHUNK_SIZE, CHUNK_OVERLAP)
            print(f"  {len(chunks)} chunks")

            for chunk in chunks:
                vec = embed(chunk)
                session.execute(
                    text(
                        "INSERT INTO document_chunks (source, text, embedding) "
                        "VALUES (:source, :text, :embedding)"
                    ),
                    {"source": url, "text": chunk, "embedding": str(vec)},
                )
                total_chunks += 1

        session.commit()

    print(f"Done. Ingested {total_chunks} chunks from {len(SOURCES)} sources.")


if __name__ == "__main__":
    main()