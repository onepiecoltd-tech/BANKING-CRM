import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { corpX, type CustomerForm } from "@/lib/corpApiExt";
import { useAuth } from "@/lib/auth";
import { t } from "@/lib/i18n";
import { Modal, Btn, ErrBox, inputCls, useMeta, productName } from "./shared";

const EMPTY: CustomerForm = {
  name: "", name_zh: "", tax_code: "", ownership: "Nội địa", investor_country: "", industry: "", province: "", industrial_zone: "", employees: 0, annual_revenue_bn: 0,
  total_assets_bn: 0, equity_bn: 0, export_usd_m: 0, import_usd_m: 0, fx_exposure_usd_m: 0, casa_balance_bn: 0, deposit_bn: 0, loan_outstanding_bn: 0, credit_limit_bn: 0,
  limit_expiry: "", debt_group: 1, relationship_years: 0, products_held: [], rm_name: "", contact_name: "", contact_name_zh: "", contact_title: "", contact_phone: "",
  contact_email: "", preferred_language: "vi",
};

const NUM = (v: string) => (v === "" ? 0 : Number(v));

function F({ label, children, span = 1 }: { label: string; children: React.ReactNode; span?: 1 | 2 | 3 }) {
  return (
    <label className={`block ${span === 2 ? "col-span-2" : span === 3 ? "col-span-3" : ""}`}>
      <span className="block text-[11px] text-muted-foreground mb-1">{label}</span>
      {children}
    </label>
  );
}

export function CustomerFormDialog({ initial, id, onClose, onSaved }: { initial?: Record<string, any>; id?: string; onClose: () => void; onSaved: (id: string) => void }) {
  const qc = useQueryClient();
  const { isAdmin } = useAuth();
  const { data: meta } = useMeta();
  const [f, setF] = useState<CustomerForm>(() => {
    if (!initial) return { ...EMPTY };
    const o: any = { ...EMPTY };
    for (const k of Object.keys(EMPTY)) if (initial[k] !== undefined && initial[k] !== null) o[k] = initial[k];
    return o;
  });
  const set = <K extends keyof CustomerForm>(k: K, v: CustomerForm[K]) => setF((p) => ({ ...p, [k]: v }));
  const m = useMutation({
    mutationFn: () => {
      const body: CustomerForm = { ...f, tax_code: f.tax_code || null, limit_expiry: f.limit_expiry || null, name_zh: f.name_zh || null, investor_country: f.ownership === "FDI" ? f.investor_country || null : null,
        industrial_zone: f.industrial_zone || null, contact_name: f.contact_name || null, contact_name_zh: f.contact_name_zh || null, contact_title: f.contact_title || null,
        contact_phone: f.contact_phone || null, contact_email: f.contact_email || null, rm_name: isAdmin ? f.rm_name || null : null };
      return id ? corpX.updateCustomer(id, body).then(() => ({ customer_id: id })) : corpX.createCustomer(body);
    },
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["corp"] }); onSaved(r.customer_id); },
  });
  const num = (k: keyof CustomerForm, step = "any") => (
    <input type="number" min={0} step={step} className={`${inputCls} w-full`} value={(f[k] as number) || ""} onChange={(e) => set(k, NUM(e.target.value) as never)} placeholder="0" />
  );
  const txt = (k: keyof CustomerForm, ph?: string) => (
    <input className={`${inputCls} w-full`} value={(f[k] as string) ?? ""} onChange={(e) => set(k, e.target.value as never)} placeholder={ph} />
  );
  const togglePro = (c: string) => set("products_held", f.products_held.includes(c) ? f.products_held.filter((x) => x !== c) : [...f.products_held, c]);
  const ok = f.name.trim().length >= 2;

  return (
    <Modal wide title={id ? t("Sửa thông tin khách hàng", "Edit customer") : t("Thêm khách hàng doanh nghiệp", "Add corporate customer")} onClose={onClose}
      footer={<>
        <ErrBox error={m.error} />
        <Btn onClick={onClose}>{t("Hủy", "Cancel")}</Btn>
        <Btn kind="primary" disabled={!ok || m.isPending} onClick={() => m.mutate()}>{m.isPending ? t("Đang lưu…", "Saving…") : t("Lưu", "Save")}</Btn>
      </>}>
      <div className="space-y-5">
        <section>
          <div className="text-xs font-semibold mb-2">{t("Thông tin chung", "General")}</div>
          <div className="grid grid-cols-3 gap-3">
            <F label={t("Tên doanh nghiệp *", "Company name *")} span={2}>{txt("name")}</F>
            <F label={t("Mã số thuế (10 số)", "Tax code (10 digits)")}>{txt("tax_code", "0312345678")}</F>
            <F label={t("Tên tiếng Trung", "Chinese name")}>{txt("name_zh")}</F>
            <F label={t("Loại hình", "Ownership")}>
              <select className={`${inputCls} w-full`} value={f.ownership} onChange={(e) => set("ownership", e.target.value)}><option value="Nội địa">{t("Nội địa", "Domestic")}</option><option value="FDI">FDI</option></select>
            </F>
            <F label={t("Quốc gia nhà đầu tư", "Investor country")}>
              <input list="dl-country" disabled={f.ownership !== "FDI"} className={`${inputCls} w-full disabled:opacity-40`} value={f.investor_country ?? ""} onChange={(e) => set("investor_country", e.target.value)} />
              <datalist id="dl-country">{(meta?.countries ?? []).map((c) => <option key={c} value={c} />)}</datalist>
            </F>
            <F label={t("Ngành nghề", "Industry")}>
              <input list="dl-industry" className={`${inputCls} w-full`} value={f.industry} onChange={(e) => set("industry", e.target.value)} />
              <datalist id="dl-industry">{(meta?.industries ?? []).map((c) => <option key={c} value={c} />)}</datalist>
            </F>
            <F label={t("Tỉnh/Thành phố", "Province")}>
              <input list="dl-prov" className={`${inputCls} w-full`} value={f.province} onChange={(e) => set("province", e.target.value)} />
              <datalist id="dl-prov">{(meta?.provinces ?? []).map((c) => <option key={c} value={c} />)}</datalist>
            </F>
            <F label="KCN/KCX">{txt("industrial_zone")}</F>
            <F label={t("Số lao động", "Employees")}>{num("employees", "1")}</F>
            <F label={t("Số năm quan hệ", "Years with bank")}>{num("relationship_years", "1")}</F>
            {isAdmin && (
              <F label={t("Cán bộ phụ trách", "Relationship manager")}>
                <input list="dl-rm" className={`${inputCls} w-full`} value={f.rm_name ?? ""} onChange={(e) => set("rm_name", e.target.value)} placeholder={t("(mặc định: bạn)", "(default: you)")} />
                <datalist id="dl-rm">{(meta?.rm_names ?? []).map((c) => <option key={c} value={c} />)}</datalist>
              </F>
            )}
          </div>
        </section>
        <section>
          <div className="text-xs font-semibold mb-2">{t("Quy mô & ngoại thương", "Scale & trade")}</div>
          <div className="grid grid-cols-3 gap-3">
            <F label={t("Doanh thu năm (tỷ đồng)", "Annual revenue (VND bn)")}>{num("annual_revenue_bn")}</F>
            <F label={t("Tổng tài sản (tỷ đồng)", "Total assets (VND bn)")}>{num("total_assets_bn")}</F>
            <F label={t("Vốn chủ sở hữu (tỷ đồng)", "Equity (VND bn)")}>{num("equity_bn")}</F>
            <F label={t("Xuất khẩu (triệu USD/năm)", "Exports (USD m/yr)")}>{num("export_usd_m")}</F>
            <F label={t("Nhập khẩu (triệu USD/năm)", "Imports (USD m/yr)")}>{num("import_usd_m")}</F>
            <F label={t("Trạng thái ngoại tệ (triệu USD)", "FX exposure (USD m)")}>{num("fx_exposure_usd_m")}</F>
          </div>
        </section>
        <section>
          <div className="text-xs font-semibold mb-2">{t("Quan hệ tín dụng & tiền gửi", "Credit & deposits")}</div>
          <div className="grid grid-cols-3 gap-3">
            <F label={t("CASA bình quân (tỷ đồng)", "Avg CASA (VND bn)")}>{num("casa_balance_bn")}</F>
            <F label={t("Tiền gửi có kỳ hạn (tỷ đồng)", "Term deposits (VND bn)")}>{num("deposit_bn")}</F>
            <F label={t("Nhóm nợ", "Debt group")}>
              <select className={`${inputCls} w-full`} value={f.debt_group} onChange={(e) => set("debt_group", Number(e.target.value))}>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{t("Nhóm", "Group")} {n}</option>)}</select>
            </F>
            <F label={t("Dư nợ (tỷ đồng)", "Loan outstanding (VND bn)")}>{num("loan_outstanding_bn")}</F>
            <F label={t("Hạn mức tín dụng (tỷ đồng)", "Credit limit (VND bn)")}>{num("credit_limit_bn")}</F>
            <F label={t("Ngày hết hạn hạn mức", "Limit expiry")}>
              <input type="date" className={`${inputCls} w-full`} value={f.limit_expiry ?? ""} onChange={(e) => set("limit_expiry", e.target.value)} />
            </F>
          </div>
          <div className="mt-3">
            <span className="block text-[11px] text-muted-foreground mb-1.5">{t("Sản phẩm đang sử dụng", "Products in use")}</span>
            <div className="flex flex-wrap gap-1.5">
              {(meta?.products ?? []).map((p) => (
                <button key={p.code} type="button" onClick={() => togglePro(p.code)}
                  className={`text-[11px] px-2 py-1 rounded-lg border transition ${f.products_held.includes(p.code) ? "border-primary/60 bg-primary/15 text-foreground" : "border-border text-muted-foreground hover:bg-muted/50"}`}>
                  {productName(meta, p.code)}
                </button>
              ))}
            </div>
          </div>
        </section>
        <section>
          <div className="text-xs font-semibold mb-2">{t("Người liên hệ", "Contact")}</div>
          <div className="grid grid-cols-3 gap-3">
            <F label={t("Họ tên", "Name")}>{txt("contact_name")}</F>
            <F label={t("Tên tiếng Trung", "Chinese name")}>{txt("contact_name_zh")}</F>
            <F label={t("Chức danh", "Title")}>
              <select className={`${inputCls} w-full`} value={f.contact_title ?? ""} onChange={(e) => set("contact_title", e.target.value)}>
                <option value="">—</option><option value="GD">{t("Giám đốc", "General Director")}</option><option value="PGD">{t("Phó Giám đốc", "Deputy Director")}</option>
                <option value="KTT">{t("Kế toán trưởng", "Chief Accountant")}</option><option value="CFO">CFO</option>
              </select>
            </F>
            <F label={t("Số điện thoại", "Phone")}>{txt("contact_phone", "09xxxxxxxx")}</F>
            <F label="Email">{txt("contact_email")}</F>
            <F label={t("Ngôn ngữ ưu tiên", "Preferred language")}>
              <select className={`${inputCls} w-full`} value={f.preferred_language} onChange={(e) => set("preferred_language", e.target.value)}><option value="vi">Tiếng Việt</option><option value="zh">中文</option><option value="en">English</option></select>
            </F>
          </div>
        </section>
      </div>
    </Modal>
  );
}
