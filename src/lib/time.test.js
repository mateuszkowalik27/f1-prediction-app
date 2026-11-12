import { describe, expect, it } from 'vitest'
import { TBC, formatWarsaw } from './time.js'

const HM = { hour: '2-digit', minute: '2-digit' }

describe('formatWarsaw', () => {
  it('tests run in a non-Polish timezone (so the result cannot depend on the device)', () => {
    expect(new Date('2027-07-04T13:00:00Z').getTimezoneOffset()).toBe(240) // Nowy Jork, lato
  })

  it('shows summer time (CEST, UTC+2)', () => {
    expect(formatWarsaw('2027-07-04T13:00:00Z', HM)).toBe('15:00')
  })

  it('shows winter time (CET, UTC+1)', () => {
    expect(formatWarsaw('2027-01-10T13:00:00Z', HM)).toBe('14:00')
  })

  it('handles the switch to summer time (2027-03-28)', () => {
    expect(formatWarsaw('2027-03-28T00:30:00Z', HM)).toBe('01:30') // jeszcze CET
    expect(formatWarsaw('2027-03-28T01:30:00Z', HM)).toBe('03:30') // już CEST
  })

  it('returns "do ustalenia" when the time is not set (TBC)', () => {
    expect(formatWarsaw(null)).toBe(TBC)
    expect(formatWarsaw(undefined, HM)).toBe('do ustalenia')
  })

  it('has a readable default format with weekday and day', () => {
    expect(formatWarsaw('2027-07-04T13:00:00Z')).toMatch(/niedz|ndz/i)
  })
})
