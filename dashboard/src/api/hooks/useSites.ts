import { useQuery } from '@tanstack/react-query'
import { apiClient, type Site, type SiteList, type Assessment } from '../client'

export function useSites(params: {
  page?: number
  size?: number
  severity?: string
  assessment_status?: string
} = {}) {
  return useQuery({
    queryKey: ['sites', params],
    queryFn: async () => {
      const { data } = await apiClient.get<SiteList>('/sites', { params })
      return data
    },
  })
}

export function useSite(id: string) {
  return useQuery({
    queryKey: ['sites', id],
    queryFn: async () => {
      const { data } = await apiClient.get<Site>(`/sites/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useSiteAssessments(siteId: string) {
  return useQuery({
    queryKey: ['sites', siteId, 'assessments'],
    queryFn: async () => {
      const { data } = await apiClient.get<Assessment[]>(`/sites/${siteId}/assessments`)
      return data
    },
    enabled: !!siteId,
  })
}
