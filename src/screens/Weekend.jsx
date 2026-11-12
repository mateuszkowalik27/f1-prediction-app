import { useState } from 'react'
import ProbabilityTable from '../components/ProbabilityTable.jsx'
import SessionList from '../components/SessionList.jsx'
import StrategyCard from '../components/StrategyCard.jsx'
import WeatherCard from '../components/WeatherCard.jsx'
import { useData } from '../lib/data.js'
import { factorLabel } from '../lib/labels.js'

export default function Weekend() {
  const weekend = useData('weekend.json')
  const standings = useData('standings.json')
  const [mode, setMode] = useState('race')

  if (weekend.loading || standings.loading) return <p className="muted">Wczytywanie…</p>
  const status = weekend.data?.status
  const malformed = status !== 'no_upcoming_race' && !(status === 'ok' && weekend.data.payload)
  if (weekend.error || malformed) {
    return <p className="banner">Nie udało się wczytać danych. Sprawdź połączenie i spróbuj ponownie.</p>
  }
  if (status === 'no_upcoming_race') {
    return (
      <section className="card">
        <h2>Brak nadchodzącego wyścigu</h2>
        <p className="muted">
          Sezon dobiegł końca albo kalendarz następnego sezonu nie został jeszcze opublikowany. Aplikacja sama się
          zaktualizuje, gdy pojawią się nowe rundy.
        </p>
      </section>
    )
  }

  const { race, weather, strategy, safety_car, qualifying, race_prediction, factors_skipped, low_data } =
    weekend.data.payload
  const nameById = Object.fromEntries((standings.data?.drivers ?? []).map((d) => [d.id, d.name]))
  const skipped = factors_skipped.map(factorLabel).join(', ')

  return (
    <>
      <h2>
        {race.name}
        {race.is_sprint && <span className="badge sprint">Sprint</span>}
      </h2>
      <p className="muted small">{`Runda ${race.round} · ${race.country}`}</p>

      {low_data && (
        <p className="banner">
          Mało danych: część czynników jest wyłączona{skipped ? ` (${skipped})` : ''}. Prognoza jest mniej pewna.
        </p>
      )}

      <section className="card">
        <h3>Harmonogram (czas polski)</h3>
        <SessionList sessions={race.sessions} />
      </section>
      <WeatherCard weather={weather} />
      <StrategyCard strategy={strategy} safetyCar={safety_car} />

      <section className="card">
        <h3>Szanse</h3>
        <div className="segmented">
          <button aria-pressed={mode === 'qualifying'} onClick={() => setMode('qualifying')}>
            Kwalifikacje
          </button>
          <button aria-pressed={mode === 'race'} onClick={() => setMode('race')}>
            Wyścig
          </button>
        </div>
        <ProbabilityTable rows={mode === 'race' ? race_prediction : qualifying} nameById={nameById} mode={mode} />
        {!low_data && skipped && <p className="muted small">{`Pominięte czynniki (brak danych): ${skipped}.`}</p>}
      </section>
    </>
  )
}
