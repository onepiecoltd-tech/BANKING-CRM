import { createFileRoute } from "@tanstack/react-router";
import { UsersPage } from "@/components/pages/admin/UsersPage";

export const Route = createFileRoute("/admin/users")({ component: UsersPage });
