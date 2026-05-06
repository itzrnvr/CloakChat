import { useRef } from "react"
import { fetchEventSource } from "@microsoft/fetch-event-source"

export function useSSE(onMessage: (data: unknown) => void) {
  const abortControllerRef = useRef<AbortController | null>(null)
  const handledTerminalEventRef = useRef(false)

  const connect = (url: string, body: unknown) => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller
    handledTerminalEventRef.current = false

    void fetchEventSource(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
      openWhenHidden: true,
      async onopen(response: Response) {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        const contentType = response.headers.get("content-type") || ""
        if (!contentType.includes("text/event-stream")) {
          throw new Error(`Expected text/event-stream but got ${contentType}`)
        }
      },
      onmessage(event: { data: string }) {
        if (!event.data) return
        try {
          const parsed = JSON.parse(event.data) as { type?: string }
          if (parsed?.type === "clarification_required" || parsed?.type === "done" || parsed?.type === "error") {
            handledTerminalEventRef.current = true
          }
          onMessage(parsed)
        } catch (error) {
          console.error("SSE parse error:", error, event.data)
        }
      },
      onclose() {
        // Clarification and done naturally end the stream. Don't surface this as an error.
        if (handledTerminalEventRef.current || controller.signal.aborted) {
          return
        }
        onMessage({ type: "error", content: "Connection closed before completion." })
      },
      onerror(error: unknown) {
        if (controller.signal.aborted || handledTerminalEventRef.current) {
          return
        }
        throw error
      },
    }).catch((error: unknown) => {
      if (error instanceof DOMException && error.name === "AbortError") {
        return
      }
      console.error("SSE Error:", error)
      onMessage({ type: "error", content: String(error) })
    })
  }

  const disconnect = () => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
  }

  return { connect, disconnect }
}
