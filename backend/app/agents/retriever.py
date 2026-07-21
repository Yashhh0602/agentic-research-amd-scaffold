"""
Retriever Agent
Job: given the user query, semantic search the pgvector knowledge base and
return the top-k relevant chunks. Retrieval itself is a DB operation, not
an LLM call (beyond embedding the query), so this agent should stay fast.
"""
import time
from typing import Any, AsyncIterator
from sqlalchemy import text
from app.agents.base import AgentEvent, AgentResult, BaseAgent, EventType
from app.core.llm_client import llm_client
from app.db.session import async_session_maker
TOP_K = 5
class RetrieverAgent(BaseAgent):
    name = "retriever"
    async def run(self, context: dict[str, Any]) -> AsyncIterator[AgentEvent | AgentResult]:
        query = context["query"]
        start = time.perf_counter()
        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.STARTED,
            detail=f"Searching knowledge base for: {query}",
        )
        query_embedding = await llm_client.embed(query)
        async with async_session_maker() as session:
            result = await session.execute(
                text(
                    "SELECT text, source, embedding <=> CAST(:query_vec AS vector) AS distance "
                    "FROM document_chunks "
                    "ORDER BY distance ASC "
                    "LIMIT :top_k"
                ),
                {"query_vec": str(query_embedding), "top_k": TOP_K},
            )
            rows = result.fetchall()
        chunks = [
            {"text": row.text, "source": row.source, "distance": float(row.distance)}
            for row in rows
        ]
        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.FINISHED,
            detail=f"Found {len(chunks)} relevant chunks",
        )
        elapsed = time.perf_counter() - start
        context["retrieved_chunks"] = chunks
        yield AgentResult(agent_name=self.name, output=chunks, latency_seconds=elapsed)