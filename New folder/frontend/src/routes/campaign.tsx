import { createFileRoute } from '@tanstack/react-router'
import { CampaignPage } from '@/components/pages/CampaignPage'

export const Route = createFileRoute('/campaign')({
  component: CampaignPage,
})
