import { useState } from 'react'
import { LoadError, Loading } from '../components/Status.jsx'
import { useData } from '../lib/data.js'

const VIEWS = [
  { id: 'drivers', label: 'Kierowcy', header: 'Kierowca' },
  { id: 'constructors', label: 'Zespoły', header: 'Zespół' },
]

export default function Standings() {
  const { data, error, loading } = useData('standings.json')
  const [view, setView] = useState('drivers')

  if (loading) return <Loading />
  if (error || !data?.drivers || !data?.constructors) return <LoadError />
  const { header } = VIEWS.find((v) => v.id === view)
  const rows = data[view]

  return (
    <>
      <h2>Klasyfikacje</h2>
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
          <table>
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
                  <td>{row.name}</td>
                  <td className="num">{row.points}</td>
                  <td className="num">{row.wins}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  )
}
