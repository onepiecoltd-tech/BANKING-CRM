import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line, LabelList, Cell } from "recharts";
import { Table2, BarChart3 } from "lucide-react";
import { corpX, type Rate } from "@/lib/corpApiExt";
import { useAuth } from "@/lib/auth";
import { t, fmtBn, fmtNum } from "@/lib/i18n";
import { PageHeader, Card, Stat, Spinner, ErrBox, Pill, FLAG_LABEL } from "./shared";

// Giữ bảng màu chung của ứng dụng; mỗi biểu đồ chỉ dùng MỘT màu (định danh nằm ở nhãn trục), trạng thái rủi ro có nhãn chữ đi kèm.
const PRIMARY = "#5b8bff";
const GRID = "rgba(148,163,184,0.14)";
const INK = "#9aa4b8";
const tip = { background: "#11151f", border: "1px solid #2a3142", borderRadius: 8, fontSize: 12 };
const RISK_COLOR: Record<string, string> = { Cao: "#fb7185", "Trung bình": "#fbbf24", Thấp: "#34d399" };
const RISK_LABEL: Record<string, [string, string]> = { Cao: ["Cao", "High"], "Trung bình": ["Trung bình", "Medium"], Thấp: ["Thấp", "Low"] };

function ChartCard({ title, rows, unit, children, hint }: { title: string; rows: { name: string; value: number; extra?: string }[]; unit?: string; children: ReactNode; hint?: string }) {
  const [asTable, setAsTable] = useState(false);
  return (
    <Card title={title} right={
      <button onClick={() => setAsTable((v) => !v)} title={asTable ? t("Xem biểu đồ", "Show chart") : t("Xem dạng bảng", "Show table")} className="w-7 h-7 grid place-items-center rounded-lg hover:bg-muted/50 text-muted-foreground">
        {asTable ? <BarChart3 className="w-4 h-4" /> : <Table2 className="w-4 h-4" />}
      </button>}>
      {rows.length === 0 || rows.every((r) => !r.value) ? <div className="h-48 grid place-items-center text-sm text-muted-foreground text-center px-6">{t("Chưa đủ dữ liệu. Ghi nhận tin đã gửi và phản hồi trong Hội thoại/Chiến dịch để có số liệu.", "Not enough data yet. Log sent messages and replies in Conversations/Campaigns.")}</div>
        : asTable ? (
          <table className="w-full text-xs"><tbody>{rows.map((r) => <tr key={r.name} className="border-b border-border/60"><td className="py-1.5">{r.name}</td><td className="text-right tabular-nums">{fmtNum(r.value, unit === "%" ? 0 : 1)}{unit ?? ""}</td><td className="text-right text-muted-foreground pl-3">{r.extra}</td></tr>)}</tbody></table>
        ) : children}
      {hint && <div className="text-[11px] text-muted-foreground mt-2">{hint}</div>}
    </Card>
  );
}

function HBar({ data, unit, color = PRIMARY, height, tooltipExtra }: { data: { name: string; value: number; extra?: string; color?: string }[]; unit?: string; color?: string; height?: number; tooltipExtra?: boolean }) {
  const h = height ?? Math.max(160, data.length * 34 + 20);
  return (
    <div style={{ height: h }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 4, right: 40, top: 4, bottom: 4 }} barCategoryGap={8}>
          <CartesianGrid stroke={GRID} horizontal={false} />
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" width={150} tick={{ fill: INK, fontSize: 11 }} axisLine={false} tickLine={false} interval={0} />
          <Tooltip cursor={{ fill: "rgba(148,163,184,0.08)" }} contentStyle={tip} formatter={(v: any, _n: any, p: any) => [`${fmtNum(v, unit === "%" ? 0 : 1)}${unit ?? ""}${tooltipExtra && p?.payload?.extra ? ` · ${p.payload.extra}` : ""}`, ""]} separator="" />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={14} fill={color} isAnimationActive={false}>
            {data.map((d, i) => <Cell key={i} fill={d.color ?? color} />)}
            <LabelList dataKey="value" position="right" formatter={(v: any) => `${fmtNum(v, unit === "%" ? 0 : 0)}${unit ?? ""}`} style={{ fill: INK, fontSize: 11 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const DIMS = [["segment", "Phân khúc", "Segment"], ["country", "Quốc gia đầu tư", "Investor country"], ["industry", "Ngành", "Industry"]] as const;

export function CorpAnalyticsPage() {
  const { isAdmin } = useAuth();
  const { data: a, isLoading, error } = useQuery({ queryKey: ["corp", "analytics"], queryFn: corpX.analytics, staleTime: 30_000 });
  const [dim, setDim] = useState<(typeof DIMS)[number][0]>("segment");
  if (isLoading) return <Spinner />;
  if (!a) return <ErrBox error={error} />;
  const k = a.kpis;
  const rateRows = (rs: Rate[]) => rs.map((r) => ({ name: r.name, value: r.rate, extra: `${r.replied}/${r.contacted}` }));
  const byDim = rateRows(dim === "segment" ? a.reply_by_segment : dim === "country" ? a.reply_by_country : a.reply_by_industry);
  const funnel = a.funnel.map((f) => ({ name: f.stage, value: f.value, extra: k.contacted ? `${Math.round((f.value / k.contacted) * 100)}%` : "" }));
  const weekday = a.reply_by_weekday.map((w) => ({ name: w.name, value: w.rate, extra: `${w.replied}/${w.sent}` }));
  const risk = a.risk.map((r) => ({ name: t(...(RISK_LABEL[r.name] ?? [r.name, r.name])), value: r.value, color: RISK_COLOR[r.name] ?? PRIMARY }));
  const cross = a.crosssell.slice(0, 8).map((c) => ({ name: c.name.length > 22 ? c.name.slice(0, 21) + "…" : c.name, value: c.value }));
  const pipe = a.pipeline.map((p) => ({ name: p.stage, value: p.value_bn, extra: `${p.count} ${t("cơ hội", "deals")}` }));
  const flags = a.flags.map((f) => ({ name: t(...(FLAG_LABEL[f.code] ?? [f.code, f.code])), value: f.value }));

  return (
    <div className="space-y-6">
      <PageHeader title={t("Phân tích số liệu doanh nghiệp", "Corporate analytics")} subtitle={t("Hiệu quả tiếp cận, phễu chuyển đổi, rủi ro, cơ hội bán chéo và pipeline. Số liệu chỉ tính trên khách hàng bạn được xem.", "Outreach effectiveness, conversion funnel, risk, cross-sell and pipeline — for the customers you can see.")} />

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3">
        <Stat label={t("Khách hàng", "Customers")} value={fmtNum(k.customers)} />
        <Stat label={t("Đã tiếp cận", "Contacted")} value={fmtNum(k.contacted)} />
        <Stat label={t("Tỷ lệ phản hồi", "Reply rate")} value={`${k.reply_rate}%`} sub={`${k.replied} ${t("khách", "cust.")}`} tone="primary" />
        <Stat label={t("Quan tâm", "Interested")} value={fmtNum(k.interested)} tone="success" />
        <Stat label={t("Chuyển đổi", "Converted")} value={fmtNum(k.converted)} sub={`${k.conv_rate}% ${t("số đã tiếp cận", "of contacted")}`} tone="success" />
        <Stat label={t("Rủi ro cao", "High risk")} value={fmtNum(k.at_risk)} tone={k.at_risk ? "destructive" : undefined} />
        <Stat label={t("Cơ hội bán chéo", "Cross-sell")} value={fmtNum(k.crosssell)} sub={t("điểm ≥ 60", "score ≥ 60")} />
        <Stat label={t("Tỷ lệ thắng", "Win rate")} value={`${k.win_rate}%`} />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title={t("Phễu chuyển đổi", "Conversion funnel")} rows={funnel} unit="" hint={t("Tỷ lệ so với số khách đã tiếp cận.", "Share of customers contacted.")}>
          <HBar data={funnel} tooltipExtra />
        </ChartCard>
        <ChartCard title={t("Tỷ lệ phản hồi theo nhóm", "Reply rate by group")} rows={byDim} unit="%" hint={t("Chỉ gồm nhóm đã được tiếp cận; di chuột để xem số khách phản hồi/đã tiếp cận.", "Contacted groups only; hover for replied/contacted.")}>
          <div className="flex gap-1 mb-2">{DIMS.map(([key, vi, en]) => <button key={key} onClick={() => setDim(key)} className={`text-xs px-2.5 py-1 rounded-lg ${dim === key ? "bg-primary/15" : "text-muted-foreground hover:bg-muted/50"}`}>{t(vi, en)}</button>)}</div>
          <HBar data={byDim} unit="%" tooltipExtra />
        </ChartCard>
        <ChartCard title={t("Phản hồi theo ngày gửi trong tuần", "Reply rate by weekday sent")} rows={weekday} unit="%" hint={t("Tin gửi đi có phản hồi trong 7 ngày.", "Outgoing messages replied to within 7 days.")}>
          <div style={{ height: 200 }}>
            <ResponsiveContainer>
              <BarChart data={weekday} margin={{ top: 18, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="name" tick={{ fill: INK, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: INK, fontSize: 11 }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
                <Tooltip cursor={{ fill: "rgba(148,163,184,0.08)" }} contentStyle={tip} formatter={(v: any, _n: any, p: any) => [`${v}% · ${p.payload.extra}`, ""]} separator="" />
                <Bar dataKey="value" fill={PRIMARY} radius={[4, 4, 0, 0]} barSize={22} isAnimationActive={false}><LabelList dataKey="value" position="top" formatter={(v: any) => (v ? `${v}%` : "")} style={{ fill: INK, fontSize: 10 }} /></Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
        <ChartCard title={t("Phân bố mức rủi ro", "Risk distribution")} rows={risk} unit="">
          <HBar data={risk} height={150} />
        </ChartCard>
        <ChartCard title={t("Cơ hội bán chéo theo sản phẩm", "Cross-sell by product")} rows={cross} unit="" hint={t("Số khách có điểm phù hợp ≥ 60 và chưa dùng sản phẩm.", "Customers with fit ≥ 60 who do not hold the product.")}>
          <HBar data={cross} />
        </ChartCard>
        <ChartCard title={t("Pipeline theo giai đoạn (tỷ đồng)", "Pipeline by stage (VND bn)")} rows={pipe} unit="" hint={t("Giá trị kỳ vọng; di chuột để xem số cơ hội.", "Expected value; hover for deal count.")}>
          <HBar data={pipe} tooltipExtra />
        </ChartCard>
        <ChartCard title={t("Cảnh báo đang kích hoạt", "Active alerts")} rows={flags} unit="">
          <HBar data={flags} color="#fbbf24" />
        </ChartCard>
        <ChartCard title={t("Hoạt động chăm sóc theo tháng", "Customer touches per month")} rows={a.activity.map((m) => ({ name: m.month, value: m.interactions }))} unit="">
          <div style={{ height: 200 }}>
            <ResponsiveContainer>
              <LineChart data={a.activity} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="month" tick={{ fill: INK, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: INK, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip contentStyle={tip} formatter={(v: any) => [v, t("Lượt tương tác", "Interactions")]} />
                <Line type="monotone" dataKey="interactions" stroke={PRIMARY} strokeWidth={2} dot={{ r: 4, fill: PRIMARY, stroke: "#11151f", strokeWidth: 2 }} activeDot={{ r: 5 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>

      <Card title={t("Chiến dịch gần đây", "Recent campaigns")}>
        {a.campaigns.length === 0 ? <div className="text-sm text-muted-foreground py-4 text-center">{t("Chưa có chiến dịch.", "No campaigns yet.")}</div> : (
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-muted-foreground border-b border-border"><th className="py-2 font-medium">{t("Chiến dịch", "Campaign")}</th><th className="font-medium">{t("Sản phẩm", "Product")}</th><th className="text-right font-medium">{t("Mục tiêu", "Targets")}</th><th className="text-right font-medium">{t("Đã liên hệ", "Contacted")}</th><th className="text-right font-medium">{t("Phản hồi", "Replied")}</th><th className="text-right font-medium">{t("Quan tâm", "Interested")}</th><th className="text-right font-medium">{t("Chuyển đổi", "Converted")}</th><th className="font-medium pl-3">{t("Trạng thái", "Status")}</th></tr></thead>
            <tbody>{a.campaigns.map((c) => (
              <tr key={c.id} className="border-b border-border/60"><td className="py-2">{c.name}</td><td className="text-muted-foreground">{c.product_name}</td><td className="text-right tabular-nums">{c.total}</td><td className="text-right tabular-nums">{c.contacted_pct}%</td><td className="text-right tabular-nums">{c.reply_pct}%</td><td className="text-right tabular-nums">{c.interest_pct}%</td><td className="text-right tabular-nums">{c.conv_pct}%</td><td className="pl-3"><Pill tone={c.status === "Đang chạy" ? "primary" : "success"}>{c.status}</Pill></td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>

      {isAdmin && a.rm_performance && (
        <Card title={t("Hiệu quả theo cán bộ quan hệ khách hàng", "Performance by relationship manager")}>
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-muted-foreground border-b border-border"><th className="py-2 font-medium">{t("Cán bộ", "RM")}</th><th className="text-right font-medium">{t("Khách hàng", "Customers")}</th><th className="text-right font-medium">{t("Hạng A", "Tier A")}</th><th className="text-right font-medium">{t("Dư nợ", "Loans")}</th><th className="text-right font-medium">CASA</th><th className="text-right font-medium">{t("Rủi ro cao", "High risk")}</th><th className="text-right font-medium">Pipeline</th><th className="text-right font-medium">{t("Có trọng số", "Weighted")}</th><th className="text-right font-medium">{t("Tương tác 30 ngày", "Touches 30d")}</th></tr></thead>
            <tbody>{a.rm_performance.map((r) => (
              <tr key={r.rm} className="border-b border-border/60"><td className="py-2">{r.rm}</td><td className="text-right tabular-nums">{r.customers}</td><td className="text-right tabular-nums">{r.tier_a}</td><td className="text-right tabular-nums">{fmtBn(r.loan_bn, 0)}</td><td className="text-right tabular-nums">{fmtBn(r.casa_bn, 0)}</td><td className="text-right tabular-nums">{r.risk_high}</td><td className="text-right tabular-nums">{fmtBn(r.pipeline_bn, 0)}</td><td className="text-right tabular-nums">{fmtBn(r.weighted_bn, 0)}</td><td className="text-right tabular-nums">{r.touches_30d}</td></tr>
            ))}</tbody>
          </table></div>
        </Card>
      )}
    </div>
  );
}
