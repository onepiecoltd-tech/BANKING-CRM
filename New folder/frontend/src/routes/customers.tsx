import { createFileRoute } from "@tanstack/react-router";
import { CustomersPage } from "@/components/pages/CustomersPage";
export const Route = createFileRoute("/customers")({ component: CustomersPage });
