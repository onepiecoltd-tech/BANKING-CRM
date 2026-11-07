import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { Building2, Landmark, Wallet, Globe2, Target, AlertTriangle } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell } from "recharts";
import { corp } from "@/lib/corpApi";
import { t, fmtBn, fmtNum } from "@/lib/i18n";
import { PageHeader, Card, COLORS, TierBadge, FlagBadge, FLAG_LABEL } from "./shared";

const tipStyle = { background: "#11151f", border: "1px solid #2a3142", borderRadius: 8, fontSize: 12 };

export function CorpDashboardPage() {
  const { data: k, isLoading } = useQuery({ queryKey: ["corp", "kpis"], queryFn: corp.kpis, staleTime: 60_000 });
  const { data: sig } = useQuery({ queryKey: ["corp", "signals"], queryFn: () => corp.signals(), staleTime: 60_000 });

  if (isLoading || !k) {
    return <div className="text-sm text-muted-foreground">{t("Đang tải dữ liệu…", "Loading…")}</div>;
  }

  const cards = [
    { label: t("Khách hàng doanh nghiệp", "Corporate customers"), value: fmtNum(k.total), sub: `${k.fdi} FDI · ${k.total - k.fdi} ${t("nội địa", "domestic")}`, icon: Building2, c: "primary" },
    { label: t("Dư nợ tín dụng", "Loans outstanding"), value: fmtBn(k.loans_bn, 0), sub: `${t("Hạng A", "Tier A")}: ${k.tier.A ?? 0} ${t("khách hàng", "customers")}`, icon: Landmark, c: "accent" },
    { label: t("CASA + tiền gửi", "CASA + deposits"), value: fmtBn(k.casa_bn + k.deposit_bn, 0), sub: `CASA ${fmtBn(k.casa_bn, 0)}`, icon: Wallet, c: "primary" },
    { label: t("Kim ngạch XNK", "Trade volume"), value: `${fmtNum(k.trade_usd_m, 0)} ${t("tr. USD", "USD m")}`, sub: t("Tổng danh mục / năm", "Portfolio / year"), icon: Globe2, c: "accent" },
    { label: t("Pipeline cơ hội", "Opportunity pipeline"), value: fmtBn(k.pipeline_value_bn, 0), sub: `${k.pipeline_count} ${t("cơ hội", "deals")} · ${t("có trọng số", "weighted")} ${fmtBn(k.pipeline_weighted_bn, 0)}`, icon: Target, c: "warning" },
    { label: t("Cảnh báo cần xử lý", "Alerts to handle"), value: fmtNum(Object.values(k.flags).reduce((a, b) => a + b, 0)), sub: `${k.flags.HET_HAN_MUC ?? 0} ${t("hạn mức sắp hết hạn", "limits expiring")}`, icon: AlertTriangle, c: "warning" },
  ];
  const tone = (c: string) => (c === "accent" ? "bg-accent/15 text-accent" : c === "warning" ? "bg-warning/15 text-warning" : "bg-primary/15 text-primary");

  const SHORT: Record<string, [string, string]> = {
    VAY_VLD: ["Vay vốn lưu động", "Working capital"], VAY_DT: ["Vay đầu tư", "Investment loan"], LC: ["L/C nhập khẩu", "Import L/C"],
    UPAS: ["UPAS L/C", "UPAS L/C"], BAO_LANH: ["Bảo lãnh", "Guarantee"], TTQT: ["Thanh toán quốc tế", "Intl payments"],
    NGOAI_TE: ["Ngoại tệ & phòng ngừa", "FX & hedging"], LUONG: ["Chi lương & thẻ", "Payroll & cards"],
    DONG_TIEN: ["Quản lý dòng tiền", "Cash management"], TIEN_GUI: ["Tiền gửi có kỳ hạn", "Term deposit"],
  };
  const crossData = k.crosssell.map((x) => ({ name: t(...(SHORT[x.code] ?? [x.name, x.name])), count: x.count }));
  const countryData = Object.entries(k.countries).map(([name, value]) => ({ name, value }));
  const indData = Object.entries(k.industries).slice(0, 8).map(([name, value]) => ({ name: name.slice(0, 18), value }));

  const panels: { key: keyof NonNullable<typeof sig>; title: string; code: string }[] = [
    { key: "limit_expiry", title: t("Hạn mức sắp hết hạn", "Limits expiring"), code: "HET_HAN_MUC" },
    { key: "inflow_drop", title: t("Doanh số qua tài khoản giảm", "Inflow decline"), code: "DOANH_SO_GIAM" },
    { key: "high_util", title: t("Sử dụng hạn mức cao", "High limit utilisation"), code: "SU_DUNG_CAO" },
    { key: "debt", title: t("Nợ nhóm ≥ 2", "Debt group ≥ 2"), code: "NHOM_NO" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Tổng quan Khách hàng Doanh nghiệp", "Corporate Customer Overview")}
        subtitle={t("Danh mục khách hàng doanh nghiệp, cơ hội bán chéo và cảnh báo cần xử lý hôm nay. (Dữ liệu mô phỏng)", "Corporate portfolio, cross-sell opportunities and alerts to handle today. (Simulated data)")}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {cards.map((c, i) => (
          <motion.div key={c.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }} className="glass rounded-xl p-5 shadow-card">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs text-muted-foreground">{c.label}</div>
                <div className="mt-2 text-2xl font-display font-semibold tracking-tight">{c.value}</div>
                <div className="mt-1 text-xs text-muted-foreground">{c.sub}</div>
              </div>
              <div className={`w-10 h-10 rounded-lg grid place-items-center ${tone(c.c)}`}><c.icon className="w-5 h-5" /></div>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card title={t("Cơ hội bán chéo theo sản phẩm (điểm ≥ 60)", "Cross-sell opportunities by product (score ≥ 60)")} className="xl:col-span-2">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={crossData} layout="vertical" margin={{ left: 10, right: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3142" horizontal={false} />
                <XAxis type="number" stroke="#8892a6" fontSize={11} />
                <YAxis type="category" dataKey="name" stroke="#8892a6" fontSize={11} width={150} />
                <Tooltip contentStyle={tipStyle} cursor={{ fill: "rgba(255,255,255,0.04)" }} formatter={(v) => [`${v} ${t("khách hàng", "customers")}`, ""]} />
                <Bar dataKey="count" fill="#5b8bff" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title={t("Quốc gia đầu tư / Nội địa", "Investor country / Domestic")}>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={countryData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2} isAnimationActive={false}>
                  {countryData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={tipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1">
            {countryData.map((d, i) => (
              <span key={d.name} className="text-[11px] text-muted-foreground flex items-center gap-1">
                <span className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />{d.name} ({d.value})
              </span>
            ))}
          </div>
        </Card>
      </div>

      <Card title={t("Phân bổ theo ngành (Top 8)", "By industry (top 8)")}>
        <div className="h-60">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={indData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3142" vertical={false} />
              <XAxis dataKey="name" stroke="#8892a6" fontSize={10} interval={0} angle={-15} textAnchor="end" height={50} />
              <YAxis stroke="#8892a6" fontSize={11} />
              <Tooltip contentStyle={tipStyle} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="value" fill="#34d399" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div>
        <h2 className="text-sm font-semibold mb-3">{t("Việc cần làm hôm nay", "Today's to-do")}</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {panels.map((p) => {
            const d = sig?.[p.key];
            return (
              <Card key={p.key} title={p.title} right={<span className="text-xs text-muted-foreground">{d?.count ?? 0} {t("khách hàng", "customers")}</span>}>
                <div className="space-y-1.5">
                  {(d?.items ?? []).slice(0, 5).map((r) => (
                    <Link key={r.customer_id} to="/corp/customers" search={{ open: r.customer_id }} className="flex items-center gap-2 text-xs py-1.5 px-2 rounded-lg hover:bg-muted/40 transition">
                      <TierBadge tier={r.tier} />
                      <span className="flex-1 truncate font-medium">{r.name}</span>
                      <FlagBadge severity={r.severity} text={r.text} />
                    </Link>
                  ))}
                  {!d?.items.length && <div className="text-xs text-muted-foreground">{t("Không có cảnh báo", "No alerts")}</div>}
                </div>
                <div className="mt-2 text-[10px] text-muted-foreground">{FLAG_LABEL[p.code]?.[0] && t(FLAG_LABEL[p.code][0], FLAG_LABEL[p.code][1])}</div>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
