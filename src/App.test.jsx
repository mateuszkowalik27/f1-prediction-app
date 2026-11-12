import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({ generated_at: '2027-04-01T12:00:00Z', season: 2027, data_sources: {} }),
  })))
})
afterEach(() => vi.unstubAllGlobals())

describe('App', () => {
  it('renders app title', () => {
    render(<App />)
    expect(screen.getByText('F1 Prediction App')).toBeInTheDocument()
  })

  it('switches screens with the bottom tabs', () => {
    render(<App />)
    expect(screen.getByRole('tab', { name: 'Weekend' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('tab', { name: 'Klasyfikacje' }))
    expect(screen.getByRole('tab', { name: 'Klasyfikacje' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('heading', { name: 'Klasyfikacje' })).toBeInTheDocument()
  })

  it('shows when the data was last updated, in Warsaw time', async () => {
    render(<App />)
    expect(await screen.findByText(/Dane z:.*14:00/)).toBeInTheDocument()
  })
})
