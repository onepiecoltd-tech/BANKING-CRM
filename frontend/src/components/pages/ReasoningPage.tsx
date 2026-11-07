import { PageHeader, tooltipStyle } from "./DashboardPage";
import { PLAYBOOK_STEPS } from "@/lib/agentSim";
import { Brain, Wrench, Sparkles, MessageSquare, Network, CheckCircle2 } from "lucide-react";
import { t } from "@/lib/i18n";

export function ReasoningPage() {
  const nodes = [
    { id: "user", label: t("User Query"), x: 50, y: 50, type: "io" },
    { id: "planner", label: t("Planner"), x: 220, y: 50, type: "plan" },
    { id: "query", label: "query_customers", x: 400, y: 20, type: "tool" },
    { id: "score", label: "score_value", x: 400, y: 90, type: "tool" },
    { id: "predict", label: "predict_conversion", x: 580, y: 20, type: "tool" },
    { id: "recommend", label: "recommend_products", x: 580, y: 90, type: "tool" },
    { id: "supp", label: "check_suppressions", x: 760, y: 50, type: "tool" },
    { id: "reflect", label: t("Reflection"), x: 920, y: 50, type: "reflect" },
    { id: "draft", label: "draft_outreach", x: 1080, y: 50, type: "tool" },
    { id: "synth", label: t("Synthesizer"), x: 1240, y: 50, type: "respond" },
  ];
  const edges = [
    ["user","planner"],["planner","query"],["planner","score"],["query","predict"],["score","recommend"],
    ["predict","supp"],["recommend","supp"],["supp","reflect"],["reflect","draft"],["draft","synth"],
  ];
  const colorFor = (t: string) =>
    t === "plan" ? "#5b8bff" : t === "tool" ? "#34d399" : t === "reflect" ? "#fbbf24" : t === "respond" ? "#a78bfa" : "#94a3b8";

  return (
    <div className="space-y-5">
      <PageHeader
        title="Reasoning & Tool Trace"
        subtitle={t("Inspect the agent's decision graph, tool calls, state transitions, and confidence over time.")}
        actions={
          <div className="text-xs px-3 py-1.5 rounded-lg glass flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-success pulse-dot" />
            {t("LangGraph v0.2 · Trace #47281")}
          </div>
        }
      />

      {/* Graph */}
      <div className="glass rounded-xl p-5 shadow-card">
        <div className="flex items-center gap-2 mb-3">
          <Network className="w-4 h-4 text-primary" />
          <div className="text-sm font-semibold">{t("Orchestration Graph")}</div>
        </div>
        <div className="overflow-x-auto grid-pattern rounded-lg">
          <svg viewBox="0 0 1320 140" className="w-full min-w-[1100px] h-[180px]">
            {edges.map(([a, b], i) => {
              const A = nodes.find((n) => n.id === a)!;
              const B = nodes.find((n) => n.id === b)!;
              return (
                <line key={i} x1={A.x + 60} y1={A.y + 18} x2={B.x} y2={B.y + 18}
                  stroke="#5b8bff" strokeOpacity={0.4} strokeWidth={1.5} strokeDasharray="3 3" />
              );
            })}
            {nodes.map((n) => (
              <g key={n.id} transform={`translate(${n.x},${n.y})`}>
                <rect width={130} height={36} rx={8}
                  fill={`${colorFor(n.type)}22`} stroke={colorFor(n.type)} strokeOpacity={0.6} strokeWidth={1} />
                <text x={65} y={22} textAnchor="middle" fill="white" fontSize="11" fontFamily="JetBrains Mono">
                  {n.label}
                </text>
              </g>
            ))}
          </svg>
        </div>
      </div>

      {/* Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 glass rounded-xl p-5 shadow-card">
          <div className="text-sm font-semibold mb-4">{t("Execution Timeline")}</div>
          <div className="space-y-2">
            {PLAYBOOK_STEPS.map((s, i) => {
              const Icon = s.type === "plan" ? Brain : s.type === "tool" ? Wrench : s.type === "reflect" ? Sparkles : MessageSquare;
              return (
                <div key={s.id} className="flex gap-3 items-start">
                  <div className="flex flex-col items-center">
                    <div className="w-7 h-7 rounded-lg bg-muted/60 grid place-items-center" style={{ color: colorFor(s.type) }}>
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    {i < PLAYBOOK_STEPS.length - 1 && <div className="w-px h-8 bg-border mt-1" />}
                  </div>
                  <div className="flex-1 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium">{s.label}</span>
                      <CheckCircle2 className="w-3 h-3 text-success" />
                      {s.toolCall && <span className="text-[10px] text-muted-foreground font-mono">{s.toolCall.durationMs}ms</span>}
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-0.5">{s.detail}</div>
                    {s.toolCall && (
                      <div className="mt-1.5 grid grid-cols-2 gap-2">
                        <pre className="text-[10px] font-mono p-2 rounded bg-muted/40 overflow-x-auto"><span className="text-primary">{t("in:")}</span> {JSON.stringify(s.toolCall.input)}</pre>
                        <pre className="text-[10px] font-mono p-2 rounded bg-muted/40 overflow-x-auto"><span className="text-accent">{t("out:")}</span> {JSON.stringify(s.toolCall.output)}</pre>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-4">
          <div className="glass rounded-xl p-5 shadow-card">
            <div className="text-sm font-semibold mb-3">{t("State Memory")}</div>
            <pre className="text-[10px] font-mono p-3 rounded bg-muted/40 overflow-x-auto leading-relaxed">{`{
  "intent": "loan_outreach",
  "filters": {
    "city": "Mumbai",
    "segments": ["HNI","Affluent"]
  },
  "audience_count": 14,
  "suppressed": 4,
  "selected_product": "Personal Loan",
  "framework": "AIDA + Cialdini",
  "confidence": 0.87
}`}</pre>
          </div>

          <div className="glass rounded-xl p-5 shadow-card">
            <div className="text-sm font-semibold mb-3">{t("Confidence Over Steps")}</div>
            <div className="space-y-2">
              {[
                { name: "Planner", v: 78 }, { name: "Tools", v: 84 },
                { name: "Reflect", v: 91 }, { name: "Synth", v: 87 },
              ].map((c) => (
                <div key={c.name}>
                  <div className="flex justify-between text-[10px] text-muted-foreground"><span>{c.name}</span><span>{c.v}%</span></div>
                  <div className="h-1.5 bg-muted rounded mt-0.5"><div className="h-full rounded gradient-primary" style={{ width: `${c.v}%` }} /></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
