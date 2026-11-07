import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X, Copy, Check, Plus, Send, Phone, Mail, MessageCircle, Pencil, Trash2, ArrowRightLeft } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { corp, type Draft } from "@/lib/corpApi";
import { t, fmtBn, fmtNum } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { corpX } from "@/lib/corpApiExt";
import { CustomerFormDialog } from "./CustomerForm";
import { Modal, Btn, inputCls, ErrBox } from "./shared";
import { TierBadge, FlagBadge, useMeta, productName, fmtDate, LANG_LABEL, CHANNEL_LABEL, copyText } from "./shared";

type Tab = "overview" | "cashflow" | "opps" | "draft" | "history";

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-1.5 border-b border-border/50 text-xs">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-medium text-right">{v}</span>
    </div>
  );
}

export function CustomerDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: meta } = useMeta();
  const { data, isLoading } = useQuery({ queryKey: ["corp", "customer", id], queryFn: () => corp.customer(id) });
  const [tab, setTab] = useState<Tab>("overview");
  const [draftProduct, setDraftProduct] = useState<string | undefined>();
  const { isAdmin } = useAuth();
  const [editing, setEditing] = useState(false);
  const [moving, setMoving] = useState(false);
  const [toRm, setToRm] = useState("");
  const del = useMutation({ mutationFn: () => corpX.deleteCustomer(id), onSuccess: () => { qc.invalidateQueries({ queryKey: ["corp"] }); onClose(); } });
  const move = useMutation({ mutationFn: () => corpX.reassign({ customer_ids: [id], to_rm: toRm }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["corp"] }); setMoving(false); } });

  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const tabs: [Tab, string][] = [
    ["overview", t("Tổng quan", "Overview")],
    ["cashflow", t("Dòng tiền", "Cash flow")],
    ["opps", t("Cơ hội sản phẩm", "Product opportunities")],
    ["draft", t("Soạn tin", "Draft message")],
    ["history", t("Lịch sử", "History")],
  ];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <aside className="relative w-full max-w-[760px] h-full bg-background border-l border-border overflow-y-auto shadow-2xl">
        <div className="sticky top-0 z-10 glass-strong border-b border-border px-6 py-4 flex items-start gap-3">
          <div className="flex-1 min-w-0">
            {data ? (
              <>
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="font-display font-semibold text-lg truncate">{data.customer.name}</h2>
                  <TierBadge tier={data.analysis.tier} />
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {data.customer.name_zh && <span className="mr-2">{data.customer.name_zh}</span>}
                  {data.customer.ownership}{data.customer.investor_country ? ` · ${data.customer.investor_country}` : ""} · {data.customer.industry} · {data.customer.province}
                </div>
              </>
            ) : (
              <div className="text-sm text-muted-foreground">{t("Đang tải…", "Loading…")}</div>
            )}
          </div>
          {data && (
            <div className="flex items-center gap-1.5">
              <Btn onClick={() => setEditing(true)}><Pencil className="w-3.5 h-3.5" /> {t("Sửa", "Edit")}</Btn>
              {isAdmin && <Btn title={t("Chuyển cán bộ phụ trách", "Reassign RM")} onClick={() => { setToRm(data.customer.rm_name ?? ""); setMoving(true); }}><ArrowRightLeft className="w-3.5 h-3.5" /></Btn>}
              {isAdmin && <Btn kind="danger" title={t("Xóa khách hàng", "Delete")} onClick={() => { if (window.confirm(t("Xóa khách hàng này và toàn bộ dữ liệu liên quan (dòng tiền, cơ hội, hội thoại)? Không thể hoàn tác.", "Delete this customer and all related data? This cannot be undone."))) del.mutate(); }}><Trash2 className="w-3.5 h-3.5" /></Btn>}
            </div>
          )}
          <button onClick={onClose} className="w-8 h-8 grid place-items-center rounded-lg hover:bg-muted/60"><X className="w-4 h-4" /></button>
        </div>
        {editing && data && <CustomerFormDialog id={id} initial={data.customer} onClose={() => setEditing(false)} onSaved={() => setEditing(false)} />}
        {moving && (
          <Modal title={t("Chuyển cán bộ phụ trách", "Reassign relationship manager")} onClose={() => setMoving(false)}
            footer={<><ErrBox error={move.error} /><Btn onClick={() => setMoving(false)}>{t("Hủy", "Cancel")}</Btn><Btn kind="primary" disabled={!toRm.trim() || move.isPending} onClick={() => move.mutate()}>{t("Chuyển", "Move")}</Btn></>}>
            <p className="text-xs text-muted-foreground mb-2">{t("Nhập đúng tên hiển thị của cán bộ (trùng với 'Tên CBQH' của tài khoản người dùng) để họ thấy khách hàng này.", "Enter the exact RM display name used on the user account so they can see this customer.")}</p>
            <input className={`${inputCls} w-full`} value={toRm} onChange={(e) => setToRm(e.target.value)} />
          </Modal>
        )}

        <div className="px-6 pt-3 flex gap-1 border-b border-border overflow-x-auto">
          {tabs.map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)} className={`px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 transition ${tab === k ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
              {label}
            </button>
          ))}
        </div>

        {isLoading || !data ? null : (
          <div className="p-6 space-y-5">
            {tab === "overview" && <Overview d={data} meta={meta} />}
            {tab === "cashflow" && <Cashflow d={data} />}
            {tab === "opps" && <Opps d={data} meta={meta} onDraft={(p) => { setDraftProduct(p); setTab("draft"); }} onChanged={() => qc.invalidateQueries({ queryKey: ["corp"] })} />}
            {tab === "draft" && <DraftTab d={data} meta={meta} initialProduct={draftProduct} />}
            {tab === "history" && <History d={data} onChanged={() => qc.invalidateQueries({ queryKey: ["corp", "customer", id] })} />}
          </div>
        )}
      </aside>
    </div>
  );
}

type D = NonNullable<ReturnType<typeof useQuery<Awaited<ReturnType<typeof corp.customer>>>>["data"]>;
type Meta = ReturnType<typeof useMeta>["data"];

function Overview({ d, meta }: { d: D; meta: Meta }) {
  const c = d.customer;
  const a = d.analysis;
  const util = a.metrics.utilization;
  return (
    <>
      {a.next_best_action && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
          <div className="text-[10px] uppercase tracking-wider text-primary font-semibold">{t("Hành động tiếp theo đề xuất", "Next best action")}</div>
          <div className="mt-1 text-sm font-medium">{a.next_best_action.name}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{a.next_best_action.why}</div>
        </div>
      )}
      {a.risk_flags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {a.risk_flags.map((f) => <FlagBadge key={f.code} severity={f.severity} text={f.text} />)}
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-x-8">
        <div>
          <Row k={t("Mã số thuế", "Tax code")} v={c.tax_code} />
          <Row k={t("Phân khúc", "Segment")} v={c.segment} />
          <Row k={t("Khu công nghiệp", "Industrial zone")} v={c.industrial_zone ?? "—"} />
          <Row k={t("Số lao động", "Employees")} v={fmtNum(c.employees)} />
          <Row k={t("Doanh thu / năm", "Revenue / year")} v={fmtBn(c.annual_revenue_bn)} />
          <Row k={t("Tổng tài sản", "Total assets")} v={fmtBn(c.total_assets_bn)} />
          <Row k={t("Vốn chủ sở hữu", "Equity")} v={fmtBn(c.equity_bn)} />
          <Row k={t("Xuất khẩu / Nhập khẩu", "Export / Import")} v={`${fmtNum(c.export_usd_m, 1)} / ${fmtNum(c.import_usd_m, 1)} ${t("tr. USD", "USD m")}`} />
          <Row k={t("Trạng thái ngoại tệ", "FX exposure")} v={`${fmtNum(c.fx_exposure_usd_m, 1)} ${t("tr. USD", "USD m")}`} />
        </div>
        <div>
          <Row k={t("CASA bình quân", "Avg CASA")} v={fmtBn(c.casa_balance_bn)} />
          <Row k={t("Tiền gửi có kỳ hạn", "Term deposit")} v={fmtBn(c.deposit_bn)} />
          <Row k={t("Dư nợ / Hạn mức", "Outstanding / Limit")} v={`${fmtBn(c.loan_outstanding_bn)} / ${fmtBn(c.credit_limit_bn)}`} />
          <Row k={t("Mức sử dụng hạn mức", "Utilisation")} v={util == null ? "—" : `${(util * 100).toFixed(0)}%`} />
          <Row k={t("Hạn mức hết hạn", "Limit expiry")} v={c.limit_expiry ? `${fmtDate(c.limit_expiry)} (${a.metrics.days_to_expiry}d)` : "—"} />
          <Row k={t("Nhóm nợ", "Debt group")} v={c.debt_group} />
          <Row k={t("Quan hệ với ngân hàng", "Relationship")} v={`${c.relationship_years} ${t("năm", "yrs")}`} />
          <Row k={t("Tỷ trọng sản phẩm sử dụng", "Product wallet share")} v={`${a.wallet_share_pct}%`} />
          <Row k="RM" v={c.rm_name} />
        </div>
      </div>
      <div className="rounded-xl bg-muted/30 p-4">
        <div className="text-xs font-semibold mb-2">{t("Đầu mối liên hệ", "Contact")}</div>
        <div className="text-sm">{c.contact_name}{c.contact_name_zh ? ` (${c.contact_name_zh})` : ""} · {c.contact_title}</div>
        <div className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-x-4">
          <span><Phone className="inline w-3 h-3 mr-1" />{c.contact_phone}</span>
          <span><Mail className="inline w-3 h-3 mr-1" />{c.contact_email}</span>
          <span>{t("Ngôn ngữ ưa thích", "Preferred language")}: {LANG_LABEL[c.preferred_language]}</span>
        </div>
      </div>
      <div>
        <div className="text-xs font-semibold mb-2">{t("Sản phẩm đang sử dụng", "Products in use")}</div>
        <div className="flex flex-wrap gap-1.5">
          {(c.products_held as string[]).length === 0 && <span className="text-xs text-muted-foreground">{t("Chưa có", "None")}</span>}
          {(c.products_held as string[]).map((p) => (
            <span key={p} className="text-[11px] px-2 py-1 rounded-md bg-accent/10 text-accent">{productName(meta, p)}</span>
          ))}
        </div>
      </div>
    </>
  );
}

function Cashflow({ d }: { d: D }) {
  const m = d.analysis.metrics;
  return (
    <>
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-muted/30 p-3"><div className="text-[10px] text-muted-foreground">{t("Dòng tiền về TB/tháng", "Avg inflow / month")}</div><div className="text-lg font-semibold mt-1">{fmtBn(m.avg_monthly_inflow_bn)}</div></div>
        <div className="rounded-lg bg-muted/30 p-3"><div className="text-[10px] text-muted-foreground">{t("Xu hướng 3 tháng", "3-month trend")}</div><div className={`text-lg font-semibold mt-1 ${m.inflow_trend_3m_pct < 0 ? "text-destructive" : "text-success"}`}>{m.inflow_trend_3m_pct > 0 ? "+" : ""}{m.inflow_trend_3m_pct}%</div></div>
        <div className="rounded-lg bg-muted/30 p-3"><div className="text-[10px] text-muted-foreground">{t("Kim ngạch XNK/năm", "Trade / year")}</div><div className="text-lg font-semibold mt-1">{fmtNum(m.trade_usd_m, 1)} {t("tr. USD", "USD m")}</div></div>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={d.monthly}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a3142" vertical={false} />
            <XAxis dataKey="month" stroke="#8892a6" fontSize={10} />
            <YAxis stroke="#8892a6" fontSize={11} />
            <Tooltip contentStyle={{ background: "#11151f", border: "1px solid #2a3142", borderRadius: 8, fontSize: 12 }} />
            <Area type="monotone" dataKey="inflow_bn" name={t("Tiền về (tỷ)", "Inflow (bn)")} stroke="#34d399" fill="#34d399" fillOpacity={0.18} />
            <Area type="monotone" dataKey="outflow_bn" name={t("Tiền đi (tỷ)", "Outflow (bn)")} stroke="#5b8bff" fill="#5b8bff" fillOpacity={0.12} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

function Opps({ d, meta, onDraft, onChanged }: { d: D; meta: Meta; onDraft: (p: string) => void; onChanged: () => void }) {
  const rows = Object.entries(d.analysis.propensities).filter(([, v]) => v.score > 0).sort((a, b) => b[1].score - a[1].score);
  const create = useMutation({ mutationFn: (product: string) => corp.createOpp({ customer_id: d.customer.customer_id, product }), onSuccess: onChanged });
  return (
    <>
      {d.opportunities.length > 0 && (
        <div className="rounded-xl bg-muted/30 p-3 text-xs space-y-1">
          <div className="font-semibold mb-1">{t("Cơ hội đang theo dõi", "Open opportunities")}</div>
          {d.opportunities.map((o) => <div key={o.id} className="flex justify-between"><span>{o.product_name}</span><span className="text-muted-foreground">{o.stage} · {fmtBn(o.expected_amount_bn)}</span></div>)}
        </div>
      )}
      {rows.map(([code, v]) => (
        <div key={code} className="rounded-xl border border-border p-4">
          <div className="flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{productName(meta, code)}</div>
              <div className="mt-1.5 h-1.5 rounded-full bg-muted overflow-hidden"><div className="h-full gradient-primary" style={{ width: `${v.score}%` }} /></div>
            </div>
            <div className="text-lg font-display font-semibold w-10 text-right">{v.score}</div>
          </div>
          <ul className="mt-2 text-xs text-muted-foreground list-disc pl-4 space-y-0.5">{v.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
          <div className="mt-3 flex gap-2">
            <button onClick={() => onDraft(code)} className="text-xs px-2.5 py-1.5 rounded-lg bg-primary/15 text-primary hover:bg-primary/25 transition flex items-center gap-1"><Send className="w-3 h-3" />{t("Soạn tin", "Draft")}</button>
            <button disabled={create.isPending} onClick={() => create.mutate(code)} className="text-xs px-2.5 py-1.5 rounded-lg border border-border hover:bg-muted/50 transition flex items-center gap-1"><Plus className="w-3 h-3" />{t("Tạo cơ hội", "Create deal")}</button>
          </div>
        </div>
      ))}
      {create.isSuccess && <div className="text-xs text-success">{t("Đã thêm vào pipeline.", "Added to pipeline.")}</div>}
    </>
  );
}

function DraftTab({ d, meta, initialProduct }: { d: D; meta: Meta; initialProduct?: string }) {
  const c = d.customer;
  const defaultProduct = initialProduct ?? d.analysis.next_best_action?.product ?? "VAY_VLD";
  const [product, setProduct] = useState(defaultProduct);
  const [channel, setChannel] = useState("zalo");
  const [lang, setLang] = useState<string>(c.preferred_language);
  const [rm, setRm] = useState(() => { try { return localStorage.getItem("corp-rm-name") || ""; } catch { return ""; } });
  const [copied, setCopied] = useState(false);
  const [text, setText] = useState("");
  const [subject, setSubject] = useState<string | null>(null);

  const gen = useMutation({
    mutationFn: () => corp.draft(c.customer_id, { product, channel, language: lang, rm_name: rm || undefined }),
    onSuccess: (r: Draft) => { setText(r.body); setSubject(r.subject); },
  });
  useEffect(() => { gen.mutate(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [product, channel, lang]);

  const sel = "bg-input/60 border border-border rounded-lg px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40";
  return (
    <>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-xs space-y-1"><span className="text-muted-foreground">{t("Sản phẩm", "Product")}</span>
          <select className={`${sel} w-full`} value={product} onChange={(e) => setProduct(e.target.value)}>
            {meta?.products.map((p) => <option key={p.code} value={p.code}>{productName(meta, p.code)}</option>)}
          </select></label>
        <label className="text-xs space-y-1"><span className="text-muted-foreground">{t("Kênh", "Channel")}</span>
          <select className={`${sel} w-full`} value={channel} onChange={(e) => setChannel(e.target.value)}>
            {["zalo", "email", "call"].map((x) => <option key={x} value={x}>{CHANNEL_LABEL(x)}</option>)}
          </select></label>
        <label className="text-xs space-y-1"><span className="text-muted-foreground">{t("Ngôn ngữ", "Language")}</span>
          <select className={`${sel} w-full`} value={lang} onChange={(e) => setLang(e.target.value)}>
            {Object.entries(LANG_LABEL).map(([k, v]) => <option key={k} value={k}>{v}{k === c.preferred_language ? ` (${t("khách ưa thích", "preferred")})` : ""}</option>)}
          </select></label>
        <label className="text-xs space-y-1"><span className="text-muted-foreground">{t("Tên RM ký tin", "RM sign-off name")}</span>
          <input className={`${sel} w-full`} value={rm} placeholder={t("VD: Nguyễn Văn A", "e.g. Nguyen Van A")}
            onChange={(e) => { setRm(e.target.value); try { localStorage.setItem("corp-rm-name", e.target.value); } catch { /* ignore */ } }}
            onBlur={() => gen.mutate()} /></label>
      </div>
      {subject && <div className="text-xs"><span className="text-muted-foreground">{t("Tiêu đề", "Subject")}: </span><span className="font-medium">{subject}</span></div>}
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={channel === "call" ? 18 : 12}
        className="w-full bg-input/60 border border-border rounded-lg p-3 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-ring/40 font-sans" />
      <div className="flex items-center gap-2">
        <button onClick={async () => { const ok = await copyText((subject ? `${subject}\n\n` : "") + text); setCopied(ok); setTimeout(() => setCopied(false), 1500); }}
          className="text-xs px-3 py-2 rounded-lg gradient-primary text-primary-foreground font-medium flex items-center gap-1.5">
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}{copied ? t("Đã sao chép", "Copied") : t("Sao chép", "Copy")}
        </button>
        {gen.isPending && <span className="text-xs text-muted-foreground">{t("Đang soạn…", "Drafting…")}</span>}
        <span className="text-[10px] text-muted-foreground ml-auto flex items-center gap-1"><MessageCircle className="w-3 h-3" />{t("Chỉ soạn nháp — RM tự gửi qua Zalo/Email.", "Draft only — the RM sends via Zalo/Email.")}</span>
      </div>
    </>
  );
}

function History({ d, onChanged }: { d: D; onChanged: () => void }) {
  const [summary, setSummary] = useState("");
  const [channel, setChannel] = useState("Điện thoại");
  const add = useMutation({
    mutationFn: () => corp.addInteraction(d.customer.customer_id, { channel, summary }),
    onSuccess: () => { setSummary(""); onChanged(); },
  });
  return (
    <>
      <div className="rounded-xl border border-border p-4 space-y-2">
        <div className="text-xs font-semibold">{t("Ghi nhận lần tiếp xúc", "Log a touchpoint")}</div>
        <div className="flex gap-2">
          <select value={channel} onChange={(e) => setChannel(e.target.value)} className="bg-input/60 border border-border rounded-lg px-2 py-2 text-sm">
            {["Điện thoại", "Gặp trực tiếp", "Zalo", "Email"].map((x) => <option key={x}>{x}</option>)}
          </select>
          <input value={summary} onChange={(e) => setSummary(e.target.value)} placeholder={t("Nội dung trao đổi…", "What was discussed…")}
            className="flex-1 bg-input/60 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40" />
          <button disabled={!summary.trim() || add.isPending} onClick={() => add.mutate()} className="px-3 rounded-lg gradient-primary text-primary-foreground text-xs font-medium disabled:opacity-50">{t("Lưu", "Save")}</button>
        </div>
      </div>
      {d.interactions.length === 0 && <div className="text-xs text-muted-foreground">{t("Chưa có lịch sử tiếp xúc.", "No touchpoints yet.")}</div>}
      <div className="space-y-2">
        {d.interactions.map((i, k) => (
          <div key={k} className="rounded-lg bg-muted/30 p-3 text-xs">
            <div className="flex justify-between text-muted-foreground"><span>{i.channel}</span><span>{fmtDate(i.date)}</span></div>
            <div className="mt-1 text-sm">{i.summary}</div>
            {i.outcome && <div className="mt-0.5 text-muted-foreground">→ {i.outcome}</div>}
          </div>
        ))}
      </div>
    </>
  );
}
