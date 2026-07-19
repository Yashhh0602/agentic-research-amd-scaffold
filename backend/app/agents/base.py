"""
Base class every agent inherits from.

Design note: `run()` doesn't just return a result, it yields AgentEvents
as it works (started, tool_call, tool_result, finished). The orchestrator
forwards these events over a WebSocket to the frontend, which is how the
live agent-trace panel works — this is not bolted on later, it's baked
into the agent interface from the start because it's core to demonstrating
"real multi-agent collaboration" rather than four functions in a trenchcoat.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class EventType(str, Enum):
    STARTED = "started"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class AgentEvent:
    agent_name: str
    event_type: EventType
    detail: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentResult:
    agent_name: str
    output: Any
    latency_seconds: float
    tokens_per_second: float | None = None


class BaseAgent(ABC):
    name: str = "base_agent"

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> AsyncIterator[AgentEvent | AgentResult]:
        """
        Do the agent's work. Must yield AgentEvent objects as it progresses
        and end by yielding exactly one AgentResult with the final output.

        `context` is the shared dict passed through the orchestrator —
        each agent reads what it needs from previous agents' outputs and
        writes its own output back under its own key.
        """
        raise NotImplementedError
