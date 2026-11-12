import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockData } from '../test/mockData.js'
import Standings from './Standings.jsx'

afterEach(() => vi.unstubAllGlobals())

describe('Standings screen', () => {
  it('shows drivers first, with points and wins', async () => {
    mockData()
    render(<Standings />)
    const rows = (await screen.findAllByRole('row')).slice(1)
    expect(within(rows[0]).getAllByRole('cell').map((c) => c.textContent)).toEqual(['1', 'Andrea Kimi Antonelli', '100', '1'])
    expect(screen.getByRole('button', { name: 'Kierowcy' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('switches between drivers and constructors', async () => {
    mockData()
    render(<Standings />)
    await screen.findByText('Andrea Kimi Antonelli')
    fireEvent.click(screen.getByRole('button', { name: 'Zespoły' }))
    expect(screen.getByText('Mercedes')).toBeInTheDocument()
    expect(screen.queryByText('Andrea Kimi Antonelli')).not.toBeInTheDocument()
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
