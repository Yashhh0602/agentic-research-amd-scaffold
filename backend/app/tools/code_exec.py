"""
Code execution tool used by the Executor agent.

SECURITY NOTE — do not skip this when implementing:
This must NOT be a raw exec()/eval() on the query string. Recommended
approach: run in a separate, disposable Docker container (no network,
CPU/memory/time limits, non-root user), similar to how Jupyter kernels or
Claude Code's own sandboxing work. A quick starting point:
  - subprocess.run() into a minimal python:3.11-slim container via
    `docker run --rm --network=none --memory=256m --cpus=0.5 --timeout ...`
  - or a library like `restrictedpython` / `firejail` if a full container
    per call is too slow for the demo
Since this may run inside the AMD pod itself, keep it lightweight —
don't spin up nested heavyweight containers if pod resources are already
tight from vLLM.

TODO: implement with the sandboxing approach above before this is wired
into the real pipeline.
"""


async def execute_code(code: str, language: str = "python", timeout_seconds: int = 10) -> dict:
    """
    Returns {"stdout": str, "stderr": str, "exit_code": int}.
    Currently a placeholder — raises NotImplementedError so it fails loudly
    instead of silently running unsandboxed code.
    """
    raise NotImplementedError(
        "execute_code not wired yet — implement with proper sandboxing, see module docstring"
    )
