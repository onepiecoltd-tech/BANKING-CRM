import { createFileRoute } from "@tanstack/react-router";
import { CorpSettingsPage } from "@/components/pages/corp/CorpSettingsPage";

export const Route = createFileRoute("/corp/settings")({ component: CorpSettingsPage });
