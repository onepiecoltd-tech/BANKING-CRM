import { createFileRoute } from "@tanstack/react-router";
import { CorpPipelinePage } from "@/components/pages/corp/CorpPipelinePage";

export const Route = createFileRoute("/corp/pipeline")({ component: CorpPipelinePage });
