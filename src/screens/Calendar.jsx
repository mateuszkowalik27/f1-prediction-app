import { useState } from 'react'
import SessionList from '../components/SessionList.jsx'
import { LoadError, Loading } from '../components/Status.jsx'
import { useData } from '../lib/data.js'
import { formatWarsaw } from '../lib/time.js'

const raceDay = (race) => formatWarsaw(race.sessions.find((s) => s.name === 'Race')?.start_utc, { day: 'numeric', month: 'short' })

export default function Calendar() {
  const { data, error, loading } = useData('calendar.json')
  const [open, setOpen] = useState(null)

  if (loading) return <Loading />
  if (error || !Array.isArray(data?.races)) return <LoadError />
  const races = [...data.races].sort((a, b) => a.round - b.round)

  return (
    <>
      <h2>{`Kalendarz ${data.season}`}</h2>
      {races.map((race) => {
        const expanded = open === race.round
        return (
          <section className="card round" key={race.round}>
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
                <SessionList sessions={race.sessions} />
              </div>
            )}
          </section>
        )
      })}
    </>
  )
}
