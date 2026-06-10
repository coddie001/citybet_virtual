import citybetLogo from '../../assets/citybet_logo.png'
import { LeagueDropdown } from '../ui/LeagueDropdown'

export function Header() {
  return (
    <header className="app-shell-header shrink-0">
      <div className="flex items-center justify-between px-5 py-4 sm:px-8 lg:px-10 lg:py-5">
        <a href="/" className="flex shrink-0 items-center transition-opacity hover:opacity-90" aria-label="CityBet home">
          <img
            src={citybetLogo}
            alt="CityBet"
            className="app-logo h-auto w-[clamp(3.5rem,10vw,6rem)] max-w-none object-contain"
          />
        </a>
        <LeagueDropdown />
      </div>
    </header>
  )
}
