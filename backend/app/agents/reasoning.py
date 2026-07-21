"""
Reasoning Agent
"""

import json
from typing import Any, AsyncIterator

from app.agents.base import AgentEvent, AgentResult, BaseAgent, EventType
from app.core.llm_client import llm_client

PLANNING_SYSTEM_PROMPT = """You are a planning agent for a research assistant.
Given a user query, decide what's needed to answer it. Respond with ONLY a JSON object,
no other text, in exactly this format:

{
  "needs_web_search": true or false,
  "needs_code_exec": true or false,
  "code": "python code as a string, only if needs_code_exec is true, else empty string",
  "reasoning": "one short sentence explaining the plan"
}

Use needs_web_search for anything requiring current/external information beyond what's
already retrieved. Use needs_code_exec only for queries that genuinely require running
code (calculations, demonstrations, data processing) -- not for conceptual questions.
"""


class ReasoningAgent(BaseAgent):
    name = "reasoning"

    async def run(self, context: dict[str, Any]) -> AsyncIterator[AgentEvent | AgentResult]:
        query = context["query"]
        retrieved_chunks = context.get("retrieved_chunks", [])

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.STARTED,
            detail="Decomposing query into sub-tasks",
        )

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.THINKING,
            detail="Calling small model to plan sub-tasks",
        )

        context_note = ""
        if retrieved_chunks:
            context_note = f"\n\n{len(retrieved_chunks)} relevant document chunk(s) already retrieved from the knowledge base."

        result = await llm_client.generate(
            prompt=f"Query: {query}{context_note}",
            size="small",
            system=PLANNING_SYSTEM_PROMPT,
        )

        plan = self._parse_plan(result.text)

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.FINISHED,
            detail=f"Plan ready: {plan.get('reasoning', 'no reasoning given')}",
            payload={"tokens_per_second": result.tokens_per_second},
        )

        context["plan"] = plan
        yield AgentResult(
            agent_name=self.name,
            output=plan,
            latency_seconds=result.latency_seconds,
            tokens_per_second=result.tokens_per_second,
        )

    def _parse_plan(self, raw_text: str) -> dict:
        """Parse the model's JSON output, with a safe fallback if it doesn't comply."""
        text = raw_text.strip()
        # strip markdown code fences if the model added them despite instructions
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            parsed = json.loads(text)
            return {
                "needs_web_search": bool(parsed.get("needs_web_search", False)),
                "needs_code_exec": bool(parsed.get("needs_code_exec", False)),
                "code": parsed.get("code", "") or "",
                "reasoning": parsed.get("reasoning", ""),
                "raw_plan": raw_text,
            }
        except (json.JSONDecodeError, AttributeError):
            # model didn't return valid JSON -- fail safe, no tool calls,
            # let Synthesizer work with just retrieved_chunks
            return {
                "needs_web_search": False,
                "needs_code_exec": False,
                "code": "",
                "reasoning": "plan parsing failed, defaulting to no tool calls",
                "raw_plan": raw_text,
            }