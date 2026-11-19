import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { FileUp, FileSpreadsheet, ScanText, Download, CheckCircle2, AlertTriangle, XCircle, Trash2, Check, X, UploadCloud } from "lucide-react";
import { corpX, type ImportBatch, type ImportUpload, type ImportPreview } from "@/lib/corpApiExt";
import { useAuth } from "@/lib/auth";
import { t } from "@/lib/i18n";
import { PageHeader, Card, Btn, ErrBox, Pill, Modal, Stat, Spinner, inputCls, fmtDateTime, useMeta } from "./shared";

const OCR_OPTS: [string, string, string][] = [
  ["auto", "Tự động (khuyến nghị)", "Auto (recommended)"],
  ["local", "OCR trên máy (Tesseract)", "Local OCR (Tesseract)"],
  ["cloud", "OCR đám mây (Gemini)", "Cloud OCR (Gemini)"],
  ["off", "Không OCR", "No OCR"],
];
const STATUS_TONE: Record<string, "muted" | "success" | "warning" | "destructive" | "primary"> = {
  "Xem trước": "muted", "Chờ duyệt": "warning", "Đã nhập": "success", "Từ chối": "destructive", "Hủy": "muted",
};
const METHOD_LABEL: Record<string, string> = {
  xlsx: "Excel", csv: "CSV", "pdf-table": t("PDF · bảng", "PDF · tables"), "pdf-text": t("PDF · văn bản", "PDF · text"), "pdf-kv": t("PDF · cặp nhãn–giá trị", "PDF · key–value"),
  "ocr-local": "OCR · Tesseract", "ocr-cloud": "OCR · Gemini",
};

export function CorpImportPage() {
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const { data: meta } = useMeta();
  const [target, setTarget] = useState<"customers" | "monthly">("customers");
  const [ocr, setOcr] = useState("auto");
  const [drag, setDrag] = useState(false);
  const [up, setUp] = useState<ImportUpload | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({}); // cột -> trường
  const [updateExisting, setUpdateExisting] = useState(true);
  const [defaultRm, setDefaultRm] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<{ status: string; created?: number; updated?: number } | null>(null);
  const [rejecting, setRejecting] = useState<ImportBatch | null>(null);
  const [rejNote, setRejNote] = useState("");
  const [detail, setDetail] = useState<number | null>(null);

  const batches = useQuery({ queryKey: ["corp", "import", "batches"], queryFn: corpX.importBatches, refetchInterval: 15_000 });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["corp"] }); };

  const upload = useMutation({
    mutationFn: ({ file, sheet }: { file: File; sheet?: string }) => corpX.importUpload(file, target, ocr, sheet),
    onSuccess: (r) => { setUp(r); setMapping(r.batch.mapping ?? {}); setPreview(null); setResult(null); refresh(); },
  });
  const fileFor = useRef<File | null>(null);
  const pick = (f: File | undefined | null, sheet?: string) => { if (!f) return; fileFor.current = f; upload.mutate({ file: f, sheet }); };

  const body = () => ({ mapping, update_existing: updateExisting, default_rm: isAdmin ? defaultRm || undefined : undefined });
  const prev = useMutation({ mutationFn: () => corpX.importPreview(up!.batch.id, body()), onSuccess: setPreview });
  const commit = useMutation({
    mutationFn: () => corpX.importCommit(up!.batch.id, body()),
    onSuccess: (r) => { setResult(r); setUp(null); setPreview(null); refresh(); },
  });
  const approve = useMutation({ mutationFn: (id: number) => corpX.importApprove(id), onSuccess: refresh });
  const reject = useMutation({ mutationFn: ({ id, note }: { id: number; note: string }) => corpX.importReject(id, note), onSuccess: () => { setRejecting(null); setRejNote(""); refresh(); } });
  const cancel = useMutation({ mutationFn: (id: number) => corpX.importCancel(id), onSuccess: refresh });

  // đảo ánh xạ: trường -> cột
  const fieldToCol: Record<string, string> = {};
  Object.entries(mapping).forEach(([c, f]) => { if (f) fieldToCol[f] = c; });
  const setField = (field: string, col: string) => {
    setPreview(null);
    setMapping((m) => {
      const n: Record<string, string> = {};
      Object.entries(m).forEach(([c, f]) => { if (f !== field) n[c] = f; });
      if (col) n[col] = field;
      return n;
    });
  };
  const missingReq = up ? up.fields.filter((f) => f.required && !fieldToCol[f.key]) : [];
  const reset = () => { setUp(null); setPreview(null); setResult(null); upload.reset(); };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Import dữ liệu khách hàng doanh nghiệp", "Corporate data import")}
        subtitle={t("Nhập từ Excel (.xlsx), CSV, PDF hoặc ảnh/PDF scan (OCR). Hệ thống tự nhận cột, bạn kiểm tra trước khi ghi vào dữ liệu.", "Import from Excel, CSV, PDF or scanned PDF/image (OCR). Columns are auto-detected; review before anything is written.")}
        right={<Link to="/corp/customers"><Btn>{t("← Danh sách khách hàng", "← Customers")}</Btn></Link>}
      />

      {result && (
        <div className={`rounded-xl px-4 py-3 text-sm flex items-start gap-2 ${result.status === "Chờ duyệt" ? "bg-warning/10 text-warning" : "bg-success/10 text-success"}`}>
          <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            {result.status === "Chờ duyệt"
              ? t("Đã gửi lô import cho quản lý duyệt. Dữ liệu sẽ vào hệ thống sau khi được phê duyệt.", "Import submitted for admin approval. Data is applied once approved.")
              : t(`Đã nhập xong: thêm mới ${result.created ?? 0}, cập nhật ${result.updated ?? 0}.`, `Done: ${result.created ?? 0} created, ${result.updated ?? 0} updated.`)}
          </div>
        </div>
      )}

      {!up && (
        <Card title={t("Bước 1 · Chọn file", "Step 1 · Choose a file")}>
          <div className="grid md:grid-cols-3 gap-4 mb-4">
            <label className="block">
              <span className="block text-[11px] text-muted-foreground mb-1">{t("Loại dữ liệu", "Data type")}</span>
              <select className={`${inputCls} w-full`} value={target} onChange={(e) => setTarget(e.target.value as any)}>
                <option value="customers">{t("Hồ sơ khách hàng doanh nghiệp", "Corporate customer profiles")}</option>
                <option value="monthly">{t("Dòng tiền theo tháng (khách hàng đã có)", "Monthly cash-flow (existing customers)")}</option>
              </select>
            </label>
            <label className="block">
              <span className="block text-[11px] text-muted-foreground mb-1">{t("Chế độ đọc file scan/ảnh", "Scan/image reading")}</span>
              <select className={`${inputCls} w-full`} value={ocr} onChange={(e) => setOcr(e.target.value)}>
                {OCR_OPTS.map(([v, vi, en]) => <option key={v} value={v}>{t(vi, en)}</option>)}
              </select>
            </label>
            <div className="flex items-end">
              <Btn onClick={() => corpX.downloadTemplate(target).catch((e) => alert(e.message))}><Download className="w-3.5 h-3.5" /> {t("Tải file Excel mẫu", "Download Excel template")}</Btn>
            </div>
          </div>
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}
            onClick={() => fileRef.current?.click()}
            className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center transition ${drag ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"}`}>
            <UploadCloud className="w-8 h-8 mx-auto text-primary mb-2" />
            <div className="text-sm font-medium">{upload.isPending ? t("Đang đọc file…", "Reading file…") : t("Kéo thả file vào đây hoặc bấm để chọn", "Drop a file here or click to choose")}</div>
            <div className="text-xs text-muted-foreground mt-1 flex items-center justify-center gap-3 flex-wrap">
              <span className="inline-flex items-center gap-1"><FileSpreadsheet className="w-3.5 h-3.5" /> .xlsx · .csv</span>
              <span className="inline-flex items-center gap-1"><FileUp className="w-3.5 h-3.5" /> PDF</span>
              <span className="inline-flex items-center gap-1"><ScanText className="w-3.5 h-3.5" /> {t("PDF scan / ảnh .png .jpg (OCR)", "Scanned PDF / .png .jpg (OCR)")}</span>
              <span>· {t("tối đa 20 MB", "max 20 MB")}</span>
            </div>
            <input ref={fileRef} type="file" hidden accept=".xlsx,.xlsm,.csv,.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
          </div>
          {upload.isPending && <Spinner />}
          <div className="mt-3"><ErrBox error={upload.error} /></div>
          <p className="text-[11px] text-muted-foreground mt-3">
            {t("OCR đọc tốt tiếng Việt/Anh/Trung nếu máy đã cài Tesseract; hoặc quản lý bật 'OCR đám mây' trong Cài đặt (gửi nội dung file lên Google Gemini). Kết quả OCR luôn cần được kiểm tra lại ở bước 2.",
              "OCR handles Vietnamese/English/Chinese when Tesseract is installed, or an admin can enable cloud OCR in Settings (file content is sent to Google Gemini). OCR output should always be reviewed in step 2.")}
          </p>
        </Card>
      )}

      {up && (
        <Card
          title={t("Bước 2 · Kiểm tra ánh xạ cột", "Step 2 · Review column mapping")}
          right={<div className="flex items-center gap-2 text-xs text-muted-foreground"><Pill tone="primary">{METHOD_LABEL[up.batch.method ?? ""] ?? up.batch.method}</Pill><span>{up.batch.filename} · {up.batch.row_count} {t("dòng", "rows")}</span><Btn onClick={reset}><X className="w-3.5 h-3.5" /> {t("Chọn file khác", "Other file")}</Btn></div>}>
          {up.warnings.length > 0 && (
            <div className="mb-3 space-y-1">
              {up.warnings.map((w, i) => <div key={i} className="text-xs text-warning bg-warning/10 rounded-lg px-3 py-1.5 flex gap-2"><AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />{w}</div>)}
            </div>
          )}
          {up.batch.row_count === 0 && (
            <div className="mb-3 text-xs text-warning bg-warning/10 rounded-lg px-3 py-1.5 flex gap-2"><AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />{t("File chưa có dòng dữ liệu nào (chỉ có dòng tiêu đề?). Điền dữ liệu vào sheet đầu tiên rồi tải lại.", "The file has no data rows (headers only?). Fill the first sheet and upload again.")}</div>
          )}
          {up.sheets.length > 1 && (
            <label className="flex items-center gap-2 text-xs mb-3">
              {t("Sheet:", "Sheet:")}
              <select className={inputCls} value={up.sheet ?? ""} onChange={(e) => pick(fileFor.current, e.target.value)}>
                {up.sheets.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          )}
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-x-4 gap-y-2.5">
            {up.fields.map((f) => (
              <label key={f.key} className="block">
                <span className="block text-[11px] text-muted-foreground mb-1">{f.label}{f.required && <span className="text-destructive"> *</span>}</span>
                <select className={`${inputCls} w-full ${f.required && !fieldToCol[f.key] ? "ring-1 ring-destructive/60" : ""}`} value={fieldToCol[f.key] ?? ""} onChange={(e) => setField(f.key, e.target.value)}>
                  <option value="">{t("— bỏ qua —", "— skip —")}</option>
                  {(up.batch.columns ?? []).map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            ))}
          </div>

          {up.sample.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] text-muted-foreground mb-1">{t("Dữ liệu đọc được (vài dòng đầu)", "Parsed data (first rows)")}</div>
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="text-xs w-full">
                  <thead className="bg-muted/40"><tr>{(up.batch.columns ?? []).map((c) => <th key={c} className="px-2 py-1.5 text-left font-medium whitespace-nowrap">{c}{mapping[c] && <span className="ml-1 text-primary">→</span>}</th>)}</tr></thead>
                  <tbody>{up.sample.map((r, i) => <tr key={i} className="border-t border-border">{(up.batch.columns ?? []).map((c) => <td key={c} className="px-2 py-1 whitespace-nowrap max-w-[220px] truncate" title={r[c]}>{r[c]}</td>)}</tr>)}</tbody>
                </table>
              </div>
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={updateExisting} onChange={(e) => { setUpdateExisting(e.target.checked); setPreview(null); }} />
              {t("Cập nhật khách hàng đã có (khớp theo MST → mã KH → tên)", "Update existing customers (match by tax code → ID → name)")}</label>
            {isAdmin && target === "customers" && (
              <label className="flex items-center gap-2 text-xs">{t("CB phụ trách mặc định:", "Default RM:")}
                <input list="imp-rm" className={`${inputCls} w-44`} value={defaultRm} onChange={(e) => setDefaultRm(e.target.value)} placeholder={t("(theo file / người nhập)", "(from file / importer)")} />
                <datalist id="imp-rm">{(meta?.rm_names ?? []).map((n) => <option key={n} value={n} />)}</datalist>
              </label>
            )}
            <div className="flex-1" />
            <Btn disabled={missingReq.length > 0 || prev.isPending} onClick={() => prev.mutate()}>{prev.isPending ? t("Đang kiểm tra…", "Checking…") : t("Xem trước kết quả", "Preview result")}</Btn>
          </div>
          {missingReq.length > 0 && <div className="text-xs text-destructive mt-2">{t("Cần ánh xạ: ", "Map required: ")}{missingReq.map((f) => f.label).join(", ")}</div>}
          <div className="mt-2"><ErrBox error={prev.error} /></div>
        </Card>
      )}

      {up && preview && (
        <Card title={t("Bước 3 · Xem trước & xác nhận", "Step 3 · Preview & confirm")}>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Stat label={t("Thêm mới", "Create")} value={preview.stats.create} tone="success" />
            <Stat label={t("Cập nhật", "Update")} value={preview.stats.update} tone="primary" />
            <Stat label={t("Bỏ qua", "Skip")} value={preview.stats.skip} />
            <Stat label={t("Lỗi", "Errors")} value={preview.stats.error} tone={preview.stats.error ? "destructive" : undefined} />
            <Stat label={t("Cảnh báo", "Warnings")} value={preview.stats.warn} tone={preview.stats.warn ? "warning" : undefined} />
          </div>
          {preview.unmapped.length > 0 && <div className="text-xs text-muted-foreground mt-3">{t("Cột chưa được dùng: ", "Unused columns: ")}{preview.unmapped.join(", ")}</div>}
          {preview.problems.length > 0 && (
            <div className="mt-3 rounded-lg border border-border overflow-hidden">
              <div className="text-[11px] px-3 py-1.5 bg-muted/40 text-muted-foreground">{t("Dòng có vấn đề (lỗi sẽ không được nhập)", "Rows with problems (errors are not imported)")}</div>
              <div className="max-h-56 overflow-y-auto divide-y divide-border">
                {preview.problems.map((p) => (
                  <div key={p.row} className="px-3 py-1.5 text-xs flex gap-2">
                    {p.errors.length ? <XCircle className="w-3.5 h-3.5 text-destructive mt-0.5 shrink-0" /> : <AlertTriangle className="w-3.5 h-3.5 text-warning mt-0.5 shrink-0" />}
                    <div><span className="text-muted-foreground">{t("Dòng", "Row")} {p.row}</span> · <span className="font-medium">{p.name || "—"}</span> · {[...p.errors, ...p.warnings].join("; ")}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {preview.ok_sample.length > 0 && (
            <div className="mt-3 text-xs text-muted-foreground">{t("Ví dụ dòng hợp lệ: ", "Valid examples: ")}{preview.ok_sample.slice(0, 4).map((r) => `${r.name} (${r.action === "create" ? t("mới", "new") : t("cập nhật", "update")})`).join(" · ")}</div>
          )}
          <div className="mt-4 flex items-center gap-3 justify-end">
            {up.requires_approval && <span className="text-xs text-warning">{t("Tài khoản nhân viên: lô này sẽ chờ quản lý duyệt trước khi ghi.", "Staff account: this batch needs admin approval before it is applied.")}</span>}
            <Btn kind="primary" disabled={commit.isPending || preview.stats.create + preview.stats.update === 0} onClick={() => commit.mutate()}>
              <Check className="w-3.5 h-3.5" /> {commit.isPending ? t("Đang xử lý…", "Working…") : up.requires_approval ? t("Gửi duyệt", "Submit for approval") : t("Xác nhận nhập", "Confirm import")}
            </Btn>
          </div>
          <div className="mt-2"><ErrBox error={commit.error} /></div>
        </Card>
      )}

      <Card title={t("Lịch sử import", "Import history")} right={batches.data && batches.data.pending > 0 && isAdmin ? <Pill tone="warning">{batches.data.pending} {t("lô chờ duyệt", "awaiting approval")}</Pill> : undefined}>
        {batches.isLoading ? <Spinner /> : (batches.data?.items ?? []).length === 0 ? (
          <div className="text-sm text-muted-foreground py-6 text-center">{t("Chưa có lô import nào.", "No imports yet.")}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-left text-muted-foreground border-b border-border">
                <th className="py-2 pr-3 font-medium">{t("Thời gian", "Time")}</th><th className="pr-3 font-medium">File</th><th className="pr-3 font-medium">{t("Loại", "Type")}</th>
                <th className="pr-3 font-medium">{t("Người nhập", "By")}</th><th className="pr-3 font-medium">{t("Trạng thái", "Status")}</th><th className="pr-3 font-medium">{t("Kết quả", "Result")}</th><th />
              </tr></thead>
              <tbody>
                {batches.data!.items.map((b) => (
                  <tr key={b.id} className="border-b border-border/60 hover:bg-muted/20">
                    <td className="py-2 pr-3 whitespace-nowrap">{fmtDateTime(b.created_at)}</td>
                    <td className="pr-3 max-w-[220px] truncate" title={b.filename}>{b.filename} <span className="text-muted-foreground">· {METHOD_LABEL[b.method ?? ""] ?? b.method}</span></td>
                    <td className="pr-3 whitespace-nowrap">{b.target === "monthly" ? t("Dòng tiền", "Cash-flow") : t("Khách hàng", "Customers")}</td>
                    <td className="pr-3 whitespace-nowrap">{b.created_by}</td>
                    <td className="pr-3"><Pill tone={STATUS_TONE[b.status] ?? "muted"}>{b.status}</Pill></td>
                    <td className="pr-3 text-muted-foreground">
                      {b.status === "Đã nhập" ? t(`+${b.summary?.created ?? 0} mới, ${b.summary?.updated ?? 0} cập nhật`, `+${b.summary?.created ?? 0} new, ${b.summary?.updated ?? 0} updated`) : `${b.row_count} ${t("dòng", "rows")}`}
                      {b.note ? <span title={b.note}> · “{b.note.slice(0, 30)}”</span> : null}
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <div className="inline-flex gap-1">
                        <Btn onClick={() => setDetail(b.id)}>{t("Xem", "View")}</Btn>
                        {isAdmin && b.status === "Chờ duyệt" && <>
                          <Btn kind="primary" disabled={approve.isPending} onClick={() => approve.mutate(b.id)}><Check className="w-3.5 h-3.5" /> {t("Duyệt", "Approve")}</Btn>
                          <Btn kind="danger" onClick={() => setRejecting(b)}><X className="w-3.5 h-3.5" /></Btn>
                        </>}
                        {(b.status === "Xem trước" || (b.status === "Chờ duyệt" && isAdmin)) && <Btn title={t("Hủy lô", "Cancel batch")} onClick={() => cancel.mutate(b.id)}><Trash2 className="w-3.5 h-3.5" /></Btn>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-2"><ErrBox error={approve.error ?? cancel.error} /></div>
      </Card>

      {rejecting && (
        <Modal title={t("Từ chối lô import", "Reject import batch")} onClose={() => setRejecting(null)}
          footer={<><ErrBox error={reject.error} /><Btn onClick={() => setRejecting(null)}>{t("Hủy", "Cancel")}</Btn><Btn kind="danger" disabled={reject.isPending} onClick={() => reject.mutate({ id: rejecting.id, note: rejNote })}>{t("Từ chối", "Reject")}</Btn></>}>
          <p className="text-xs text-muted-foreground mb-2">{rejecting.filename} — {rejecting.created_by}</p>
          <textarea className={`${inputCls} w-full h-24`} placeholder={t("Lý do (nhân viên sẽ thấy)", "Reason (visible to the staff member)")} value={rejNote} onChange={(e) => setRejNote(e.target.value)} />
        </Modal>
      )}
      {detail !== null && <BatchDetail id={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

function BatchDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({ queryKey: ["corp", "import", "detail", id], queryFn: () => corpX.importDetail(id) });
  const cols = data?.batch.columns ?? Object.keys(data?.sample?.[0] ?? {});
  return (
    <Modal wide title={data ? `${data.batch.filename}` : t("Chi tiết lô import", "Import batch")} onClose={onClose}>
      {isLoading && <Spinner />}
      <ErrBox error={error} />
      {data && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 text-xs">
            <Pill tone={STATUS_TONE[data.batch.status] ?? "muted"}>{data.batch.status}</Pill>
            <span className="text-muted-foreground">{t("Người nhập", "By")}: {data.batch.created_by} · {fmtDateTime(data.batch.created_at)}</span>
            {data.batch.reviewed_by && <span className="text-muted-foreground">{t("Duyệt bởi", "Reviewed by")}: {data.batch.reviewed_by} · {fmtDateTime(data.batch.reviewed_at)}</span>}
          </div>
          {data.batch.note && <div className="text-xs bg-muted/40 rounded-lg px-3 py-2">{data.batch.note}</div>}
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="text-xs w-full">
              <thead className="bg-muted/40"><tr>{cols.map((c) => <th key={c} className="px-2 py-1.5 text-left font-medium whitespace-nowrap">{c}</th>)}</tr></thead>
              <tbody>{data.sample.map((r, i) => <tr key={i} className="border-t border-border">{cols.map((c) => <td key={c} className="px-2 py-1 whitespace-nowrap max-w-[220px] truncate">{r[c]}</td>)}</tr>)}</tbody>
            </table>
          </div>
          <div className="text-[11px] text-muted-foreground">{t("Hiển thị tối đa vài chục dòng đầu.", "Showing the first rows only.")}</div>
        </div>
      )}
    </Modal>
  );
}
