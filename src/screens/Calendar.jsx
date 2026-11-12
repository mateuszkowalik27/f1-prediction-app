import { useEffect, useRef, useState } from 'react'
import RoundSessions from '../components/RoundSessions.jsx'
import { LoadError, Loading } from '../components/Status.jsx'
import { useData } from '../lib/data.js'
import { formatWarsaw, nextRound } from '../lib/time.js'

const raceDay = (race) => formatWarsaw(race.sessions.find((s) => s.name === 'Race')?.start_utc, { day: 'numeric', month: 'short' })

export default function Calendar() {
  const { data, error, loading } = useData('calendar.json')
  // undefined = użytkownik jeszcze niczego nie klikał: wtedy pokazujemy rozwiniętą najbliższą rundę
  const [open, setOpen] = useState(undefined)
  const nextRef = useRef(null)
  const next = Array.isArray(data?.races) ? nextRound(data.races) : null

  useEffect(() => {
    nextRef.current?.scrollIntoView?.({ block: 'start' })   // najbliższa runda jest nisko na liście: przewijamy do niej
  }, [next])

  if (loading) return <Loading />
  if (error || !Array.isArray(data?.races)) return <LoadError />
  const races = [...data.races].sort((a, b) => a.round - b.round)

  return (
    <>
      <h2>{`Kalendarz ${data.season}`}</h2>
      {races.map((race) => {
        const expanded = (open === undefined ? next : open) === race.round
        return (
          <section className="card round" key={race.round} ref={race.round === next ? nextRef : undefined}>
            <button
              className="round-button"
              aria-expanded={expanded}
              aria-controls={`round-${race.round}`}
              onClick={() => setOpen(expanded ? null : race.round)}
            >
              <span>
                <strong>{race.name}</strong>
                {race.is_sprint && <span className="badge sprint">Sprint</span>}
                <span className="muted small block">{`Runda ${race.round}`}</span>
              </span>
              <span className="muted">{raceDay(race)}</span>
            </button>
            {expanded && (
              <div id={`round-${race.round}`}>
                <RoundSessions race={race} />
              </div>
            )}
          </section>
        )
      })}
    </>
  )
}
