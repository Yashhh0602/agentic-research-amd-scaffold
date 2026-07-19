"""
Executor Agent

Job: carry out the plan from the Reasoning agent — call whichever tools are
needed (web search, code execution, external APIs). Doesn't necessarily
need an LLM call itself for simple tool dispatch, but may use the small
model to interpret tool output before handing it to the Synthesizer.

TODO (next pass):
- Wire real tool calls from app/tools/ (web_search.py, code_exec.py)
- Support parallel tool calls when the plan has independent sub-tasks
  (this matters for the concurrent execution mode / benchmark story)
- Error handling: a failed tool call shouldn't kill the whole pipeline,
  should degrade gracefully and let Synthesizer know what's missing
"""

from typing import Any, AsyncIterator

from app.agents.base import AgentEvent, AgentResult, BaseAgent, EventType


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
            # TODO: replace with real app/tools/web_search.py call
            tool_outputs.append({"tool": "web_search", "result": "[placeholder web result]"})
            yield AgentEvent(
                agent_name=self.name,
                event_type=EventType.TOOL_RESULT,
                detail="web_search returned 1 result",
            )

        if plan.get("needs_code_exec"):
            yield AgentEvent(
                agent_name=self.name,
                event_type=EventType.TOOL_CALL,
                detail="code_exec",
            )
            # TODO: replace with real app/tools/code_exec.py call
            tool_outputs.append({"tool": "code_exec", "result": "[placeholder code output]"})
            yield AgentEvent(
                agent_name=self.name,
                event_type=EventType.TOOL_RESULT,
                detail="code_exec finished",
            )

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.FINISHED,
            detail=f"Ran {len(tool_outputs)} tool(s)",
        )

        context["tool_outputs"] = tool_outputs
        yield AgentResult(agent_name=self.name, output=tool_outputs, latency_seconds=0.0)
