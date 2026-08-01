import asyncio
from app.agents.retriever import RetrieverAgent
from app.agents.base import AgentResult

async def main():
    agent = RetrieverAgent()
    context = {"query": "What are the differences between ROCm's memory model and CUDA's, and what changes are needed to port a CUDA kernel to HIP?"}

    async for item in agent.run(context):
        if isinstance(item, AgentResult):
            for i, chunk in enumerate(item.output):
                print(f"--- chunk {i+1} ---")
                print(f"source: {chunk['source']}")
                print(f"text: {chunk['text'][:300]}")
                print()

asyncio.run(main())