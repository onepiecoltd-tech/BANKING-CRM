import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, XCircle, Trash2, Download, ShieldAlert } from "lucide-react";
import { corpX, type CorpSettings } from "@/lib/corpApiExt";
import { useAuth } from "@/lib/auth";
import { t } from "@/lib/i18n";
import { PageHeader, Card, Btn, ErrBox, Spinner, Stat, inputCls } from "./shared";

function Toggle({ on, onChange, label, hint }: { on: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer">
      <button type="button" role="switch" aria-checked={on} onClick={() => onChange(!on)} className={`mt-0.5 w-9 h-5 rounded-full relative transition shrink-0 ${on ? "bg-primary" : "bg-muted"}`}>
        <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${on ? "left-[18px]" : "left-0.5"}`} />
      </button>
      <span><span className="block text-sm">{label}</span>{hint && <span className="block text-[11px] text-muted-foreground mt-0.5">{hint}</span>}</span>
    </label>
  );
}

function Row({ label, ok, text }: { label: string; ok?: boolean; text: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border/60 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="inline-flex items-center gap-1.5">{ok === undefined ? null : ok ? <CheckCircle2 className="w-3.5 h-3.5 text-success" /> : <XCircle className="w-3.5 h-3.5 text-muted-foreground" />}{text}</span>
    </div>
  );
}

export function CorpSettingsPage() {
  const { isAdmin } = useAuth();
  if (!isAdmin) return <NoAccess />;
  return <SettingsInner />;
}

function NoAccess() {
  return (
    <div className="glass rounded-xl p-10 text-center shadow-card">
      <div className="text-lg font-semibold">{t("Chỉ dành cho Admin (Quản lý)", "Admin (manager) only")}</div>
      <p className="text-sm text-muted-foreground mt-1">{t("Tài khoản của bạn không có quyền truy cập trang này.", "Your account does not have access to this page.")}</p>
    </div>
  );
}

function SettingsInner() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["corp", "settings"], queryFn: corpX.settings });
  const [f, setF] = useState<Partial<CorpSettings>>({});
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (data) setF(data.settings); }, [data]);
  const set = <K extends keyof CorpSettings>(k: K, v: CorpSettings[K]) => { setSaved(false); setF((p) => ({ ...p, [k]: v })); };
  const save = useMutation({
    mutationFn: () => corpX.saveSettings(f),
    onSuccess: () => { setSaved(true); qc.invalidateQueries({ queryKey: ["corp"] }); },
  });
  const backup = useMutation({ mutationFn: corpX.downloadBackup, onSuccess: () => qc.invalidateQueries({ queryKey: ["corp", "settings"] }) });

  if (isLoading || !data) return <Spinner />;
  const sys = data.system;
  const demo = sys.demo_customers ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader title={t("Quản trị & Cài đặt (Doanh nghiệp)", "Admin & settings (Corporate)")} subtitle={t("Chỉ Admin được xem và chỉnh. Mọi thay đổi được ghi vào nhật ký thao tác.", "Admin only. Every change is written to the audit log.")} />
      <ErrBox error={error} />

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Stat label={t("Khách hàng DN trong hệ thống", "Corporate customers")} value={sys.corp_customers ?? 0} />
        <Stat label={t("Trong đó dữ liệu mẫu", "of which demo data")} value={demo} tone={demo ? "warning" : "success"} />
        <Stat label={t("Cơ sở dữ liệu", "Database")} value={<span className="text-base">{sys.database ?? "—"}</span>} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card title={t("Quy tắc tiếp cận khách hàng", "Outreach rules")}>
          <div className="space-y-3">
            <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{t("Tên ngân hàng / chi nhánh (hiện trong tin nhắn)", "Bank / branch name (used in messages)")}</span>
              <input className={`${inputCls} w-full`} value={f.bank_name ?? ""} onChange={(e) => set("bank_name", e.target.value)} /></label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{t("Giãn cách tối thiểu giữa 2 lần liên hệ (ngày)", "Min days between contacts")}</span>
                <input type="number" min={0} max={365} className={`${inputCls} w-full`} value={f.freq_cap_days ?? 0} onChange={(e) => set("freq_cap_days", Number(e.target.value))} /></label>
              <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{t("Không bán chéo nếu nhóm nợ >", "No cross-sell if debt group >")}</span>
                <select className={`${inputCls} w-full`} value={f.max_debt_group_outreach ?? 2} onChange={(e) => set("max_debt_group_outreach", Number(e.target.value))}>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
              <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{t("Giờ yên lặng từ", "Quiet hours from")}</span>
                <input type="time" className={`${inputCls} w-full`} value={f.quiet_start ?? "20:00"} onChange={(e) => set("quiet_start", e.target.value)} /></label>
              <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{t("đến", "to")}</span>
                <input type="time" className={`${inputCls} w-full`} value={f.quiet_end ?? "08:00"} onChange={(e) => set("quiet_end", e.target.value)} /></label>
            </div>
          </div>
        </Card>

        <Card title={t("Phân quyền nhập liệu & AI", "Data entry & AI")}>
          <div className="space-y-4">
            <Toggle on={!!f.import_requires_approval} onChange={(v) => set("import_requires_approval", v)}
              label={t("Lô import của nhân viên phải được quản lý duyệt", "Staff imports need admin approval")}
              hint={t("Bật: dữ liệu chỉ vào hệ thống sau khi Admin bấm Duyệt. Tắt: nhân viên nhập trực tiếp (vẫn chỉ cho khách hàng của mình).", "On: data is applied only after an admin approves. Off: staff import directly (still limited to own customers).")} />
            <Toggle on={!!f.allow_cloud_ocr} onChange={(v) => set("allow_cloud_ocr", v)}
              label={t("Cho phép OCR đám mây (Google Gemini)", "Allow cloud OCR (Google Gemini)")}
              hint={t("Chỉ bật khi chính sách bảo mật của ngân hàng cho phép gửi nội dung file ra ngoài. Mặc định tắt — OCR chạy trên máy bằng Tesseract.", "Enable only if bank policy allows sending file content externally. Off by default — OCR runs locally with Tesseract.")} />
            <Toggle on={!!f.llm_enabled} onChange={(v) => set("llm_enabled", v)}
              label={t("Cho phép dùng mô hình ngôn ngữ (trợ lý AI, gợi ý trả lời)", "Allow language-model features (AI assistant, reply suggestions)")}
              hint={t("Tắt: hệ thống dùng luật & mẫu có sẵn, không gửi dữ liệu khách hàng ra ngoài.", "Off: rule-based templates only; no customer data leaves the machine.")} />
          </div>
        </Card>
      </div>

      <div className="flex items-center gap-3">
        <Btn kind="primary" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? t("Đang lưu…", "Saving…") : t("Lưu cài đặt", "Save settings")}</Btn>
        {saved && <span className="text-xs text-success inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> {t("Đã lưu", "Saved")}</span>}
        <ErrBox error={save.error} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card title={t("Trạng thái hệ thống", "System status")}>
          <Row label={t("OCR trên máy (Tesseract)", "Local OCR (Tesseract)")} ok={!!sys.ocr_local} text={sys.ocr_local ? t("Đã cài", "Installed") : t("Chưa cài — scan/ảnh cần Tesseract hoặc OCR đám mây", "Not installed — scans need Tesseract or cloud OCR")} />
          <Row label={t("Khóa Gemini (.env)", "Gemini key (.env)")} ok={!!sys.has_gemini_key} text={sys.has_gemini_key ? t("Có", "Present") : t("Chưa có", "Missing")} />
          <Row label={t("Mô hình ngôn ngữ", "LLM backend")} text={sys.llm_backend ?? "—"} />
          <Row label={t("Kênh gửi tin", "Message sender")} text={sys.sender_backend ?? "—"} />
          <p className="text-[11px] text-muted-foreground mt-3">{t("Để cài Tesseract trên Windows: tải bản UB-Mannheim, chọn thêm ngôn ngữ Vietnamese & Chinese (Simplified).", "To install Tesseract on Windows: use the UB-Mannheim build and add the Vietnamese & Chinese (Simplified) language data.")}</p>
        </Card>

        <Card title={t("Sao lưu dữ liệu", "Data backup")}>
          <p className="text-sm text-muted-foreground">
            {sys.backup_auto
              ? t("Máy chủ tự sao lưu mỗi ngày và giữ các bản gần nhất. Hãy tải thêm một bản về máy/ổ cứng ngoài định kỳ để phòng sự cố máy chủ.", "The server backs up daily and keeps recent copies. Also download a copy to your own device periodically in case the server fails.")
              : t("Máy chủ chưa bật sao lưu tự động (chạy trên máy cá nhân). Hãy tải bản sao lưu định kỳ.", "Automatic backup is off (running on a personal machine). Download backups regularly.")}
          </p>
          <div className="mt-2 text-xs text-muted-foreground">
            {sys.backup ? t(`Bản gần nhất: ${sys.backup.at.replace("T", " ")} — ${(sys.backup.bytes / 1048576).toFixed(1)} MB (${sys.backup.count} bản đang giữ)`, `Latest: ${sys.backup.at.replace("T", " ")} — ${(sys.backup.bytes / 1048576).toFixed(1)} MB (${sys.backup.count} kept)`) : t("Chưa có bản sao lưu tự động nào.", "No automatic backup yet.")}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <Btn disabled={backup.isPending} onClick={() => backup.mutate()}>
              <Download className="w-3.5 h-3.5" /> {backup.isPending ? t("Đang tạo…", "Creating…") : t("Tải bản sao lưu về máy", "Download backup")}
            </Btn>
            {backup.isSuccess && <span className="text-xs text-success">{t(`Đã tải ${backup.data}`, `Downloaded ${backup.data}`)}</span>}
          </div>
          <div className="mt-2"><ErrBox error={backup.error} /></div>
        </Card>

        <CleanupCard />
      </div>
    </div>
  );
}


const GROUPS = [
  { key: "retail" as const, vi: "Khách hàng cá nhân mô phỏng", en: "Simulated retail customers",
    hint: ["Toàn bộ khách hàng cá nhân mẫu cùng giao dịch, tương tác, định danh, đồng ý, danh sách chặn.", "All sample retail customers with their transactions, interactions, identities, consents and suppressions."],
    rows: [["customers", "Khách hàng", "Customers"], ["transactions", "Giao dịch", "Transactions"], ["interactions", "Tương tác/ghi chú", "Interactions/notes"], ["identity_graph", "Định danh", "Identities"], ["consents", "Đồng ý", "Consents"], ["suppressions", "Danh sách chặn", "Suppressions"]] },
  { key: "corp_demo" as const, vi: "Khách hàng DN mẫu (CORPxxxx) & ghi chú mô phỏng", en: "Sample corporate customers (CORPxxxx) & simulated notes",
    hint: ["Khách hàng DN mẫu cùng dòng tiền, cơ hội, ghi chú tương tác, hội thoại, chiến dịch mẫu. KH thật (nhập từ Excel) không bị đụng.", "Sample corporate customers with cash flow, opportunities, interaction notes, conversations and campaigns. Real (imported) customers are untouched."],
    rows: [["customers", "Khách hàng", "Customers"], ["monthly", "Dòng tiền tháng", "Monthly cash flow"], ["interactions", "Ghi chú tương tác", "Interaction notes"], ["opportunities", "Cơ hội", "Opportunities"], ["messages", "Tin nhắn", "Messages"], ["campaigns", "Chiến dịch", "Campaigns"]] },
  { key: "junk" as const, vi: "Dữ liệu rác", en: "Junk data",
    hint: ["Dòng mồ côi (khách hàng đã bị xóa), ghi chú trống, nhật ký chạy AI bị lỗi, chiến dịch rỗng.", "Orphan rows (customer deleted), blank notes, failed AI-run logs, empty campaigns."],
    rows: [["orphans", "Dòng mồ côi", "Orphan rows"], ["blank_notes", "Ghi chú trống", "Blank notes"], ["failed_ai_runs", "Log AI lỗi", "Failed AI runs"], ["empty_campaigns", "Chiến dịch rỗng", "Empty campaigns"]] },
];

function CleanupCard() {
  const qc = useQueryClient();
  const { data, error, isLoading } = useQuery({ queryKey: ["corp", "cleanup"], queryFn: corpX.cleanupPlan });
  const [pick, setPick] = useState({ retail: true, corp_demo: true, junk: true });
  const [word, setWord] = useState("");
  const run = useMutation({
    mutationFn: () => corpX.cleanupRun({ ...pick, confirm: word }),
    onSuccess: () => { setWord(""); qc.invalidateQueries(); },
  });
  if (isLoading || !data) return <Card title={t("Dọn dữ liệu mô phỏng & rác", "Clean simulated & junk data")}><Spinner /></Card>;
  const total = GROUPS.reduce((n, g) => n + (pick[g.key] ? data[g.key].total : 0), 0);
  const any = pick.retail || pick.corp_demo || pick.junk;
  return (
    <Card title={t("Dọn dữ liệu mô phỏng & rác", "Clean simulated & junk data")} className="md:col-span-2">
      <p className="text-sm text-muted-foreground">
        {t("Chọn nhóm cần xóa. Hệ thống tự sao lưu CSDL trước khi xóa và sẽ không nạp lại dữ liệu mẫu ở lần khởi động sau.", "Pick what to delete. The database is backed up automatically first, and sample data will not be re-seeded on next start.")}
      </p>
      <div className="mt-3 grid md:grid-cols-3 gap-3">
        {GROUPS.map((g) => {
          const grp = data[g.key];
          const on = pick[g.key];
          return (
            <label key={g.key} className={`rounded-lg border p-3 cursor-pointer transition ${on ? "border-primary/50 bg-primary/5" : "border-border bg-muted/20"}`}>
              <div className="flex items-start gap-2">
                <input type="checkbox" className="mt-1" checked={on} onChange={(e) => setPick((p) => ({ ...p, [g.key]: e.target.checked }))} />
                <div className="min-w-0">
                  <div className="text-sm font-medium">{t(g.vi, g.en)}</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{t(g.hint[0], g.hint[1])}</div>
                </div>
              </div>
              <ul className="mt-2 text-[11px] space-y-0.5">
                {g.rows.map(([k, vi, en]) => (
                  <li key={k} className="flex justify-between"><span className="text-muted-foreground">{t(vi, en)}</span><span className="tabular-nums">{(grp[k] ?? 0).toLocaleString()}</span></li>
                ))}
              </ul>
              <div className={`mt-2 text-xs font-semibold ${grp.total ? "text-warning" : "text-success"}`}>
                {grp.total ? t(`${grp.total.toLocaleString()} dòng sẽ bị xóa`, `${grp.total.toLocaleString()} rows will be deleted`) : t("Đã sạch", "Already clean")}
              </div>
            </label>
          );
        })}
      </div>
      <div className="mt-3 flex items-center gap-1.5 text-xs text-success">
        <CheckCircle2 className="w-3.5 h-3.5" />
        {t(`Giữ nguyên ${data.real_corp_customers.toLocaleString()} khách hàng doanh nghiệp thật, tài khoản và nhật ký thao tác.`, `Keeps ${data.real_corp_customers.toLocaleString()} real corporate customers, accounts and the audit log.`)}
      </div>
      {!data.backup_ok && <div className="mt-2 text-xs text-destructive flex items-center gap-1.5"><ShieldAlert className="w-3.5 h-3.5" />{t("Chỉ hỗ trợ dọn khi dùng SQLite (cần sao lưu trước khi xóa).", "Cleanup requires SQLite (a backup is taken first).")}</div>}
      <div className="mt-3 flex items-center gap-3 flex-wrap">
        <input className={`${inputCls} w-44`} value={word} onChange={(e) => setWord(e.target.value)} placeholder={t("Gõ XOA để xác nhận", "Type XOA to confirm")} />
        <Btn kind="danger" disabled={run.isPending || !any || total === 0 || word.trim().toUpperCase() !== "XOA" || !data.backup_ok} onClick={() => run.mutate()}>
          <Trash2 className="w-3.5 h-3.5" /> {run.isPending ? t("Đang dọn…", "Cleaning…") : t(`Sao lưu rồi xóa ${total.toLocaleString()} dòng`, `Back up, then delete ${total.toLocaleString()} rows`)}
        </Btn>
        {run.isSuccess && <span className="text-xs text-success">{t(`Đã xóa ${run.data.deleted_total.toLocaleString()} dòng. Bản sao lưu: ${run.data.backup}`, `Deleted ${run.data.deleted_total.toLocaleString()} rows. Backup: ${run.data.backup}`)}</span>}
      </div>
      <div className="mt-2"><ErrBox error={error || run.error} /></div>
    </Card>
  );
}
