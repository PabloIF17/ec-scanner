import { useQuery } from '@tanstack/react-query'
import { apiClient, type ScanJob } from '../client'

interface ScanStatus {
  job_id: string
  celery_task_id: string | null
  status: string
  progress_pct: number
  phase: string | null
  sites_processed: number
  sites_total: number
  error_message: string | null
}

export function useScans(params: { page?: number; status?: string } = {}) {
  return useQuery({
    queryKey: ['scans', params],
    queryFn: async () => {
      const { data } = await apiClient.get<ScanJob[]>('/scans', { params })
      return data
    },
    refetchInterval: 10_000,
  })
}

export function useScanStatus(jobId: string | null) {
  return useQuery({
    queryKey: ['scans', jobId, 'status'],
    queryFn: async () => {
      const { data } = await apiClient.get<ScanStatus>(`/scans/${jobId}/status`)
      return data
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'running' || status === 'queued' ? 2000 : false
    },
  })
}
