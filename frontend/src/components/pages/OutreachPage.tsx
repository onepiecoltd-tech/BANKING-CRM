import { Link } from "@tanstack/react-router";
import { Rocket, Sparkles, Briefcase } from "lucide-react";
import { PageHeader } from "./DashboardPage";
import { t } from "@/lib/i18n";

/** Trung tâm tiếp cận (cá nhân). Trước đây hiển thị chiến dịch/số liệu mô phỏng cứng; nay chỉ dẫn tới công cụ chạy dữ liệu thật. */
export function OutreachPage() {
  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Outreach Center")}
        subtitle={t("AI-generated personalized WhatsApp campaigns with A/B testing, persuasion frameworks, and compliance suppression.")}
      />
      <div className="glass rounded-xl p-8 shadow-card text-center space-y-3">
        <div className="text-base font-semibold">{t("Chưa có chiến dịch nào", "No campaigns yet")}</div>
        <p className="text-sm text-muted-foreground max-w-xl mx-auto">
          {t("Màn hình này chỉ hiển thị chiến dịch thật. Hãy tạo chiến dịch ở Campaign Builder hoặc nhờ RM AI Workspace soạn tin; số liệu sẽ xuất hiện khi có khách hàng cá nhân và tin nhắn thật.",
            "This screen shows real campaigns only. Create one in Campaign Builder or ask the RM AI Workspace to draft messages; figures appear once real retail customers and messages exist.")}
        </p>
        <div className="flex items-center justify-center gap-2 flex-wrap pt-1">
          <Link to="/campaign" className="text-xs px-3 py-1.5 rounded-lg gradient-primary text-primary-foreground font-medium inline-flex items-center gap-1.5 hover:opacity-90">
            <Rocket className="w-3.5 h-3.5" /> Campaign Builder
          </Link>
          <Link to="/workspace" className="text-xs px-3 py-1.5 rounded-lg border border-border inline-flex items-center gap-1.5 hover:bg-muted/50">
            <Sparkles className="w-3.5 h-3.5" /> RM AI Workspace
          </Link>
          <Link to="/corp/outreach" className="text-xs px-3 py-1.5 rounded-lg border border-border inline-flex items-center gap-1.5 hover:bg-muted/50">
            <Briefcase className="w-3.5 h-3.5" /> {t("Tiếp cận khách hàng doanh nghiệp", "Corporate outreach")}
          </Link>
        </div>
      </div>
    </div>
  );
}
