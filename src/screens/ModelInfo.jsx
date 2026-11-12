import { LoadError, Loading } from '../components/Status.jsx'
import { useData } from '../lib/data.js'
import { factorLabel, num, pct, weightChanges } from '../lib/labels.js'

const FACTORS = ['car_pace', 'driver_form', 'track_history', 'practice_pace', 'weekend_shift', 'car_track_fit', 'wet_skill', 'reliability']
const mean = (values) => values.reduce((sum, v) => sum + v, 0) / values.length

export default function ModelInfo() {
  const { data, error, loading } = useData('model.json')

  if (loading) return <Loading />
  if (error || !data?.weights || !Array.isArray(data.evaluation)) return <LoadError />

  const { weights, factors_used: used = [], factors_skipped: skipped = [], evaluation, weight_history: history } = data
  const maxWeight = Math.max(...FACTORS.map((key) => weights[key] ?? 0), 0.0001)
  const changes = weightChanges(history)
  const top3 = evaluation.filter((e) => e.winner_in_top3).length

  return (
    <>
      <h2>Model</h2>

      <section className="card">
        <h3>Czynniki i ich wagi</h3>
        <ul className="list">
          {FACTORS.filter((key) => key in weights).map((key) => (
            <li key={key}>
              <span>{factorLabel(key)}</span>
              <span className="weight">
                <span className="bar" aria-hidden="true">
                  <span style={{ width: `${(weights[key] / maxWeight) * 100}%` }} />
                </span>
                {num(weights[key])}
                {used.includes(key) && <span className="badge">używany</span>}
                {skipped.includes(key) && <span className="badge">brak danych</span>}
              </span>
            </li>
          ))}
        </ul>
        <p className="muted small">
          {`Siła pozycji startowej: ${num(weights.grid_base_weight ?? 0)} · poziom losowości: ${num(weights.race_noise_base ?? 0)}`}
        </p>
      </section>

      {changes.length > 0 && (
        <section className="card">
          <h3>Ostatnie zmiany wag</h3>
          <ul className="list">
            {changes.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <h3>Trafność przewidywań</h3>
        {evaluation.length === 0 ? (
          <p className="muted">Ocena pojawi się po pierwszych rozegranych wyścigach sezonu.</p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Runda</th>
                  <th className="num">Szansa zwycięzcy</th>
                  <th className="num">Top 3</th>
                  <th className="num">Błąd pozycji</th>
                </tr>
              </thead>
              <tbody>
                {evaluation.map((e) => (
                  <tr key={e.round}>
                    <td>{e.round}</td>
                    <td className="num">{pct(e.winner_prob)}</td>
                    <td className="num">{e.winner_in_top3 ? 'tak' : 'nie'}</td>
                    <td className="num">{num(e.mean_abs_position_error, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p>
              {`Średnia szansa przypisana zwycięzcy: ${pct(mean(evaluation.map((e) => e.winner_prob)))}; w trójce faworytów: ${top3} z ${evaluation.length}.`}
            </p>
            <p className="muted small">
              Ocena po fakcie, przy znanej siatce startowej (jak po kwalifikacjach). Wagi są dostrajane na tych samych
              wyścigach, więc wynik jest nieco optymistyczny.
            </p>
          </>
        )}
      </section>
    </>
  )
}
