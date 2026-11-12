import { SESSION_LABELS } from '../lib/labels.js'
import { formatWarsaw } from '../lib/time.js'

export default function SessionList({ sessions }) {
  return (
    <ul className="list">
      {sessions.map((session) => (
        <li key={session.name}>
          <span>{SESSION_LABELS[session.name] ?? session.name}</span>
          <span className={session.start_utc ? '' : 'muted'}>{formatWarsaw(session.start_utc)}</span>
        </li>
      ))}
    </ul>
  )
}
