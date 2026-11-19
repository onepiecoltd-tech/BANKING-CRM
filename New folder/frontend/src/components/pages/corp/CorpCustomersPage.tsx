import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Search, Plus, FileUp, UserCheck } from "lucide-react";
import { corp } from "@/lib/corpApi";
import { t, fmtBn } from "@/lib/i18n";
import { PageHeader, TierBadge, FlagBadge, Select, Pill, useMeta, productName } from "./shared";
import { useAuth } from "@/lib/auth";
import { NO_RM } from "@/lib/corpApiExt";
import { AssignDialog, type AssignSelection } from "./AssignDialog";
import { CustomerDrawer } from "./CustomerDrawer";
import { CustomerFormDialog } from "./CustomerForm";
import { Btn } from "./shared";
import { Link } from "@tanstack/react-router";

const SHOW = 60;

export function CorpCustomersPage({ openId }: { openId?: string }) {
  const nav = useNavigate();
  const { data: meta } = useMeta();
  const { isAdmin } = useAuth();
  const [f, setF] = useState({ q: "", ownership: "", country: "", industry: "", province: "", tier: "", product: "", risk: "", lifecycle: "", rm: "", sort: "priority" });
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [allMode, setAllMode] = useState(false);       // chọn toàn bộ kết quả theo bộ lọc (kể cả phần chưa tải)
  const [assigning, setAssigning] = useState<AssignSelection | null>(null);
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(SHOW);
  const [adding, setAdding] = useState(false);

  useEffect(() => { const h = setTimeout(() => setF((p) => ({ ...p, q })), 250); return () => clearTimeout(h); }, [q]);
  useEffect(() => { setShown(SHOW); setSel(new Set()); setAllMode(false); }, [f]);

  const { data, isLoading } = useQuery({
    queryKey: ["corp", "customers", f],
    queryFn: () => corp.customers({ ...f, limit: 500 }),
    staleTime: 30_000,
  });
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));
  const items = data?.items ?? [];
  const visible = items.slice(0, shown);
  const allVisibleSelected = visible.length > 0 && visible.every((c) => sel.has(c.customer_id));
  const toggleAll = () => { setAllMode(false); setSel(allVisibleSelected ? new Set() : new Set(visible.map((c) => c.customer_id))); };
  const toggleOne = (id: string) => { setAllMode(false); setSel((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; }); };
  const activeFilters = Object.fromEntries(Object.entries(f).filter(([k, v]) => v && k !== "sort")) as Record<string, string>;
  const picked = allMode ? (data?.total ?? 0) : sel.size;
  const colSpan = isAdmin ? 10 : 8;

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Khách hàng doanh nghiệp", "Corporate customers")}
        subtitle={t("Lọc theo loại hình, ngành, địa bàn, cơ hội sản phẩm và cảnh báo. Bấm vào dòng để xem hồ sơ & soạn tin.", "Filter by ownership, industry, location, product opportunity and alerts. Click a row for the profile and drafts.")}
        right={
          <div className="flex gap-2">
            <Link to="/corp/import"><Btn><FileUp className="w-3.5 h-3.5" /> {t("Import Excel/PDF", "Import Excel/PDF")}</Btn></Link>
            <Btn kind="primary" onClick={() => setAdding(true)}><Plus className="w-3.5 h-3.5" /> {t("Thêm khách hàng", "Add customer")}</Btn>
          </div>
        }
      />

      <div className="glass rounded-xl p-4 shadow-card flex flex-wrap gap-2 items-center">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("Tên DN, mã số thuế, mã KH…", "Name, tax code, ID…")}
            className="bg-input/60 border border-border rounded-lg pl-8 pr-3 py-2 text-sm w-60 focus:outline-none focus:ring-2 focus:ring-ring/40" />
        </div>
        <Select value={f.ownership} onChange={set("ownership")} placeholder={t("Loại hình", "Ownership")} options={[{ value: "FDI", label: "FDI" }, { value: "Nội địa", label: t("Nội địa", "Domestic") }]} />
        <Select value={f.country} onChange={set("country")} placeholder={t("Quốc gia đầu tư", "Investor country")} options={(meta?.countries ?? []).map((x) => ({ value: x, label: x }))} />
        <Select value={f.industry} onChange={set("industry")} placeholder={t("Ngành", "Industry")} options={(meta?.industries ?? []).map((x) => ({ value: x, label: x }))} />
        <Select value={f.province} onChange={set("province")} placeholder={t("Tỉnh/TP", "Province")} options={(meta?.provinces ?? []).map((x) => ({ value: x, label: x }))} />
        <Select value={f.tier} onChange={set("tier")} placeholder={t("Hạng", "Tier")} options={["A", "B", "C"].map((x) => ({ value: x, label: `${t("Hạng", "Tier")} ${x}` }))} />
        <Select value={f.product} onChange={set("product")} placeholder={t("Cơ hội sản phẩm", "Product opportunity")} options={(meta?.products ?? []).map((p) => ({ value: p.code, label: productName(meta, p.code) }))} />
        <Select value={f.risk} onChange={set("risk")} placeholder={t("Cảnh báo", "Alert")} options={[
          { value: "HET_HAN_MUC", label: t("Hạn mức sắp hết hạn", "Limit expiring") }, { value: "DOANH_SO_GIAM", label: t("Doanh số giảm", "Inflow decline") },
          { value: "NHOM_NO", label: t("Nợ nhóm ≥ 2", "Debt group ≥ 2") }, { value: "SU_DUNG_CAO", label: t("Sử dụng hạn mức cao", "High utilisation") }, { value: "CASA_GIAM", label: t("CASA giảm", "CASA decline") }]} />
        <Select value={f.lifecycle} onChange={set("lifecycle")} placeholder={t("Loại KH", "Lifecycle")} options={(meta?.lifecycles ?? []).map((x) => ({ value: x.code, label: x.name }))} />
        {isAdmin && <Select value={f.rm} onChange={set("rm")} placeholder={t("CBBH phụ trách", "RM")} options={[{ value: NO_RM, label: t("(Chưa phân công)", "(Unassigned)") }, ...(meta?.rm_names ?? []).map((x) => ({ value: x, label: x }))]} />}
        <Select value={f.sort} onChange={(v) => set("sort")(v || "priority")} placeholder={t("Sắp xếp", "Sort")} options={[
          { value: "priority", label: t("Điểm ưu tiên", "Priority score") }, { value: "revenue", label: t("Doanh thu", "Revenue") }, { value: "loan", label: t("Dư nợ", "Loans") }, { value: "name", label: t("Tên", "Name") }]} />
        <span className="ml-auto text-xs text-muted-foreground">{data ? `${data.total} ${t("doanh nghiệp", "companies")}` : ""}</span>
      </div>

      {isAdmin && picked > 0 && (
        <div className="glass rounded-xl px-4 py-2.5 shadow-card flex flex-wrap items-center gap-3 border border-primary/30">
          <span className="text-sm font-medium">{t(`Đã chọn ${picked} khách hàng`, `${picked} selected`)}</span>
          {!allMode && allVisibleSelected && (data?.total ?? 0) > sel.size && (
            <button className="text-xs text-primary underline" onClick={() => setAllMode(true)}>{t(`Chọn cả ${data?.total} khách hàng khớp bộ lọc`, `Select all ${data?.total} matching`)}</button>
          )}
          <Btn kind="primary" onClick={() => setAssigning(allMode
            ? { filters: activeFilters, label: t(`Toàn bộ ${data?.total} khách hàng khớp bộ lọc hiện tại`, `All ${data?.total} customers matching the current filters`) }
            : { ids: [...sel], label: t(`${sel.size} khách hàng đã chọn`, `${sel.size} selected customers`) })}>
            <UserCheck className="w-3.5 h-3.5" /> {t("Gán cho CBBH…", "Assign to RM…")}
          </Btn>
          <button className="text-xs text-muted-foreground hover:text-foreground" onClick={() => { setSel(new Set()); setAllMode(false); }}>{t("Bỏ chọn", "Clear")}</button>
        </div>
      )}

      <div className="glass rounded-xl shadow-card overflow-x-auto">
        <table className={`w-full text-sm ${isAdmin ? "min-w-[1180px]" : ""}`}>
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-muted-foreground border-b border-border">
              {isAdmin && <th className="pl-4 py-3 w-8"><input type="checkbox" checked={allVisibleSelected} onChange={toggleAll} aria-label={t("Chọn tất cả đang hiển thị", "Select all shown")} /></th>}
              <th className="px-4 py-3">{t("Doanh nghiệp", "Company")}</th>
              <th className="px-3 py-3">{t("Loại hình / Ngành", "Type / Industry")}</th>
              <th className="px-3 py-3 text-right">{t("Doanh thu", "Revenue")}</th>
              <th className="px-3 py-3 text-right">{t("Dư nợ", "Loans")}</th>
              <th className="px-3 py-3 text-right">CASA</th>
              {isAdmin && <th className="px-3 py-3">CBBH</th>}
              <th className="px-3 py-3">{t("Cảnh báo", "Alerts")}</th>
              <th className="px-3 py-3">{t("Cơ hội hàng đầu", "Top opportunity")}</th>
              <th className="px-3 py-3 text-right">{t("Ưu tiên", "Priority")}</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={colSpan} className="px-4 py-8 text-center text-muted-foreground">{t("Đang tải…", "Loading…")}</td></tr>}
            {!isLoading && items.length === 0 && <tr><td colSpan={colSpan} className="px-4 py-8 text-center text-muted-foreground">{t("Không có doanh nghiệp phù hợp.", "No matching companies.")}</td></tr>}
            {visible.map((c) => (
              <tr key={c.customer_id} onClick={() => nav({ to: "/corp/customers", search: { open: c.customer_id } })} className="border-b border-border/50 hover:bg-muted/30 cursor-pointer transition">
                {isAdmin && <td className="pl-4 py-3 w-8" onClick={(e) => e.stopPropagation()}><input type="checkbox" checked={allMode || sel.has(c.customer_id)} onChange={() => toggleOne(c.customer_id)} aria-label={c.name} /></td>}
                <td className="px-4 py-3 max-w-[260px]">
                  <div className="flex items-center gap-2"><TierBadge tier={c.tier} /><span className="font-medium truncate">{c.name}</span></div>
                  <div className="text-[11px] text-muted-foreground mt-0.5 truncate">{c.name_zh ? `${c.name_zh} · ` : ""}{c.province}{c.industrial_zone ? ` · ${c.industrial_zone}` : ""}</div>
                </td>
                <td className="px-3 py-3 text-xs"><div>{c.ownership}{c.investor_country ? ` · ${c.investor_country}` : ""}</div><div className="text-muted-foreground">{c.industry}</div></td>
                <td className="px-3 py-3 text-right tabular-nums">{fmtBn(c.annual_revenue_bn, 0)}</td>
                <td className="px-3 py-3 text-right tabular-nums">{fmtBn(c.loan_outstanding_bn, 0)}</td>
                <td className="px-3 py-3 text-right tabular-nums">{fmtBn(c.casa_balance_bn, 0)}</td>
                {isAdmin && <td className="px-3 py-3 text-xs whitespace-nowrap">{c.rm_name || <Pill tone="warning">{t("chưa gán", "unassigned")}</Pill>}</td>}
                <td className="px-3 py-3"><div className="flex flex-wrap gap-1 max-w-[200px]">{c.risk_flags.slice(0, 2).map((x) => <FlagBadge key={x.code} severity={x.severity} text={x.text} />)}</div></td>
                <td className="px-3 py-3 text-xs max-w-[220px]">{c.top_opportunities[0] ? <><div className="truncate">{productName(meta, c.top_opportunities[0].product)}</div><div className="text-muted-foreground">{t("Điểm", "Score")} {c.top_opportunities[0].score}</div></> : <span className="text-muted-foreground">—</span>}</td>
                <td className="px-3 py-3 text-right font-semibold tabular-nums">{c.priority_score.toFixed(0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length > shown && (
          <div className="p-3 text-center border-t border-border">
            <button onClick={() => setShown((s) => s + SHOW)} className="text-xs px-3 py-1.5 rounded-lg border border-border hover:bg-muted/50">{t("Hiện thêm", "Show more")} ({items.length - shown})</button>
          </div>
        )}
      </div>

      {adding && <CustomerFormDialog onClose={() => setAdding(false)} onSaved={(id) => { setAdding(false); nav({ to: "/corp/customers", search: { open: id } }); }} />}
      {assigning && <AssignDialog selection={assigning} onClose={() => setAssigning(null)} onDone={() => { setSel(new Set()); setAllMode(false); }} />}
      {openId && <CustomerDrawer id={openId} onClose={() => nav({ to: "/corp/customers", search: {} })} />}
    </div>
  );
}
