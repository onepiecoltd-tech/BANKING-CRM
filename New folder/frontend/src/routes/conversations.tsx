import { createFileRoute } from "@tanstack/react-router";
import { ConversationsPage } from "@/components/pages/ConversationsPage";
export const Route = createFileRoute("/conversations")({ component: ConversationsPage });
