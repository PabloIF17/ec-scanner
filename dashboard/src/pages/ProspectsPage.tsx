import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { Building2, Users } from 'lucide-react'

interface Prospect {
  id: string
  site_id: string
  company_name: string | null
  industry: string | null
  employee_count: number | null
  estimated_revenue: string | null
  enrichment_source: string | null
  created_at: string
  contacts: Array<{
    id: string
    name: string | null
    title: string | null
    email: string | null
  }>
}

function useProspects() {
  return useQuery({
    queryKey: ['prospects'],
    queryFn: async () => {
      const { data } = await apiClient.get<Prospect[]>('/prospects')
      return data
    },
  })
}

export default function ProspectsPage() {
  const { data: prospects, isLoading } = useProspects()

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Prospects</h1>
        {prospects && (
          <span className="text-gray-500 text-sm">{prospects.length} enriched prospects</span>
        )}
      </div>

      {isLoading ? (
        <div className="text-gray-500">Loading...</div>
      ) : !prospects?.length ? (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
          <Users className="mx-auto text-gray-700 mb-3" size={40} />
          <p className="text-gray-500">No prospects yet.</p>
          <p className="text-gray-600 text-sm mt-1">
            Prospects are enriched automatically when sites reach MEDIUM+ risk score.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {prospects.map((prospect) => (
            <div key={prospect.id} className="bg-gray-900 rounded-xl border border-gray-800 p-5">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-gray-800 flex items-center justify-center flex-shrink-0">
                  <Building2 className="text-gray-500" size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-white">
                    {prospect.company_name ?? 'Unknown Company'}
                  </p>
                  <p className="text-gray-500 text-xs mt-0.5">
                    {prospect.industry ?? 'Unknown industry'} ·{' '}
                    {prospect.employee_count ? `${prospect.employee_count} employees` : 'Size unknown'}
                  </p>
                </div>
                <span className="text-xs text-gray-600 capitalize">
                  {prospect.enrichment_source ?? '—'}
                </span>
              </div>

              {prospect.contacts.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-800">
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Contacts</p>
                  <div className="space-y-1">
                    {prospect.contacts.slice(0, 3).map((contact) => (
                      <div key={contact.id} className="flex items-center justify-between">
                        <div>
                          <span className="text-sm text-gray-300">{contact.name ?? '—'}</span>
                          {contact.title && (
                            <span className="text-xs text-gray-500 ml-2">{contact.title}</span>
                          )}
                        </div>
                        {contact.email && (
                          <span className="text-xs text-blue-400 font-mono">{contact.email}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
