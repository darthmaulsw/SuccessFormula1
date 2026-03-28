import { useState, useEffect, useRef } from 'react'

const SSE_URL = '/stream'
const RECONNECT_DELAY = 3000

/**
 * Connects to the backend SSE /stream endpoint.
 * Auto-reconnects on disconnect.
 * Returns { state, connected, lastUpdated }
 */
export function useSSE() {
  const [state, setState] = useState(null)
  const [connected, setConnected] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const esRef = useRef(null)
  const reconnectTimer = useRef(null)

  function connect() {
    if (esRef.current) esRef.current.close()

    const es = new EventSource(SSE_URL)
    esRef.current = es

    es.onopen = () => {
      setConnected(true)
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setState(data)
        setLastUpdated(new Date())
      } catch (err) {
        console.error('[SSE] Parse error', err)
      }
    }

    es.onerror = () => {
      setConnected(false)
      es.close()
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY)
    }
  }

  useEffect(() => {
    connect()
    return () => {
      if (esRef.current) esRef.current.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [])

  return { state, connected, lastUpdated }
}
