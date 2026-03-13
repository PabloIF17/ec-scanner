import axios from 'axios'

export const apiClient = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL as string) ?? '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

export interface Site {
  id: string
  domain: string
  cname_target: string | null
  discovery_source: string | null
  http_status: number | null
  is_active: boolean
  is_excluded: boolean
  assessment_status: string
  last_validated: string | null
  created_at: string
  updated_at: string
}

export interface Assessment {
  id: string
  site_id: string
  assessment_date: string
  risk_score: number | null
  severity: string | null
  checks: Record<string, unknown>
  remediation_summary: string[] | null
  scan_duration_seconds: number | null
  error_message: string | null
}

export interface ScanJob {
  id: string
  celery_task_id: string | null
  job_type: string
  status: string
  sites_processed: number
  sites_total: number
  error_message: string | null
  created_at: string
}

export interface DashboardOverview {
  total_sites: number
  active_sites: number
  assessed_sites: number
  pending_assessment: number
  by_severity: Record<string, number>
  recent_scans: ScanJob[]
}

export interface SiteList {
  items: Site[]
  total: number
  page: number
  size: number
}
