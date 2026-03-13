import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Play, RefreshCw } from 'lucide-react'
import { useDashboardOverview, useTriggerDiscovery, useTriggerAssessment } from '../api/hooks/useDashboard'
import StatCard from '../components/StatCard'
import SeverityBadge from '../components/SeverityBadge'
import { useQueryClient } from '@tanstack/react-query'

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#3b82f6',
  MINIMAL: '#6b7280',
}

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboardOverview()
  const triggerDiscovery = useTriggerDiscovery()
  const triggerAssessment = useTriggerAssessment()
  const queryClient = useQueryClient()
  const [lastAction, setLastAction] = useState<string | null>(null)

  if (isLoading) return <div className="p-8 text-gray-500">Loading...</div>
  if (error) return <div className="p-8 text-red-400">Failed to load dashboard.</div>
  if (!data) return null

  const severityChartData = Object.entries(data.by_severity).map(([severity, count]) => ({
    severity,
    count,
  }))

  const handleDiscovery = async () => {
    await triggerDiscovery.mutateAsync()
    setLastAction('Discovery scan queued')
    queryClient.invalidateQueries({ queryKey: ['scans'] })
  }

  const handleAssessment = async () => {
    await triggerAssessment.mutateAsync()
    setLastAction('Assessment scan queued for all pending sites')
    queryClient.invalidateQueries({ queryKey: ['scans'] })
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Pipeline Overview</h1>
          <p className="text-gray-500 text-sm mt-1">Experience Cloud Security Scanner</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleDiscovery}
            disabled={triggerDiscovery.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
          >
            <Play size={14} />
            Run Discovery
          </button>
          <button
            onClick={handleAssessment}
            disabled={triggerAssessment.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} />
            Assess Pending
          </button>
        </div>
      </div>

      {lastAction && (
        <div className="mb-6 px-4 py-3 bg-green-900/40 border border-green-700 rounded-lg text-green-300 text-sm">
          {lastAction}
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Sites" value={data.total_sites} />
        <StatCard label="Active Sites" value={data.active_sites} color="blue" />
        <StatCard label="Assessed" value={data.assessed_sites} color="green" />
        <StatCard label="Pending Assessment" value={data.pending_assessment} color="yellow" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Severity distribution chart */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">Findings by Severity</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={severityChartData}>
              <XAxis dataKey="severity" tick={{ fill: '#6b7280', fontSize: 11 }} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151' }}
                labelStyle={{ color: '#f3f4f6' }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {severityChartData.map((entry) => (
                  <Cell
                    key={entry.severity}
                    fill={SEVERITY_COLORS[entry.severity] ?? '#6b7280'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Severity stats */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">Risk Breakdown</h2>
          <div className="space-y-3">
            {Object.entries(data.by_severity).map(([severity, count]) => (
              <div key={severity} className="flex items-center justify-between">
                <SeverityBadge severity={severity} />
                <span className="text-white font-semibold">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent scans */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">Recent Scan Jobs</h2>
        {data.recent_scans.length === 0 ? (
          <p className="text-gray-600 text-sm">No scans yet. Run a discovery scan to get started.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-800">
                  <th className="pb-2 pr-4">Type</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Progress</th>
                  <th className="pb-2">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {data.recent_scans.map((scan) => (
                  <tr key={scan.id}>
                    <td className="py-2 pr-4 text-gray-300 capitalize">{scan.job_type}</td>
                    <td className="py-2 pr-4">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        scan.status === 'complete' ? 'bg-green-900 text-green-300' :
                        scan.status === 'running' ? 'bg-blue-900 text-blue-300' :
                        scan.status === 'failed' ? 'bg-red-900 text-red-300' :
                        'bg-gray-800 text-gray-400'
                      }`}>
                        {scan.status}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-gray-400">
                      {scan.sites_total > 0
                        ? `${scan.sites_processed}/${scan.sites_total}`
                        : '—'}
                    </td>
                    <td className="py-2 text-gray-500 text-xs">
                      {new Date(scan.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
