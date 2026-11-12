import { pct, prettifyId } from '../lib/labels.js'

export default function ProbabilityTable({ rows, nameById, numberById = {}, mode }) {
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
              {numberById[row.driver_id] != null && (
                <span className="car-no" title="Numer startowy">{numberById[row.driver_id]}</span>
              )}
              {nameById[row.driver_id] ?? prettifyId(row.driver_id)}
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
