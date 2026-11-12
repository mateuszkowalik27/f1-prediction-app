import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useData } from './data.js'

afterEach(() => vi.unstubAllGlobals())

describe('useData', () => {
  it('loads JSON from /data/<file>', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({ hello: 'world' }) }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useData('meta.json'))
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toEqual({ hello: 'world' })
    expect(fetchMock.mock.calls[0][0]).toBe('/data/meta.json')
  })

  it('reports an error when the file is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404 })))
    const { result } = renderHook(() => useData('nope.json'))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toBeNull()
    expect(result.current.error).toBeInstanceOf(Error)
  })
})
