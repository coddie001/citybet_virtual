import { useLeague } from '../../context/LeagueContext'
import type { TabId } from '../../types'

const TABS: { id: TabId; label: string }[] = [
  { id: 'table', label: 'Table' },
  { id: 'fixtures', label: 'Fixtures' },
  { id: 'results', label: 'Results' },
  { id: 'stats', label: 'Stats' },
]

export function TabSwitcher() {
  const { activeTab, setActiveTab } = useLeague()

  return (
    <div className="inline-flex rounded-xl border border-white/10 bg-surface-raised p-1">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => setActiveTab(tab.id)}
          className={`rounded-lg px-4 py-2 text-fluid-xs font-semibold transition-all duration-200 sm:px-5 sm:text-fluid-sm ${
            activeTab === tab.id
              ? 'bg-white/15 text-white shadow-inner'
              : 'text-white/50 hover:text-white/80'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
