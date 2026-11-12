import { pct } from '../lib/labels.js'

export default function WeatherCard({ weather }) {
  return (
    <section className="card weather">
      <h3>Pogoda</h3>
      {weather ? (
        <>
          <p>
            Szansa deszczu: <strong>{pct(weather.rain_probability)}</strong>
          </p>
          <p>{`Temperatura: ${Math.round(weather.temperature_c)} °C`}</p>
        </>
      ) : (
        <p className="muted">Brak prognozy (wyścig za więcej niż 16 dni albo brak danych).</p>
      )}
    </section>
  )
}
