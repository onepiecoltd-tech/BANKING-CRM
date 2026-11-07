import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Sparkles, Loader2, Copy, Check, Play } from "lucide-react";
import { corp, type AgentResult } from "@/lib/corpApi";
import { t, fmtBn, getLang } from "@/lib/i18n";
import { PageHeader, Card, TierBadge, FlagBadge, copyText, CHANNEL_LABEL, LANG_LABEL } from "./shared";

const EXAMPLES_VI = [
  "Top 5 doanh nghiệp FDI Trung Quốc ở Bình Dương có nhu cầu UPAS, soạn tin Zalo tiếng Trung",
  "Khách hàng có hạn mức sắp hết hạn cần gia hạn, top 8",
  "Doanh nghiệp dệt may xuất khẩu cần phòng ngừa tỷ giá",
  "Doanh nghiệp FDI đông lao động chưa chi lương qua ngân hàng, soạn email",
  "Khách hàng hạng A có doanh số qua tài khoản giảm mạnh",
  "Doanh nghiệp Đài Loan ở Đồng Nai cần thanh toán quốc tế, soạn kịch bản gọi",
];
const EXAMPLES_EN = [
  "Top 5 Chinese FDI companies in Binh Duong that need UPAS, draft a Zalo message in Chinese",
  "Customers whose credit limit is expiring and need renewal, top 8",
  "Textile exporters that need FX hedging",
  "Large FDI employers not yet using payroll, draft an email",
];

export function CorpAgentPage() {
  const [query, setQuery] = useState("");
  const [useLlm, setUseLlm] = useState(true);
  const [copied, setCopied] = useState<number | null>(null);
  const run = useMutation({
    mutationFn: (q: string) => corp.agent({ query: q, use_llm: useLlm, rm_name: (() => { try { return localStorage.getItem("corp-rm-name") || undefined; } catch { return undefined; } })() }),
  });
  const res: AgentResult | undefined = run.data;
  const submit = (q?: string) => { const v = (q ?? query).trim(); if (v) { setQuery(v); run.mutate(v); } };
  const examples = getLang() === "vi" ? EXAMPLES_VI : EXAMPLES_EN;

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Trợ lý AI cho RM doanh nghiệp", "Corporate RM AI assistant")}
        subtitle={t("Hỏi bằng tiếng Việt, Anh hoặc Trung. Trợ lý lọc danh mục, xếp hạng theo cơ hội/cảnh báo và soạn sẵn nội dung tiếp cận.", "Ask in Vietnamese, English or Chinese. The assistant filters the portfolio, ranks by opportunity/alert and drafts outreach.")}
      />

      <Card>
        <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={3}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(); }}
          placeholder={t("VD: Top 5 doanh nghiệp FDI Hàn Quốc ở Đồng Nai cần bảo lãnh, soạn email…", "e.g. Top 5 Korean FDI companies in Dong Nai that need guarantees, draft an email…")}
          className="w-full bg-input/60 border border-border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40" />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button onClick={() => submit()} disabled={run.isPending || !query.trim()} className="px-4 py-2 rounded-lg gradient-primary text-primary-foreground text-sm font-medium flex items-center gap-2 disabled:opacity-50">
            {run.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}{t("Chạy", "Run")}
          </button>
          <label className="text-xs flex items-center gap-2 text-muted-foreground cursor-pointer">
            <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />{t("Dùng LLM để tóm tắt (cần API key trong .env)", "Use LLM for the summary (needs API key in .env)")}
          </label>
          <span className="text-[10px] text-muted-foreground ml-auto">Ctrl+Enter</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {examples.map((e) => (
            <button key={e} onClick={() => submit(e)} className="text-[11px] px-2.5 py-1.5 rounded-lg border border-border hover:bg-muted/50 text-left transition">{e}</button>
          ))}
        </div>
      </Card>

      {run.isError && <div className="text-sm text-destructive">{(run.error as Error).message}</div>}

      {res && (
        <>
          <Card title={t("Quy trình xử lý", "Processing steps")}>
            <ol className="space-y-2">
              {res.steps.map((s, i) => (
                <li key={i} className="flex gap-3 text-xs">
                  <span className="w-5 h-5 rounded-full bg-primary/15 text-primary grid place-items-center shrink-0 text-[10px] font-semibold">{i + 1}</span>
                  <div><div className="font-medium">{s.step}</div><div className="text-muted-foreground">{s.detail}</div></div>
                </li>
              ))}
            </ol>
          </Card>

          <Card title={t("Kết luận", "Summary")} right={res.llm_used ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent flex items-center gap-1"><Sparkles className="w-3 h-3" />LLM</span> : <span className="text-[10px] text-muted-foreground">{t("Tóm tắt mặc định", "Default summary")}</span>}>
            <p className="text-sm leading-relaxed whitespace-pre-line">{res.answer}</p>
            {!res.llm_used && res.llm_error && <p className="mt-2 text-[11px] text-muted-foreground">LLM: {res.llm_error}</p>}
          </Card>

          <Card title={`${t("Doanh nghiệp phù hợp", "Matching companies")} (${res.customers.length}/${res.total_matched})`}>
            <div className="space-y-2">
              {res.customers.map((c) => (
                <Link key={c.customer_id} to="/corp/customers" search={{ open: c.customer_id }} className="block rounded-lg border border-border p-3 hover:bg-muted/30 transition">
                  <div className="flex items-center gap-2 flex-wrap">
                    <TierBadge tier={c.tier} /><span className="font-medium text-sm">{c.name}</span>
                    {c.name_zh && <span className="text-xs text-muted-foreground">{c.name_zh}</span>}
                    <span className="ml-auto text-xs text-muted-foreground">{c.ownership}{c.investor_country ? ` · ${c.investor_country}` : ""} · {c.province} · {fmtBn(c.annual_revenue_bn, 0)}</span>
                  </div>
                  {c.headline && <div className="mt-1 text-xs text-muted-foreground">{c.headline}</div>}
                  {c.risk_flags.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{c.risk_flags.slice(0, 3).map((x) => <FlagBadge key={x.code} severity={x.severity} text={x.text} />)}</div>}
                </Link>
              ))}
              {res.customers.length === 0 && <div className="text-xs text-muted-foreground">{t("Không có kết quả.", "No results.")}</div>}
            </div>
          </Card>

          {res.drafts.length > 0 && (
            <Card title={`${t("Bản nháp tiếp cận", "Outreach drafts")} (${res.drafts.length})`}>
              <div className="space-y-3">
                {res.drafts.map((d, i) => (
                  <div key={i} className="rounded-lg border border-border p-3">
                    <div className="flex items-center gap-2 text-xs mb-2">
                      <span className="font-medium">{d.customer_name}</span>
                      <span className="text-muted-foreground">· {d.product_name} · {CHANNEL_LABEL(d.channel)} · {LANG_LABEL[d.language]}</span>
                      <button onClick={async () => { const ok = await copyText((d.subject ? `${d.subject}\n\n` : "") + d.body); if (ok) { setCopied(i); setTimeout(() => setCopied(null), 1500); } }} className="ml-auto text-[11px] px-2 py-1 rounded-md border border-border hover:bg-muted/50 flex items-center gap-1">
                        {copied === i ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}{copied === i ? t("Đã chép", "Copied") : t("Sao chép", "Copy")}
                      </button>
                    </div>
                    {d.subject && <div className="text-xs mb-1"><span className="text-muted-foreground">{t("Tiêu đề", "Subject")}: </span>{d.subject}</div>}
                    <pre className="whitespace-pre-wrap text-xs leading-relaxed font-sans">{d.body}</pre>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
