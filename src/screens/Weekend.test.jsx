import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockData, sampleWeekend } from '../test/mockData.js'
import Weekend from './Weekend.jsx'

afterEach(() => vi.unstubAllGlobals())

// Nazwy sesji powtarzają się na przełączniku (Wyścig, Kwalifikacje), więc szukamy wiersza listy.
const sessionRow = (label) => screen.getAllByText(label).map((el) => el.closest('li')).find(Boolean)

const withPayload = (change) => {
  const w = sampleWeekend()
  change(w.payload)
  return { 'weekend.json': w }
}

describe('Weekend screen', () => {
  it('shows sessions in Warsaw time', async () => {
    mockData()
    render(<Weekend />)
    await screen.findByText('Trening 1')
    expect(sessionRow('Trening 1')).toHaveTextContent('01:30') // 00:30 UTC w listopadzie = 01:30 w Polsce
    expect(sessionRow('Wyścig')).toHaveTextContent('05:00')
  })

  it('shows "do ustalenia" for a session without a time', async () => {
    mockData(withPayload((p) => { p.race.sessions[3].start_utc = null }))
    render(<Weekend />)
    await screen.findByText('Trening 1')
    expect(sessionRow('Kwalifikacje')).toHaveTextContent('do ustalenia')
  })

  it('shows a message when there is no weather forecast', async () => {
    mockData(withPayload((p) => { p.weather = null }))
    render(<Weekend />)
    expect(await screen.findByText(/Brak prognozy/)).toBeInTheDocument()
  })

  it('shows rain chance and temperature when there is a forecast', async () => {
    mockData()
    render(<Weekend />)
    expect(await screen.findByText(/8%/, { selector: '.weather *' })).toBeInTheDocument()
    expect(screen.getByText(/15 °C/)).toBeInTheDocument()
  })

  it('shows a low-data banner', async () => {
    mockData(withPayload((p) => { p.low_data = true }))
    render(<Weekend />)
    expect(await screen.findByText(/Mało danych/)).toBeInTheDocument()
  })

  it('shows a message instead of an empty screen when there is no upcoming race', async () => {
    mockData({ 'weekend.json': { status: 'no_upcoming_race', payload: null } })
    render(<Weekend />)
    expect(await screen.findByText(/Brak nadchodzącego wyścigu/)).toBeInTheDocument()
  })

  it('shows an error instead of crashing when the file has an unexpected shape', async () => {
    mockData({ 'weekend.json': { generated_at: '2027-04-01T12:00:00Z' } })
    render(<Weekend />)
    expect(await screen.findByText(/Nie udało się wczytać/)).toBeInTheDocument()
  })

  it('shows an error instead of crashing when a "ok" file has no payload', async () => {
    mockData({ 'weekend.json': { status: 'ok', payload: null } })
    render(<Weekend />)
    expect(await screen.findByText(/Nie udało się wczytać/)).toBeInTheDocument()
  })

  it('shows an error when the data cannot be loaded', async () => {
    mockData({ 'weekend.json': null })
    render(<Weekend />)
    expect(await screen.findByText(/Nie udało się wczytać/)).toBeInTheDocument()
  })

  it('formats probabilities as percent, sorted from the most likely', async () => {
    mockData()
    render(<Weekend />)
    await screen.findByText('Trening 1')
    const rows = screen.getAllByRole('row').slice(1) // bez nagłówka
    expect(rows.map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual([
      'Charles Leclerc', 'Andrea Kimi Antonelli', 'George Russell', 'Lando Norris',
    ])
    expect(rows[1]).toHaveTextContent('28%')
    expect(rows[3]).toHaveTextContent('<1%') // 0,4% to nie 0%
  })

  it('switches between race and qualifying predictions', async () => {
    mockData()
    render(<Weekend />)
    await screen.findByText('Trening 1')
    expect(screen.getByRole('button', { name: 'Wyścig' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Kwalifikacje' }))
    expect(screen.getByRole('button', { name: 'Kwalifikacje' })).toHaveAttribute('aria-pressed', 'true')
    const first = screen.getAllByRole('row')[1]
    expect(within(first).getAllByRole('cell')[0]).toHaveTextContent('Lando Norris')
    expect(screen.getByRole('columnheader', { name: 'Pole position' })).toBeInTheDocument()
  })

  it('warns when the lineup comes from the previous season', async () => {
    mockData(withPayload((p) => { p.lineup = 'previous_season' }))
    render(<Weekend />)
    expect(await screen.findByText(/Skład kierowców pochodzi z poprzedniego sezonu/)).toBeInTheDocument()
  })

  it('does not warn about the lineup when it is current', async () => {
    mockData()
    render(<Weekend />)
    await screen.findByText('Trening 1')
    expect(screen.queryByText(/Skład kierowców pochodzi/)).not.toBeInTheDocument()
  })

  it('says where the track data comes from (measured)', async () => {
    mockData()
    render(<Weekend />)
    expect(await screen.findByText(/wyliczona z historii \(5 wyścigów\)/)).toBeInTheDocument()
    expect(screen.getByText(/Profil zakrętów: z telemetrii/)).toBeInTheDocument()
  })

  it('labels defaults and estimates as such', async () => {
    mockData(withPayload((p) => { p.track_source = 'default'; p.track_sample_size = 0; p.profile_source = 'estimate' }))
    render(<Weekend />)
    expect(await screen.findByText(/wartości domyślne/)).toBeInTheDocument()
    expect(screen.getByText(/szacunek/)).toBeInTheDocument()
  })

  it('shows grid penalties with driver names', async () => {
    mockData(withPayload((p) => {
      p.grid_source = 'official'
      p.penalties = [{ driver_id: 'leclerc', from_pos: 3, to_pos: 13 }]
    }))
    render(<Weekend />)
    expect(await screen.findByText('Kary na starcie')).toBeInTheDocument()
    expect(screen.getByText('Charles Leclerc z 3. na 13.')).toBeInTheDocument()
  })

  it('falls back to a readable name for a driver missing from the standings', async () => {
    mockData(withPayload((p) => { p.penalties = [{ driver_id: 'max_verstappen', from_pos: 1, to_pos: 11 }] }))
    render(<Weekend />)
    expect(await screen.findByText('Max Verstappen z 1. na 11.')).toBeInTheDocument()
  })

  it('shows no penalty card when there are no penalties', async () => {
    mockData()
    render(<Weekend />)
    await screen.findByText('Trening 1')
    expect(screen.queryByText('Kary na starcie')).not.toBeInTheDocument()
  })

  it('still renders files from before penalties existed (no penalties field)', async () => {
    mockData(withPayload((p) => { delete p.penalties; delete p.grid_source }))
    render(<Weekend />)
    expect(await screen.findByText('Trening 1')).toBeInTheDocument()
    expect(screen.queryByText('Kary na starcie')).not.toBeInTheDocument()
  })

  it('shows the strategy and safety car odds', async () => {
    mockData()
    render(<Weekend />)
    expect(await screen.findByText(/1 pit-stop/)).toBeInTheDocument()
    expect(screen.getByText(/Safety car 49%/)).toBeInTheDocument()
    expect(screen.getByText(/VSC 54%/)).toBeInTheDocument()
  })
})
