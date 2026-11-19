import { createFileRoute } from "@tanstack/react-router";
import { CorpConversationsPage } from "@/components/pages/corp/CorpConversationsPage";

export const Route = createFileRoute("/corp/conversations")({
  validateSearch: (s: Record<string, unknown>): { customer?: string } => ({ customer: typeof s.customer === "string" ? s.customer : undefined }),
  component: function CorpConversationsRoute() {
    const { customer } = Route.useSearch();
    return <CorpConversationsPage customerId={customer} />;
  },
});
