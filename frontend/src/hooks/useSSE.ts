export function useSSE(url: string, onMessage: (data: unknown) => void) {
  const connect = (body: unknown) => {
    // SSE usually uses GET, but for chat we often need POST
    // Standard EventSource only supports GET.
    // For this implementation, we'll use fetch with ReadableStream to simulate SSE
    // or use a library like @microsoft/fetch-event-source
    
    // Let's implement a simple fetch-based reader for SSE
    
    const fetchData = async () => {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
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
        console.error('SSE Error:', error)
        onMessage({ type: 'error', content: String(error) })
      }
    }

    fetchData()
  }

  return { connect }
}
