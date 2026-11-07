import { createFileRoute } from "@tanstack/react-router";
import { CorpImportPage } from "@/components/pages/corp/CorpImportPage";

export const Route = createFileRoute("/corp/import")({ component: CorpImportPage });
