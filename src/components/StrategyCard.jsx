import { COMPOUND_LABELS, pct, stopsLabel } from '../lib/labels.js'

const CONFIDENCE = { low: 'mała pewność', medium: 'średnia pewność', high: 'duża pewność' }
const describe = (s) => `${stopsLabel(s.stops)}: ${s.compounds.map((c) => COMPOUND_LABELS[c] ?? c).join(' → ')}`

export default function StrategyCard({ strategy, safetyCar }) {
  return (
    <section className="card">
      <h3>
        Strategia opon <span className="badge">{CONFIDENCE[strategy.confidence]}</span>
      </h3>
      <p>{describe(strategy.primary)}</p>
      <p className="muted small">{`Alternatywa: ${describe(strategy.alternative)}`}</p>
      <p>{`Safety car ${pct(safetyCar.sc)} · VSC ${pct(safetyCar.vsc)}`}</p>
    </section>
  )
}
