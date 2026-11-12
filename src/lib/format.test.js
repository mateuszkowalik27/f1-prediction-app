import { describe, expect, it } from 'vitest'
import { formatLap, formatRaceResult } from './format.js'

describe('formatLap', () => {
  it('formats minutes with a decimal comma', () => {
    expect(formatLap(79.5)).toBe('1:19,500')
    expect(formatLap(90.939)).toBe('1:30,939')
    expect(formatLap(60)).toBe('1:00,000')
  })
  it('formats sub-minute times and missing values', () => {
    expect(formatLap(24.394)).toBe('24,394')
    expect(formatLap(null)).toBe('–')
  })
})

describe('formatRaceResult', () => {
  it('shows the winner time and gaps with a decimal comma', () => {
    expect(formatRaceResult({ time: '1:35:23.504', status: 'Finished' }).text).toBe('1:35:23,504')
    expect(formatRaceResult({ time: '+14.602', status: 'Finished' }).text).toBe('+14,602')
  })
  it('shows laps down', () => {
    expect(formatRaceResult({ time: null, status: '+1 Lap' }).text).toBe('+1 okr.')
    expect(formatRaceResult({ time: null, status: '+2 Laps' }).text).toBe('+2 okr.')
  })
  it('shows DNF with the reason, and DSQ / DNS', () => {
    expect(formatRaceResult({ time: null, status: 'Engine' })).toEqual({ text: 'DNF', reason: 'Engine' })
    expect(formatRaceResult({ time: null, status: 'Disqualified' }).text).toBe('DSQ')
    expect(formatRaceResult({ time: null, status: 'Did not start' }).text).toBe('DNS')
  })
})
