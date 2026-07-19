"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AGENT_ORDER,
  matchAgentKey,
  type ChatMessage,
  type LaneState,
  type StreamMsg,
} from "@/lib/types";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/api/query/stream";

function freshLanes(): Record<string, LaneState> {
  const lanes: Record<string, LaneState> = {};
  for (const a of AGENT_ORDER) {
    lanes[a.key] = {
      key: a.key,
      label: a.label,
      color: a.color,
      status: "idle",
      startedAt: null,
      finishedAt: null,
      latencySeconds: null,
      tokensPerSecond: null,
      lastDetail: "",
    };
  }
  return lanes;
}

export default function Home() {
  const [mode, setMode] = useState<"sequential" | "concurrent">("sequential");
  const [connected, setConnected] = useState(false);
  const [running, setRunning] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lanes, setLanes] = useState<Record<string, LaneState>>(freshLanes());
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [, forceTick] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);

  // Connect once on mount, reconnect on close
  useEffect(() => {
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => !cancelled && setConnected(true);
      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (raw) => {
        const msg: StreamMsg = JSON.parse(raw.data);

        if (msg.type === "event") {
          const key = matchAgentKey(msg.agent_name);
          setLanes((prev) => {
            const lane = prev[key];
            if (!lane) return prev;
            const next: LaneState = { ...lane, lastDetail: msg.detail };
            if (msg.event_type === "started") {
              next.status = "running";
              next.startedAt = msg.timestamp;
            } else if (msg.event_type === "finished") {
              next.status = "done";
              next.finishedAt = msg.timestamp;
            } else if (msg.event_type === "error") {
              next.status = "error";
              next.finishedAt = msg.timestamp;
            }
            return { ...prev, [key]: next };
          });
        }

        if (msg.type === "summary") {
          setLanes((prev) => {
            const next = { ...prev };
            for (const b of msg.agent_breakdown) {
              const key = matchAgentKey(b.agent);
              if (!next[key]) continue;
              next[key] = {
                ...next[key],
                status: next[key].status === "error" ? "error" : "done",
                latencySeconds: b.latency_seconds,
                tokensPerSecond: b.tokens_per_second,
              };
            }
            return next;
          });
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: msg.final_answer },
          ]);
          setRunning(false);
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  // live-tick while a run is active, so bars grow smoothly
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => forceTick((t) => t + 1), 100);
    return () => clearInterval(id);
  }, [running]);

  const submit = useCallback(() => {
    const query = input.trim();
    if (!query || !wsRef.current || wsRef.current.readyState !== 1 || running)
      return;

    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setLanes(freshLanes());
    setRunStartedAt(Date.now() / 1000);
    setRunning(true);
    setInput("");
    wsRef.current.send(JSON.stringify({ query, mode }));
  }, [input, mode, running]);

  const now = Date.now() / 1000;
  // scale bars against the longest span currently on screen (min 3s so idle runs don't look frozen)
  const spanEnd = Math.max(
    ...Object.values(lanes).map((l) => l.finishedAt ?? (l.startedAt ? now : 0)),
    (runStartedAt ?? now) + 3
  );
  const spanStart = runStartedAt ?? now;
  const totalSpan = Math.max(spanEnd - spanStart, 0.5);

  return (
    <main className="min-h-screen flex flex-col">
      <header className="border-b border-[var(--panel-border)] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold tracking-wide">
            Agentic Research Assistant
          </h1>
          <span
            className={`h-2 w-2 rounded-full ${
              connected ? "bg-emerald-400" : "bg-red-400 pulse"
            }`}
            title={connected ? "connected" : "reconnecting…"}
          />
        </div>
        <div className="flex rounded-md border border-[var(--panel-border)] overflow-hidden text-xs">
          {(["sequential", "concurrent"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              disabled={running}
              className={`px-3 py-1.5 mono capitalize transition-colors ${
                mode === m
                  ? "bg-[var(--panel-border)] text-[var(--text)]"
                  : "text-[var(--text-dim)] hover:text-[var(--text)]"
              } disabled:opacity-50`}
            >
              {m}
            </button>
          ))}
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Chat column */}
        <section className="w-[42%] border-r border-[var(--panel-border)] flex flex-col">
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {messages.length === 0 && (
              <p className="text-sm text-[var(--text-dim)]">
                Ask a question to run the pipeline.
              </p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-right" : ""}>
                <div
                  className={`inline-block max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                    m.role === "user"
                      ? "bg-[var(--panel-border)]"
                      : "bg-[var(--panel)] border border-[var(--panel-border)]"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {running && (
              <div className="text-xs text-[var(--text-dim)] mono">
                running…
              </div>
            )}
          </div>
          <div className="border-t border-[var(--panel-border)] p-3 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder="Ask something…"
              disabled={running}
              className="flex-1 bg-[var(--panel)] border border-[var(--panel-border)] rounded-md px-3 py-2 text-sm outline-none focus:border-[var(--text-dim)] disabled:opacity-50"
            />
            <button
              onClick={submit}
              disabled={running || !input.trim()}
              className="px-4 py-2 rounded-md bg-[var(--panel-border)] text-sm disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </section>

        {/* Trace lanes */}
        <section className="flex-1 px-6 py-5 space-y-4 overflow-y-auto">
          {AGENT_ORDER.map((a) => {
            const lane = lanes[a.key];
            const startOffset = lane.startedAt
              ? Math.max(lane.startedAt - spanStart, 0)
              : null;
            const endOffset = lane.finishedAt
              ? lane.finishedAt - spanStart
              : lane.startedAt
              ? now - spanStart
              : null;

            const leftPct = startOffset !== null ? (startOffset / totalSpan) * 100 : 0;
            const widthPct =
              startOffset !== null && endOffset !== null
                ? Math.max(((endOffset - startOffset) / totalSpan) * 100, 1)
                : 0;

            return (
              <div key={a.key} className="border border-[var(--panel-border)] rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: a.color }}
                    />
                    <span className="text-sm font-medium">{a.label}</span>
                    <span
                      className={`text-[10px] mono uppercase px-1.5 py-0.5 rounded ${
                        lane.status === "running"
                          ? "text-amber-300"
                          : lane.status === "done"
                          ? "text-emerald-300"
                          : lane.status === "error"
                          ? "text-red-300"
                          : "text-[var(--text-dim)]"
                      }`}
                    >
                      {lane.status}
                    </span>
                  </div>
                  <span className="text-[11px] mono text-[var(--text-dim)]">
                    {lane.latencySeconds !== null
                      ? `${lane.latencySeconds.toFixed(2)}s`
                      : ""}
                    {lane.tokensPerSecond !== null
                      ? ` · ${lane.tokensPerSecond.toFixed(1)} tok/s`
                      : ""}
                  </span>
                </div>

                <div className="relative h-2 bg-[var(--panel)] rounded-full overflow-hidden mb-2">
                  <div
                    className="absolute top-0 h-full rounded-full transition-all"
                    style={{
                      left: `${leftPct}%`,
                      width: `${widthPct}%`,
                      backgroundColor: a.color,
                      opacity: lane.status === "running" ? 0.9 : 0.6,
                    }}
                  />
                </div>

                <p className="text-xs text-[var(--text-dim)] mono truncate">
                  {lane.lastDetail || "—"}
                </p>
              </div>
            );
          })}
        </section>
      </div>
    </main>
  );
}