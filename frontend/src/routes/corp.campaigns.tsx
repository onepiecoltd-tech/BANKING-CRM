import { createFileRoute } from "@tanstack/react-router";
import { CorpCampaignsPage } from "@/components/pages/corp/CorpCampaignsPage";

export const Route = createFileRoute("/corp/campaigns")({
  validateSearch: (s: Record<string, unknown>): { open?: number } => {
    const n = Number(s.open);
    return { open: Number.isFinite(n) && n > 0 ? n : undefined };
  },
  component: function CorpCampaignsRoute() {
    const { open } = Route.useSearch();
    return <CorpCampaignsPage openId={open} />;
  },
});
