import { useRef } from "react"

export function useSSE(onMessage: (data: unknown) => void) {
  const abortControllerRef = useRef<AbortController | null>(null)

  const connect = (url: string, body: unknown) => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    const fetchData = async () => {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        if (!reader) return

        while (true) {
          const { value, done } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6)
              try {
                const parsed = JSON.parse(data)
                onMessage(parsed)
              } catch (e) {
                console.error('Error parsing SSE data:', e)
              }
            }
          }
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        console.error('SSE Error:', error)
        onMessage({ type: 'error', content: String(error) })
      }
    }

    fetchData()
  }

  const disconnect = () => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
  }

  return { connect, disconnect }
}
