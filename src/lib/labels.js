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
  quali_gap: 'różnica czasów w kwalifikacjach',
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

export const TRACK_SOURCE = {
  computed: (n) => `wyliczona z historii (${n === 1 ? '1 wyścig' : n >= 2 && n <= 4 ? `${n} wyścigi` : `${n} wyścigów`})`,
  default: () => 'wartości domyślne (brak historii toru)',
  manual: () => 'ustawiona ręcznie',
}

export const PROFILE_SOURCE = {
  telemetry: 'z telemetrii',
  estimate: 'szacunek (nie dane oficjalne)',
  manual: 'ustawiony ręcznie',
}
