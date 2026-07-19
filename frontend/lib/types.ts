export type EventType =
  | "started"
  | "tool_call"
  | "tool_result"
  | "thinking"
  | "finished"
  | "error";

export interface AgentEventMsg {
  type: "event";
  agent_name: string;
  event_type: EventType;
  detail: string;
  payload: Record<string, unknown>;
  timestamp: number;
}

export interface AgentBreakdownItem {
  agent: string;
  latency_seconds: number;
  tokens_per_second: number | null;
}

export interface SummaryMsg {
  type: "summary";
  mode: "sequential" | "concurrent";
  total_latency_seconds: number;
  final_answer: string;
  agent_breakdown: AgentBreakdownItem[];
}

export type StreamMsg = AgentEventMsg | SummaryMsg;

export type LaneStatus = "idle" | "running" | "done" | "error";

export interface LaneState {
  key: string;
  label: string;
  color: string;
  status: LaneStatus;
  startedAt: number | null;
  finishedAt: number | null;
  latencySeconds: number | null;
  tokensPerSecond: number | null;
  lastDetail: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export const AGENT_ORDER: { key: string; label: string; color: string }[] = [
  { key: "retriever", label: "Retriever", color: "#4FD1C5" },
  { key: "reasoning", label: "Reasoning", color: "#A78BFA" },
  { key: "executor", label: "Executor", color: "#F5A623" },
  { key: "synthesizer", label: "Synthesizer", color: "#F0678C" },
];

export function matchAgentKey(agentName: string): string {
  const lower = agentName.toLowerCase();
  const found = AGENT_ORDER.find((a) => lower.includes(a.key));
  return found ? found.key : lower;
}