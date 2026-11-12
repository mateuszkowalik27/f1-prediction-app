import { pct } from '../lib/labels.js'
import DriverCell from './DriverCell.jsx'

export default function ProbabilityTable({ rows, drivers, mode }) {
  const race = mode === 'race'
  const sorted = [...rows].sort((a, b) => b.win - a.win)
  const max = sorted[0]?.win || 1
  return (
    <table>
      <thead>
        <tr>
          <th>Kierowca</th>
          <th>{race ? 'Wygrana' : 'Pole position'}</th>
          <th className="num">{race ? 'Podium' : 'Top 3'}</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.driver_id}>
            <td>
              <DriverCell id={row.driver_id} drivers={drivers} />
            </td>
            <td>
              <span>{pct(row.win)}</span>
              <div className="bar" aria-hidden="true">
                <span style={{ width: `${(row.win / max) * 100}%` }} />
              </div>
            </td>
            <td className="num">{pct(row.podium)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
