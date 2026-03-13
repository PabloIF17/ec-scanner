import { useQuery, useMutation } from '@tanstack/react-query'
import { apiClient, type DashboardOverview } from '../client'

export function useDashboardOverview() {
  return useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: async () => {
      const { data } = await apiClient.get<DashboardOverview>('/dashboard/overview')
      return data
    },
    refetchInterval: 30_000,
  })
}

export function useTriggerDiscovery() {
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post('/scans/discovery')
      return data
    },
  })
}

export function useTriggerAssessment(siteId?: string) {
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post('/scans/assessment', {
        job_type: 'assessment',
        site_id: siteId,
      })
      return data
    },
  })
}
