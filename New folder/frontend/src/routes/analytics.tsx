import { createFileRoute } from "@tanstack/react-router";
import { AnalyticsPage } from "@/components/pages/AnalyticsPage";
export const Route = createFileRoute("/analytics")({ component: AnalyticsPage });
