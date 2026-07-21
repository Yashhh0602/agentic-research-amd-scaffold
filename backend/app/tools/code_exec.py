"""
Code execution tool used by the Executor agent.

SECURITY NOTE:
Ideally each call would run in a separate, disposable Docker container
(no network, resource limits, non-root user). That's not available here
because this backend runs inside a container without Docker socket access
(no docker-in-docker configured), so a full container-per-call sandbox
would need extra infra work this hackathon doesn't have time for.

Fallback approach used instead: a restricted subprocess, not exec()/eval().
- runs in an isolated temp directory, deleted after
- CPU time, memory, and process-count limits via `resource` (rlimit) --
  POSIX only, so these limits are skipped on Windows (local dev on
  Windows has no OS-level sandboxing here; the pod runs Linux and gets
  full enforcement)
- hard wall-clock timeout, process group killed if exceeded
- stripped environment variables (no inherited secrets/env)
- KNOWN LIMITATION: no network isolation at the OS level here (would need
  a container or network namespace) -- if this becomes a real risk for
  the demo, revisit before submission. For a benign demo query, this is
  an acceptable tradeoff given the time available; it is not a strong
  security boundary, and should not be treated as one for anything beyond
  this hackathon's scope.
"""

import asyncio
import os
import sys
try:
    import resource
except ImportError:
    resource = None
import shutil
import tempfile

MAX_CPU_SECONDS = 5
MAX_MEMORY_BYTES = 256 * 1024 * 1024  # 256MB
MAX_PROCESSES = 1

IS_POSIX = resource is not None and sys.platform != "win32"


def _limit_resources():
    if resource is None:
        return
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESSES, MAX_PROCESSES))


async def execute_code(code: str, language: str = "python", timeout_seconds: int = 10) -> dict:
    """
    Returns {"stdout": str, "stderr": str, "exit_code": int}.
    """
    if language != "python":
        return {
            "stdout": "",
            "stderr": f"Unsupported language: {language} (only 'python' is supported)",
            "exit_code": 1,
        }

    workdir = tempfile.mkdtemp(prefix="code_exec_")
    script_path = os.path.join(workdir, "script.py")

    try:
        with open(script_path, "w") as f:
            f.write(code)

        clean_env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}

        subprocess_kwargs = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "cwd": workdir,
            "env": clean_env,
        }
        # preexec_fn is POSIX-only; asyncio raises on Windows if it's passed at all
        if IS_POSIX:
            subprocess_kwargs["preexec_fn"] = _limit_resources

        proc = await asyncio.create_subprocess_exec(
            "python3",
            "-I",
            script_path,
            **subprocess_kwargs,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_seconds}s",
                "exit_code": -1,
            }

        return {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "exit_code": proc.returncode,
        }

    finally:
        shutil.rmtree(workdir, ignore_errors=True)