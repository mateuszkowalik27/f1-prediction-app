import { describe, expect, it } from 'vitest'
import { shortName, teamColors, teamLogo } from './teams.js'

describe('shortName', () => {
  it('uses the first letter of the first name and the surname', () => {
    expect(shortName('Andrea Kimi Antonelli')).toBe('A. Antonelli')
    expect(shortName('Max Verstappen')).toBe('M. Verstappen')
    expect(shortName('Nico Hülkenberg')).toBe('N. Hülkenberg')
  })
  it('keeps a single word and handles empty input', () => {
    expect(shortName('Verstappen')).toBe('Verstappen')
    expect(shortName('')).toBe('')
    expect(shortName(undefined)).toBe('')
  })
})

describe('team assets', () => {
  const teams = ['ferrari', 'mercedes', 'red_bull', 'mclaren', 'aston_martin', 'alpine', 'williams', 'rb', 'haas', 'audi', 'cadillac']
  it('has a logo and a color for every 2026 team', () => {
    for (const t of teams) {
      expect(teamLogo(t), t).toBeTruthy()
      expect(teamColors(t)?.bg, t).toMatch(/^#[0-9A-F]{6}$/i)
    }
  })
  it('returns null for an unknown team', () => {
    expect(teamLogo('nope')).toBeNull()
    expect(teamColors('nope')).toBeNull()
  })
})
