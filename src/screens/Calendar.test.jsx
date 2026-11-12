import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockData } from '../test/mockData.js'
import Calendar from './Calendar.jsx'

afterEach(() => vi.unstubAllGlobals())

const roundButton = (name) => screen.getByRole('button', { name: new RegExp(name) })

describe('Calendar screen', () => {
  it('lists all rounds in order', async () => {
    mockData()
    render(<Calendar />)
    await screen.findByText(/Australian Grand Prix/)
    const buttons = screen.getAllByRole('button')
    expect(buttons.map((b) => b.textContent)).toEqual([
      expect.stringContaining('Australian'), expect.stringContaining('Chinese'), expect.stringContaining('Japanese'),
    ])
  })

  it('marks sprint rounds', async () => {
    mockData()
    render(<Calendar />)
    await screen.findByText(/Chinese Grand Prix/)
    expect(roundButton('Chinese')).toHaveTextContent('Sprint')
    expect(roundButton('Australian')).not.toHaveTextContent('Sprint')
  })

  it('expands the sessions of a round on click, in Warsaw time', async () => {
    mockData()
    render(<Calendar />)
    await screen.findByText(/Australian Grand Prix/)
    expect(roundButton('Australian')).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(roundButton('Australian'))
    expect(roundButton('Australian')).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Trening 1').closest('li')).toHaveTextContent('02:30') // 01:30 UTC, zima w Polsce
  })

  it('shows "do ustalenia" for rounds without session times', async () => {
    mockData()
    render(<Calendar />)
    await screen.findByText(/Japanese Grand Prix/)
    expect(roundButton('Japanese')).toHaveTextContent('do ustalenia')
    fireEvent.click(roundButton('Japanese'))
    expect(screen.getByText('Kwalifikacje').closest('li')).toHaveTextContent('do ustalenia')
  })

  it('shows an error when the calendar cannot be loaded', async () => {
    mockData({ 'calendar.json': null })
    render(<Calendar />)
    expect(await screen.findByText(/Nie udało się wczytać/)).toBeInTheDocument()
  })
})
