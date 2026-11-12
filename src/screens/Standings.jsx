import { useState } from 'react'
import { LoadError, Loading } from '../components/Status.jsx'
import DriverCell from '../components/DriverCell.jsx'
import { useData } from '../lib/data.js'
import { driverMaps } from '../lib/drivers.js'
import { teamColors, teamLogo } from '../lib/teams.js'

const VIEWS = [
  { id: 'drivers', label: 'Kierowcy', header: 'Kierowca' },
  { id: 'constructors', label: 'Zespoły', header: 'Zespół' },
]

// Zespół: pasek w jego barwach, białe logo i nazwa.
function TeamCell({ row }) {
  const colors = teamColors(row.id)
  const logo = teamLogo(row.id)
  return (
    <span className="driver">
      <span className="team-bar" style={colors ? { background: colors.bg } : undefined} />
      {logo ? <img className="team-logo" src={logo} alt="" /> : <span className="team-logo" />}
      <span className="driver-name">{row.name}</span>
    </span>
  )
}

export default function Standings() {
  const { data, error, loading } = useData('standings.json')
  const [view, setView] = useState('drivers')

  if (loading) return <Loading />
  if (error || !data?.drivers || !data?.constructors) return <LoadError />
  const { header } = VIEWS.find((v) => v.id === view)
  const rows = data[view]
  const drivers = driverMaps(data)

  return (
    <>
      <h2>{data.season ? `Klasyfikacje ${data.season}` : 'Klasyfikacje'}</h2>
      <div className="segmented">
        {VIEWS.map((v) => (
          <button key={v.id} aria-pressed={view === v.id} onClick={() => setView(v.id)}>
            {v.label}
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <p className="card muted">Klasyfikacja pojawi się po pierwszym wyścigu sezonu.</p>
      ) : (
        <section className="card">
          <div className="table-scroll" tabIndex={0} role="region" aria-label="Klasyfikacja (przewiń w bok)">
          <table className="standings">
            <thead>
              <tr>
                <th>Poz.</th>
                <th>{header}</th>
                <th className="num">Pkt</th>
                <th className="num">Wygrane</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.position}</td>
                  <td>{view === 'drivers' ? <DriverCell id={row.id} drivers={drivers} /> : <TeamCell row={row} />}</td>
                  <td className="num">{row.points}</td>
                  <td className="num">{row.wins}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </section>
      )}
    </>
  )
}
