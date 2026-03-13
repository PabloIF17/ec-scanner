const SEVERITY_STYLES: Record<string, string> = {
  CRITICAL: 'bg-red-900 text-red-300 border border-red-700',
  HIGH: 'bg-orange-900 text-orange-300 border border-orange-700',
  MEDIUM: 'bg-yellow-900 text-yellow-300 border border-yellow-700',
  LOW: 'bg-blue-900 text-blue-300 border border-blue-700',
  MINIMAL: 'bg-gray-800 text-gray-400 border border-gray-600',
}

export default function SeverityBadge({ severity }: { severity: string | null }) {
  if (!severity) return <span className="text-gray-600 text-xs">—</span>
  const s = severity.toUpperCase()
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${SEVERITY_STYLES[s] ?? 'bg-gray-800 text-gray-400'}`}>
      {s}
    </span>
  )
}
