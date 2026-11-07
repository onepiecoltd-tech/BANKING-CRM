import { createFileRoute } from "@tanstack/react-router";
import { CorpReasoningPage } from "@/components/pages/corp/CorpReasoningPage";

export const Route = createFileRoute("/corp/reasoning")({ component: CorpReasoningPage });
