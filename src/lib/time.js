// Wszystkie godziny w aplikacji są pokazywane w czasie polskim, niezależnie od strefy urządzenia.
export const TBC = 'do ustalenia'

const DEFAULT_FORMAT = { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }

export function formatWarsaw(isoUtc, options = DEFAULT_FORMAT) {
  if (!isoUtc) return TBC
  return new Intl.DateTimeFormat('pl-PL', { ...options, timeZone: 'Europe/Warsaw' }).format(new Date(isoUtc))
}

// Najbliższa runda: pierwsza, której wyścig jeszcze się nie skończył (3 godziny po starcie), albo bez godziny wyścigu.
// Ta sama reguła co w robocie (select_next_race), żeby Weekend i Kalendarz wskazywały tę samą rundę.
export const RACE_DURATION_MS = 3 * 60 * 60 * 1000

export function nextRound(races, now = Date.now()) {
  const sorted = [...races].sort((a, b) => a.round - b.round)
  const next = sorted.find((race) => {
    const start = race.sessions.find((s) => s.name === 'Race')?.start_utc
    return !start || new Date(start).getTime() + RACE_DURATION_MS > now
  })
  return next?.round ?? null
}
