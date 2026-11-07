import { createFileRoute } from "@tanstack/react-router";
import { CorpOutreachPage } from "@/components/pages/corp/CorpOutreachPage";

export const Route = createFileRoute("/corp/outreach")({ component: CorpOutreachPage });
