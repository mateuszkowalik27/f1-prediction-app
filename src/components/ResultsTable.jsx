import { formatLap, formatRaceResult } from '../lib/format.js'
import { prettifyId } from '../lib/labels.js'

const Name = ({ id, nameById, numberById }) => (
  <>
    {numberById[id] != null && <span className="car-no" title="Numer startowy">{numberById[id]}</span>}
    {nameById[id] ?? prettifyId(id)}
  </>
)

// Tabela wyników jednej sesji. `table.kind`: practice | qualifying | race.
export default function ResultsTable({ table, nameById = {}, numberById = {} }) {
  const { kind, rows } = table
  return (
    <table className="results">
      <thead>
        <tr>
          <th className="num">#</th>
          <th>Kierowca</th>
          {kind === 'practice' && <th className="num">Najlepszy czas</th>}
          {kind === 'qualifying' && ['Q1', 'Q2', 'Q3'].map((q) => <th className="num" key={q}>{q}</th>)}
          {kind === 'race' && <th className="num">Czas</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => {
          const result = kind === 'race' ? formatRaceResult(row) : null
          return (
            <tr key={row.driver_id}>
              <td className="num">{row.position ?? i + 1}</td>
              <td><Name id={row.driver_id} nameById={nameById} numberById={numberById} /></td>
              {kind === 'practice' && <td className="num">{formatLap(row.best_s)}</td>}
              {kind === 'qualifying' && [row.q1, row.q2, row.q3].map((t, n) => <td className="num" key={n}>{formatLap(t)}</td>)}
              {kind === 'race' && (
                <td className="num">
                  {result.text}
                  {result.reason && <span className="muted small block">{result.reason}</span>}
                </td>
              )}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
