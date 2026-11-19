import { createFileRoute } from "@tanstack/react-router";
import { CorpCustomersPage } from "@/components/pages/corp/CorpCustomersPage";

export const Route = createFileRoute("/corp/customers")({
  validateSearch: (s: Record<string, unknown>): { open?: string } => ({
    open: typeof s.open === "string" ? s.open : undefined,
  }),
  component: function CorpCustomersRoute() {
    const { open } = Route.useSearch();
    return <CorpCustomersPage openId={open} />;
  },
});
