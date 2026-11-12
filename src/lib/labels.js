// Polskie nazwy używane w interfejsie.
export const FACTOR_LABELS = {
  car_pace: 'siła bolidu',
  driver_form: 'forma kierowcy',
  track_history: 'historia toru',
  practice_pace: 'tempo z treningów',
  weekend_shift: 'zmiana formy w weekendzie',
  car_track_fit: 'dopasowanie bolidu do toru',
  wet_skill: 'jazda w deszczu',
  reliability: 'niezawodność',
  grid_base_weight: 'siła pozycji startowej',
  race_noise_base: 'poziom losowości',
}

export const SESSION_LABELS = {
  FP1: 'Trening 1',
  FP2: 'Trening 2',
  FP3: 'Trening 3',
  SprintQualifying: 'Kwalifikacje sprintu',
  Sprint: 'Sprint',
  Qualifying: 'Kwalifikacje',
  Race: 'Wyścig',
}

export const COMPOUND_LABELS = {
  SOFT: 'miękkie',
  MEDIUM: 'średnie',
  HARD: 'twarde',
  INTERMEDIATE: 'przejściowe',
  WET: 'deszczowe',
}

export const factorLabel = (name) => FACTOR_LABELS[name] ?? name

// 0,28 -> "28%", a coś możliwego, ale bardzo mało prawdopodobnego -> "<1%" (a nie mylące "0%")
export function pct(value) {
  if (value > 0 && value < 0.005) return '<1%'
  return `${Math.round(value * 100)}%`
}

// "max_verstappen" -> "Max Verstappen" (gdy nie znamy pełnego imienia i nazwiska)
export const prettifyId = (id) => id.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')

export function stopsLabel(n) {
  if (n === 1) return '1 pit-stop'
  return n >= 2 && n <= 4 ? `${n} pit-stopy` : `${n} pit-stopów`
}

// Liczba w polskim zapisie: 0.2 -> "0,20"
export const num = (value, digits = 2) =>
  value.toLocaleString('pl-PL', { minimumFractionDigits: digits, maximumFractionDigits: digits })

// Zmiany wag między dwiema ostatnimi rundami, np. "forma kierowcy: 0,20 → 0,27 po rundzie 14".
// Pomijamy wagi, które po zaokrągleniu wyglądają tak samo.
export function weightChanges(history) {
  if (!Array.isArray(history) || history.length < 2) return []
  const previous = history[history.length - 2]
  const last = history[history.length - 1]
  return Object.keys(last.weights)
    .filter((key) => key in previous.weights && num(previous.weights[key]) !== num(last.weights[key]))
    .map((key) => `${factorLabel(key)}: ${num(previous.weights[key])} → ${num(last.weights[key])} po rundzie ${last.round}`)
}
