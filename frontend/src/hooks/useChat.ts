import { useRef } from "react"
import { useAppStore } from "@/stores/appStore"
import { useSSE } from "./useSSE"

export function useChat() {
  const {
    addMessage,
    addTraceEvent,
    setStatus,
    status,
    startNewRequest,
    setCloudStreamingContent,
    appendCloudStreamingContent,
    updateSession,
    anonymizedHistory,
    entityMap,
  } = useAppStore()

  // Capture anonymized message and new entity entries mid-stream
  const anonymizedMsgRef = useRef<string>("")
  const newEntriesRef = useRef<Record<string, string>>({})
  const anonymizedResponseRef = useRef<string>("")

  const { connect } = useSSE('/api/chat', (data: unknown) => {
    const event = data as Record<string, unknown>

    switch (event.type) {
      case 'detection':
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'detection',
          content: event,
          timestamp: new Date().toISOString()
        })
        break

      case 'anonymized':
        anonymizedMsgRef.current = event.text as string
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'anonymized',
          content: event,
          timestamp: new Date().toISOString()
        })
        break

      case 'validation':
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'validation',
          content: event,
          timestamp: new Date().toISOString()
        })
        break

      case 'cloud_chunk':
        anonymizedResponseRef.current += event.content as string
        appendCloudStreamingContent(event.content as string)
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'cloud_chunk',
          content: event.content,
          timestamp: new Date().toISOString()
        })
        break

      case 'reconstruction':
        addMessage({
          role: 'assistant',
          content: event.text as string,
          timestamp: new Date().toISOString()
        })
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'reconstruction',
          content: event,
          timestamp: new Date().toISOString()
        })
        break

      case 'entity_map_update':
        newEntriesRef.current = (event.new_entries as Record<string, string>) ?? {}
        break

      case 'done':
        // Commit this turn to session history
        updateSession(
          anonymizedMsgRef.current,
          anonymizedResponseRef.current,
          newEntriesRef.current,
        )
        // Reset turn-local refs
        anonymizedMsgRef.current = ""
        anonymizedResponseRef.current = ""
        newEntriesRef.current = {}

        setStatus('ready')
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'done',
          content: null,
          timestamp: new Date().toISOString()
        })
        break

      case 'error':
        setStatus('error', event.content as string)
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'error',
          content: event.content,
          timestamp: new Date().toISOString()
        })
        break
    }
  })

  const sendMessage = (content: string) => {
    if (status === 'processing') return

    const requestId = crypto.randomUUID()
    startNewRequest(requestId, content)
    setCloudStreamingContent("")

    addMessage({
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    })

    setStatus('processing')
    connect({
      message: content,
      history: anonymizedHistory,
      entity_map: entityMap,
    })
  }

  return { sendMessage }
}
