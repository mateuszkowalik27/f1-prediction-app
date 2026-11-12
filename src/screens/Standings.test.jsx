import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockData, sampleStandings } from '../test/mockData.js'
import Standings from './Standings.jsx'

afterEach(() => vi.unstubAllGlobals())

describe('Standings screen', () => {
  it('shows drivers first, with points and wins', async () => {
    mockData()
    render(<Standings />)
    const rows = (await screen.findAllByRole('row')).slice(1)
    expect(within(rows[0]).getAllByRole('cell').map((c) => c.textContent)).toEqual(['1', 'A. AntonelliANT', '100', '1'])
    expect(screen.getByRole('button', { name: 'Kierowcy' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('switches between drivers and constructors', async () => {
    mockData()
    render(<Standings />)
    await screen.findByText('A. Antonelli')
    fireEvent.click(screen.getByRole('button', { name: 'Zespoły' }))
    expect(screen.getByText('Mercedes')).toBeInTheDocument()
    expect(screen.queryByText('A. Antonelli')).not.toBeInTheDocument()
  })

  it('shows the team logo and color bar for constructors', async () => {
    mockData()
    render(<Standings />)
    await screen.findByText('A. Antonelli')
    fireEvent.click(screen.getByRole('button', { name: 'Zespoły' }))
    const row = screen.getByText('Mercedes').closest('tr')
    expect(row.querySelector('img.team-logo')).not.toBeNull()
    expect(row.querySelector('.team-bar').style.background).not.toBe('')
  })

  it('names the season when the table is not from the current one', async () => {
    mockData({ 'standings.json': { ...sampleStandings(), season: 2026 } })
    render(<Standings />)
    expect(await screen.findByRole('heading', { name: 'Klasyfikacje 2026' })).toBeInTheDocument()
  })

  it('explains an empty table at the start of the season', async () => {
    mockData({ 'standings.json': { drivers: [], constructors: [] } })
    render(<Standings />)
    expect(await screen.findByText(/pierwszym wyścigu/)).toBeInTheDocument()
  })

  it('shows an error when the data cannot be loaded', async () => {
    mockData({ 'standings.json': null })
    render(<Standings />)
    expect(await screen.findByText(/Nie udało się wczytać/)).toBeInTheDocument()
  })
})
