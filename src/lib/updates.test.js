import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setupUpdates } from './updates.js'

// Atrapa document: zdarzenia + stan widoczności.
function fakeDoc() {
  const doc = new EventTarget()
  doc.visibilityState = 'hidden'
  return doc
}

function setup() {
  let options
  const register = vi.fn((opts) => { options = opts })
  const registration = { update: vi.fn(() => Promise.resolve()) }
  const doc = fakeDoc()
  setupUpdates(register, doc, 1000)
  options.onRegisteredSW('/sw.js', registration)
  return { register, registration, doc, options }
}

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('setupUpdates', () => {
  it('registers the service worker immediately', () => {
    const { register } = setup()
    expect(register).toHaveBeenCalledWith(expect.objectContaining({ immediate: true }))
  })

  it('checks for a new version when the app comes back to the foreground', () => {
    const { registration, doc } = setup()
    doc.visibilityState = 'visible'
    doc.dispatchEvent(new Event('visibilitychange'))
    expect(registration.update).toHaveBeenCalledTimes(1)
  })

  it('does not check when the app goes to the background', () => {
    const { registration, doc } = setup()
    doc.visibilityState = 'hidden'
    doc.dispatchEvent(new Event('visibilitychange'))
    expect(registration.update).not.toHaveBeenCalled()
  })

  it('also checks periodically while the app stays open', () => {
    const { registration } = setup()
    vi.advanceTimersByTime(3500)
    expect(registration.update).toHaveBeenCalledTimes(3)
  })

  it('survives a failing update check (no internet)', async () => {
    const { registration, doc } = setup()
    registration.update.mockRejectedValue(new Error('offline'))
    doc.visibilityState = 'visible'
    expect(() => doc.dispatchEvent(new Event('visibilitychange'))).not.toThrow()
    await Promise.resolve()
  })

  it('ignores a missing registration', () => {
    let options
    setupUpdates((o) => { options = o }, fakeDoc(), 1000)
    expect(() => options.onRegisteredSW('/sw.js', undefined)).not.toThrow()
  })
})
