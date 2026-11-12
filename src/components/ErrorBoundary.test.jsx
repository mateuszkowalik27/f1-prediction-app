import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ErrorBoundary from './ErrorBoundary.jsx'

afterEach(() => vi.restoreAllMocks())

const Boom = () => {
  throw new Error('zepsute dane')
}

describe('ErrorBoundary', () => {
  it('renders its children when nothing is wrong', () => {
    render(<ErrorBoundary><p>wszystko gra</p></ErrorBoundary>)
    expect(screen.getByText('wszystko gra')).toBeInTheDocument()
  })

  it('shows the error and a reset button instead of a blank screen', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<ErrorBoundary><Boom /></ErrorBoundary>)
    expect(screen.getByRole('alert')).toHaveTextContent('Coś poszło nie tak')
    expect(screen.getByText('zepsute dane')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Wyczyść i odśwież' })).toBeInTheDocument()
  })

  it('clears service workers and caches on reset, then reloads', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const unregister = vi.fn().mockResolvedValue(true)
    const del = vi.fn().mockResolvedValue(true)
    const reload = vi.fn()
    vi.stubGlobal('caches', { keys: async () => ['a', 'b'], delete: del })
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { getRegistrations: async () => [{ unregister }] } })
    vi.stubGlobal('location', { reload })
    render(<ErrorBoundary><Boom /></ErrorBoundary>)
    fireEvent.click(screen.getByRole('button', { name: 'Wyczyść i odśwież' }))
    await vi.waitFor(() => expect(reload).toHaveBeenCalled())
    expect(unregister).toHaveBeenCalledTimes(1)
    expect(del).toHaveBeenCalledTimes(2)
    vi.unstubAllGlobals()
  })
})
