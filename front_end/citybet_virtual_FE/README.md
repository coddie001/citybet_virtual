# CityBet Virtuals — Frontend

React + Vite + Tailwind CSS. Mock data phase — API integration next.

## Run

```bash
cd front_end/citybet_virtual_FE
npm install
npm run dev
```

Open http://localhost:5173

API proxy: `/api/*` → `http://localhost:8000` (configure in `vite.config.ts`).

## Structure

```
src/
  components/
    layout/     Header, Footer, PromoBanner
    carousel/   UpcomingGamesCarousel, MatchCard
    table/      DataPanel, LeagueTable, Fixtures, Results, Stats
    match/      LiveMatchPanel, PitchView, GameStatsBar
    ui/         LeagueDropdown, FormDots
  context/      LeagueContext (ALL vs single league)
  hooks/        useCountdown, useLeagueRotation, useFilteredData
  data/         mockData.ts (replace with API calls)
  pages/        HomePage
```

## League modes

- **All Leagues**: carousel + live panel show all leagues; table rotates every 8s with crossfade; multiple live games with arrows.
- **Single league**: filtered data; one live game only.

## Next: API integration

Replace `src/data/mockData.ts` usage with `src/api/client.ts` calling backend endpoints.
