import { useState, useEffect } from "react";
import { PageHeader, tooltipStyle } from "./DashboardPage";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  PieChart, Pie,
} from "recharts";
import { t } from "@/lib/i18n";

// ─── Fallback data ─────────────────────────────────────────────────────────────

const FALLBACK_REPLY_BY_SEGMENT = [
  { segment: "Mass", reply_rate: 18 },
  { segment: "Affluent", reply_rate: 28 },
  { segment: "Premium", reply_rate: 41 },
];

const FALLBACK_REPLY_BY_DAY = [
  { day: "Mon", reply_rate: 22 },
  { day: "Tue", reply_rate: 27 },
  { day: "Wed", reply_rate: 31 },
  { day: "Thu", reply_rate: 29 },
  { day: "Fri", reply_rate: 25 },
  { day: "Sat", reply_rate: 14 },
  { day: "Sun", reply_rate: 10 },
];

const FALLBACK_FUNNEL = [
  { stage: "CONTACTED", count: 1200 },
  { stage: "ENGAGED", count: 480 },
  { stage: "INTERESTED", count: 210 },
  { stage: "CONVERTED", count: 87 },
];

const FALLBACK_CROSS_SELL = [
  { product: "Credit Card", count: 320 },
  { product: "Personal Loan", count: 210 },
  { product: "FD", count: 175 },
  { product: "Home Loan", count: 95 },
];

const FUNNEL_COLORS: Record<string, string> = {
  CONTACTED: "#5b8bff",
  ENGAGED: "#a78bfa",
  INTERESTED: "#22d3ee",
  CONVERTED: "#34d399",
};

// ─── Types ──────────────────────────────────────────────────────────────────────

interface ReplyRatesData {
  overall?: {
    sent?: number;
    reply_rate?: number;
    conversion_rate?: number;
  };
  by_segment?: Array<{ segment: string; reply_rate: number }>;
  by_day_of_week?: Array<{ day: string; reply_rate: number }>;
}

interface ChurnData {
  at_risk_count?: number;
  high?: number;
  medium?: number;
  low?: number;
}

interface CrossSellData {
  total_opportunities?: number;
  by_product?: Array<{ product: string; count: number }>;
}

interface PipelineData {
  funnel?: Array<{ stage: string; count: number }>;
}

// ─── Component ──────────────────────────────────────────────────────────────────

export function AnalyticsPage() {
  const [replyRates, setReplyRates] = useState<ReplyRatesData | null>(null);
  const [churnData, setChurnData] = useState<ChurnData | null>(null);
  const [crossSell, setCrossSell] = useState<CrossSellData | null>(null);
  const [pipelineData, setPipelineData] = useState<PipelineData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetches = [
      fetch("http://localhost:8000/api/analytics/reply-rates").then(r => r.json()).then(setReplyRates).catch(() => {}),
      fetch("http://localhost:8000/api/analytics/churn-signals").then(r => r.json()).then(setChurnData).catch(() => {}),
      fetch("http://localhost:8000/api/analytics/cross-sell").then(r => r.json()).then(setCrossSell).catch(() => {}),
      fetch("http://localhost:8000/api/outreach/pipeline").then(r => r.json()).then(setPipelineData).catch(() => {}),
    ];
    Promise.allSettled(fetches).finally(() => setLoading(false));
  }, []);

  // ── Derived / fallback values ──────────────────────────────────────────────
  const replyBySegment = replyRates?.by_segment?.length
    ? replyRates.by_segment
    : FALLBACK_REPLY_BY_SEGMENT;

  const replyByDay = replyRates?.by_day_of_week?.length
    ? replyRates.by_day_of_week
    : FALLBACK_REPLY_BY_DAY;

  const funnelData: Array<{ stage: string; count: number }> = pipelineData?.funnel?.length
    ? pipelineData.funnel
    : FALLBACK_FUNNEL;

  const crossSellByProduct = crossSell?.by_product?.length
    ? crossSell.by_product
    : FALLBACK_CROSS_SELL;

  const churnPieData = (() => {
    if (!churnData) return [
      { name: "High Risk", value: 45, fill: "#f87171" },
      { name: "Medium Risk", value: 120, fill: "#fbbf24" },
      { name: "Low Risk", value: 835, fill: "#34d399" },
    ];
    const high = churnData.high ?? 0;
    const medium = churnData.medium ?? 0;
    const low = churnData.low ?? 0;
    return [
      { name: "High Risk", value: high, fill: "#f87171" },
      { name: "Medium Risk", value: medium, fill: "#fbbf24" },
      { name: "Low Risk", value: low, fill: "#34d399" },
    ];
  })();

  const radarData = [
    { metric: "Personalization", v: Math.round((replyRates?.overall?.reply_rate ?? 40) * 2) },
    { metric: "Timing", v: 76 },
    { metric: "Framework Fit", v: 91 },
    { metric: "Compliance", v: 99 },
    { metric: "Conv. Rate", v: Math.round((replyRates?.overall?.conversion_rate ?? 48) * 1.5) },
    { metric: "Cost / Lead", v: 65 },
  ];

  // ── KPI values ─────────────────────────────────────────────────────────────
  const kpiCards = [
    {
      label: t("Total Contacted"),
      value: replyRates?.overall?.sent?.toLocaleString() ?? "—",
      color: "text-primary",
      bg: "bg-primary/15",
    },
    {
      label: t("Reply Rate"),
      value: replyRates?.overall?.reply_rate != null
        ? `${replyRates.overall.reply_rate.toFixed(1)}%`
        : "—",
      color: "text-accent",
      bg: "bg-accent/15",
    },
    {
      label: t("Conversion Rate"),
      value: replyRates?.overall?.conversion_rate != null
        ? `${replyRates.overall.conversion_rate.toFixed(1)}%`
        : "—",
      color: "text-success",
      bg: "bg-success/15",
    },
    {
      label: t("Churn At Risk"),
      value: churnData?.at_risk_count?.toLocaleString() ?? "—",
      color: "text-destructive",
      bg: "bg-destructive/15",
    },
    {
      label: t("Cross-sell Opps"),
      value: crossSell?.total_opportunities?.toLocaleString() ?? "—",
      color: "text-warning",
      bg: "bg-warning/15",
    },
  ];

  if (loading) {
    return (
      <div className="space-y-5">
        <PageHeader
          title={t("Analytics")}
          subtitle={t("Deep performance analytics across campaigns, customers, and AI workflows.")}
        />
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="glass rounded-xl p-5 shadow-card animate-pulse h-24" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="glass rounded-xl p-5 shadow-card animate-pulse h-72" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Analytics")}
        subtitle={t("Deep performance analytics across campaigns, customers, and AI workflows.")}
      />

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {kpiCards.map((k) => (
          <div key={k.label} className="glass rounded-xl p-4 shadow-card text-center">
            <div className={`text-2xl font-display font-bold ${k.color}`}>{k.value}</div>
            <div className="text-[11px] text-muted-foreground mt-1">{k.label}</div>
          </div>
        ))}
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* 1. Reply Rate by Segment */}
        <Card title={t("Reply Rate by Segment")} subtitle={t("How each segment responds to outreach")}>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={replyBySegment}>
              <CartesianGrid stroke="#ffffff10" vertical={false} />
              <XAxis dataKey="segment" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} unit="%" />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#ffffff08" }} formatter={(v) => [`${v}%`, "Reply Rate"]} />
              <Bar dataKey="reply_rate" radius={[4, 4, 0, 0]}>
                {replyBySegment.map((_, i) => (
                  <Cell key={i} fill={["#5b8bff", "#a78bfa", "#34d399"][i % 3]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* 2. Reply Rate by Day of Week */}
        <Card title={t("Reply Rate by Day of Week")} subtitle={t("Optimal days for outreach campaigns")}>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={replyByDay}>
              <CartesianGrid stroke="#ffffff10" vertical={false} />
              <XAxis dataKey="day" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} unit="%" />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#ffffff08" }} formatter={(v) => [`${v}%`, "Reply Rate"]} />
              <Bar dataKey="reply_rate" radius={[4, 4, 0, 0]}>
                {replyByDay.map((entry, i) => {
                  const isWeekend = entry.day === "Sat" || entry.day === "Sun";
                  return <Cell key={i} fill={isWeekend ? "#fbbf24" : "#5b8bff"} />;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* 3. Conversion Funnel (live) */}
        <Card title={t("Conversion Funnel")} subtitle={t("CONTACTED → ENGAGED → INTERESTED → CONVERTED")}>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={funnelData} layout="vertical">
              <CartesianGrid stroke="#ffffff10" horizontal={false} />
              <XAxis type="number" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="stage" stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} width={90} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#ffffff08" }} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {funnelData.map((entry, i) => (
                  <Cell key={i} fill={FUNNEL_COLORS[entry.stage] ?? "#5b8bff"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* 4. Churn Risk Distribution */}
        <Card title={t("Churn Risk Distribution")} subtitle={t("High / Medium / Low risk customer breakdown")}>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={churnPieData}
                dataKey="value"
                nameKey="name"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={3}
              >
                {churnPieData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-3 gap-2 mt-3">
            {churnPieData.map((entry) => (
              <div key={entry.name} className="flex flex-col items-center gap-1 text-center">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: entry.fill }} />
                <span className="text-[10px] text-muted-foreground">{entry.name}</span>
                <span className="text-sm font-semibold">{entry.value.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* 5. Cross-sell Opportunity Map */}
        <Card title={t("Cross-sell Opportunity Map")} subtitle={t("Customers per product opportunity")}>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={crossSellByProduct}>
              <CartesianGrid stroke="#ffffff10" vertical={false} />
              <XAxis dataKey="product" stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#ffffff08" }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {crossSellByProduct.map((_, i) => (
                  <Cell key={i} fill={["#5b8bff", "#34d399", "#a78bfa", "#fbbf24"][i % 4]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* 6. AI Campaign Scorecard (Radar) */}
        <Card title={t("AI Campaign Scorecard")} subtitle={t("Multi-dimensional effectiveness radar")}>
          <ResponsiveContainer width="100%" height={240}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#ffffff15" />
              <PolarAngleAxis dataKey="metric" stroke="#94a3b8" fontSize={10} />
              <PolarRadiusAxis stroke="#ffffff10" tick={false} axisLine={false} domain={[0, 100]} />
              <Radar dataKey="v" stroke="#5b8bff" fill="#5b8bff" fillOpacity={0.35} />
            </RadarChart>
          </ResponsiveContainer>
        </Card>

      </div>
    </div>
  );
}

function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="glass rounded-xl p-5 shadow-card">
      <div className="mb-3">
        <div className="text-sm font-semibold">{title}</div>
        {subtitle && <div className="text-xs text-muted-foreground">{subtitle}</div>}
      </div>
      {children}
    </div>
  );
}
