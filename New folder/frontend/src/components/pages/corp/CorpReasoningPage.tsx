import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, ShieldCheck, Network, History, ChevronRight } from "lucide-react";
import { corpX } from "@/lib/corpApiExt";
import { t, fmtBn } from "@/lib/i18n";
import { PageHeader, Card, ErrBox, Pill, Spinner, CustomerPicker, fmtDateTime } from "./shared";

export function CorpReasoningPage() {
  const [tab, setTab] = useState<"customer" | "runs">("customer");
  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Lập luận & truy vết", "Reasoning & trace")}
        subtitle={t("Xem hệ thống chấm điểm và đề xuất dựa trên dữ liệu nào, luật nào kích hoạt, và lịch sử từng lần trợ lý AI chạy — để cán bộ kiểm chứng được mọi gợi ý.", "See what data and rules drive each score and recommendation, and the history of every AI assistant run — so every suggestion can be verified.")}
      />
      <div className="flex gap-1 border-b border-border">
        {([["customer", t("Giải thích theo khách hàng", "Explain a customer"), Network], ["runs", t("Nhật ký trợ lý AI", "AI assistant log"), History]] as const).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-2 text-sm -mb-px border-b-2 inline-flex items-center gap-1.5 ${tab === k ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}><Icon className="w-3.5 h-3.5" />{l}</button>
        ))}
      </div>
      {tab === "customer" ? <ExplainTab /> : <RunsTab />}
    </div>
  );
}

function ExplainTab() {
  const [id, setId] = useState<string>("");
  const [name, setName] = useState("");
  const { data, isLoading, error } = useQuery({ queryKey: ["corp", "explain", id], queryFn: () => corpX.explain(id), enabled: !!id });
  return (
    <div className="space-y-4">
      <div className="max-w-md"><CustomerPicker onPick={(i, n) => { setId(i); setName(n); }} /></div>
      {!id && <Card><div className="py-10 text-center text-sm text-muted-foreground">{t("Tìm và chọn một khách hàng để xem hệ thống đã lập luận thế nào.", "Find and pick a customer to see how the system reasoned.")}</div></Card>}
      {id && isLoading && <Spinner />}
      <ErrBox error={error} />
      {data && (
        <>
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-lg font-semibold">{(data.customer.name as string) ?? name}</h2>
            
            <span className="text-xs text-muted-foreground">{data.customer.customer_id} · {data.customer.segment} · {data.customer.industry}</span>
          </div>

          {data.decision && (
            <div className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
              <div className="text-[11px] uppercase tracking-wider text-primary">{t("Đề xuất hành động tiếp theo", "Next best action")}</div>
              <div className="text-sm font-medium mt-0.5">{data.decision.name}</div>
              <div className="text-xs text-muted-foreground mt-1">{data.decision.why}</div>
            </div>
          )}

          <div className="grid lg:grid-cols-2 gap-4">
            <Card title={t("1 · Dữ liệu đầu vào", "1 · Inputs")}>
              <dl className="text-sm divide-y divide-border/60">{data.inputs.map((x) => <div key={x.label} className="flex justify-between gap-3 py-1.5"><dt className="text-muted-foreground">{x.label}</dt><dd className="text-right tabular-nums">{x.value}</dd></div>)}</dl>
            </Card>
            <Card title={t("2 · Chỉ số tính toán", "2 · Derived metrics")}>
              <dl className="text-sm divide-y divide-border/60">{data.metrics.map((x) => <div key={x.label} className="flex justify-between gap-3 py-1.5"><dt className="text-muted-foreground">{x.label}</dt><dd className="text-right tabular-nums">{x.value}</dd></div>)}</dl>
            </Card>
          </div>

          <Card title={t("3 · Luật cảnh báo rủi ro", "3 · Risk rules")}>
            <div className="overflow-x-auto"><table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted-foreground border-b border-border"><th className="py-2 font-medium">{t("Luật", "Rule")}</th><th className="font-medium">{t("Ngưỡng", "Threshold")}</th><th className="font-medium">{t("Thực tế", "Actual")}</th><th className="font-medium">{t("Kết quả", "Result")}</th></tr></thead>
              <tbody>{data.rules.map((r) => (
                <tr key={r.code} className="border-b border-border/60"><td className="py-2">{r.name}</td><td className="text-muted-foreground">{r.threshold}</td><td className="tabular-nums">{r.actual}</td>
                  <td>{r.fired ? <Pill tone="destructive">{t("Kích hoạt", "Fired")}</Pill> : <Pill tone="success">{t("Không", "Clear")}</Pill>}</td></tr>
              ))}</tbody>
            </table></div>
          </Card>

          <div className="grid lg:grid-cols-2 gap-4">
            <Card title={t("4 · Điểm phù hợp từng sản phẩm", "4 · Product fit scores")}>
              <div className="space-y-2.5">
                {data.propensities.map((p) => (
                  <div key={p.code}>
                    <div className="flex items-center justify-between text-xs mb-1"><span>{p.name} {p.held && <Pill tone="muted">{t("đang dùng", "held")}</Pill>}</span><span className="tabular-nums font-medium">{p.score}</span></div>
                    <div className="h-1.5 rounded-full bg-muted/50 overflow-hidden"><div className={`h-full ${p.held ? "bg-muted-foreground/50" : p.score >= 70 ? "bg-success" : "bg-primary/70"}`} style={{ width: `${Math.min(100, p.score)}%` }} /></div>
                    {p.reasons.length > 0 && <div className="text-[11px] text-muted-foreground mt-0.5">{p.reasons.slice(0, 3).join("; ")}</div>}
                  </div>
                ))}
              </div>
            </Card>
            <Card title={t("5 · Điểm ưu tiên khách hàng", "5 · Priority score")} right={<span className="text-2xl font-display font-semibold tabular-nums">{Math.round(data.priority.score)}</span>}>
              <table className="w-full text-xs"><thead><tr className="text-left text-muted-foreground border-b border-border"><th className="py-1.5 font-medium">{t("Thành phần", "Component")}</th><th className="text-right font-medium">{t("Giá trị", "Value")}</th><th className="text-right font-medium">{t("Trọng số", "Weight")}</th><th className="text-right font-medium">{t("Đóng góp", "Contribution")}</th></tr></thead>
                <tbody>{data.priority.parts.map((p) => (
                  <tr key={p.label} className="border-b border-border/60"><td className="py-1.5">{p.label}{p.note && <div className="text-[10px] text-muted-foreground">{p.note}</div>}</td><td className="text-right tabular-nums">{Math.round(p.value)}</td><td className="text-right tabular-nums">{Math.round(p.weight * 100)}%</td><td className="text-right tabular-nums">{p.contribution.toFixed(1)}</td></tr>
                ))}</tbody></table>
              <div className="text-[11px] text-muted-foreground mt-2">{t("Tổng “ví” khách hàng tại ngân hàng", "Customer wallet at the bank")}: {fmtBn(data.priority.wallet_bn, 1)}</div>
            </Card>
          </div>

          <Card title={t("6 · Kiểm tra tuân thủ khi tiếp cận", "6 · Outreach compliance checks")} right={<ShieldCheck className="w-4 h-4 text-muted-foreground" />}>
            <div className="grid md:grid-cols-2 gap-2">
              {data.compliance.map((c) => (
                <div key={c.name} className="flex items-start gap-2 text-sm rounded-lg bg-muted/30 px-3 py-2">
                  {c.ok ? <CheckCircle2 className="w-4 h-4 text-success mt-0.5 shrink-0" /> : <XCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />}
                  <div><div>{c.name}</div><div className="text-[11px] text-muted-foreground">{c.detail}</div></div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function RunsTab() {
  const list = useQuery({ queryKey: ["corp", "runs"], queryFn: corpX.runs });
  const [sel, setSel] = useState<number | null>(null);
  const run = useQuery({ queryKey: ["corp", "run", sel], queryFn: () => corpX.run(sel!), enabled: sel !== null });
  return (
    <div className="grid lg:grid-cols-[380px_1fr] gap-4 items-start">
      <Card title={t("Các lần chạy gần đây", "Recent runs")}>
        {list.isLoading ? <Spinner /> : (list.data?.items ?? []).length === 0 ? <div className="text-sm text-muted-foreground py-6 text-center">{t("Chưa có lần chạy nào. Dùng “Trợ lý AI cho RM” để tạo.", "No runs yet. Use the RM AI assistant to create some.")}</div> : (
          <div className="divide-y divide-border/60 max-h-[65vh] overflow-y-auto">
            {list.data!.items.map((r) => (
              <button key={r.id} onClick={() => setSel(r.id)} className={`w-full text-left py-2.5 px-1 flex items-start gap-2 hover:bg-muted/20 ${sel === r.id ? "bg-primary/10" : ""}`}>
                <div className="min-w-0 flex-1"><div className="text-sm truncate">{r.query}</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{r.username} · {fmtDateTime(r.created_at)} · {r.total_matched} {t("khách phù hợp", "matches")} · {r.step_count} {t("bước", "steps")}{r.llm_used ? " · AI" : ""}</div></div>
                <ChevronRight className="w-4 h-4 text-muted-foreground mt-1 shrink-0" />
              </button>
            ))}
          </div>
        )}
        <ErrBox error={list.error} />
      </Card>
      <Card title={t("Chi tiết lần chạy", "Run detail")}>
        {sel === null ? <div className="text-sm text-muted-foreground py-10 text-center">{t("Chọn một lần chạy bên trái.", "Pick a run on the left.")}</div> : run.isLoading ? <Spinner /> : run.data && (
          <div className="space-y-4">
            <div><div className="text-[11px] text-muted-foreground">{t("Câu hỏi", "Query")}</div><div className="text-sm font-medium">{run.data.query}</div></div>
            <div className="flex gap-2 flex-wrap"><Pill tone={run.data.llm_used ? "primary" : "muted"}>{run.data.llm_used ? t("Có dùng AI", "AI used") : t("Chỉ dùng luật", "Rules only")}</Pill>{run.data.llm_error && <Pill tone="warning">{run.data.llm_error}</Pill>}</div>
            <div><div className="text-[11px] text-muted-foreground mb-1">{t("Bộ lọc đã suy ra", "Inferred filters")}</div>
              <div className="flex flex-wrap gap-1.5">{Object.entries(run.data.filters).filter(([, v]) => v !== null && v !== "" && v !== undefined).map(([k, v]) => <Pill key={k}>{k}: {String(v)}</Pill>)}</div></div>
            <div><div className="text-[11px] text-muted-foreground mb-1">{t("Các bước lập luận", "Reasoning steps")}</div>
              <ol className="space-y-2">{run.data.steps.map((s, i) => (
                <li key={i} className="flex gap-2.5 text-sm"><span className="w-5 h-5 rounded-full bg-primary/15 text-primary text-[11px] grid place-items-center shrink-0 mt-0.5">{i + 1}</span><div><div className="font-medium text-xs">{s.step}</div><div className="text-xs text-muted-foreground">{s.detail}</div></div></li>
              ))}</ol></div>
          </div>
        )}
        <ErrBox error={run.error} />
      </Card>
    </div>
  );
}
