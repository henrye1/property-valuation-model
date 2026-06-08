import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/lib/auth'
import { PortfolioSummarySchema, PortfolioTimeseriesSchema } from '@/schemas/portfolio'

export function usePortfolioSummary() {
  const { api } = useAuth()
  return useQuery({
    queryKey: ['portfolio', 'summary'],
    queryFn: async () => PortfolioSummarySchema.parse(await api.get('/portfolio/summary')),
  })
}

export function usePortfolioTimeseries() {
  const { api } = useAuth()
  return useQuery({
    queryKey: ['portfolio', 'timeseries'],
    queryFn: async () => PortfolioTimeseriesSchema.parse(await api.get('/portfolio/timeseries')),
  })
}
