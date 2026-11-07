import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, Link } from "@tanstack/react-router";
import { Send, Rocket, Copy, Check, ShieldAlert, Users, Wand2 } from "lucide-react";
import { corpX, type Audience, type AudienceFilters, type DraftOut } from "@/lib/corpApiExt";
import { useAuth } from "@/lib/auth";
import { t, fmtBn, getLang } from "@/lib/i18n";
import { PageHeader, Card, Btn, ErrBox, Pill, Modal, Spinner, TierBadge, inputCls, useMeta, productName, copyText, LANG_LABEL, CHANNEL_LABEL } from "./shared";

const FW_LABEL: Record<string, [string, string]> = {
  consultative: ["Tư vấn giải pháp", "Consultative"], aida: ["AIDA (Chú ý → Hành động)", "AIDA"], spin: ["SPIN (Tình huống → Nhu cầu)", "SPIN"],
};
const SUPPRESS_LABEL: Record<string, [string, string]> = {
  optout: ["Đã từ chối nhận tin", "Opted out"], debt: ["Nợ nhóm cao", "High debt group"], freq: ["Mới liên hệ gần đây", "Contacted recently"],
  contact: ["Thiếu thông tin liên hệ", "Missing contact info"],
};
const MAX_SELECT = 60;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{label}</span>{children}</label>;
}

export function CorpOutreachPage() {
  const { isAdmin } = useAuth();
  const { data: meta } = useMeta();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [flt, setFlt] = useState<AudienceFilters>({ product: "", channel: "zalo", min_score: 60 });
  const [language, setLanguage] = useState("auto");
  const [framework, setFramework] = useState("consultative");
  const [aud, setAud] = useState<Audience | null>(null);
  const [tab, setTab] = useState<"ok" | "sup">("ok");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [drafts, setDrafts] = useState<DraftOut[] | null>(null);
  const [campaignOpen, setCampaignOpen] = useState(false);

  const set = <K extends keyof AudienceFilters>(k: K, v: AudienceFilters[K]) => setFlt((p) => ({ ...p, [k]: v }));
  const find = useMutation({
    mutationFn: () => corpX.audience(flt),
    onSuccess: (r) => { setAud(r); setTab("ok"); setSel(new Set()); },
  });
  const mkDrafts = useMutation({
    mutationFn: () => corpX.drafts({ product: flt.product, channel: flt.channel, language, framework, customer_ids: [...sel] }),
    onSuccess: (r) => setDrafts(r.drafts),
  });

  const toggle = (id: string) => setSel((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else if (n.size < MAX_SELECT) n.add(id); return n; });
  const eligible = aud?.eligible ?? [];
  const allOn = eligible.length > 0 && eligible.slice(0, MAX_SELECT).every((r) => sel.has(r.customer_id));
  const toggleAll = () => setSel(allOn ? new Set() : new Set(eligible.slice(0, MAX_SELECT).map((r) => r.customer_id)));
  const opts = (xs: string[] | undefined) => (xs ?? []).map((x) => <option key={x} value={x}>{x}</option>);
  const ch = (c: string) => (
    <button key={c} type="button" onClick={() => set("channel", c)} className={`px-3 py-2 text-sm rounded-lg border transition ${flt.channel === c ? "border-primary/60 bg-primary/15" : "border-border text-muted-foreground hover:bg-muted/50"}`}>{CHANNEL_LABEL(c)}</button>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Trung tâm tiếp cận khách hàng doanh nghiệp", "Corporate outreach center")}
        subtitle={t("Chọn sản phẩm → hệ thống lọc tệp khách hàng phù hợp, tự loại trừ ai không nên liên hệ → soạn tin cá nhân hóa → ghi nhận đã gửi hoặc tạo chiến dịch.", "Pick a product → the system builds the matching audience, excludes who should not be contacted → drafts personalised messages → log as sent or start a campaign.")}
        right={<Link to="/corp/campaigns"><Btn><Rocket className="w-3.5 h-3.5" /> {t("Các chiến dịch", "Campaigns")}</Btn></Link>}
      />

      <Card title={t("1 · Tệp khách hàng mục tiêu", "1 · Target audience")}>
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
          <Field label={t("Sản phẩm muốn tiếp cận *", "Product to pitch *")}>
            <select className={`${inputCls} w-full`} value={flt.product} onChange={(e) => set("product", e.target.value)}>
              <option value="">{t("— chọn sản phẩm —", "— choose —")}</option>
              {(meta?.products ?? []).map((p) => <option key={p.code} value={p.code}>{getLang() === "vi" ? p.vi : p.en}</option>)}
            </select>
          </Field>
          <Field label={t("Phân khúc", "Segment")}><select className={`${inputCls} w-full`} value={flt.segment ?? ""} onChange={(e) => set("segment", e.target.value)}><option value="">{t("Tất cả", "All")}</option>{opts(meta?.segments)}</select></Field>
          <Field label={t("Loại hình", "Ownership")}><select className={`${inputCls} w-full`} value={flt.ownership ?? ""} onChange={(e) => set("ownership", e.target.value)}><option value="">{t("Tất cả", "All")}</option><option value="FDI">FDI</option><option value="Nội địa">{t("Nội địa", "Domestic")}</option></select></Field>
          <Field label={t("Quốc gia nhà đầu tư", "Investor country")}><select className={`${inputCls} w-full`} value={flt.country ?? ""} onChange={(e) => set("country", e.target.value)}><option value="">{t("Tất cả", "All")}</option>{opts(meta?.countries)}</select></Field>
          <Field label={t("Ngành", "Industry")}><select className={`${inputCls} w-full`} value={flt.industry ?? ""} onChange={(e) => set("industry", e.target.value)}><option value="">{t("Tất cả", "All")}</option>{opts(meta?.industries)}</select></Field>
          <Field label={t("Tỉnh/Thành", "Province")}><select className={`${inputCls} w-full`} value={flt.province ?? ""} onChange={(e) => set("province", e.target.value)}><option value="">{t("Tất cả", "All")}</option>{opts(meta?.provinces)}</select></Field>
          <Field label={t("Hạng khách hàng", "Tier")}><select className={`${inputCls} w-full`} value={flt.tier ?? ""} onChange={(e) => set("tier", e.target.value)}><option value="">{t("Tất cả", "All")}</option><option value="A">A</option><option value="B">B</option><option value="C">C</option></select></Field>
          {isAdmin ? (
            <Field label={t("Cán bộ phụ trách", "RM")}><select className={`${inputCls} w-full`} value={flt.rm ?? ""} onChange={(e) => set("rm", e.target.value)}><option value="">{t("Tất cả", "All")}</option>{opts(meta?.rm_names)}</select></Field>
          ) : <div />}
          <Field label={`${t("Điểm phù hợp tối thiểu", "Min fit score")}: ${flt.min_score}`}><input type="range" min={0} max={95} step={5} value={flt.min_score} onChange={(e) => set("min_score", Number(e.target.value))} className="w-full mt-2" /></Field>
          <Field label={t("Kênh", "Channel")}><div className="flex gap-1.5">{["zalo", "email", "call"].map(ch)}</div></Field>
          <Field label={t("Ngôn ngữ tin nhắn", "Message language")}>
            <select className={`${inputCls} w-full`} value={language} onChange={(e) => setLanguage(e.target.value)}><option value="auto">{t("Theo ngôn ngữ từng khách hàng", "Per customer preference")}</option>{Object.entries(LANG_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          </Field>
          <Field label={t("Khung thuyết phục", "Persuasion framework")}>
            <select className={`${inputCls} w-full`} value={framework} onChange={(e) => setFramework(e.target.value)}>{Object.entries(FW_LABEL).map(([k, [vi, en]]) => <option key={k} value={k}>{t(vi, en)}</option>)}</select>
          </Field>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Btn kind="primary" disabled={!flt.product || find.isPending} onClick={() => find.mutate()}><Users className="w-3.5 h-3.5" /> {find.isPending ? t("Đang lọc…", "Filtering…") : t("Tìm tệp khách hàng", "Find audience")}</Btn>
          <ErrBox error={find.error} />
        </div>
      </Card>

      {find.isPending && <Spinner />}

      {aud && (
        <Card
          title={t("2 · Kết quả & loại trừ tự động", "2 · Result & automatic exclusions")}
          right={<div className="text-[11px] text-muted-foreground">{t(`Quy tắc: giãn cách ${aud.rules.freq_cap_days} ngày · không chào bán nếu nợ nhóm > ${aud.rules.max_debt_group} · ${aud.rules.quiet}`, `Rules: ${aud.rules.freq_cap_days}-day gap · no pitch above debt group ${aud.rules.max_debt_group} · ${aud.rules.quiet}`)}</div>}>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <button onClick={() => setTab("ok")} className={`px-3 py-1.5 text-sm rounded-lg ${tab === "ok" ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-muted/50"}`}>{t("Đủ điều kiện", "Eligible")} <b>{aud.eligible_total}</b></button>
            <button onClick={() => setTab("sup")} className={`px-3 py-1.5 text-sm rounded-lg inline-flex items-center gap-1 ${tab === "sup" ? "bg-warning/15 text-foreground" : "text-muted-foreground hover:bg-muted/50"}`}><ShieldAlert className="w-3.5 h-3.5" /> {t("Bị loại trừ", "Excluded")} <b>{aud.suppressed_total}</b></button>
            {Object.entries(aud.suppress_counts).map(([k, v]) => <Pill key={k} tone="warning">{t(...(SUPPRESS_LABEL[k] ?? [k, k]))}: {v}</Pill>)}
          </div>

          {tab === "ok" && (
            <>
              {eligible.length === 0 ? <div className="py-8 text-center text-sm text-muted-foreground">{t("Không có khách hàng phù hợp. Thử giảm điểm tối thiểu hoặc bỏ bớt bộ lọc.", "No matching customers. Lower the minimum score or relax the filters.")}</div> : (
                <div className="overflow-x-auto max-h-[26rem] overflow-y-auto rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-card z-10"><tr className="text-left text-xs text-muted-foreground border-b border-border">
                      <th className="py-2 pl-3 w-8"><input type="checkbox" checked={allOn} onChange={toggleAll} /></th>
                      <th className="pr-3 font-medium">{t("Khách hàng", "Customer")}</th><th className="pr-3 font-medium">{t("Ngành · Tỉnh", "Industry · Province")}</th>
                      <th className="pr-3 font-medium text-right">{t("Điểm", "Score")}</th><th className="pr-3 font-medium text-right">{t("Kỳ vọng", "Expected")}</th><th className="pr-3 font-medium">{t("Lý do phù hợp", "Why it fits")}</th>
                    </tr></thead>
                    <tbody>
                      {eligible.map((r) => (
                        <tr key={r.customer_id} onClick={() => toggle(r.customer_id)} className={`border-b border-border/60 cursor-pointer hover:bg-muted/20 ${sel.has(r.customer_id) ? "bg-primary/5" : ""}`}>
                          <td className="py-2 pl-3"><input type="checkbox" checked={sel.has(r.customer_id)} onChange={() => toggle(r.customer_id)} onClick={(e) => e.stopPropagation()} /></td>
                          <td className="pr-3"><div className="flex items-center gap-1.5"><span className="font-medium truncate max-w-[240px]">{r.name}</span><TierBadge tier={r.tier} /></div><div className="text-[11px] text-muted-foreground">{r.customer_id}{r.contact_name ? ` · ${r.contact_name}` : ""}{r.rm_name ? ` · ${r.rm_name}` : ""}</div></td>
                          <td className="pr-3 text-xs text-muted-foreground">{r.industry} · {r.province}</td>
                          <td className="pr-3 text-right tabular-nums">{r.product_score}</td>
                          <td className="pr-3 text-right tabular-nums text-xs">{r.expected_amount_bn ? fmtBn(r.expected_amount_bn, 1) : "—"}</td>
                          <td className="pr-3 text-xs text-muted-foreground max-w-[320px]">{(r.reasons ?? []).slice(0, 2).join("; ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {aud.eligible_total > eligible.length && <div className="text-[11px] text-muted-foreground mt-2">{t(`Hiển thị ${eligible.length}/${aud.eligible_total} khách hàng phù hợp nhất.`, `Showing the top ${eligible.length} of ${aud.eligible_total}.`)}</div>}
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <span className="text-sm">{t("Đã chọn", "Selected")}: <b>{sel.size}</b><span className="text-muted-foreground text-xs"> / {t("tối đa", "max")} {MAX_SELECT}</span></span>
                <div className="flex-1" />
                <Btn disabled={sel.size === 0 || mkDrafts.isPending} onClick={() => mkDrafts.mutate()}><Wand2 className="w-3.5 h-3.5" /> {mkDrafts.isPending ? t("Đang soạn…", "Drafting…") : t("Soạn tin cho khách đã chọn", "Draft messages for selected")}</Btn>
                <Btn kind="primary" disabled={sel.size === 0} onClick={() => setCampaignOpen(true)}><Rocket className="w-3.5 h-3.5" /> {t("Tạo chiến dịch", "Create campaign")}</Btn>
              </div>
              <div className="mt-2"><ErrBox error={mkDrafts.error} /></div>
            </>
          )}

          {tab === "sup" && (
            aud.suppressed.length === 0 ? <div className="py-8 text-center text-sm text-muted-foreground">{t("Không có khách hàng bị loại trừ.", "No customers excluded.")}</div> : (
              <div className="overflow-x-auto max-h-[26rem] overflow-y-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card"><tr className="text-left text-xs text-muted-foreground border-b border-border"><th className="py-2 pl-3 font-medium">{t("Khách hàng", "Customer")}</th><th className="font-medium">{t("Lý do loại trừ", "Reason")}</th></tr></thead>
                  <tbody>{aud.suppressed.map((r) => (
                    <tr key={r.customer_id} className="border-b border-border/60"><td className="py-2 pl-3"><span className="font-medium">{r.name}</span><div className="text-[11px] text-muted-foreground">{r.customer_id} · {r.rm_name}</div></td><td className="text-xs text-warning">{r.suppress_reason}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            )
          )}
        </Card>
      )}

      {drafts && <DraftsModal drafts={drafts} channel={flt.channel} onClose={() => setDrafts(null)} onLogged={() => qc.invalidateQueries({ queryKey: ["corp"] })} />}
      {campaignOpen && (
        <CampaignDialog
          defaultName={`${productName(meta, flt.product)} · ${new Date().toLocaleDateString(getLang() === "vi" ? "vi-VN" : "en-GB")}`}
          onClose={() => setCampaignOpen(false)}
          onCreate={(name) => corpX.createCampaign({ ...flt, name, language, framework, customer_ids: [...sel] }).then((r) => { qc.invalidateQueries({ queryKey: ["corp"] }); nav({ to: "/corp/campaigns", search: { open: r.id } }); })}
        />
      )}
    </div>
  );
}

function CampaignDialog({ defaultName, onClose, onCreate }: { defaultName: string; onClose: () => void; onCreate: (name: string) => Promise<unknown> }) {
  const [name, setName] = useState(defaultName);
  const m = useMutation({ mutationFn: () => onCreate(name.trim()) });
  return (
    <Modal title={t("Tạo chiến dịch", "Create campaign")} onClose={onClose}
      footer={<><ErrBox error={m.error} /><Btn onClick={onClose}>{t("Hủy", "Cancel")}</Btn><Btn kind="primary" disabled={name.trim().length < 2 || m.isPending} onClick={() => m.mutate()}>{t("Tạo", "Create")}</Btn></>}>
      <Field label={t("Tên chiến dịch", "Campaign name")}><input className={`${inputCls} w-full`} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <p className="text-xs text-muted-foreground mt-3">{t("Mỗi khách hàng đã chọn được soạn sẵn một tin riêng. Bạn theo dõi trạng thái (đã liên hệ → phản hồi → quan tâm → chuyển đổi) trong trang Chiến dịch.", "Each selected customer gets a pre-drafted message. Track status (contacted → replied → interested → converted) on the Campaigns page.")}</p>
    </Modal>
  );
}

function DraftsModal({ drafts, channel, onClose, onLogged }: { drafts: DraftOut[]; channel: string; onClose: () => void; onLogged: () => void }) {
  const [body, setBody] = useState<Record<string, string>>(() => Object.fromEntries(drafts.map((d) => [d.customer_id, d.body])));
  const [done, setDone] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<Record<string, string>>({});
  const log = useMutation({
    mutationFn: (ds: DraftOut[]) => corpX.logSent(ds.map((d) => ({ customer_id: d.customer_id, product: d.product, channel: d.channel, language: d.language, subject: d.subject, body: body[d.customer_id] ?? d.body }))),
    onSuccess: (r, ds) => {
      const bl = Object.fromEntries(r.blocked.map((b) => [b.customer_id, b.reason]));
      setBlocked((p) => ({ ...p, ...bl }));
      setDone((p) => { const n = new Set(p); ds.forEach((d) => { if (!bl[d.customer_id]) n.add(d.customer_id); }); return n; });
      onLogged();
    },
  });
  const pending = drafts.filter((d) => !done.has(d.customer_id));
  return (
    <Modal wide title={t(`Tin nhắn đã soạn (${drafts.length}) · ${CHANNEL_LABEL(channel)}`, `Drafted messages (${drafts.length}) · ${CHANNEL_LABEL(channel)}`)} onClose={onClose}
      footer={<><ErrBox error={log.error} /><Btn onClick={onClose}>{t("Đóng", "Close")}</Btn><Btn kind="primary" disabled={pending.length === 0 || log.isPending} onClick={() => log.mutate(pending)}><Check className="w-3.5 h-3.5" /> {t(`Ghi nhận đã gửi tất cả (${pending.length})`, `Log all as sent (${pending.length})`)}</Btn></>}>
      <p className="text-xs text-muted-foreground mb-3">{t("Sao chép từng tin để gửi qua Zalo/Email/điện thoại, rồi bấm “Đã gửi” để hệ thống ghi nhận (tạo cơ hội và tính giãn cách liên hệ). Bạn có thể sửa nội dung trước khi gửi.", "Copy each message to send via Zalo/email/phone, then press “Sent” so it is logged (creates the opportunity and starts the contact-gap timer). You can edit the text first.")}</p>
      <div className="space-y-3">
        {drafts.map((d) => (
          <div key={d.customer_id} className={`rounded-xl border p-3 ${done.has(d.customer_id) ? "border-success/40 bg-success/5" : "border-border"}`}>
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="text-sm font-medium truncate">{d.customer_name} <span className="text-[11px] text-muted-foreground font-normal">· {LANG_LABEL[d.language] ?? d.language}</span></div>
              <div className="flex gap-1.5 shrink-0">
                <Btn onClick={async () => { await copyText((d.subject ? d.subject + "\n\n" : "") + (body[d.customer_id] ?? d.body)); setCopied(d.customer_id); setTimeout(() => setCopied(null), 1500); }}>
                  {copied === d.customer_id ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />} {t("Sao chép", "Copy")}
                </Btn>
                {done.has(d.customer_id) ? <Pill tone="success">{t("Đã ghi nhận", "Logged")}</Pill> : <Btn disabled={log.isPending} onClick={() => log.mutate([d])}><Send className="w-3.5 h-3.5" /> {t("Đã gửi", "Sent")}</Btn>}
              </div>
            </div>
            {d.subject && <div className="text-xs mb-1.5"><span className="text-muted-foreground">{t("Tiêu đề", "Subject")}:</span> {d.subject}</div>}
            <textarea className={`${inputCls} w-full text-xs leading-relaxed min-h-[110px]`} value={body[d.customer_id] ?? ""} onChange={(e) => setBody((p) => ({ ...p, [d.customer_id]: e.target.value }))} />
            {blocked[d.customer_id] && <div className="text-xs text-destructive mt-1">{blocked[d.customer_id]}</div>}
          </div>
        ))}
      </div>
    </Modal>
  );
}
