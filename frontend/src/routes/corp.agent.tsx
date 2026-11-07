import { createFileRoute } from "@tanstack/react-router";
import { CorpAgentPage } from "@/components/pages/corp/CorpAgentPage";

export const Route = createFileRoute("/corp/agent")({ component: CorpAgentPage });
