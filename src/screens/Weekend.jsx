import { useState } from 'react'
import ProbabilityTable from '../components/ProbabilityTable.jsx'
import SessionList from '../components/SessionList.jsx'
import { LoadError, Loading } from '../components/Status.jsx'
import StrategyCard from '../components/StrategyCard.jsx'
import WeatherCard from '../components/WeatherCard.jsx'
import { useData } from '../lib/data.js'
import { factorLabel, prettifyId } from '../lib/labels.js'

export default function Weekend() {
  const weekend = useData('weekend.json')
  const standings = useData('standings.json')
  const [mode, setMode] = useState('race')

  if (weekend.loading || standings.loading) return <Loading />
  const status = weekend.data?.status
  const malformed = status !== 'no_upcoming_race' && !(status === 'ok' && weekend.data.payload)
  if (weekend.error || malformed) return <LoadError />
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

  const {
    race, weather, strategy, safety_car, qualifying, race_prediction, factors_skipped, low_data,
    lineup, penalties = [],
  } = weekend.data.payload
  const nameById = Object.fromEntries((standings.data?.drivers ?? []).map((d) => [d.id, d.name]))
  const numberById = Object.fromEntries((standings.data?.drivers ?? []).map((d) => [d.id, d.number]))
  const skipped = factors_skipped.map(factorLabel).join(', ')

  return (
    <>
      <h2>
        {race.name}
        {race.is_sprint && <span className="badge sprint">Sprint</span>}
      </h2>
      <p className="muted small">{`Runda ${race.round} · ${race.country}`}</p>

      {lineup === 'previous_season' && (
        <p className="banner">
          Skład kierowców pochodzi z poprzedniego sezonu i może się różnić od prawdziwego. Zaktualizuje się po
          kwalifikacjach.
        </p>
      )}
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
        <ProbabilityTable
          rows={mode === 'race' ? race_prediction : qualifying}
          nameById={nameById}
          numberById={numberById}
          mode={mode}
        />
        {!low_data && skipped && <p className="muted small">{`Pominięte czynniki (brak danych): ${skipped}.`}</p>}
      </section>

      {penalties.length > 0 && (
        <section className="card">
          <h3>Kary na starcie</h3>
          <ul className="list">
            {penalties.map((p) => (
              <li key={p.driver_id}>
                {numberById[p.driver_id] != null && <span className="car-no">{numberById[p.driver_id]}</span>}
                {`${nameById[p.driver_id] ?? prettifyId(p.driver_id)} z ${p.from_pos}. na ${p.to_pos}.`}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
