import { fireEvent, render, screen, within } from '@testing-library/react'
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

  describe('session results', () => {
    const results = {
      season: 2027, round: 1, generated_at: '2027-03-15T12:00:00Z',
      sessions: {
        FP1: { kind: 'practice', rows: [{ driver_id: 'antonelli', position: 1, best_s: 79.5 }] },
        Qualifying: { kind: 'qualifying', rows: [
          { driver_id: 'antonelli', position: 1, q1: 80.1, q2: 79.4, q3: 78.9 },
          { driver_id: 'russell', position: 2, q1: 80.9, q2: null, q3: null },
        ] },
        Race: { kind: 'race', rows: [
          { driver_id: 'antonelli', position: 1, time: '1:30:00.123', status: 'Finished', points: 25 },
          { driver_id: 'russell', position: 2, time: '+5.123', status: 'Finished', points: 18 },
          { driver_id: 'leclerc', position: 3, time: null, status: 'Engine', points: 0 },
        ] },
      },
    }
    const open = async (files) => {
      mockData(files)
      render(<Calendar />)
      await screen.findByText(/Australian Grand Prix/)
      fireEvent.click(roundButton('Australian'))
    }

    it('offers results only for sessions that have them', async () => {
      await open({ 'results/2027-1.json': results })
      await screen.findAllByRole('button', { name: 'Wyniki' })
      expect(screen.getAllByRole('button', { name: 'Wyniki' })).toHaveLength(3)
      expect(screen.getByText('Trening 2').closest('li')).not.toHaveTextContent('Wyniki')
    })

    it('shows practice best times', async () => {
      await open({ 'results/2027-1.json': results })
      fireEvent.click(within(await screen.findByText('Trening 1').then((e) => e.closest('li'))).getByRole('button', { name: 'Wyniki' }))
      expect(screen.getByText('1:19,500')).toBeInTheDocument()
    })

    it('shows Q1, Q2 and Q3, with dashes where the driver dropped out', async () => {
      await open({ 'results/2027-1.json': results })
      const li = (await screen.findByText('Kwalifikacje')).closest('li')
      fireEvent.click(within(li).getByRole('button', { name: 'Wyniki' }))
      expect(within(li).getByText('Q3')).toBeInTheDocument()
      expect(within(li).getByText('1:18,900')).toBeInTheDocument()
      expect(within(li).getAllByText('–')).toHaveLength(2)
      expect(within(li).getByText('+0,800')).toBeInTheDocument()   // Russell w Q1: 80,9 - 80,1 (strata do lidera części)
    })

    it('shows race times, gaps and the reason for retiring', async () => {
      await open({ 'results/2027-1.json': results })
      const li = (await screen.findByText('Wyścig')).closest('li')
      fireEvent.click(within(li).getByRole('button', { name: 'Wyniki' }))
      expect(within(li).getByText('A. Antonelli')).toBeInTheDocument()   // wyżej: pierwsza litera imienia i nazwisko
      expect(within(li).getByText('ANT')).toBeInTheDocument()            // niżej: oficjalny skrót
      expect(within(li).getByText('RUS')).toBeInTheDocument()            // brak kodu w danych: trzy litery nazwiska
      expect(within(li).getByText('1:30:00,123')).toBeInTheDocument()
      expect(within(li).getByText('+5,123')).toBeInTheDocument()
      expect(within(li).getByText('DNF')).toBeInTheDocument()
      expect(within(li).getByText('Engine')).toBeInTheDocument()
      expect(within(li).getByText('Pkt')).toBeInTheDocument()
      expect(within(li).getByText('25')).toBeInTheDocument()
      expect(within(li).getByText('18')).toBeInTheDocument()
    })

    it('keeps the plain schedule when there is no results file', async () => {
      await open({})
      await screen.findByText('Trening 1')
      expect(screen.queryByRole('button', { name: 'Wyniki' })).not.toBeInTheDocument()
    })
  })
})
