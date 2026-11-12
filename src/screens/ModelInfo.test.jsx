import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockData, sampleModel } from '../test/mockData.js'
import ModelInfo from './ModelInfo.jsx'

afterEach(() => vi.unstubAllGlobals())

const factorRow = (label) => screen.getByText(label).closest('li')

describe('Model screen', () => {
  it('lists used and skipped factors with their weights', async () => {
    mockData()
    render(<ModelInfo />)
    await screen.findByText('siła bolidu')
    expect(factorRow('siła bolidu')).toHaveTextContent('0,26')
    expect(factorRow('siła bolidu')).toHaveTextContent('używany')
    expect(factorRow('tempo z treningów')).toHaveTextContent('brak danych')
  })

  it('shows how a weight changed between the last two rounds', async () => {
    mockData()
    render(<ModelInfo />)
    expect(await screen.findByText('forma kierowcy: 0,20 → 0,27 po rundzie 14')).toBeInTheDocument()
    expect(screen.getByText('niezawodność: 0,21 → 0,25 po rundzie 14')).toBeInTheDocument()
    expect(screen.queryByText(/siła bolidu: /)).not.toBeInTheDocument() // niezmieniona
  })

  it('does not invent weight changes when there is a single snapshot', async () => {
    const model = sampleModel()
    model.weight_history = model.weight_history.slice(-1)
    mockData({ 'model.json': model })
    render(<ModelInfo />)
    await screen.findByText('siła bolidu')
    expect(screen.queryByText(/po rundzie/)).not.toBeInTheDocument()
  })

  it('does not compare weights across different seasons', async () => {
    const model = sampleModel()
    model.weight_history = [
      { ...model.weight_history[0], season: 2026, round: 24 },
      { ...model.weight_history[1], season: 2027, round: 3 },
    ]
    mockData({ 'model.json': model })
    render(<ModelInfo />)
    await screen.findByText('siła bolidu')
    expect(screen.queryByText(/po rundzie/)).not.toBeInTheDocument()
  })

  it('shows the predictions the user actually saw, scored after the race', async () => {
    const model = sampleModel()
    model.live_evaluation = [{ round: 15, winner_prob: 0.21, winner_in_top3: true, mean_abs_position_error: 3.4, brier_win: 0.04 }]
    mockData({ 'model.json': model })
    render(<ModelInfo />)
    expect(await screen.findByText('Przewidywania, które faktycznie widziałeś')).toBeInTheDocument()
    expect(screen.getByText('21%')).toBeInTheDocument()
  })

  it('hides the "seen predictions" section until there are any', async () => {
    mockData()
    render(<ModelInfo />)
    await screen.findByText('siła bolidu')
    expect(screen.queryByText('Przewidywania, które faktycznie widziałeś')).not.toBeInTheDocument()
  })

  it('shows evaluation rows and an average', async () => {
    mockData()
    render(<ModelInfo />)
    await screen.findByText('siła bolidu')
    const table = screen.getByRole('table')
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    expect(rows[1]).toHaveTextContent('13')
    expect(rows[1]).toHaveTextContent('5%')
    expect(rows[1]).toHaveTextContent('nie')
    expect(screen.getByText(/w trójce faworytów: 2 z 3/)).toBeInTheDocument()
  })

  it('shows an empty state when there is no evaluation yet', async () => {
    mockData({ 'model.json': { ...sampleModel(), evaluation: [], weight_history: [] } })
    render(<ModelInfo />)
    expect(await screen.findByText(/Ocena pojawi się/)).toBeInTheDocument()
  })

  it('shows an error when the data cannot be loaded', async () => {
    mockData({ 'model.json': null })
    render(<ModelInfo />)
    expect(await screen.findByText(/Nie udało się wczytać/)).toBeInTheDocument()
  })
})
