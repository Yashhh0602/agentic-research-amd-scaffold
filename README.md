# Agentic Research Assistant

A multi-agent research assistant built for the AMD AI DevMaster Hackathon (Track 2: Agentic AI). Four specialized agents collaborate to answer research questions by combining semantic search over a local knowledge base, tool use (web search, sandboxed code execution), and LLM synthesis, running on AMD ROCm hardware via vLLM.

Built for [AMD AI DevMaster Hackathon](https://lu.ma/amd-ai-devmaster), submission deadline Aug 6, 2026.

## Why this exists

Most agentic demos show one model doing plan → tool → observe → answer in a loop. This project asks a different question: **what happens when you have multiple agents with genuinely different jobs, and you have to decide how they share a GPU?**

That's not a hypothetical problem. A real agentic pipeline burns GPU time waiting between steps if agents run naively one after another. This project treats *agent scheduling* itself as the optimization target, not just single-model throughput.

## Architecture

Four agents, each with a distinct job:

| Agent | Job | Model size |
|---|---|---|
| **Retriever** | Semantic search over a pgvector knowledge base | none (DB-only) |
| **Reasoning** | Decomposes the query into sub-tasks, decides which tools are needed | small (3B) |
| **Executor** | Calls tools: web search (Tavily), sandboxed code execution | none / small |
| **Synthesizer** | Combines everything into a final, cited answer | large (7B, AWQ) |

**Dependency graph** (this is the real constraint, not an arbitrary choice):
- Retriever and Reasoning both only need the original query — no dependency on each other
- Executor needs Reasoning's plan
- Synthesizer needs everything
