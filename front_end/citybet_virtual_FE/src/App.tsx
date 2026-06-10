import { LeagueProvider } from './context/LeagueContext'
import { PlatformDataProvider } from './context/PlatformDataContext'
import { HomePage } from './pages/HomePage'

export default function App() {
  return (
    <PlatformDataProvider>
      <LeagueProvider>
        <HomePage />
      </LeagueProvider>
    </PlatformDataProvider>
  )
}
