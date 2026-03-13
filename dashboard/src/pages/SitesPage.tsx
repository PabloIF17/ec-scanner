import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, ChevronLeft } from 'lucide-react'
import { useSites } from '../api/hooks/useSites'
import SeverityBadge from '../components/SeverityBadge'

const STATUS_OPTIONS = ['', 'pending', 'in_progress', 'complete', 'error']
const SEVERITY_OPTIONS = ['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'MINIMAL']

export default function SitesPage() {
  const [page, setPage] = useState(1)
  const [assessmentStatus, setAssessmentStatus] = useState('')
  const [severity, setSeverity] = useState('')

  const { data, isLoading } = useSites({
    page,
    size: 50,
    assessment_status: assessmentStatus || undefined,
    severity: severity || undefined,
  })

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Discovered Sites</h1>
        {data && <span className="text-gray-500 text-sm">{data.total} total</span>}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <select
          value={assessmentStatus}
          onChange={(e) => { setAssessmentStatus(e.target.value); setPage(1) }}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg px-3 py-2"
        >
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.filter(Boolean).map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={severity}
          onChange={(e) => { setSeverity(e.target.value); setPage(1) }}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg px-3 py-2"
        >
          <option value="">All Severities</option>
          {SEVERITY_OPTIONS.filter(Boolean).map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-800 bg-gray-900">
                <th className="px-4 py-3">Domain</th>
                <th className="px-4 py-3">CNAME Target</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">HTTP</th>
                <th className="px-4 py-3">Last Validated</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    Loading...
                  </td>
                </tr>
              ) : data?.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    No sites found. Run a discovery scan first.
                  </td>
                </tr>
              ) : (
                data?.items.map((site) => (
                  <tr key={site.id} className="hover:bg-gray-800/50 transition-colors">
                    <td className="px-4 py-3 font-mono text-blue-300 text-xs">
                      {site.domain}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs font-mono">
                      {site.cname_target ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs capitalize">
                      {site.discovery_source ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        site.assessment_status === 'complete' ? 'bg-green-900/60 text-green-300' :
                        site.assessment_status === 'in_progress' ? 'bg-blue-900/60 text-blue-300' :
                        site.assessment_status === 'error' ? 'bg-red-900/60 text-red-300' :
                        'bg-gray-800 text-gray-400'
                      }`}>
                        {site.assessment_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {site.http_status ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {site.last_validated
                        ? new Date(site.last_validated).toLocaleDateString()
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/sites/${site.id}`}
                        className="text-blue-400 hover:text-blue-300 text-xs flex items-center gap-1"
                      >
                        Details
                        <ChevronRight size={12} />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total > data.size && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={14} /> Prev
            </button>
            <span className="text-xs text-gray-500">
              Page {page} of {Math.ceil(data.total / data.size)}
            </span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page >= Math.ceil(data.total / data.size)}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
