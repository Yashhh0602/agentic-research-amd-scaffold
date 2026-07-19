"""
DB models. Only one table for now: document_chunks, which is what the
Retriever agent queries.

EMBEDDING_DIM: set this to match whatever embedding model you pick.
  - nomic-embed-text (Ollama)        -> 768
  - mxbai-embed-large (Ollama)       -> 1024
  - Qwen/Qwen3-Embedding or similar via vLLM -> check model card
Pick one and set this before running the ingestion script — changing it
later means re-embedding everything.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 768  # TODO: confirm against chosen embedding model


class Base(DeclarativeBase):
    pass


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
