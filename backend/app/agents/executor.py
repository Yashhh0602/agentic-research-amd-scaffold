"""
Executor Agent

Job: carry out the plan from the Reasoning agent — call whichever tools are
needed (web search, code execution, external APIs). Doesn't necessarily
need an LLM call itself for simple tool dispatch, but may use the small
model to interpret tool output before handing it to the Synthesizer.

TODO (next pass):
- Wire real tool call for code_exec.py (still placeholder, needs sandboxing)
- Support parallel tool calls when the plan has independent sub-tasks
  (this matters for the concurrent execution mode / benchmark story)
- Error handling: a failed tool call shouldn't kill the whole pipeline,
  should degrade gracefully and let Synthesizer know what's missing
"""

from typing import Any, AsyncIterator

from app.agents.base import AgentEvent, AgentResult, BaseAgent, EventType
from app.tools.web_search import web_search
from app.tools.code_exec import execute_code


class ExecutorAgent(BaseAgent):
    name = "executor"

    async def run(self, context: dict[str, Any]) -> AsyncIterator[AgentEvent | AgentResult]:
        plan = context.get("plan", {})

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.STARTED,
            detail="Executing plan",
        )

        tool_outputs = []

        if plan.get("needs_web_search"):
            yield AgentEvent(
                agent_name=self.name,
                event_type=EventType.TOOL_CALL,
                detail="web_search",
            )
            try:
                results = await web_search(context["query"])
                tool_outputs.append({"tool": "web_search", "result": results})
                yield AgentEvent(
                    agent_name=self.name,
                    event_type=EventType.TOOL_RESULT,
                    detail=f"web_search returned {len(results)} result(s)",
                )
            except Exception as e:
                tool_outputs.append({"tool": "web_search", "result": None, "error": str(e)})
                yield AgentEvent(
                    agent_name=self.name,
                    event_type=EventType.ERROR,
                    detail=f"web_search failed: {e}",
                )

        if plan.get("needs_code_exec"):
            yield AgentEvent(
                agent_name=self.name,
                event_type=EventType.TOOL_CALL,
                detail="code_exec",
            )
            try:
                code = plan.get("code", "")
                exec_result = await execute_code(code)
                tool_outputs.append({"tool": "code_exec", "result": exec_result})
                yield AgentEvent(
                    agent_name=self.name,
                    event_type=EventType.TOOL_RESULT,
                    detail=f"code_exec finished (exit_code={exec_result['exit_code']})",
                )
            except Exception as e:
                tool_outputs.append({"tool": "code_exec", "result": None, "error": str(e)})
                yield AgentEvent(
                    agent_name=self.name,
                    event_type=EventType.ERROR,
                    detail=f"code_exec failed: {e}",
                )

        context["tool_outputs"] = tool_outputs
        yield AgentResult(agent_name=self.name, output=tool_outputs, latency_seconds=0.0)