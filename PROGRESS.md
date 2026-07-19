# Build Progress — Agentic Research Assistant (AMD DevMaster Track 2)

Last updated: Step 3 (full backend skeleton runnable end-to-end with placeholder
logic — DB models, tool stubs, API, main.py all done. Frontend not started.)

## Context for whoever picks this up
- Hackathon: AMD AI DevMaster, Track 2 (Agentic AI), deadline Aug 6 2026.
- Project: multi-agent research assistant. 4 agents — Retriever (pgvector),
  Reasoning (query decomposition), Executor (tools: web search, code exec, APIs),
  Synthesizer (final answer + citations).
- Stack: FastAPI backend, Next.js 14 frontend, Postgres+pgvector, Redis, vLLM-ROCm
  on AMD Radeon Cloud pod (image: vllm-dev:rocm7.2.1_navi_ubuntu22.04_py3.10_pytorch_2.9_vllm_0.16.0).
  Local dev machine has NO usable GPU (Ryzen 3 4300U integrated graphics) — all
  local work is CPU-mode / logic-only. Real GPU work happens only on the pod.
- Key differentiator vs competitor reference (RepoMind, a coding-assistant repo
  we studied for calibration, NOT something we're building on): our ROCm story
  is SEQUENTIAL vs CONCURRENT multi-agent execution (agents waiting on GPU
  between each other vs batched/parallel), not just single-model throughput.
  Second differentiator: mixed model routing — small model for
  Retriever/Reasoning, larger model only for Synthesizer.
- User preferences: no em dashes, avoid AI-sounding phrasing, keep responses
  concise. User's dev environment: WSL on Windows.
- LLM backend must be swappable via env var: `LLM_BACKEND=ollama` (local CPU
  dev, functional testing) or `LLM_BACKEND=vllm` (pod, OpenAI-compatible
  endpoint from `vllm serve`).

## Done so far
- [x] `docker-compose.yml` — postgres(pgvector), redis, ollama, backend, frontend services
- [x] `backend/Dockerfile`
- [x] Repo directory structure created
- [x] `backend/requirements.txt`
- [x] `backend/app/core/config.py` — Settings (env-driven, pydantic-settings, LLM_BACKEND switch)
- [x] `backend/app/core/llm_client.py` — unified client (Ollama + vLLM/OpenAI-compatible),
      captures latency + tokens/sec on every call (feeds proofs/ later)
- [x] `backend/app/agents/base.py` — BaseAgent, AgentEvent, AgentResult (event-streaming
      design so live trace panel and benchmark numbers share one code path)
- [x] `backend/app/agents/retriever.py` — stub, pgvector wiring pending DB layer
- [x] `backend/app/agents/reasoning.py` — stub, uses SMALL model, real prompt pending
- [x] `backend/app/agents/executor.py` — stub, tool wiring pending app/tools/
- [x] `backend/app/agents/synthesizer.py` — stub, uses LARGE model (mixed routing story)
- [x] `backend/app/core/orchestrator.py` — BOTH sequential and concurrent modes implemented.
      Concurrent mode runs Retriever+Reasoning in parallel (real dependency graph, not
      fake concurrency), then Executor, then Synthesizer. This IS the benchmark toggle.

- [x] `backend/app/db/models.py` — DocumentChunk model w/ pgvector column
      (EMBEDDING_DIM=768 placeholder, MUST confirm against chosen embedding
      model before running ingestion — see TODO comment in file)
- [x] `backend/app/db/session.py` — async SQLAlchemy session
- [x] `backend/app/tools/web_search.py` — stub, raises NotImplementedError
      (recommend Tavily API when implementing — good free tier, built for agents)
- [x] `backend/app/tools/code_exec.py` — stub, raises NotImplementedError.
      IMPORTANT: has a security note in the docstring, do not implement with
      raw exec()/eval() — must be sandboxed (Docker container, no network,
      resource/time limits). Read that docstring before implementing.
- [x] `backend/app/api/routes.py` — POST /api/query (simple) + WS
      /api/query/stream (live trace, what frontend actually uses)
- [x] `backend/app/main.py` — FastAPI entrypoint
- [x] `.env.example`

## Backend is runnable end-to-end right now (with placeholder data)
You can `docker compose up` (once .env exists) and POST to /api/query and
get a real response through all 4 agents — retrieval and tools return
placeholder text, but the orchestration, event streaming, and both
sequential/concurrent modes actually work. Good checkpoint to verify before
moving on: pull an Ollama model (`docker exec ara_ollama ollama pull qwen2.5:3b`
and the 7b one too) and hit the endpoint.

## In progress / next up (in order)
- [ ] Ingestion script: chunk + embed real documents into document_chunks table
      (needed before Retriever's placeholder can be replaced with real pgvector query)
- [ ] Wire Retriever agent to real pgvector query (depends on above)
- [ ] Implement web_search.py for real (pick Tavily or similar)
- [ ] Implement code_exec.py for real WITH sandboxing (see security note in file)
- [ ] Frontend (Next.js 14) — chat UI + live agent trace panel (consumes the
      WebSocket at /api/query/stream) + sequential/concurrent toggle switch
- [ ] `proofs/` folder structure + benchmark script (run same query both
      modes, log latency/tokens-per-sec/rocm-smi output, save to proofs/)
- [ ] `README.md` (architecture diagram, reproduce steps)
- [ ] Knowledge base seed content — user needs to decide domain + "hero demo
      query" (see earlier recommendation: pick this before building more,
      it shapes what documents/tools actually matter)
- [ ] .gitignore, push scaffold to github.com/Yashhh0602

## Decisions locked in (don't re-litigate these)
- vLLM primary for pod (platform's Dedicated Model API only supports vLLM anyway);
  Ollama kept as local dev + emergency fallback if vLLM-ROCm setup fails on pod.
- Persistent (PVC) storage on the pod, model dir under `/workspace/models`.
- Deploy Type on pod = Notebook (Jupyter/OpenCode), SSH access ON. NOT the
  "vLLM Model API" deploy type — that's reserved for later, isolated benchmarking only.
- Timeline: days 1-8 full pipeline working locally (CPU mode), days 9-16 pod +
  ROCm wiring + benchmarking + frontend polish, last 2 days demo video + README.
