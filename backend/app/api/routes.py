"""
API layer.

Two ways to run a query:
  POST /api/query          -> simple request/response, waits for full answer
  WS   /api/query/stream    -> streams AgentEvents live as they happen, this
                                is what the frontend's live trace panel and
                                sequential/concurrent toggle actually use

Both paths go through the same orchestrator.run(), so there's no separate
"demo mode" — what you see in the trace panel is exactly what's driving
the benchmark numbers.
"""

from dataclasses import asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.agents.base import AgentEvent
from app.core.orchestrator import RunSummary, orchestrator

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    mode: str = "sequential"  # "sequential" | "concurrent"


class QueryResponse(BaseModel):
    answer: str
    mode: str
    total_latency_seconds: float
    agent_breakdown: list[dict]


@router.post("/api/query", response_model=QueryResponse)
async def run_query(req: QueryRequest) -> QueryResponse:
    summary: RunSummary | None = None
    async for item in orchestrator.run(req.query, mode=req.mode):
        if isinstance(item, RunSummary):
            summary = item

    assert summary is not None
    return QueryResponse(
        answer=summary.final_answer,
        mode=summary.mode,
        total_latency_seconds=round(summary.total_latency_seconds, 3),
        agent_breakdown=[
            {
                "agent": r.agent_name,
                "latency_seconds": round(r.latency_seconds, 3),
                "tokens_per_second": r.tokens_per_second,
            }
            for r in summary.agent_results
        ],
    )


@router.websocket("/api/query/stream")
async def stream_query(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        init = await websocket.receive_json()
        query = init["query"]
        mode = init.get("mode", "sequential")

        async for item in orchestrator.run(query, mode=mode):
            if isinstance(item, AgentEvent):
                await websocket.send_json({"type": "event", **asdict(item)})
            elif isinstance(item, RunSummary):
                await websocket.send_json(
                    {
                        "type": "summary",
                        "mode": item.mode,
                        "total_latency_seconds": round(item.total_latency_seconds, 3),
                        "final_answer": item.final_answer,
                        "agent_breakdown": [
                            {
                                "agent": r.agent_name,
                                "latency_seconds": round(r.latency_seconds, 3),
                                "tokens_per_second": r.tokens_per_second,
                            }
                            for r in item.agent_results
                        ],
                    }
                )
    except WebSocketDisconnect:
        pass
