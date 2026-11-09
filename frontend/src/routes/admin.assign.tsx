import { createFileRoute } from "@tanstack/react-router";
import { AssignPage } from "@/components/pages/admin/AssignPage";

export const Route = createFileRoute("/admin/assign")({ component: AssignPage });
