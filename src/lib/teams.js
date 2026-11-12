// Logo (białe SVG) i kolor zespołu. Klucze: constructorId z Jolpica.
const logos = import.meta.glob('../assets/teams/*.svg', { eager: true, query: '?url', import: 'default' })

export const teamLogo = (teamId) => logos[`../assets/teams/${teamId}.svg`] ?? null

// Kolory zespołów (ich oficjalne barwy z F1). `fg`: kolor numeru na takim tle.
export const TEAM_COLORS = {
  ferrari: { bg: '#E8002D', fg: '#fff' },
  mercedes: { bg: '#27F4D2', fg: '#06201c' },
  red_bull: { bg: '#3671C6', fg: '#fff' },
  mclaren: { bg: '#FF8000', fg: '#1a0d00' },
  aston_martin: { bg: '#229971', fg: '#fff' },
  alpine: { bg: '#0093CC', fg: '#fff' },
  williams: { bg: '#64C4FF', fg: '#06202e' },
  rb: { bg: '#6692FF', fg: '#07123a' },
  haas: { bg: '#B6BABD', fg: '#1a1c1e' },
  audi: { bg: '#F50537', fg: '#fff' },
  cadillac: { bg: '#8C9196', fg: '#fff' },
}

export const teamColors = (teamId) => TEAM_COLORS[teamId] ?? null

// "Andrea Kimi Antonelli" -> "A. Antonelli"; jedno słowo zostaje bez zmian.
export function shortName(fullName) {
  const parts = String(fullName ?? '').trim().split(/\s+/).filter(Boolean)
  if (parts.length < 2) return parts[0] ?? ''
  return `${parts[0][0]}. ${parts[parts.length - 1]}`
}
