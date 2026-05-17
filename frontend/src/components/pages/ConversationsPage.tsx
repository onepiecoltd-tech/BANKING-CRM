import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { PageHeader } from "./DashboardPage";
import { pipeline as pipelineApi, type PipelineData, type PipelineReply } from "@/lib/api";
import {
  MessageSquare, CheckCheck, Sparkles, RefreshCw,
  TrendingUp, Users, Target, ArrowRight, Phone,
  Clock, Inbox, AlertTriangle, ChevronRight, X, Keyboard,
} from "lucide-react";

// ── Intent badge colours ──────────────────────────────────────────────────────

const INTENT_STYLE: Record<string, string> = {
  YES:              "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  NO:               "bg-red-500/20 text-red-400 border-red-500/30",
  PRICE_OBJECTION:  "bg-amber-500/20 text-amber-400 border-amber-500/30",
  HAS_PRODUCT:      "bg-blue-500/20 text-blue-400 border-blue-500/30",
  DOCUMENTS:        "bg-purple-500/20 text-purple-400 border-purple-500/30",
  TIMELINE:         "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
  WANTS_CALLBACK:   "bg-orange-500/20 text-orange-400 border-orange-500/30",
  THINKING:         "bg-slate-500/20 text-slate-400 border-slate-500/30",
  GENERAL:          "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
  INTERESTED:       "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};

const STAGE_ORDER = [
  "NEW", "CONTACTED", "ENGAGED", "CONSIDERING",
  "CALLBACK_REQUESTED", "INTERESTED", "OBJECTION",
  "DECLINED", "CONVERTED", "WON", "LOST",
];

function intentLabel(state: string) {
  const map: Record<string, string> = {
    YES: "✅ Yes / Interested",
    NO: "❌ Not Interested",
    PRICE_OBJECTION: "💰 Price Objection",
    HAS_PRODUCT: "📋 Has Product",
    DOCUMENTS: "📄 Docs Query",
    TIMELINE: "⏱️ Timeline Query",
    WANTS_CALLBACK: "📞 Callback Request",
    THINKING: "🤔 Considering",
    GENERAL: "💬 General",
    INTERESTED: "✅ Interested",
  };
  return map[state] ?? state;
}

// ── Filter pill types ─────────────────────────────────────────────────────────

type FilterType = "ALL" | "HOT" | "ENGAGED" | "OBJECTION" | "NO_REPLY" | "CONVERTED";

const FILTER_PILLS: { id: FilterType; label: string }[] = [
  { id: "ALL",       label: "All" },
  { id: "HOT",       label: "🔥 Hot" },
  { id: "ENGAGED",   label: "💬 Engaged" },
  { id: "OBJECTION", label: "❌ Objection" },
  { id: "NO_REPLY",  label: "🔕 No Reply" },
  { id: "CONVERTED", label: "✅ Converted" },
];

function filterReplies(replies: PipelineReply[], filter: FilterType): PipelineReply[] {
  switch (filter) {
    case "ALL":
      return replies;
    case "HOT":
      return replies.filter(r =>
        r.pipeline_state === "INTERESTED" || r.pipeline_state === "CALLBACK_REQUESTED"
      );
    case "ENGAGED":
      return replies.filter(r => r.pipeline_state === "ENGAGED");
    case "OBJECTION":
      return replies.filter(r => r.pipeline_state === "OBJECTION");
    case "NO_REPLY":
      return replies.filter(r => !r.response || r.response.trim() === "");
    case "CONVERTED":
      return replies.filter(r =>
        r.pipeline_state === "CONVERTED" || r.pipeline_state === "WON"
      );
    default:
      return replies;
  }
}

// ── Needs Human detection ─────────────────────────────────────────────────────

const HUMAN_TRIGGER_PHRASES = [
  "expensive", "high rate", "already have", "other bank", "different bank",
];

function needsHuman(reply: PipelineReply): boolean {
  if (reply.pipeline_state === "CALLBACK_REQUESTED") return true;
  const text = (reply.response ?? "").toLowerCase();
  return HUMAN_TRIGGER_PHRASES.some(phrase => text.includes(phrase));
}

// ── Funnel bar ────────────────────────────────────────────────────────────────

function FunnelBar({ funnel }: { funnel: { stage: string; count: number }[] }) {
  const ordered = STAGE_ORDER
    .map(s => funnel.find(f => f.stage === s))
    .filter(Boolean) as { stage: string; count: number }[];

  const max = Math.max(...ordered.map(f => f.count), 1);
  const highlight: Record<string, string> = {
    INTERESTED: "bg-emerald-500",
    CONVERTED: "bg-emerald-600",
    WON: "bg-emerald-700",
    OBJECTION: "bg-amber-500",
    DECLINED: "bg-red-500",
    LOST: "bg-red-600",
  };

  return (
    <div className="space-y-1.5">
      {ordered.map(({ stage, count }) => (
        <div key={stage} className="flex items-center gap-2">
          <div className="w-28 text-[10px] font-mono text-muted-foreground text-right truncate">
            {stage}
          </div>
          <div className="flex-1 h-5 bg-muted/30 rounded overflow-hidden">
            <div
              className={`h-full rounded transition-all duration-700 ${highlight[stage] ?? "bg-primary/60"}`}
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
          <div className="w-6 text-[11px] font-semibold text-right">{count}</div>
        </div>
      ))}
    </div>
  );
}

// ── Conversation thread card ──────────────────────────────────────────────────

function ConvCard({
  reply,
  active,
  onClick,
  resolved,
}: {
  reply: PipelineReply;
  active: boolean;
  onClick: () => void;
  resolved: boolean;
}) {
  const badge = INTENT_STYLE[reply.pipeline_state] ?? INTENT_STYLE.GENERAL;
  const initials = reply.customer_name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
  const time = new Date(reply.date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const showNeedsHuman = needsHuman(reply) && !resolved;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex items-start gap-3 px-3 py-3 rounded-lg transition
        ${active ? "bg-primary/15 border border-primary/30" : "hover:bg-muted/40 border border-transparent"}`}
    >
      <div className="w-9 h-9 rounded-full gradient-primary grid place-items-center text-xs font-bold text-primary-foreground flex-shrink-0">
        {initials}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-1 mb-0.5">
          <span className="text-sm font-medium truncate">{reply.customer_name}</span>
          <span className="text-[10px] text-muted-foreground flex-shrink-0">{time}</span>
        </div>
        <div className="text-[11px] text-muted-foreground truncate">{reply.response}</div>
        <div className="flex items-center gap-1.5 flex-wrap mt-1">
          <div className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border ${badge}`}>
            {intentLabel(reply.pipeline_state)}
          </div>
          {showNeedsHuman && (
            <div className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border bg-red-500/20 text-red-400 border-red-500/30 font-semibold">
              👋 Needs Human
            </div>
          )}
          {resolved && (
            <div className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
              ✅ Resolved
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

// ── WhatsApp bubble ───────────────────────────────────────────────────────────

function WaBubble({ text, from, time }: { text: string; from: "customer" | "agent"; time: string }) {
  const isAgent = from === "agent";
  const html = text
    .replace(/\*(.*?)\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br/>");

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      className={`flex items-end gap-2 ${isAgent ? "justify-start" : "justify-end"}`}
    >
      {isAgent && (
        <div className="w-7 h-7 rounded-full gradient-primary grid place-items-center flex-shrink-0">
          <Sparkles className="w-3.5 h-3.5 text-primary-foreground" />
        </div>
      )}
      <div className={`max-w-[78%] min-w-0 rounded-2xl px-3 py-2 text-sm leading-snug shadow-sm ${
        isAgent
          ? "bg-[#1e2535] border border-white/8 rounded-bl-sm"
          : "bg-[#025144] border border-white/8 rounded-br-sm"
      }`}>
        <div
          className="break-words overflow-wrap-anywhere whitespace-pre-wrap"
          style={{ overflowWrap: "anywhere" }}
          dangerouslySetInnerHTML={{ __html: html }}
        />
        <div className="flex items-center justify-end gap-1 mt-1 text-[9px] text-muted-foreground">
          {time}
          {!isAgent && <CheckCheck className="w-3 h-3 text-blue-400" />}
        </div>
      </div>
    </motion.div>
  );
}

// ── Stage tracker ─────────────────────────────────────────────────────────────

const VISIBLE_STAGES = ["CONTACTED", "ENGAGED", "INTERESTED", "CALLBACK_REQUESTED", "CONVERTED"];

function StageTracker({ stage }: { stage: string }) {
  const normalised = stage === "WON" ? "CONVERTED" : stage === "LOST" ? "DECLINED" : stage;
  const idx = VISIBLE_STAGES.indexOf(normalised);

  return (
    <div className="space-y-1.5">
      {VISIBLE_STAGES.map((s, i) => {
        const done = i < idx;
        const current = i === idx;
        return (
          <div key={s} className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs transition ${
            current ? "bg-primary/15 text-primary border border-primary/30" :
            done ? "text-emerald-400" : "text-muted-foreground"
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${
              current ? "bg-primary animate-pulse" :
              done ? "bg-emerald-400" : "bg-muted-foreground/30"
            }`} />
            <span className="font-mono font-medium">{s}</span>
            {current && (
              <AnimatePresence>
                <motion.span
                  initial={{ width: 0, opacity: 0 }} animate={{ width: "auto", opacity: 1 }}
                  className="ml-auto text-[10px] text-muted-foreground"
                >
                  active
                </motion.span>
              </AnimatePresence>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Follow-up Cadence ─────────────────────────────────────────────────────────

const CADENCE_STEPS = [
  { day: 0,  label: "Initial outreach sent" },
  { day: 3,  label: "Value-add follow-up" },
  { day: 7,  label: "Social proof" },
  { day: 14, label: "Last attempt" },
];

function FollowUpCadence({ interactionDate }: { interactionDate: string }) {
  const startDate = new Date(interactionDate);
  const now = new Date();
  const daysSinceStart = Math.floor((now.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));

  return (
    <div className="glass rounded-xl p-4 shadow-card">
      <div className="text-xs font-semibold mb-3 flex items-center gap-2">
        <span>📅</span>
        Follow-up Schedule
      </div>
      <div className="space-y-2">
        {CADENCE_STEPS.map((step, i) => {
          const isDone = daysSinceStart > step.day;
          const isCurrent = daysSinceStart >= step.day && (i === CADENCE_STEPS.length - 1 || daysSinceStart < CADENCE_STEPS[i + 1].day);
          const daysUntil = step.day - daysSinceStart;

          let statusText = "";
          if (isDone && !isCurrent) {
            statusText = "✓";
          } else if (isCurrent) {
            statusText = "Active";
          } else if (daysUntil <= 3) {
            statusText = `Due in ${daysUntil} day${daysUntil !== 1 ? "s" : ""}`;
          } else {
            statusText = "Pending";
          }

          return (
            <div key={step.day} className={`flex items-center gap-2 text-xs ${
              isDone && !isCurrent ? "text-emerald-400" :
              isCurrent ? "text-primary" :
              "text-muted-foreground"
            }`}>
              <span className="flex-shrink-0 text-base leading-none">
                {isDone && !isCurrent ? "●" : isCurrent ? "●" : "○"}
              </span>
              <span className="font-mono w-12 flex-shrink-0 text-[10px]">Day {step.day}</span>
              <span className="flex-1 truncate">{step.label}</span>
              <span className={`text-[10px] flex-shrink-0 ${
                isDone && !isCurrent ? "text-emerald-400" :
                isCurrent ? "text-primary font-semibold" :
                daysUntil <= 3 && daysUntil > 0 ? "text-amber-400" :
                "text-muted-foreground"
              }`}>
                {isDone && !isCurrent ? "✓" : statusText}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Keyboard Shortcuts Overlay ────────────────────────────────────────────────

function KeyboardHelp({ onClose }: { onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="glass rounded-2xl p-6 shadow-2xl w-80 border border-border"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Keyboard className="w-4 h-4 text-primary" />
            Keyboard Shortcuts
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-2.5">
          {[
            { key: "J", desc: "Next conversation" },
            { key: "K", desc: "Previous conversation" },
            { key: "R", desc: "Mark as resolved" },
            { key: "?", desc: "Toggle this help" },
          ].map(({ key, desc }) => (
            <div key={key} className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{desc}</span>
              <kbd className="px-2.5 py-1 rounded-lg bg-muted/60 border border-border text-xs font-mono font-semibold text-foreground">
                {key}
              </kbd>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

// ── Morning Digest Banner ─────────────────────────────────────────────────────

function MorningDigestBanner({
  callbackCount,
  followupCount,
  onDismiss,
}: {
  callbackCount: number;
  followupCount: number;
  onDismiss: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      className="w-full flex items-center justify-between gap-4 px-4 py-2.5 rounded-xl bg-blue-500/15 border border-blue-500/30 text-blue-300 text-xs"
    >
      <div className="flex items-center gap-2">
        <span className="text-base">📋</span>
        <span className="font-medium">
          {callbackCount} callback{callbackCount !== 1 ? "s" : ""} requested
          {followupCount > 0 && ` · ${followupCount} follow-up${followupCount !== 1 ? "s" : ""} due today`}
        </span>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button className="px-2.5 py-1 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/30 text-blue-300 transition text-[11px] font-medium">
          View all
        </button>
        <button
          onClick={onDismiss}
          className="p-1 rounded-lg hover:bg-blue-500/20 text-blue-400 hover:text-blue-200 transition"
          aria-label="Dismiss banner"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </motion.div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function ConversationsPage() {
  const [data, setData] = useState<PipelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<PipelineReply | null>(null);

  // New state for features
  const [activeFilter, setActiveFilter] = useState<FilterType>("ALL");
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  const chatRef = useRef<HTMLDivElement>(null);
  const POLL_MS = 8000; // refresh every 8 s

  const load = async () => {
    try {
      const d = await pipelineApi.get();
      setData(d);
      if (!selected && d.recent_replies.length > 0) {
        setSelected(d.recent_replies[0]);
      }
    } catch (e) {
      console.error("pipeline fetch failed", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [selected]);

  const replies = data?.recent_replies ?? [];
  const filteredReplies = filterReplies(replies, activeFilter);

  // Unique ID for a reply (used in resolvedIds set)
  const replyId = (r: PipelineReply) => `${r.customer_id}-${r.date}`;

  // Keep selectedIndex in sync when filtered list changes
  useEffect(() => {
    if (selected) {
      const idx = filteredReplies.findIndex(
        r => r.customer_id === selected.customer_id && r.date === selected.date
      );
      if (idx !== -1) setSelectedIndex(idx);
    }
  }, [activeFilter, filteredReplies.length]);

  // ── Keyboard navigation ────────────────────────────────────────────────────
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Don't fire if focus is inside an input/textarea
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return;
      }

      switch (e.key.toLowerCase()) {
        case "j": {
          e.preventDefault();
          setSelectedIndex(prev => {
            const next = Math.min(prev + 1, filteredReplies.length - 1);
            if (filteredReplies[next]) setSelected(filteredReplies[next]);
            return next;
          });
          break;
        }
        case "k": {
          e.preventDefault();
          setSelectedIndex(prev => {
            const next = Math.max(prev - 1, 0);
            if (filteredReplies[next]) setSelected(filteredReplies[next]);
            return next;
          });
          break;
        }
        case "r": {
          e.preventDefault();
          if (selected) {
            setResolvedIds(prev => {
              const next = new Set(prev);
              const id = replyId(selected);
              if (next.has(id)) next.delete(id); else next.add(id);
              return next;
            });
          }
          break;
        }
        case "?": {
          e.preventDefault();
          setShowKeyboardHelp(prev => !prev);
          break;
        }
      }
    },
    [filteredReplies, selected]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // ── KPI tiles ──────────────────────────────────────────────────────────────
  const kpis = [
    { label: "Contacted",  val: data?.total_contacted ?? 0, icon: <Users className="w-4 h-4" />,    color: "text-blue-400" },
    { label: "Replied",    val: data?.total_replied   ?? 0, icon: <MessageSquare className="w-4 h-4" />, color: "text-primary" },
    { label: "Converted",  val: data?.total_converted ?? 0, icon: <Target className="w-4 h-4" />,   color: "text-emerald-400" },
    {
      label: "Conv Rate",
      val: data && data.total_replied > 0
        ? `${Math.round((data.total_converted / data.total_replied) * 100)}%`
        : "—",
      icon: <TrendingUp className="w-4 h-4" />,
      color: "text-amber-400",
    },
  ];

  // ── Morning digest counts ──────────────────────────────────────────────────
  const callbackCount = replies.filter(r => r.pipeline_state === "CALLBACK_REQUESTED").length;
  // "Follow-ups due today" = conversations that are 3 days old (day 3 step) or 7 days old (day 7 step)
  const now = new Date();
  const followupCount = replies.filter(r => {
    const age = Math.floor((now.getTime() - new Date(r.date).getTime()) / (1000 * 60 * 60 * 24));
    return age === 3 || age === 7;
  }).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Loading pipeline data…
        </div>
      </div>
    );
  }

  return (
    <>
      {/* ── Keyboard Help Overlay ─────────────────────────────────────────── */}
      <AnimatePresence>
        {showKeyboardHelp && (
          <KeyboardHelp onClose={() => setShowKeyboardHelp(false)} />
        )}
      </AnimatePresence>

      <div className="space-y-5 h-[calc(100vh-7rem)] flex flex-col">
        {/* ── Morning Digest Banner ───────────────────────────────────────── */}
        <AnimatePresence>
          {callbackCount > 0 && !bannerDismissed && (
            <MorningDigestBanner
              callbackCount={callbackCount}
              followupCount={followupCount}
              onDismiss={() => setBannerDismissed(true)}
            />
          )}
        </AnimatePresence>

        <PageHeader
          title="WhatsApp Inbox & Pipeline"
          subtitle="Live AI sales conversations — replies tracked, intents classified, funnel updated automatically."
          actions={
            <button
              onClick={load}
              className="text-xs px-3 py-1.5 rounded-lg border border-border bg-muted/40 hover:bg-muted/60 flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
          }
        />

        {/* KPI strip */}
        <div className="grid grid-cols-4 gap-3 flex-shrink-0">
          {kpis.map(({ label, val, icon, color }) => (
            <div key={label} className="glass rounded-xl p-3 shadow-card flex items-center gap-3">
              <div className={`${color} opacity-80`}>{icon}</div>
              <div>
                <div className="text-lg font-bold leading-none">{val}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{label}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0">

          {/* ── Left: inbox list ────────────────────────────────────────────── */}
          <div className="lg:col-span-3 glass rounded-xl flex flex-col shadow-card overflow-hidden">
            {/* Header */}
            <div className="px-3 py-2.5 border-b border-border text-xs font-semibold flex items-center gap-2">
              <Inbox className="w-3.5 h-3.5 text-primary" />
              Replies{" "}
              <span className="ml-auto bg-primary/20 text-primary px-1.5 py-0.5 rounded-full text-[10px]">
                {filteredReplies.length}
              </span>
            </div>

            {/* Filter Pills */}
            <div className="px-2 py-2 border-b border-border flex flex-wrap gap-1">
              {FILTER_PILLS.map(pill => (
                <button
                  key={pill.id}
                  onClick={() => setActiveFilter(pill.id)}
                  className={`px-2.5 py-1 rounded-full text-[10px] font-medium transition-all duration-150 flex-shrink-0
                    ${activeFilter === pill.id
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "bg-muted/40 text-muted-foreground hover:bg-muted/70 hover:text-foreground border border-border"
                    }`}
                >
                  {pill.label}
                </button>
              ))}
            </div>

            {/* Conversation list */}
            <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
              {filteredReplies.length === 0 ? (
                <div className="text-center py-10 text-muted-foreground text-xs">
                  <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  No conversations in this category.
                </div>
              ) : (
                filteredReplies.map((r, i) => (
                  <ConvCard
                    key={`${r.customer_id}-${i}`}
                    reply={r}
                    active={selected?.customer_id === r.customer_id && selected?.date === r.date}
                    onClick={() => {
                      setSelected(r);
                      setSelectedIndex(i);
                    }}
                    resolved={resolvedIds.has(replyId(r))}
                  />
                ))
              )}
            </div>

            {/* Keyboard hint */}
            <div className="px-3 py-2 border-t border-border text-[10px] text-muted-foreground flex items-center justify-between">
              <span>J/K navigate · R resolve · ? help</span>
              <button
                onClick={() => setShowKeyboardHelp(true)}
                className="hover:text-foreground transition"
                aria-label="Show keyboard shortcuts"
              >
                <Keyboard className="w-3 h-3" />
              </button>
            </div>
          </div>

          {/* ── Centre: chat thread ─────────────────────────────────────────── */}
          <div className="lg:col-span-6 glass rounded-xl flex flex-col shadow-card overflow-hidden">
            {selected ? (
              <>
                {/* Header */}
                <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-card/40 flex-shrink-0">
                  <div className="w-9 h-9 rounded-full gradient-primary grid place-items-center text-xs font-bold text-primary-foreground">
                    {selected.customer_name.split(" ").map(w => w[0]).join("").slice(0, 2)}
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-medium flex items-center gap-2">
                      {selected.customer_name}
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    </div>
                    <div className="text-[10px] text-muted-foreground">{selected.product ?? "Unknown product"} · WhatsApp</div>
                  </div>
                  <div className={`text-[10px] px-2 py-0.5 rounded border ${INTENT_STYLE[selected.pipeline_state] ?? INTENT_STYLE.GENERAL}`}>
                    {intentLabel(selected.pipeline_state)}
                  </div>
                </div>

                {/* Chat */}
                <div
                  ref={chatRef}
                  className="flex-1 overflow-y-auto p-4 space-y-3 bg-[radial-gradient(ellipse_at_top,oklch(0.18_0.03_260),oklch(0.14_0.02_260))]"
                >
                  {/* Product context chip */}
                  <div className="flex justify-center mb-2">
                    <span className="text-[10px] text-muted-foreground bg-muted/40 border border-border px-3 py-1 rounded-full">
                      {selected.product_offered ?? selected.product ?? "Outreach"} · AI agent active
                    </span>
                  </div>

                  {/* Full conversation thread if available */}
                  {selected.conversation_thread && selected.conversation_thread.length > 0 ? (
                    <>
                      {selected.conversation_thread.map((turn, idx) => (
                        <WaBubble
                          key={idx}
                          text={turn.content}
                          from={turn.role === "customer" ? "customer" : "agent"}
                          time={turn.date ? new Date(turn.date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                        />
                      ))}
                      {!selected.ai_reply && (
                        <div className="flex justify-center">
                          <span className="text-[10px] text-muted-foreground bg-muted/40 border border-border px-3 py-1 rounded-full flex items-center gap-1">
                            <Clock className="w-3 h-3" /> Awaiting AI reply…
                          </span>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      {/* Fallback: show outreach message if available */}
                      {selected.outreach_message ? (
                        <WaBubble
                          text={selected.outreach_message}
                          from="agent"
                          time={new Date(selected.date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        />
                      ) : (
                        <div className="flex justify-center mb-2">
                          <span className="text-[10px] text-muted-foreground bg-muted/40 border border-border px-3 py-1 rounded-full">
                            Campaign outreach sent · AI agent active
                          </span>
                        </div>
                      )}

                      {/* Customer reply */}
                      <WaBubble
                        text={selected.response}
                        from="customer"
                        time={new Date(selected.date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      />

                      {/* AI reply */}
                      {selected.ai_reply && (
                        <WaBubble
                          text={selected.ai_reply}
                          from="agent"
                          time={new Date(selected.date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        />
                      )}

                      {!selected.ai_reply && (
                        <div className="flex justify-center">
                          <span className="text-[10px] text-muted-foreground bg-muted/40 border border-border px-3 py-1 rounded-full flex items-center gap-1">
                            <Clock className="w-3 h-3" /> Awaiting AI reply…
                          </span>
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* Composer — read only, shows dynamic RM persona name */}
                <div className="border-t border-border p-3 flex items-center gap-2 bg-card/40 flex-shrink-0">
                  <div className="flex-1 bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm text-muted-foreground italic">
                    AI Sales Agent handles replies automatically · {selected.pipeline_state === "CALLBACK_REQUESTED" ? "📞 Callback scheduled" : "Monitoring for response…"}
                  </div>
                  <div className="w-9 h-9 grid place-items-center rounded-lg gradient-primary">
                    <Sparkles className="w-4 h-4 text-primary-foreground" />
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-3">
                <MessageSquare className="w-12 h-12 opacity-20" />
                <div className="text-sm">Select a conversation to view</div>
              </div>
            )}
          </div>

          {/* ── Right: pipeline + actions ───────────────────────────────────── */}
          <div className="lg:col-span-3 space-y-4 overflow-y-auto">
            {/* Stage tracker */}
            <div className="glass rounded-xl p-4 shadow-card">
              <div className="text-xs font-semibold mb-3 flex items-center gap-2">
                <ArrowRight className="w-3.5 h-3.5 text-primary" />
                Pipeline Stage
              </div>
              {selected ? (
                <StageTracker stage={selected.pipeline_state} />
              ) : (
                <div className="text-xs text-muted-foreground">Select a conversation</div>
              )}
            </div>

            {/* Follow-up Cadence */}
            {selected && (
              <FollowUpCadence interactionDate={selected.date} />
            )}

            {/* Funnel overview */}
            {data && (
              <div className="glass rounded-xl p-4 shadow-card">
                <div className="text-xs font-semibold mb-3 flex items-center gap-2">
                  <TrendingUp className="w-3.5 h-3.5 text-primary" />
                  Full Funnel
                </div>
                <FunnelBar funnel={data.funnel} />
              </div>
            )}

            {/* Quick actions for selected conv */}
            {selected && (
              <div className="glass rounded-xl p-4 shadow-card space-y-2">
                <div className="text-xs font-semibold">Quick Actions</div>
                {selected.pipeline_state === "INTERESTED" || selected.pipeline_state === "CALLBACK_REQUESTED" ? (
                  <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-2">
                    🔥 Hot lead — schedule callback!
                  </div>
                ) : selected.pipeline_state === "OBJECTION" ? (
                  <div className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-lg p-2">
                    ⚠️ Objection detected — AI countered. Monitor for follow-up.
                  </div>
                ) : null}
                {needsHuman(selected) && !resolvedIds.has(replyId(selected)) && (
                  <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-2">
                    👋 Human intervention recommended for this lead.
                  </div>
                )}
                <button className="w-full text-xs py-2 rounded-lg gradient-primary text-primary-foreground font-medium flex items-center justify-center gap-1.5">
                  <Phone className="w-3 h-3" /> Schedule Callback
                </button>
                <button className="w-full text-xs py-2 rounded-lg border border-border bg-muted/40 hover:bg-muted/60 flex items-center justify-center gap-1.5">
                  <ChevronRight className="w-3 h-3" /> View Customer Profile
                </button>
                <button
                  onClick={() => {
                    setResolvedIds(prev => {
                      const next = new Set(prev);
                      const id = replyId(selected);
                      if (next.has(id)) next.delete(id); else next.add(id);
                      return next;
                    });
                  }}
                  className={`w-full text-xs py-2 rounded-lg border flex items-center justify-center gap-1.5 transition ${
                    resolvedIds.has(replyId(selected))
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                      : "border-border bg-muted/40 hover:bg-muted/60"
                  }`}
                >
                  {resolvedIds.has(replyId(selected)) ? "✅ Resolved · Undo" : "Mark as Resolved"}
                </button>
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
}
