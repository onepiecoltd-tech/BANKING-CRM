import { createFileRoute } from "@tanstack/react-router";
import { CorpDashboardPage } from "@/components/pages/corp/CorpDashboardPage";

export const Route = createFileRoute("/corp/")({ component: CorpDashboardPage });
