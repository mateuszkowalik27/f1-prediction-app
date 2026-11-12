// Wszystkie godziny w aplikacji są pokazywane w czasie polskim, niezależnie od strefy urządzenia.
export const TBC = 'do ustalenia'

const DEFAULT_FORMAT = { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }

export function formatWarsaw(isoUtc, options = DEFAULT_FORMAT) {
  if (!isoUtc) return TBC
  return new Intl.DateTimeFormat('pl-PL', { ...options, timeZone: 'Europe/Warsaw' }).format(new Date(isoUtc))
}
