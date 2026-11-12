import { useData } from '../lib/data.js'
import { driverMaps } from '../lib/drivers.js'
import SessionList from './SessionList.jsx'

// Sesje rundy; wyniki (jeśli robot je zapisał) wczytujemy dopiero tutaj. Brak pliku = zwykła lista z godzinami.
export default function RoundSessions({ race }) {
  const results = useData(`results/${race.season}-${race.round}.json`)
  const standings = useData('standings.json')
  return <SessionList sessions={race.sessions} results={results.data?.sessions ?? null} drivers={driverMaps(standings.data)} />
}
