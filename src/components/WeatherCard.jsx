import { pct } from '../lib/labels.js'

// Temperatura jest z godziny startu wyścigu (czas lokalny toru), a nie z "teraz" ani z maksimum dnia.
// Gdy takiej prognozy brak, pokazujemy maksimum dnia i mówimy to wprost.
function Temperature({ weather }) {
  const { start_temperature_c: atStart, start_local_time: time, temperature_c: dayMax } = weather
  if (atStart == null) return <p>{`Temperatura (maks. w dniu wyścigu): ${Math.round(dayMax)} °C`}</p>
  const when = time ? `o ${time} czasu lokalnego` : 'o godzinie startu'
  return (
    <p>
      {`Temperatura na starcie wyścigu (${when}): `}
      <strong>{`${Math.round(atStart)} °C`}</strong>
    </p>
  )
}

export default function WeatherCard({ weather }) {
  return (
    <section className="card weather">
      <h3>Pogoda</h3>
      {weather ? (
        <>
          <p>
            Szansa deszczu: <strong>{pct(weather.rain_probability)}</strong>
          </p>
          <Temperature weather={weather} />
        </>
      ) : (
        <p className="muted">Brak prognozy (wyścig za więcej niż 16 dni albo brak danych).</p>
      )}
    </section>
  )
}
