// Czas okrążenia: 79.5 -> "1:19,500", 24.394 -> "24,394". Brak -> "–".
export function formatLap(seconds) {
  if (seconds == null) return '–'
  const minutes = Math.floor(seconds / 60)
  const rest = (seconds - minutes * 60).toFixed(3).padStart(minutes ? 6 : 1, '0')
  return (minutes ? `${minutes}:${rest}` : rest).replace('.', ',')
}

// Wynik kierowcy w sprincie/wyścigu: czas zwycięzcy, strata, zdublowanie albo powód odpadnięcia.
// Zwraca { text, reason } (reason: dopisek, gdy kierowca nie ukończył).
export function formatRaceResult(row) {
  if (row.time) return { text: row.time.replace('.', ','), reason: null }
  const status = row.status ?? ''
  const lapped = status.match(/^\+(\d+) Laps?$/)
  if (lapped) return { text: `+${lapped[1]} okr.`, reason: null }
  if (status === 'Disqualified') return { text: 'DSQ', reason: null }
  if (status === 'Did not start') return { text: 'DNS', reason: null }
  if (status === 'Finished') return { text: '–', reason: null }
  return { text: 'DNF', reason: status || null }
}

// Strata do lidera: 0.123 -> "+0,123"; lider (0) i brak czasu -> null.
export function formatGap(seconds, best) {
  if (seconds == null || best == null || seconds <= best) return null
  return `+${(seconds - best).toFixed(3).replace('.', ',')}`
}
