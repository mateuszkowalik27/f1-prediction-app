import { driverCode } from '../lib/drivers.js'
import { prettifyId } from '../lib/labels.js'
import { shortName, teamColors, teamLogo } from '../lib/teams.js'

// Kierowca: numer w barwach zespołu, białe logo zespołu, "A. Nazwisko", a niżej szary skrót (ANT).
// `drivers`: wynik driverMaps(); bez danych o kierowcy pokazujemy to, co się da (nazwa z id).
export default function DriverCell({ id, drivers }) {
  const { nameById = {}, numberById = {}, teamById = {} } = drivers ?? {}
  const full = nameById[id] ?? prettifyId(id)
  const team = teamById[id]
  const colors = teamColors(team)
  const logo = teamLogo(team)
  return (
    <span className="driver">
      {numberById[id] != null && (
        <span
          className="car-no"
          title="Numer startowy"
          style={colors ? { background: colors.bg, color: colors.fg } : undefined}
        >
          {numberById[id]}
        </span>
      )}
      {logo ? <img className="team-logo" src={logo} alt="" /> : <span className="team-logo" />}
      <span className="driver-names" title={full}>
        <span className="driver-name">{shortName(full)}</span>
        <span className="driver-code">{driverCode(id, drivers ?? {})}</span>
      </span>
    </span>
  )
}
