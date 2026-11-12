import { useEffect, useState } from 'react'

// Wczytuje plik JSON z /data/ (generowany przez robota). Zwraca { data, error, loading }.
export function useData(file) {
  const [state, setState] = useState({ data: null, error: null, loading: true })

  useEffect(() => {
    let cancelled = false
    setState({ data: null, error: null, loading: true })
    fetch(`${import.meta.env.BASE_URL}data/${file}`, { cache: 'no-cache' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
      })
      .then((data) => !cancelled && setState({ data, error: null, loading: false }))
      .catch((error) => !cancelled && setState({ data: null, error, loading: false }))
    return () => {
      cancelled = true
    }
  }, [file])

  return state
}
