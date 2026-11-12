import { Component } from 'react'
import { resetApp } from '../lib/reset.js'

// Zamiast białego ekranu pokazuje, że coś poszło nie tak, z treścią błędu (do zgłoszenia) i przyciskiem naprawy.
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <section className="card" role="alert">
        <h2>Coś poszło nie tak</h2>
        <p className="muted">Aplikacja napotkała błąd. Zwykle pomaga wyczyszczenie zapamiętanej wersji.</p>
        <p className="small error-text">{String(this.state.error?.message ?? this.state.error)}</p>
        <button className="results-toggle" onClick={resetApp}>Wyczyść i odśwież</button>
      </section>
    )
  }
}
