import { vi } from 'vitest'
import standings from './standings.sample.json'
import weekend from './weekend.sample.json'

// Podstawia fetch zwracający pliki JSON z /data/. `overrides`: { 'weekend.json': {...} } albo funkcja zwracająca błąd.
export function mockData(overrides = {}) {
  const meta = { generated_at: '2027-04-01T12:00:00Z', season: 2027, data_sources: {} }
  const files = { 'weekend.json': weekend, 'standings.json': standings, 'meta.json': meta, ...overrides }
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    const name = String(url).split('/data/')[1]
    if (!(name in files) || files[name] === null) return { ok: false, status: 404 }
    return { ok: true, json: async () => structuredClone(files[name]) }
  }))
}

export const sampleWeekend = () => structuredClone(weekend)
