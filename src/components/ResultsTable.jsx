import { formatGap, formatLap, formatRaceResult } from '../lib/format.js'
import { prettifyId } from '../lib/labels.js'

// Skrót kierowcy: oficjalny trzyliterowy kod (ANT, HAM), a bez niego trzy pierwsze litery nazwiska.
export const driverCode = (id, codeById, nameById) =>
  codeById[id] ?? (nameById[id] ?? prettifyId(id)).split(' ').pop().slice(0, 3).toUpperCase()

const Name = ({ id, nameById, numberById, codeById }) => (
  <>
    {numberById[id] != null && <span className="car-no" title="Numer startowy">{numberById[id]}</span>}
    <span title={nameById[id] ?? prettifyId(id)}>{driverCode(id, codeById, nameById)}</span>
  </>
)

// Tabela wyników jednej sesji. `table.kind`: practice | qualifying | race.
export default function ResultsTable({ table, nameById = {}, numberById = {}, codeById = {} }) {
  const { kind, rows } = table
  // najlepszy czas w każdej części kwalifikacji: do niego liczymy stratę
  const best = ['q1', 'q2', 'q3'].map((q) => Math.min(...rows.map((r) => r[q]).filter((t) => t != null)))
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Wyniki sesji (przewiń w bok)">
    <table className="results">
      <thead>
        <tr>
          <th className="num">#</th>
          <th>Kierowca</th>
          {kind === 'practice' && <th className="num">Najlepszy czas</th>}
          {kind === 'qualifying' && ['Q1', 'Q2', 'Q3'].map((q) => <th className="num" key={q}>{q}</th>)}
          {kind === 'race' && <th className="num">Czas</th>}
          {kind === 'race' && <th className="num">Pkt</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => {
          const result = kind === 'race' ? formatRaceResult(row) : null
          return (
            <tr key={row.driver_id}>
              <td className="num">{row.position ?? i + 1}</td>
              <td><Name id={row.driver_id} nameById={nameById} numberById={numberById} codeById={codeById} /></td>
              {kind === 'practice' && <td className="num">{formatLap(row.best_s)}</td>}
              {kind === 'qualifying' && [row.q1, row.q2, row.q3].map((t, n) => (
                <td className="num" key={n}>
                  {formatLap(t)}
                  {formatGap(t, best[n]) && <span className="muted small block">{formatGap(t, best[n])}</span>}
                </td>
              ))}
              {kind === 'race' && (
                <td className="num">
                  {result.text}
                  {result.reason && <span className="muted small block">{result.reason}</span>}
                </td>
              )}
              {kind === 'race' && <td className="num">{row.points ?? '–'}</td>}
            </tr>
          )
        })}
      </tbody>
    </table>
    </div>
  )
}
