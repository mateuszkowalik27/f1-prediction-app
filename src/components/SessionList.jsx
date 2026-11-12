import { useState } from 'react'
import { SESSION_LABELS } from '../lib/labels.js'
import { formatWarsaw } from '../lib/time.js'
import ResultsTable from './ResultsTable.jsx'

// `results`: { [nazwaSesji]: { kind, rows } } albo null. Sesja z wynikami dostaje przycisk "Wyniki".
export default function SessionList({ sessions, results = null, nameById, numberById }) {
  const [open, setOpen] = useState(null)
  return (
    <ul className="list">
      {sessions.map((session) => {
        const table = results?.[session.name]
        const expanded = open === session.name
        return (
          <li key={session.name}>
            <div className="session-row">
              <span>{SESSION_LABELS[session.name] ?? session.name}</span>
              <span className="session-meta">
                <span className={session.start_utc ? '' : 'muted'}>{formatWarsaw(session.start_utc)}</span>
                {table && (
                  <button
                    className="results-toggle"
                    aria-expanded={expanded}
                    onClick={() => setOpen(expanded ? null : session.name)}
                  >
                    {expanded ? 'Ukryj' : 'Wyniki'}
                  </button>
                )}
              </span>
            </div>
            {table && expanded && <ResultsTable table={table} nameById={nameById} numberById={numberById} />}
          </li>
        )
      })}
    </ul>
  )
}
