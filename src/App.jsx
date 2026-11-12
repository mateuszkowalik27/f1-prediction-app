import { useState } from 'react'
import { useData } from './lib/data.js'
import { formatWarsaw } from './lib/time.js'
import Calendar from './screens/Calendar.jsx'
import ModelInfo from './screens/ModelInfo.jsx'
import Standings from './screens/Standings.jsx'
import Weekend from './screens/Weekend.jsx'

const TABS = [
  { id: 'weekend', label: 'Weekend', Screen: Weekend },
  { id: 'standings', label: 'Klasyfikacje', Screen: Standings },
  { id: 'calendar', label: 'Kalendarz', Screen: Calendar },
  { id: 'model', label: 'Model', Screen: ModelInfo },
]

export default function App() {
  const [active, setActive] = useState('weekend')
  const { data: meta } = useData('meta.json')
  const { Screen } = TABS.find((tab) => tab.id === active)

  return (
    <div className="app">
      <header className="topbar">
        <h1>F1 Prediction App</h1>
        {meta && <p className="muted small">Dane z: {formatWarsaw(meta.generated_at)}</p>}
      </header>
      <main role="tabpanel" id="panel" aria-labelledby={`tab-${active}`}>
        <Screen />
      </main>
      <nav className="tabbar" role="tablist" aria-label="Sekcje aplikacji">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            role="tab"
            aria-selected={tab.id === active}
            aria-controls="panel"
            onClick={() => setActive(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  )
}
