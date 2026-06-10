import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { LeagueId, TabId } from '../types'
import { usePlatformData } from './PlatformDataContext'

interface LeagueContextValue {
  selectedLeague: LeagueId
  setSelectedLeague: (league: LeagueId) => void
  activeTab: TabId
  setActiveTab: (tab: TabId) => void
  isAllLeagues: boolean
  leagueOptions: { id: LeagueId; label: string }[]
  displayLeagueName: string
}

const LeagueContext = createContext<LeagueContextValue | null>(null)

export function LeagueProvider({ children }: { children: ReactNode }) {
  const { leagues } = usePlatformData()
  const [selectedLeague, setSelectedLeague] = useState<LeagueId>('ALL')
  const [activeTab, setActiveTab] = useState<TabId>('table')

  const value = useMemo<LeagueContextValue>(() => ({
    selectedLeague,
    setSelectedLeague,
    activeTab,
    setActiveTab,
    isAllLeagues: selectedLeague === 'ALL',
    leagueOptions: [
      { id: 'ALL', label: 'All Leagues' },
      ...leagues.map((l) => ({ id: l.id, label: l.name })),
    ],
    displayLeagueName: selectedLeague === 'ALL' ? 'All Leagues' : selectedLeague,
  }), [selectedLeague, activeTab, leagues])

  return <LeagueContext.Provider value={value}>{children}</LeagueContext.Provider>
}

export function useLeague() {
  const ctx = useContext(LeagueContext)
  if (!ctx) throw new Error('useLeague must be used within LeagueProvider')
  return ctx
}
