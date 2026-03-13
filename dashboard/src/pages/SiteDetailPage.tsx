import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Play } from 'lucide-react'
import { useSite, useSiteAssessments } from '../api/hooks/useSites'
import { useTriggerAssessment } from '../api/hooks/useDashboard'
import SeverityBadge from '../components/SeverityBadge'
import { useQueryClient } from '@tanstack/react-query'

export default function SiteDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: site, isLoading: siteLoading } = useSite(id!)
  const { data: assessments, isLoading: assessLoading } = useSiteAssessments(id!)
  const triggerAssessment = useTriggerAssessment(id)
  const queryClient = useQueryClient()

  if (siteLoading) return <div className="p-8 text-gray-500">Loading...</div>
  if (!site) return <div className="p-8 text-red-400">Site not found.</div>

  const latestAssessment = assessments?.[0]

  const handleAssess = async () => {
    await triggerAssessment.mutateAsync()
    queryClient.invalidateQueries({ queryKey: ['sites', id, 'assessments'] })
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Link to="/sites" className="text-gray-500 hover:text-gray-300">
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-white font-mono">{site.domain}</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            {site.cname_target ?? 'No CNAME recorded'} · {site.discovery_source ?? 'manual'}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {latestAssessment && <SeverityBadge severity={latestAssessment.severity} />}
          <button
            onClick={handleAssess}
            disabled={triggerAssessment.isPending}
            className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg disabled:opacity-50"
          >
            <Play size={12} />
            Assess Now
          </button>
        </div>
      </div>

      {/* Site info grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Assessment Status', value: site.assessment_status },
          { label: 'HTTP Status', value: site.http_status ?? '—' },
          { label: 'Active', value: site.is_active ? 'Yes' : 'No' },
          { label: 'Last Validated', value: site.last_validated ? new Date(site.last_validated).toLocaleDateString() : '—' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
            <p className="text-white font-semibold mt-1">{value}</p>
          </div>
        ))}
      </div>

      {/* Latest assessment */}
      {assessLoading ? (
        <div className="text-gray-500">Loading assessments...</div>
      ) : latestAssessment ? (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-300">Latest Assessment</h2>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">
                {new Date(latestAssessment.assessment_date).toLocaleString()}
              </span>
              <SeverityBadge severity={latestAssessment.severity} />
              <span className="text-2xl font-bold text-white">
                {latestAssessment.risk_score ?? '—'}
                <span className="text-sm text-gray-500">/100</span>
              </span>
            </div>
          </div>

          {/* Risk score bar */}
          {latestAssessment.risk_score !== null && (
            <div className="w-full bg-gray-800 rounded-full h-2 mb-6">
              <div
                className={`h-2 rounded-full ${
                  latestAssessment.risk_score >= 90 ? 'bg-red-500' :
                  latestAssessment.risk_score >= 70 ? 'bg-orange-500' :
                  latestAssessment.risk_score >= 50 ? 'bg-yellow-500' :
                  latestAssessment.risk_score >= 30 ? 'bg-blue-500' : 'bg-gray-600'
                }`}
                style={{ width: `${latestAssessment.risk_score}%` }}
              />
            </div>
          )}

          {/* Remediation items */}
          {latestAssessment.remediation_summary && latestAssessment.remediation_summary.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Remediation Steps
              </h3>
              <ul className="space-y-2">
                {latestAssessment.remediation_summary.map((item, i) => (
                  <li key={i} className={`text-sm px-3 py-2 rounded-lg ${
                    item.startsWith('CRITICAL') ? 'bg-red-900/30 text-red-200 border border-red-800' :
                    item.startsWith('HIGH') ? 'bg-orange-900/30 text-orange-200 border border-orange-800' :
                    item.startsWith('MEDIUM') ? 'bg-yellow-900/30 text-yellow-200 border border-yellow-800' :
                    'bg-gray-800 text-gray-300'
                  }`}>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 text-center text-gray-500">
          <p>No assessments yet. Click "Assess Now" to run a security check.</p>
        </div>
      )}

      {/* Assessment history */}
      {assessments && assessments.length > 1 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">Assessment History</h2>
          <div className="space-y-2">
            {assessments.slice(1).map((a) => (
              <div key={a.id} className="flex items-center justify-between py-2 border-b border-gray-800">
                <span className="text-xs text-gray-500">
                  {new Date(a.assessment_date).toLocaleString()}
                </span>
                <div className="flex items-center gap-3">
                  <SeverityBadge severity={a.severity} />
                  <span className="text-white text-sm font-semibold">
                    {a.risk_score ?? '—'}/100
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
