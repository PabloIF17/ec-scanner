import { useScans } from '../api/hooks/useScans'
import { useTriggerDiscovery, useTriggerAssessment } from '../api/hooks/useDashboard'
import { useQueryClient } from '@tanstack/react-query'
import { Play, Search } from 'lucide-react'
import { useState } from 'react'

export default function ScansPage() {
  const { data: scans, isLoading } = useScans()
  const triggerDiscovery = useTriggerDiscovery()
  const triggerAssessment = useTriggerAssessment()
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string | null>(null)

  const handleDiscovery = async () => {
    await triggerDiscovery.mutateAsync()
    setMessage('Discovery scan queued successfully')
    queryClient.invalidateQueries({ queryKey: ['scans'] })
  }

  const handleAssessment = async () => {
    await triggerAssessment.mutateAsync()
    setMessage('Assessment scan queued for all pending sites')
    queryClient.invalidateQueries({ queryKey: ['scans'] })
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Scan Jobs</h1>
        <div className="flex gap-3">
          <button
            onClick={handleDiscovery}
            disabled={triggerDiscovery.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg disabled:opacity-50"
          >
            <Search size={14} />
            Discovery Scan
          </button>
          <button
            onClick={handleAssessment}
            disabled={triggerAssessment.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg disabled:opacity-50"
          >
            <Play size={14} />
            Assess All Pending
          </button>
        </div>
      </div>

      {message && (
        <div className="mb-6 px-4 py-3 bg-green-900/40 border border-green-700 rounded-lg text-green-300 text-sm">
          {message}
        </div>
      )}

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-800">
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Progress</th>
              <th className="px-4 py-3">Task ID</th>
              <th className="px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">Loading...</td>
              </tr>
            ) : !scans?.length ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  No scan jobs yet.
                </td>
              </tr>
            ) : (
              scans.map((scan) => (
                <tr key={scan.id} className="hover:bg-gray-800/50">
                  <td className="px-4 py-3 text-gray-300 capitalize">{scan.job_type}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      scan.status === 'complete' ? 'bg-green-900/60 text-green-300' :
                      scan.status === 'running' ? 'bg-blue-900/60 text-blue-300 animate-pulse' :
                      scan.status === 'failed' ? 'bg-red-900/60 text-red-300' :
                      'bg-gray-800 text-gray-400'
                    }`}>
                      {scan.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {scan.sites_total > 0
                      ? `${scan.sites_processed} / ${scan.sites_total}`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                    {scan.celery_task_id ? scan.celery_task_id.slice(0, 16) + '…' : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {new Date(scan.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
