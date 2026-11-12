import { prettifyId } from './labels.js'

// Mapy kierowców z pliku klasyfikacji (standings.json): nazwa, numer, skrót i zespół po id kierowcy.
export function driverMaps(standingsData) {
  const list = standingsData?.drivers ?? []
  const by = (key) => Object.fromEntries(list.map((d) => [d.id, d[key]]))
  return { nameById: by('name'), numberById: by('number'), codeById: by('code'), teamById: by('team_id') }
}

// Skrót kierowcy: oficjalny trzyliterowy kod (ANT, HAM), a bez niego trzy pierwsze litery nazwiska.
export const driverCode = (id, { codeById = {}, nameById = {} }) =>
  codeById[id] ?? (nameById[id] ?? prettifyId(id)).split(' ').pop().slice(0, 3).toUpperCase()
