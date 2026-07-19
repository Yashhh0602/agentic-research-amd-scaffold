"""
Web search tool used by the Executor agent.

TODO: wire a real search API. Options, pick one based on what's free/available
when you get to this:
  - Tavily (has a generous free tier, built for LLM agents specifically)
  - SerpAPI
  - Brave Search API
Keep the function signature stable so ExecutorAgent doesn't need changes
regardless of which provider you pick.
"""

import httpx


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Returns a list of {"title": str, "url": str, "snippet": str}.
    Currently a placeholder — raises NotImplementedError so it fails loudly
    instead of silently returning fake data once wired into the real pipeline.
    """
    raise NotImplementedError(
        "web_search not wired yet — pick a provider (Tavily recommended) and implement here"
    )
