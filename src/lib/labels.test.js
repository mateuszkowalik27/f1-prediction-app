import { describe, expect, it } from 'vitest'
import { factorLabel } from './labels.js'

describe('factorLabel', () => {
  it('has a Polish name for every model factor', () => {
    expect(factorLabel('car_pace')).toBe('siła bolidu')
    expect(factorLabel('quali_gap')).toBe('różnica czasów w kwalifikacjach')
  })

  it('falls back to the raw name for an unknown factor', () => {
    expect(factorLabel('something_new')).toBe('something_new')
  })
})
