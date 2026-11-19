import { createFileRoute } from "@tanstack/react-router";
import { CorpAnalyticsPage } from "@/components/pages/corp/CorpAnalyticsPage";

export const Route = createFileRoute("/corp/analytics")({ component: CorpAnalyticsPage });
