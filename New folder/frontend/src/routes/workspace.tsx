import { createFileRoute } from "@tanstack/react-router";
import { WorkspacePage } from "@/components/pages/WorkspacePage";
export const Route = createFileRoute("/workspace")({ component: WorkspacePage });
