import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { PageHeader } from "./DashboardPage";
import {
  agent as agentApi, outreach as outreachApi, apiSettings,
  type AgentStep, type AgentResult, type ModelConfig,
  type SendBatchItem, type SendBatchResult, type ApiSettings, type WhatsAppStatus,
} from "@/lib/api";
import {
  Send, Sparkles, Brain, Wrench, CheckCircle2, Loader2, ArrowRight,
  MessageSquare, Activity, ChevronDown, ChevronRight, Zap, AlertCircle,
  Cloud, Server, Cpu, ChevronUp, Settings2, X, Phone, History, Clock, Trash2,
} from "lucide-react";
import { t } from "@/lib/i18n";

type ChatMessage = {
  id: string;
  role: "user" | "agent";
  content: string;
  steps?: AgentStep[];
  result?: AgentResult | null;
  error?: string;
};

// ── History (localStorage) ────────────────────────────────────────────────────

const HISTORY_KEY = "bankrm_workspace_history";
const MAX_HISTORY = 20;

type HistorySession = {
  id: string;
  timestamp: string;
  summary: string;          // first user message, truncated
  messageCount: number;
  messages: ChatMessage[];
};

function loadHistory(): HistorySession[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveToHistory(messages: ChatMessage[]) {
  if (!messages.some(m => m.role === "user")) return;
  const userMsg = messages.find(m => m.role === "user");
  const session: HistorySession = {
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    summary: (userMsg?.content ?? "Session").slice(0, 80),
    messageCount: messages.length,
    messages,
  };
  const existing = loadHistory();
  const updated = [session, ...existing].slice(0, MAX_HISTORY);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
}

function clearHistory() {
  localStorage.removeItem(HISTORY_KEY);
}

const SUGGESTED = [
  "Find high-value customers likely to convert for a personal loan this month",
  "Show me dormant premium clients and draft a re-engagement message",
  "Which customers have credit score above 750 and no credit card?",
  "Score the top 5 affluent customers",
];

// ── Model registry ────────────────────────────────────────────────────────────

interface ModelOption {
  id: string;
  label: string;
  sublabel: string;
  backend: "gemini" | "ollama" | "nvidia";
  ollama_model?: string;
  nvidia_model?: string;
  icon: "cloud" | "local" | "nvidia";
  badge?: string;
  badgeColor?: string;
  speed: number;   // 1-3
  quality: number; // 1-3
}

const MODELS: ModelOption[] = [
  // ── NVIDIA NIM (cloud, free tier) ─────────────────────────────────────────
  {
    id: "nvidia-llama70b",
    label: t("Llama 3.1 70B"),
    sublabel: "nvidia nim · llama-3.1-70b-instruct",
    backend: "nvidia",
    nvidia_model: "meta/llama-3.1-70b-instruct",
    icon: "nvidia",
    badge: "Free · Cloud",
    badgeColor: "text-green-400 bg-green-400/10",
    speed: 3,
    quality: 3,
  },
  {
    id: "nvidia-nemotron",
    label: t("Nemotron 70B"),
    sublabel: "nvidia nim · llama-3.1-nemotron-70b",
    backend: "nvidia",
    nvidia_model: "nvidia/llama-3.1-nemotron-70b-instruct",
    icon: "nvidia",
    badge: "Free · Cloud",
    badgeColor: "text-green-400 bg-green-400/10",
    speed: 2,
    quality: 3,
  },
  {
    id: "nvidia-mixtral",
    label: t("Mixtral 8x7B"),
    sublabel: "nvidia nim · mixtral-8x7b-instruct",
    backend: "nvidia",
    nvidia_model: "mistralai/mixtral-8x7b-instruct-v0.1",
    icon: "nvidia",
    badge: "Free · Cloud",
    badgeColor: "text-green-400 bg-green-400/10",
    speed: 3,
    quality: 2,
  },
  // ── Gemini ─────────────────────────────────────────────────────────────────
  {
    id: "gemini-flash",
    label: t("Gemini Flash"),
    sublabel: "google · gemini-flash-latest",
    backend: "gemini",
    icon: "cloud",
    badge: "20 req/day",
    badgeColor: "text-blue-400 bg-blue-400/10",
    speed: 3,
    quality: 3,
  },
  // ── Ollama (local) ─────────────────────────────────────────────────────────
  {
    id: "ollama-gemma3",
    label: t("Gemma 3 4B"),
    sublabel: "ollama · gemma3:4b",
    backend: "ollama",
    ollama_model: "gemma3:4b",
    icon: "local",
    badge: "Local",
    badgeColor: "text-muted-foreground bg-muted/40",
    speed: 2,
    quality: 2,
  },
  {
    id: "ollama-llama3",
    label: t("Llama 3.1 8B"),
    sublabel: "ollama · llama3.1:8b",
    backend: "ollama",
    ollama_model: "llama3.1:8b",
    icon: "local",
    badge: "Local",
    badgeColor: "text-muted-foreground bg-muted/40",
    speed: 1,
    quality: 3,
  },
];

function modelById(id: string) {
  return MODELS.find((m) => m.id === id) ?? MODELS[0];
}

function buildConfig(globalModel: string, splitMode: boolean, plannerModel: string, executorModel: string): ModelConfig {
  if (!splitMode) {
    const m = modelById(globalModel);
    return { llm_backend: m.backend, ollama_model: m.ollama_model, nvidia_model: m.nvidia_model };
  }
  const p = modelById(plannerModel);
  const e = modelById(executorModel);
  return {
    llm_backend: p.backend,
    ollama_model: p.backend === "ollama" ? p.ollama_model : (e.backend === "ollama" ? e.ollama_model : undefined),
    nvidia_model: p.backend === "nvidia" ? p.nvidia_model : (e.backend === "nvidia" ? e.nvidia_model : undefined),
    planner_backend: p.backend,
    executor_backend: e.backend,
  };
}

// ── ModelPicker ───────────────────────────────────────────────────────────────

function Dots({ count, filled }: { count: number; filled: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: count }).map((_, i) => (
        <span
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${i < filled ? "bg-primary" : "bg-muted-foreground/30"}`}
        />
      ))}
    </div>
  );
}

function ModelCard({ model, selected, onClick }: { model: ModelOption; selected: boolean; onClick: () => void }) {
  const Icon = model.icon === "nvidia" ? Cpu : model.icon === "cloud" ? Cloud : Server;
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-xl border p-3 transition-all ${
        selected
          ? "border-primary/60 bg-primary/10 ring-1 ring-primary/30"
          : "border-border bg-muted/20 hover:border-primary/30 hover:bg-muted/40"
      }`}
    >
      <div className="flex items-start gap-2.5">
        <div className={`w-7 h-7 rounded-lg grid place-items-center flex-shrink-0 ${
          selected ? "bg-primary/20" : "bg-muted/60"
        }`}>
          <Icon className={`w-3.5 h-3.5 ${selected ? "text-primary" : "text-muted-foreground"}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold">{model.label}</span>
            {model.badge && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${model.badgeColor}`}>
                {model.badge}
              </span>
            )}
          </div>
          <div className="text-[10px] text-muted-foreground mt-0.5">{model.sublabel}</div>
          <div className="flex items-center gap-3 mt-1.5">
            <div className="flex items-center gap-1">
              <span className="text-[9px] text-muted-foreground">{t("Speed")}</span>
              <Dots count={3} filled={model.speed} />
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[9px] text-muted-foreground">{t("Quality")}</span>
              <Dots count={3} filled={model.quality} />
            </div>
          </div>
        </div>
        {selected && <CheckCircle2 className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />}
      </div>
    </button>
  );
}

function ModelPicker({
  open, onClose,
  globalModel, setGlobalModel,
  splitMode, setSplitMode,
  plannerModel, setPlannerModel,
  executorModel, setExecutorModel,
}: {
  open: boolean; onClose: () => void;
  globalModel: string; setGlobalModel: (v: string) => void;
  splitMode: boolean; setSplitMode: (v: boolean) => void;
  plannerModel: string; setPlannerModel: (v: string) => void;
  executorModel: string; setExecutorModel: (v: string) => void;
}) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={onClose} />
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 z-50 w-[420px] glass rounded-2xl border border-border shadow-2xl p-4 space-y-4"
          >
            {/* Split toggle */}
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs font-semibold">{t("Model Configuration")}</div>
                <div className="text-[10px] text-muted-foreground mt-0.5">
                  {t("Use different models for planning vs execution")}
                </div>
              </div>
              <button
                onClick={() => setSplitMode(!splitMode)}
                className={`flex items-center gap-1.5 text-[10px] px-2.5 py-1.5 rounded-lg border font-medium transition ${
                  splitMode
                    ? "border-primary/60 bg-primary/10 text-primary"
                    : "border-border bg-muted/30 text-muted-foreground hover:border-primary/30"
                }`}
              >
                <Cpu className="w-3 h-3" />
                Split mode {splitMode ? "ON" : "OFF"}
              </button>
            </div>

            {!splitMode ? (
              <div className="space-y-1.5">
                <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wide mb-2">
                  {t("All nodes")}
                </div>
                {MODELS.map((m) => (
                  <ModelCard key={m.id} model={m} selected={globalModel === m.id} onClick={() => setGlobalModel(m.id)} />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground font-medium uppercase tracking-wide mb-2">
                    <Brain className="w-3 h-3 text-primary" /> Planner
                  </div>
                  {MODELS.map((m) => (
                    <div key={m.id} className="mb-1.5">
                      <ModelCard model={m} selected={plannerModel === m.id} onClick={() => setPlannerModel(m.id)} />
                    </div>
                  ))}
                </div>
                <div>
                  <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground font-medium uppercase tracking-wide mb-2">
                    <Wrench className="w-3 h-3 text-accent" /> Executor
                  </div>
                  {MODELS.map((m) => (
                    <div key={m.id} className="mb-1.5">
                      <ModelCard model={m} selected={executorModel === m.id} onClick={() => setExecutorModel(m.id)} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-1 border-t border-border text-[10px] text-muted-foreground">
              {t("Local models require Ollama running at localhost:11434")}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ── MVP Limitation Note ────────────────────────────────────────────────────────

function MvpNote() {
  const [open, setOpen] = useState(false);
  return (
    <div className="text-[10px] bg-amber-500/5 border border-amber-500/20 rounded-lg px-3 py-1.5 flex-shrink-0">
      <div className="flex items-center gap-2">
        <span className="text-amber-400/80">
          <span className="font-semibold">{t("⚠ MVP Note:")}</span>{" "}
          Customer queries sample <strong>{t("50 from 500")}</strong> candidates in insertion order — not necessarily the best 50.
        </span>
        <button
          onClick={() => setOpen((v) => !v)}
          className="ml-auto text-amber-400 underline underline-offset-2 whitespace-nowrap hover:text-amber-300 transition-colors"
        >
          {open ? t("Hide") : t("Read more")}
        </button>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-2 pt-2 border-t border-amber-500/20 space-y-2 text-amber-200/70 leading-relaxed">
              <p>
                <span className="text-amber-400 font-semibold">{t("What's broken now:")}</span>{" "}
                <code className="bg-amber-500/10 px-1 rounded">query_customers(limit=50)</code> fetches the first 50 rows in DB insertion order — not ranked by value or relevance. The agent then scores only those 50, so high-value customers beyond row 50 are never seen.
              </p>
              <p>
                <span className="text-amber-400 font-semibold">{t("Quick fix (no infra change):")}</span>{" "}
                Add <code className="bg-amber-500/10 px-1 rounded">{t("ORDER BY credit_score DESC, annual_income DESC")}</code> before the LIMIT so the sample is always the financially strongest 50, not an arbitrary 50.
              </p>
              <p>
                <span className="text-amber-400 font-semibold">{t("Proper fix (scalable to 1M+ customers):")}</span>{" "}
                Embed each customer profile as a vector (e.g. OpenAI <code className="bg-amber-500/10 px-1 rounded">{t("text-embedding-3-small")}</code>) and store in pgvector / Pinecone. When the agent runs a query, embed the intent ("high-value personal loan conversion") and retrieve the top-K most semantically similar profiles via ANN search — bypassing the LIMIT entirely and finding the right customers regardless of portfolio size.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Workspace page ─────────────────────────────────────────────────────────────

export function WorkspacePage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [running, setRunning] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Model state
  const [pickerOpen, setPickerOpen] = useState(false);
  const [splitMode, setSplitMode] = useState(false);
  const [globalModel, setGlobalModel] = useState("nvidia-llama70b");
  const [plannerModel, setPlannerModel] = useState("gemini-flash");
  const [executorModel, setExecutorModel] = useState("ollama-gemma3");

  // History state
  const [rightTab, setRightTab] = useState<"workflow" | "history">("workflow");
  const [history, setHistory] = useState<HistorySession[]>(() => loadHistory());
  const [viewingSession, setViewingSession] = useState<HistorySession | null>(null);

  // Live streaming node state for workflow rail
  const [liveNodes, setLiveNodes] = useState<{
    node: string; label: string; status: "running" | "done" | "error"; detail?: string;
  }[]>([]);
  const [liveTools, setLiveTools] = useState<{ name: string; count?: number | null }[]>([]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, running]);

  const activeConfig = buildConfig(globalModel, splitMode, plannerModel, executorModel);

  const activeLabel = splitMode
    ? `${modelById(plannerModel).label} + ${modelById(executorModel).label}`
    : modelById(globalModel).label;

  const activeIcon = splitMode
    ? <Cpu className="w-3.5 h-3.5 text-primary" />
    : modelById(globalModel).icon === "nvidia"
      ? <Cpu className="w-3.5 h-3.5 text-green-400" />
      : modelById(globalModel).icon === "cloud"
        ? <Cloud className="w-3.5 h-3.5 text-blue-400" />
        : <Server className="w-3.5 h-3.5 text-muted-foreground" />;

  async function send(text: string) {
    if (!text.trim() || running) return;
    setInput("");
    setPickerOpen(false);
    setLiveNodes([]);
    setLiveTools([]);
    setRightTab("workflow"); // switch to workflow tab on send

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text };
    const agentMsgId = crypto.randomUUID();
    const agentMsg: ChatMessage = { id: agentMsgId, role: "agent", content: "", steps: [], result: null };
    setMessages((m) => [...m, userMsg, agentMsg]);
    setRunning(true);

    try {
      const config = activeConfig;
      const body = typeof config === "string"
        ? { query: text, llm_backend: config }
        : { query: text, ...config };

      const resp = await fetch("/api/agent/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.slice(6));

            if (evt.event === "node") {
              setLiveNodes((prev) => {
                const existing = prev.findIndex((n) => n.node === evt.node);
                const entry = { node: evt.node, label: evt.label, status: evt.status, detail: evt.detail };
                if (existing >= 0) {
                  const next = [...prev]; next[existing] = entry; return next;
                }
                return [...prev, entry];
              });
            }

            if (evt.event === "tool") {
              setLiveTools((prev) => [...prev, { name: evt.name, count: evt.count }]);
            }

            if (evt.event === "done") {
              // Build step list from live nodes + tools for the message
              const steps: import("@/lib/api").AgentStep[] = [
                ...liveNodes.map((n, i) => ({
                  id: `node-${i}`, type: "plan" as const, label: n.label,
                  detail: n.detail ?? "", startedAt: 0, endedAt: 1,
                })),
              ];
              setMessages((m) => {
                const updated = m.map((msg) =>
                  msg.id === agentMsgId
                    ? {
                        ...msg,
                        content: evt.answer ?? "Agent completed.",
                        steps,
                        result: evt,
                        error: evt.error ?? undefined,
                      }
                    : msg
                );
                saveToHistory(updated);
                setHistory(loadHistory());
                return updated;
              });
            }
          } catch {
            // skip malformed SSE lines
          }
        }
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : "Unknown error";
      setMessages((m) =>
        m.map((msg) => msg.id === agentMsgId ? { ...msg, content: "", error: errMsg, steps: [] } : msg)
      );
    } finally {
      setRunning(false);
    }
  }

  const latestAgentMsg = [...messages].reverse().find((m) => m.role === "agent");

  return (
    <div className="space-y-5 h-[calc(100vh-7rem)] flex flex-col">
      {/* MVP note */}
      <MvpNote />

      <PageHeader
        title={t("RM AI Workspace")}
        subtitle={t("Your AI copilot for portfolio actions. Plans, calls tools, reasons, and drafts outreach in real time.")}
        actions={
          <div className="flex items-center gap-3">
            {/* Model picker trigger */}
            <div className="relative">
              <button
                onClick={() => setPickerOpen((v) => !v)}
                className="flex items-center gap-2 text-xs bg-input/60 border border-border rounded-lg px-3 py-1.5 hover:border-primary/40 hover:bg-muted/60 transition"
              >
                {activeIcon}
                <span className="max-w-[160px] truncate font-medium">{activeLabel}</span>
                {splitMode && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary font-semibold">{t("SPLIT")}</span>
                )}
                {pickerOpen ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
              </button>
              <ModelPicker
                open={pickerOpen}
                onClose={() => setPickerOpen(false)}
                globalModel={globalModel} setGlobalModel={setGlobalModel}
                splitMode={splitMode} setSplitMode={setSplitMode}
                plannerModel={plannerModel} setPlannerModel={setPlannerModel}
                executorModel={executorModel} setExecutorModel={setExecutorModel}
              />
            </div>

            <div className="flex items-center gap-2 text-xs text-muted-foreground glass px-3 py-1.5 rounded-lg">
              <span className="w-1.5 h-1.5 rounded-full bg-success pulse-dot" />
              {t("LangGraph Agent")}
            </div>
          </div>
        }
      />

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-0">
        {/* Chat */}
        <div className="lg:col-span-2 glass rounded-xl flex flex-col overflow-hidden shadow-card">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-5">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center">
                <div className="w-14 h-14 rounded-2xl gradient-primary grid place-items-center glow mb-4">
                  <Sparkles className="w-7 h-7 text-primary-foreground" />
                </div>
                <h2 className="text-xl font-display font-semibold">{t("How can I help you today?")}</h2>
                <p className="text-sm text-muted-foreground mt-1 max-w-md">
                  {t("Ask anything about your portfolio. The real LangGraph agent will plan, call tools, and draft outreach.")}
                </p>
                <div className="grid sm:grid-cols-2 gap-2 mt-6 max-w-2xl w-full">
                  {SUGGESTED.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="text-left text-sm p-3 rounded-lg bg-muted/40 border border-border hover:border-primary/40 hover:bg-muted/60 transition group"
                    >
                      <div className="flex items-start gap-2">
                        <Zap className="w-3.5 h-3.5 text-primary mt-0.5 flex-shrink-0" />
                        <span className="text-muted-foreground group-hover:text-foreground">{s}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => (
              <MessageBubble key={m.id} msg={m} isRunning={running && m === messages[messages.length - 1]} />
            ))}
          </div>

          {/* Input */}
          <div className="border-t border-border p-3 bg-card/30">
            <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-end gap-2">
              <div className="flex-1 relative">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
                  placeholder={running ? t("Agent working… this may take 20-60 seconds") : t("Ask the agent…")}
                  disabled={running}
                  rows={1}
                  className="w-full bg-input/60 border border-border rounded-lg px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40 resize-none"
                />
              </div>
              <button
                type="submit"
                disabled={running || !input.trim()}
                className="h-10 px-4 rounded-lg gradient-primary text-primary-foreground text-sm font-medium flex items-center gap-2 disabled:opacity-40 transition hover:opacity-90"
              >
                {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Send
              </button>
            </form>
          </div>
        </div>

        {/* Right rail: Workflow | History tabs */}
        <div className="glass rounded-xl shadow-card flex flex-col overflow-hidden">
          {/* Tab bar */}
          <div className="flex border-b border-border">
            {[
              { id: "workflow" as const, icon: Activity, label: t("Workflow") },
              { id: "history" as const, icon: History, label: `History${history.length > 0 ? ` (${history.length})` : ""}` },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setRightTab(tab.id); setViewingSession(null); }}
                className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-xs font-medium transition border-b-2 ${
                  rightTab === tab.id
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <tab.icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Workflow panel */}
          {rightTab === "workflow" && (
            <div className="p-5 flex flex-col flex-1 overflow-hidden">
              <div className="flex flex-wrap gap-1.5 mb-3">
                {splitMode ? (
                  <>
                    <span className="flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary">
                      <Brain className="w-2.5 h-2.5" /> {modelById(plannerModel).label}
                    </span>
                    <span className="flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20 text-accent">
                      <Wrench className="w-2.5 h-2.5" /> {modelById(executorModel).label}
                    </span>
                  </>
                ) : (
                  <span className="flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-full bg-muted border border-border text-muted-foreground">
                    <Settings2 className="w-2.5 h-2.5" /> {modelById(globalModel).label}
                  </span>
                )}
              </div>
              <div className="text-xs text-muted-foreground mb-3">{t("Live LangGraph execution")}</div>

              {/* Live streaming node progress */}
              {(running || liveNodes.length > 0) && (
                <div className="space-y-2 mb-4">
                  {liveNodes.map((n) => (
                    <div key={n.node} className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs transition-all overflow-hidden ${
                      n.status === "running" ? "bg-primary/10 border border-primary/30" :
                      n.status === "done"    ? "bg-emerald-500/10 border border-emerald-500/20" :
                                              "bg-destructive/10 border border-destructive/20"
                    }`}>
                      <span className="mt-0.5 shrink-0">
                        {n.status === "running" ? <Loader2 className="w-3 h-3 animate-spin text-primary" /> :
                         n.status === "done"    ? <span className="text-emerald-400">✓</span> :
                                                  <span className="text-destructive">✗</span>}
                      </span>
                      <div className="min-w-0 flex-1 overflow-hidden">
                        <div className={`font-medium truncate ${n.status === "running" ? "text-primary" : n.status === "done" ? "text-emerald-400" : "text-destructive"}`}>
                          {n.label}
                        </div>
                        {n.detail && (
                          <div className="text-[10px] text-muted-foreground mt-0.5 truncate" title={n.detail}>{n.detail}</div>
                        )}
                      </div>
                    </div>
                  ))}
                  {running && liveNodes.length > 0 && liveNodes[liveNodes.length - 1]?.status === "running" && (
                    <div className="text-[10px] text-muted-foreground px-1 animate-pulse">{t("Agent is working…")}</div>
                  )}
                </div>
              )}

              {/* Tool calls fired */}
              {liveTools.length > 0 && (
                <div className="mb-4">
                  <div className="text-[10px] text-muted-foreground mb-1.5 font-medium uppercase tracking-wide">{t("Tools called")}</div>
                  <div className="flex flex-wrap gap-1">
                    {/* Dedupe tool names, show unique only */}
                    {Array.from(new Map(liveTools.map(t => [t.name, t])).values()).map((t, i) => (
                      <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20 text-accent font-mono max-w-full truncate" title={t.name}>
                        {t.name.replace(/_/g, " ")}{t.count != null ? ` ·${t.count}` : ""}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Static WorkflowMini when idle */}
              {!running && liveNodes.length === 0 && (
                <WorkflowMini running={false} steps={latestAgentMsg?.steps} splitMode={splitMode} plannerModel={plannerModel} executorModel={executorModel} globalModel={globalModel} />
              )}
            </div>
          )}

          {/* History panel */}
          {rightTab === "history" && (
            <div className="flex-1 flex flex-col overflow-hidden">
              {viewingSession ? (
                /* Session detail view */
                <div className="flex flex-col flex-1 overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
                    <button
                      onClick={() => setViewingSession(null)}
                      className="text-xs text-primary hover:underline flex items-center gap-1"
                    >
                      ← Back
                    </button>
                    <span className="text-[10px] text-muted-foreground ml-auto">
                      {new Date(viewingSession.timestamp).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="flex-1 overflow-y-auto p-3 space-y-3">
                    {viewingSession.messages.map((m) => (
                      <div key={m.id} className={`text-xs rounded-lg p-2.5 ${m.role === "user" ? "bg-primary/10 border border-primary/20 ml-4" : "bg-muted/40 border border-border mr-4"}`}>
                        <div className="text-[10px] text-muted-foreground mb-1 font-medium">{m.role === "user" ? t("You") : t("AI Agent")}</div>
                        <div className="leading-relaxed line-clamp-6">{m.content || (m.error ? `Error: ${m.error}` : "…")}</div>
                      </div>
                    ))}
                  </div>
                  <div className="px-4 py-3 border-t border-border">
                    <button
                      onClick={() => { setMessages(viewingSession.messages); setViewingSession(null); setRightTab("workflow"); }}
                      className="w-full text-xs py-2 rounded-lg bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20 transition font-medium"
                    >
                      {t("Restore this session")}
                    </button>
                  </div>
                </div>
              ) : (
                /* Session list */
                <div className="flex-1 overflow-y-auto">
                  {history.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center p-6 gap-3">
                      <History className="w-10 h-10 text-muted-foreground/30" />
                      <div className="text-xs text-muted-foreground">{t("No sessions yet.")}<br />{t("Your workspace conversations will appear here.")}</div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
                        <span className="text-[10px] text-muted-foreground">{history.length} sessions saved</span>
                        <button
                          onClick={() => { clearHistory(); setHistory([]); }}
                          className="text-[10px] text-muted-foreground hover:text-destructive flex items-center gap-1 transition"
                        >
                          <Trash2 className="w-3 h-3" /> Clear
                        </button>
                      </div>
                      <div className="divide-y divide-border">
                        {history.map((session) => (
                          <button
                            key={session.id}
                            onClick={() => setViewingSession(session)}
                            className="w-full text-left px-4 py-3 hover:bg-muted/30 transition group"
                          >
                            <div className="flex items-start gap-2">
                              <MessageSquare className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0 group-hover:text-primary transition" />
                              <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium truncate group-hover:text-primary transition">{session.summary}</div>
                                <div className="flex items-center gap-2 mt-0.5">
                                  <Clock className="w-2.5 h-2.5 text-muted-foreground" />
                                  <span className="text-[10px] text-muted-foreground">
                                    {new Date(session.timestamp).toLocaleDateString([], { month: "short", day: "numeric" })} · {new Date(session.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                  </span>
                                  <span className="text-[10px] text-muted-foreground ml-auto">{session.messageCount} msgs</span>
                                </div>
                              </div>
                            </div>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg, isRunning }: { msg: ChatMessage; isRunning: boolean }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] glass rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm">{msg.content}</div>
      </div>
    );
  }

  const showSpinner = isRunning && !msg.content && !msg.error;

  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg gradient-primary grid place-items-center flex-shrink-0">
          <Sparkles className="w-4 h-4 text-primary-foreground" />
        </div>
        <div className="flex-1 space-y-3 min-w-0">
          {showSpinner && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {t("Agent is thinking… planning and calling tools")}
            </div>
          )}
          {msg.steps && msg.steps.length > 0 && <ReasoningTrace steps={msg.steps} />}
          {msg.error && (
            <div className="flex items-start gap-2 text-xs text-destructive rounded-lg border border-destructive/30 bg-destructive/5 p-3">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-medium mb-0.5">{t("Agent error")}</div>
                <div className="text-muted-foreground">{msg.error}</div>
              </div>
            </div>
          )}
          {msg.content && <div className="text-sm leading-relaxed">{msg.content}</div>}
          {msg.result?.drafts && msg.result.drafts.length > 0 && <DraftsCard drafts={msg.result.drafts} />}
          {msg.result?.customers && msg.result.customers.length > 0 && <CustomersCard customers={msg.result.customers} />}
        </div>
      </div>
    </div>
  );
}

function ReasoningTrace({ steps }: { steps: AgentStep[] }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-xl border border-border bg-muted/30 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium hover:bg-muted/60 transition"
      >
        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        <Brain className="w-3.5 h-3.5 text-primary" />
        {t("Reasoning trace")}
        <span className="text-muted-foreground font-normal">· {steps.length} steps</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden">
            <div className="px-3 pb-3 pt-1 space-y-1.5">
              {steps.map((s, i) => <StepRow key={s.id || i} step={s} index={i} />)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StepRow({ step, index }: { step: AgentStep; index: number }) {
  const [open, setOpen] = useState(false);
  const Icon = step.type === "plan" ? Brain : step.type === "tool" ? Wrench : step.type === "reflect" ? Sparkles : MessageSquare;
  const color = step.type === "plan" ? "text-primary" : step.type === "tool" ? "text-accent" : step.type === "reflect" ? "text-warning" : "text-info";
  return (
    <div className="rounded-lg border border-border/60 bg-card/40">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs hover:bg-muted/30 transition"
      >
        <span className={`w-5 h-5 rounded grid place-items-center bg-muted/60 ${color}`}>
          <Icon className="w-3 h-3" />
        </span>
        <span className="font-mono text-[10px] text-muted-foreground w-4">{(index + 1).toString().padStart(2, "0")}</span>
        <span className="font-medium flex-1 text-left truncate">{step.label}</span>
        <span className="flex items-center gap-2 flex-shrink-0">
          {step.toolCall && <span className="text-[10px] text-muted-foreground">{step.toolCall.durationMs}ms</span>}
          <CheckCircle2 className="w-3.5 h-3.5 text-success" />
        </span>
      </button>
      {open && (
        <div className="px-2.5 pb-2.5 pt-0 text-[11px] text-muted-foreground space-y-1.5">
          <div>{step.detail}</div>
          {step.toolCall && (
            <div className="grid grid-cols-2 gap-2 mt-1">
              <div className="rounded bg-muted/40 p-2 font-mono text-[10px] overflow-x-auto">
                <div className="text-primary mb-1">{t("input")}</div>
                <pre>{JSON.stringify(step.toolCall.input, null, 2)}</pre>
              </div>
              <div className="rounded bg-muted/40 p-2 font-mono text-[10px] overflow-x-auto">
                <div className="text-accent mb-1">{t("output")}</div>
                <pre className="whitespace-pre-wrap">{JSON.stringify(step.toolCall.output, null, 2)?.slice(0, 300)}</pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ConvBadge({ prob }: { prob?: number | null }) {
  if (prob == null) return null;
  const pct = Math.round(prob * 100);
  const color =
    pct >= 55 ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20" :
    pct >= 30 ? "text-amber-400 bg-amber-400/10 border-amber-400/20" :
                "text-rose-400 bg-rose-400/10 border-rose-400/20";
  return (
    <span className={`inline-flex items-center gap-0.5 border rounded px-1.5 py-0.5 text-[9px] font-semibold ${color}`}>
      {pct}% conv.
    </span>
  );
}

// ── Send Modal ────────────────────────────────────────────────────────────────

type DraftRow = AgentResult["drafts"][number] & { phone: string; sendResult?: SendBatchResult };

/** Shows the WhatsApp QR when the service is running but not yet authenticated */
function WhatsAppQRPanel() {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const s = await outreachApi.whatsappStatus();
        if (!cancelled) setStatus(s);
      } catch { /* service down */ }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (!status || status.state === "SERVICE_DOWN") {
    return (
      <div className="rounded-lg bg-muted/30 border border-border/40 px-3 py-2.5 text-[10px] text-muted-foreground space-y-1">
        <div className="font-semibold text-xs flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
          {t("WhatsApp Web service not running")}
        </div>
        <p>{t("Start it in a new terminal:")}</p>
        <code className="block bg-background rounded px-2 py-1 font-mono text-[10px] border border-border/40">
          cd banking-crm-backend/whatsapp-service && node server.js
        </code>
        <p className="text-[9px]">{t("Then scan the QR code that appears in the terminal with WhatsApp → Linked Devices.")}</p>
      </div>
    );
  }

  if (status.ready) {
    return (
      <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-400/5 border border-emerald-400/20 rounded-lg px-3 py-2">
        <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
        <span>{t("WhatsApp connected — messages will be sent from your account")}</span>
      </div>
    );
  }

  if (status.qr) {
    // Render QR using qrcode.react alternative: use an img tag with a QR API
    const qrImg = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(status.qr)}`;
    return (
      <div className="rounded-lg border border-border/40 p-3 space-y-2 text-center">
        <p className="text-[10px] text-muted-foreground">{t("Scan with WhatsApp → Linked Devices")}</p>
        <img src={qrImg} alt={t("WhatsApp QR")} className="w-36 h-36 mx-auto rounded border border-border/30" />
        <div className="flex items-center justify-center gap-1.5 text-[10px] text-amber-400">
          <Loader2 className="w-3 h-3 animate-spin" /> Waiting for scan…
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <Loader2 className="w-3.5 h-3.5 animate-spin" />
      {status.state === "INITIALIZING" ? "Starting WhatsApp…" : status.state}
    </div>
  );
}

type BackendTab = "whatsapp-web" | "twilio" | "mock";

function SendModal({
  drafts,
  onClose,
}: {
  drafts: AgentResult["drafts"];
  onClose: () => void;
}) {
  const [rows, setRows] = useState<DraftRow[]>(drafts.map((d) => ({ ...d, phone: "" })));
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [appSettings, setAppSettings] = useState<ApiSettings | null>(null);
  const [activeTab, setActiveTab] = useState<BackendTab>("whatsapp-web");

  // Sandbox state
  const [sandbox, setSandbox] = useState(true);
  const [sandboxNumber, setSandboxNumber] = useState("+917838146286");

  // Fetch settings + phone numbers on mount
  useEffect(() => {
    apiSettings.get().then((s) => {
      setAppSettings(s);
      setSandbox(s.whatsapp_sandbox ?? true);
      setSandboxNumber(s.whatsapp_sandbox_number || "+917838146286");
      if (s.sender_backend === "twilio") setActiveTab("twilio");
      else if (s.sender_backend === "whatsapp-web") setActiveTab("whatsapp-web");
      else setActiveTab("mock");
    }).catch(() => {});

    Promise.all(
      drafts.map(async (d, i) => {
        try {
          const res = await outreachApi.phone(d.customer_id);
          if (res.phone) {
            setRows((prev) => prev.map((r, idx) => idx === i ? { ...r, phone: res.phone! } : r));
          }
        } catch { /* user fills in */ }
      })
    ).finally(() => setLoading(false));
  }, []);

  const updatePhone = (i: number, val: string) =>
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, phone: val } : r)));

  const handleSend = async () => {
    setSending(true);
    const items: SendBatchItem[] = rows.map((r) => ({
      customer_id: r.customer_id,
      customer_name: r.customer_name,
      product_id: r.product_id,
      message: r.message,
      // In sandbox: phone doesn't matter (server overrides). In prod: use CRM phone.
      phone_number: sandbox ? sandboxNumber : r.phone.trim(),
      framework: r.framework,
    }));
    if (!items.length) { setSending(false); return; }
    try {
      const res = await outreachApi.sendBatch(items, sandbox, sandboxNumber, activeTab);
      setRows((prev) => prev.map((r) => {
        const result = res.results.find((x) => x.customer_id === r.customer_id);
        return result ? { ...r, sendResult: result } : r;
      }));
      setSent(true);
    } catch (e) { console.error(e); }
    finally { setSending(false); }
  };

  // In sandbox: only need sandboxNumber. In prod: need a phone per row.
  const canSend = sandbox
    ? sandboxNumber.trim().length > 6
    : rows.every((r) => r.phone.trim().length > 0);
  const sentCount = rows.filter((r) => r.sendResult?.status?.startsWith("sent")).length;

  const TABS: { id: BackendTab; label: string; badge: string; color: string }[] = [
    { id: "whatsapp-web", label: t("WhatsApp Web"), badge: "Free", color: "text-emerald-400 border-emerald-400/40 bg-emerald-400/5" },
    { id: "twilio",       label: t("Twilio API"),   badge: "Pro",  color: "text-blue-400 border-blue-400/40 bg-blue-400/5" },
    { id: "mock",         label: t("Mock / Log"),   badge: "Dev",  color: "text-muted-foreground border-border bg-muted/20" },
  ];

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-lg max-h-[92vh] flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-2 font-semibold text-sm">
            <Phone className="w-4 h-4 text-primary" /> Send WhatsApp Outreach
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-muted/50">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* ── Sandbox / Production toggle ───────────────────────────── */}
        <div className="px-5 pt-4 flex-shrink-0">
          <div className="flex items-center justify-between rounded-xl border border-border/50 bg-muted/20 px-3 py-2.5 mb-4">
            <div>
              <p className="text-xs font-semibold">
                {sandbox ? t("🧪 Sandbox Mode") : t("🚀 Production Mode")}
              </p>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {sandbox
                  ? "All messages go to your test number only — real customers won't be contacted"
                  : "Messages go to each customer's actual CRM phone number"}
              </p>
            </div>
            {/* Toggle switch */}
            <button
              onClick={() => setSandbox((v) => !v)}
              className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${
                sandbox ? "bg-amber-500/70" : "bg-emerald-500/70"
              }`}
            >
              <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${
                sandbox ? "left-0.5" : "left-[22px]"
              }`} />
            </button>
          </div>

          {/* Sandbox number input */}
          {sandbox && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2">
              <Phone className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-[9px] text-amber-400 font-semibold uppercase tracking-wide mb-0.5">{t("Test number — all messages go here")}</p>
                <input
                  type="tel"
                  value={sandboxNumber}
                  onChange={(e) => setSandboxNumber(e.target.value)}
                  className="w-full bg-transparent font-mono text-xs outline-none text-amber-200 placeholder:text-amber-400/40"
                  placeholder="+917838146286"
                />
              </div>
            </div>
          )}

        {/* Backend tabs */}
        <div>
          <p className="text-[10px] text-muted-foreground mb-2 uppercase tracking-wide font-medium">{t("Send via")}</p>
          <div className="flex gap-1.5">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`flex items-center gap-1.5 text-[10px] font-semibold px-2.5 py-1.5 rounded-lg border transition-all ${
                  activeTab === t.id ? t.color : "text-muted-foreground border-border/40 bg-transparent hover:bg-muted/30"
                }`}
              >
                {t.label}
                <span className="opacity-70">{t.badge}</span>
                {appSettings?.sender_backend === t.id && (
                  <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
                )}
              </button>
            ))}
          </div>

          {/* Per-tab info */}
          <div className="mt-3">
            {activeTab === "whatsapp-web" && <WhatsAppQRPanel />}
            {activeTab === "twilio" && (
              <div className={`rounded-lg border px-3 py-2 text-[10px] space-y-1.5 ${
                appSettings?.has_twilio
                  ? "border-blue-400/30 bg-blue-400/5 text-blue-300"
                  : "border-amber-400/30 bg-amber-400/5 text-amber-300"
              }`}>
                {appSettings?.has_twilio ? (
                  <>
                    <span className="flex items-center gap-1.5 font-semibold">
                      <CheckCircle2 className="w-3 h-3" />
                      {t("Twilio connected · Sandbox +14155238886")}
                    </span>
                    <p className="text-[9px] opacity-80">
                      Sends via <strong>{t("Content Template")}</strong> with 3 quick-reply buttons (✅ Yes · 📞 Call Me · ❌ Not Now).
                      Variables auto-filled from customer loan details.
                    </p>
                    <p className="text-[9px] opacity-60 font-mono">{t("Template SID: HX2bc78adf93fb63c4b571799910d53776")}</p>
                  </>
                ) : (
                  <span>
                    Twilio credentials missing. Add <code className="font-mono">{t("TWILIO_ACCOUNT_SID")}</code>,{" "}
                    <code className="font-mono">{t("TWILIO_AUTH_TOKEN")}</code> {t("to")} <code className="font-mono">.env</code>.
                  </span>
                )}
              </div>
            )}
            {activeTab === "mock" && (
              <div className="rounded-lg border border-border/40 bg-muted/20 px-3 py-2 text-[10px] text-muted-foreground">
                {t("Messages are logged to the CRM database but not delivered. Safe for dev and demos.")}
              </div>
            )}
          </div>
        </div>
        </div>

        {/* Draft rows */}
        <div className="overflow-y-auto flex-1 px-5 py-3 space-y-3">
          {loading && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Looking up phone numbers…
            </div>
          )}
          {rows.map((r, i) => {
            const res = r.sendResult;
            const isSentOk = res?.status?.startsWith("sent");
            const isErr = res?.status === "error";
            return (
              <div key={i} className={`rounded-xl border p-3 space-y-2 text-xs transition-colors ${
                isSentOk ? "border-emerald-500/30 bg-emerald-500/5" :
                isErr    ? "border-rose-500/30 bg-rose-500/5" :
                           "border-border bg-muted/20"
              }`}>
                {/* Customer name + status */}
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{r.customer_name}</span>
                  {isSentOk && (
                    <span className="flex items-center gap-1 text-emerald-400 text-[10px]">
                      <CheckCircle2 className="w-3 h-3" />
                      {res?.backend === "whatsapp-web" ? "Sent via WhatsApp" :
                       res?.backend === "twilio"       ? t("Sent via Twilio") : t("Logged")}
                    </span>
                  )}
                  {isErr && (
                    <span className="flex items-center gap-1 text-rose-400 text-[10px]">
                      <AlertCircle className="w-3 h-3" /> {res?.error ?? "Error"}
                    </span>
                  )}
                </div>

                {/* Phone — sandbox shows redirect notice, prod shows editable field */}
                {sandbox ? (
                  <div className="flex items-center gap-2 text-[10px] text-amber-400/80">
                    <Phone className="w-3 h-3 flex-shrink-0" />
                    <span>{t("CRM:")} <span className="font-mono line-through opacity-50">{r.phone || "no number"}</span></span>
                    <span className="text-amber-400">{t("→ redirected to")} <span className="font-mono">{sandboxNumber}</span></span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <Phone className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                    <input
                      type="tel"
                      placeholder="+91 9876543210"
                      value={r.phone}
                      onChange={(e) => updatePhone(i, e.target.value)}
                      disabled={!!res}
                      className="flex-1 bg-background border border-border rounded px-2 py-1 text-xs font-mono outline-none focus:border-primary/60 disabled:opacity-50"
                    />
                  </div>
                )}

                {/* WhatsApp-style message bubble */}
                <div className="rounded-xl rounded-tl-sm bg-[#1a1a1a] border border-white/5 p-3 max-h-56 overflow-y-auto">
                  <div className="flex items-center gap-1.5 mb-2">
                    <div className="w-5 h-5 rounded-full bg-[#25d366] flex items-center justify-center flex-shrink-0">
                      <svg viewBox="0 0 24 24" className="w-3 h-3 fill-white"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.127.558 4.126 1.533 5.859L.057 23.486a.5.5 0 00.636.606l5.82-1.527A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-1.907 0-3.693-.484-5.25-1.334l-.374-.214-3.875 1.016 1.035-3.77-.234-.389A9.957 9.957 0 012 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10z"/></svg>
                    </div>
                    <span className="text-[9px] text-[#25d366] font-semibold">{t("BankingRM AI")}</span>
                    {activeTab === "twilio" && (
                      <span className="text-[8px] text-blue-400 border border-blue-400/30 px-1 py-0.5 rounded ml-1">{t("Twilio template")}</span>
                    )}
                    <span className="text-[9px] text-white/30 ml-auto">{t("Preview")}</span>
                  </div>
                  <div
                    className="text-[11px] leading-relaxed text-white/90 whitespace-pre-line"
                    dangerouslySetInnerHTML={{
                      __html: r.message
                        .replace(/\*(.*?)\*/g, '<strong>$1</strong>')
                        .replace(/_(.*?)_/g, '<em>$1</em>')
                    }}
                  />
                  <div className="text-[9px] text-white/30 text-right mt-1.5">
                    {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ✓✓
                  </div>
                  {/* Quick-reply buttons — shown for Twilio template */}
                  {activeTab === "twilio" && (
                    <div className="mt-2.5 pt-2 border-t border-white/10 flex flex-col gap-1">
                      {["✅ Yes, Interested!", "📞 Call Me", "❌ Not Now"].map((btn) => (
                        <div key={btn} className="text-center text-[10px] text-blue-300 border border-blue-400/25 rounded-lg py-1.5 bg-blue-400/5 font-medium">
                          {btn}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {r.personalization_note && (
                  <div className="text-[9px] text-primary/60">🎯 {r.personalization_note}</div>
                )}
                {res?.sent_to && res.sandbox && (
                  <div className="text-[9px] text-amber-400/70 font-mono">Sent to: {res.sent_to} (sandbox)</div>
                )}
                {res?.sid && <div className="text-[9px] text-muted-foreground font-mono">Twilio SID: {res.sid}</div>}
                {res?.messageId && <div className="text-[9px] text-muted-foreground font-mono">ID: {res.messageId}</div>}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-5 pb-5 pt-3 border-t border-border flex-shrink-0 flex gap-2">
          {!sent ? (
            <>
              <button
                onClick={handleSend}
                disabled={sending || !canSend}
                className="flex-1 text-xs px-4 py-2.5 rounded-lg gradient-primary text-primary-foreground font-medium flex items-center justify-center gap-1.5 hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {sending ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t("Sending…")}</>
                ) : (
                  <><Send className="w-3.5 h-3.5" />
                    {sandbox
                      ? `Send ${rows.length} msg${rows.length !== 1 ? "s" : ""} → ${sandboxNumber} (sandbox)`
                      : `Send ${rows.length} msg${rows.length !== 1 ? "s" : ""} to customers (prod)`}
                  </>
                )}
              </button>
              <button onClick={onClose} className="text-xs px-4 py-2.5 rounded-lg border border-border bg-muted/40 hover:bg-muted/60">
                {t("Cancel")}
              </button>
            </>
          ) : (
            <button onClick={onClose} className="flex-1 text-xs px-4 py-2.5 rounded-lg border border-border bg-muted/40 hover:bg-muted/60 flex items-center justify-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              {sentCount} of {rows.length} sent — Close
            </button>
          )}
        </div>
      </motion.div>
    </div>,
    document.body
  );
}

// ── DraftsCard ─────────────────────────────────────────────────────────────────

function DraftsCard({ drafts }: { drafts: AgentResult["drafts"] }) {
  // null = closed, "all" = all drafts, index = single customer
  const [sendTarget, setSendTarget] = useState<null | "all" | number>(null);

  const modalDrafts = sendTarget === "all"
    ? drafts
    : sendTarget !== null
      ? [drafts[sendTarget]]
      : [];

  return (
    <>
      <div className="rounded-xl border border-primary/30 bg-gradient-to-br from-primary/10 to-accent/5 p-4 space-y-3">
        <div className="text-xs font-semibold flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          {drafts.length} outreach draft{drafts.length !== 1 ? "s" : ""} — personalized with real data
        </div>
        {drafts.slice(0, 3).map((d, i) => (
          <div key={i} className="rounded-lg bg-card/60 p-3 text-xs space-y-2 border border-border/30">
            {/* Header row */}
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="font-semibold">{d.customer_name}</span>
              <div className="flex items-center gap-1.5 flex-wrap">
                <ConvBadge prob={d.conversion_probability} />
                <span className="text-[9px] text-muted-foreground uppercase tracking-wide border border-border/40 rounded px-1 py-0.5">
                  {d.framework}
                </span>
                <span className="text-[9px] text-muted-foreground capitalize border border-border/40 rounded px-1 py-0.5">
                  {d.tone}
                </span>
                {d.offer_expiry && (
                  <span className="text-[9px] text-muted-foreground">⏰ {d.offer_expiry}</span>
                )}
                {/* Per-customer send button */}
                <button
                  onClick={() => setSendTarget(i)}
                  className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 font-medium transition-colors"
                  title={`Send to ${d.customer_name} only`}
                >
                  <Send className="w-2.5 h-2.5" /> Send
                </button>
              </div>
            </div>
            {/* Personalization signals */}
            {d.personalization_note && (
              <div className="text-[10px] text-primary/70 bg-primary/5 rounded px-2 py-1 border border-primary/10">
                🎯 {d.personalization_note}
              </div>
            )}
            {/* WhatsApp message */}
            <div className="whitespace-pre-line leading-relaxed text-foreground/90 bg-muted/20 rounded p-2 font-mono text-[10px]">
              {d.message}
            </div>
            {/* Short variant */}
            {d.short_variant && (
              <div className="text-[9px] text-muted-foreground italic border-t border-border/30 pt-1.5">
                📱 SMS: {d.short_variant}
              </div>
            )}
          </div>
        ))}
        <div className="flex gap-2">
          <button
            onClick={() => setSendTarget("all")}
            className="text-xs px-3 py-1.5 rounded-lg gradient-primary text-primary-foreground font-medium flex items-center gap-1.5 hover:opacity-90"
          >
            <Send className="w-3 h-3" /> Send to all customers
          </button>
          <button className="text-xs px-3 py-1.5 rounded-lg border border-border bg-muted/40 hover:bg-muted/60">
            {t("Schedule cadence")}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {sendTarget !== null && modalDrafts.length > 0 && (
          <SendModal drafts={modalDrafts} onClose={() => setSendTarget(null)} />
        )}
      </AnimatePresence>
    </>
  );
}

function CustomersCard({ customers }: { customers: AgentResult["customers"] }) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 overflow-hidden">
      <div className="px-3 py-2 text-xs font-semibold border-b border-border">{customers.length} customers found</div>
      {customers.slice(0, 5).map((c) => (
        <div key={c.customer_id} className="flex items-center gap-3 px-3 py-2 text-xs border-b border-border/50 last:border-0">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-primary/40 to-accent/40 grid place-items-center text-[9px] font-semibold flex-shrink-0">
            {c.name.split(" ").map((p: string) => p[0]).slice(0, 2).join("")}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-medium truncate">{c.name}</div>
            <div className="text-[10px] text-muted-foreground">{c.city} · {c.segment}</div>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="font-mono">{c.credit_score}</div>
            <div className="text-[10px] text-muted-foreground">{t("credit")}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function WorkflowMini({ running, steps, splitMode, plannerModel, executorModel, globalModel }: {
  running: boolean;
  steps?: AgentStep[];
  splitMode: boolean;
  plannerModel: string;
  executorModel: string;
  globalModel: string;
}) {
  const planSteps = steps?.filter((s) => s.type === "plan") ?? [];
  const toolSteps = steps?.filter((s) => s.type === "tool") ?? [];

  const nodes = [
    {
      label: t("Planner"),
      model: splitMode ? modelById(plannerModel).label : modelById(globalModel).label,
      color: "primary",
      done: planSteps.length > 0,
    },
    ...toolSteps.map((s) => ({
      label: s.label,
      model: splitMode ? modelById(executorModel).label : modelById(globalModel).label,
      color: "accent",
      done: true,
    })),
    {
      label: t("Responder"),
      model: splitMode ? modelById(plannerModel).label : modelById(globalModel).label,
      color: "primary",
      done: !running && (steps?.length ?? 0) > 0,
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto space-y-2 pr-1">
      {running && nodes.length <= 1 && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" />
          {t("Waiting for agent…")}
        </div>
      )}
      {nodes.map((n, i) => (
        <div key={`${n.label}-${i}`} className="relative">
          <div className={`flex items-center gap-2.5 p-2.5 rounded-lg border transition ${
            n.done ? "border-success/40 bg-success/5" : "border-border bg-muted/20"
          }`}>
            <div className={`w-7 h-7 rounded grid place-items-center text-[10px] font-mono font-semibold ${
              n.done ? "bg-success/20 text-success" : "bg-muted text-muted-foreground"
            }`}>
              {String(i + 1).padStart(2, "0")}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate">{n.label}</div>
              <div className="text-[9px] text-muted-foreground truncate">{n.model}</div>
            </div>
            {n.done && <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0" />}
          </div>
          {i < nodes.length - 1 && <div className={`ml-6 h-2 w-px ${n.done ? "bg-success/40" : "bg-border"}`} />}
        </div>
      ))}
    </div>
  );
}
