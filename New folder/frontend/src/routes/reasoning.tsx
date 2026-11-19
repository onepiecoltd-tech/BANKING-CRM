import { createFileRoute } from "@tanstack/react-router";
import { ReasoningPage } from "@/components/pages/ReasoningPage";
export const Route = createFileRoute("/reasoning")({ component: ReasoningPage });
