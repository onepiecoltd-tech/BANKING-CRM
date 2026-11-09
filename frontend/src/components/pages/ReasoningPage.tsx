import { PageHeader } from "./DashboardPage";
import { Network } from "lucide-react";
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

      <div className="glass rounded-xl p-6 shadow-card text-sm text-muted-foreground">
        {t("Sơ đồ trên là kiến trúc điều phối của trợ lý AI. Nhật ký truy vết từng lượt chạy (công cụ đã gọi, thời gian, độ tin cậy) chỉ xuất hiện khi có lượt chạy thật — hiện chưa có.",
          "The graph above is the assistant's orchestration architecture. Per-run traces (tools called, timings, confidence) appear only when real runs exist — none yet.")}
      </div>
    </div>
  );
}
