import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'
import { mockData } from './test/mockData.js'

beforeEach(() => mockData())
afterEach(() => vi.unstubAllGlobals())

describe('App', () => {
  it('renders app title', () => {
    render(<App />)
    expect(screen.getByText('F1 Prediction App')).toBeInTheDocument()
  })

  it('has exactly three tabs: Weekend, Klasyfikacje, Kalendarz (no Model tab)', () => {
    render(<App />)
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Weekend', 'Klasyfikacje', 'Kalendarz'])
  })

  it('switches screens with the bottom tabs', async () => {
    render(<App />)
    expect(screen.getByRole('tab', { name: 'Weekend' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('tab', { name: 'Klasyfikacje' }))
    expect(screen.getByRole('tab', { name: 'Klasyfikacje' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByRole('heading', { name: 'Klasyfikacje' })).toBeInTheDocument()
  })

  it('shows when the data was last updated, in Warsaw time', async () => {
    render(<App />)
    expect(await screen.findByText(/Dane z:.*14:00/)).toBeInTheDocument()
  })
})
