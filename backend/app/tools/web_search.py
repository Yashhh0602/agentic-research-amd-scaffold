"""
Web search tool used by the Executor agent, backed by Tavily's API
(built for LLM agent tool-calling, includes an "answer" summary + sources).
"""

import httpx

from app.core.config import settings

TAVILY_URL = "https://api.tavily.com/search"


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Returns a list of {"title": str, "url": str, "snippet": str}.
    """
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY not set in .env")

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(TAVILY_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        }
        for r in data.get("results", [])
    ]