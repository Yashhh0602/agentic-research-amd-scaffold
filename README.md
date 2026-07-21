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
| **Synthesizer** | Combines everything into a final, cited answer | large (14B) |

**Dependency graph** (this is the real constraint, not an arbitrary choice):
- Retriever and Reasoning both only need the original query — no dependency on each other
- Executor needs Reasoning's plan
- Synthesizer needs everything

```
SEQUENTIAL (naive):
Retriever -> Reasoning -> Executor -> Synthesizer
(each agent idles while the previous one runs)

CONCURRENT (optimized):
Retriever ─┐
           ├─> Executor -> Synthesizer
Reasoning ─┘
(Retriever + Reasoning run in parallel, real dependency graph respected downstream)
```

This is the core benchmark: same query, same hardware, sequential vs concurrent execution mode, real wall-clock time and GPU utilization compared. The mode is a live toggle in the UI, not just a config flag, so it can be demonstrated directly.

**Second optimization: mixed model-size routing.** Reasoning (routing/planning) runs on a small 3B model. Only Synthesizer, which produces the actual answer a user reads, uses a larger 14B model. This is a deliberate throughput/quality tradeoff, not a cost-cutting default applied everywhere.

### Stack

- **Backend:** FastAPI, async orchestrator, WebSocket streaming for live agent trace events
- **Frontend:** Next.js 14, live 4-lane agent trace panel, sequential/concurrent toggle
- **Retrieval:** PostgreSQL + pgvector, cosine similarity search
- **Inference:** vLLM on ROCm (AMD Radeon Cloud pod), swappable to Ollama for local CPU dev via `LLM_BACKEND` env var
- **Tools:** Tavily (web search), sandboxed subprocess execution with resource limits (code execution)
- **Containerization:** Docker Compose (postgres, redis, backend, frontend)

## Knowledge base

Scoped to AMD ROCm/HIP documentation — specifically the HIP porting guide, the HIP programming model, and the memory management docs (coherence control, host/device/unified/virtual memory). 7 source pages, 259 chunks, ingested via `scripts/ingest.py`.

This scope was chosen deliberately: "how do I port CUDA to HIP" and "how does HIP's memory model differ from CUDA's" are genuinely independent sub-questions, which makes them good material for demonstrating concurrent multi-agent execution rather than an artificially split single question.

## Running it locally

Requires Docker, Python 3.11+, and a `.env` file (copy `.env.example` and fill in).

```bash
git clone https://github.com/Yashhh0602/agentic-research-amd-scaffold
cd agentic-research-amd-scaffold
cp .env.example .env
# edit .env: set TAVILY_API_KEY, and LLM_BACKEND=ollama for local CPU dev
docker compose up
```

Frontend: `http://localhost:3001`
Backend health check: `http://localhost:8000/health`

**Local dev note:** the LLM backend is swappable. `LLM_BACKEND=ollama` runs inference against a local Ollama instance (CPU, works for logic testing, too slow for real synthesis quality on larger models). `LLM_BACKEND=vllm` points at a vLLM endpoint (see below), used for real GPU-backed inference.

## Running on AMD ROCm (vLLM)

1. Launch an AMD Radeon Cloud pod using the `ROCm vLLM-dev (Navi)` template
2. SSH in, serve a model:
   ```bash
   vllm serve Qwen/Qwen2.5-3B-Instruct --host 0.0.0.0 --port 8000
   ```
3. Tunnel the pod's port to your local machine:
   ```bash
   ssh -L 0.0.0.0:8001:localhost:8000 root@<pod-host> -p <pod-port>
   ```
4. Set in `.env`:
   ```
   LLM_BACKEND=vllm
   VLLM_BASE_URL=http://<your-local-lan-ip>:8001/v1
   ```
5. Restart the backend: `docker compose restart backend`

## Benchmarks

Run the benchmark scripts against a live vLLM endpoint on the AMD ROCm pod:

```bash
python scripts/benchmark.py --query "<hero query>" --runs 5
python scripts/throughput_benchmark.py --queries 5
```

Results are logged to `proofs/` as timestamped JSON, including `rocm-smi` output where available, so numbers here are reproducible, not hand-typed.

### Throughput under concurrent load: 2.54x

The strongest result: **5 different users asking 5 different questions simultaneously**, one-at-a-time vs all fired concurrently at the same vLLM endpoint.

| | Total time (5 queries) |
|---|---|
| One-at-a-time | 68.793s |
| Concurrent batch | 27.11s |
| **Speedup** | **2.54x** |

Being direct about what this does and doesn't show: individual query latency for any single user was not faster under concurrent load (in fact slightly worse for some queries, e.g. one query went from 21.7s solo to 25.6s concurrent) — that's expected, since GPU compute is shared across simultaneous requests. What improved is total system throughput: how many different users' questions this pipeline can serve per minute. That's the metric that matters for real deployment, where multiple people query the assistant at once rather than one person waiting alone. This result reflects vLLM's continuous batching doing real work on ROCm, not the multi-agent orchestration itself.

### Agent-level orchestration: sequential vs concurrent, 1.19x

Same query, same hardware, comparing the orchestrator's two execution modes (see Architecture above): Retriever+Reasoning running in parallel vs strictly one after another.

| | Mean total latency (5 runs) |
|---|---|
| Sequential | 13.184s |
| Concurrent | 11.09s |
| **Speedup** | **1.19x** |

This number is smaller than the throughput result, and that's expected, not a weak result to downplay: agent-level concurrency is bounded by real dependencies (Executor genuinely needs Reasoning's plan before it can start, Synthesizer genuinely needs everything). Only two of four agents (Retriever, Reasoning) have no dependency on each other, so there's a hard ceiling on how much this specific optimization can win by design, not by implementation gap. The two benchmarks together tell an honest story: orchestration-level concurrency gets a modest, dependency-bounded win, while request-level concurrency (multiple users) is where vLLM's batching shows its real strength.

**CPU (local, Ollama) baseline for reference:** sequential mean 6.581s vs concurrent mean 5.641s (1.17x speedup), consistent with the GPU agent-level result above. This was a pre-pod sanity check confirming the orchestration logic itself was correct before spending GPU-hours on it.

## Known limitations

Being direct about what this is and isn't:
- Local models (3B/14B class) are not frontier-model quality. The value proposition here is deployability, cost, and data privacy for an on-prem research assistant, not raw reasoning capability competing with hosted frontier models.
- GPU access for this project was constrained to 5 GPU-hours total (AMD hackathon credit allocation), which shaped how benchmark sessions were structured — deliberate short, focused runs rather than long exploratory sessions.
- `code_exec` sandboxing uses subprocess + resource limits, not full container isolation. Sufficient for this scope, not something to expose to untrusted input in production without further hardening.

## Project structure

```
backend/app/
  agents/         retriever, reasoning, executor, synthesizer
  core/           orchestrator, llm_client, config
  api/            FastAPI routes + WebSocket
  db/             SQLAlchemy models, pgvector
  tools/          web_search (Tavily), code_exec (sandboxed)
frontend/app/     Next.js chat UI + live agent trace panel
scripts/          ingest.py (knowledge base), benchmark.py
proofs/           benchmark run logs (JSON)
```