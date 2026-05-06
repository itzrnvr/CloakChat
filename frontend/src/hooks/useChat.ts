import { useRef } from "react"
import { useAppStore } from "@/stores/appStore"
import { useSSE } from "./useSSE"
import type { ClarificationItem, ClarificationSelection } from "@/types"

export function useChat() {
  const {
    addMessage,
    startAssistantMessage,
    appendToLastAssistantMessage,
    replaceLastAssistantMessage,
    addTraceEvent,
    setStatus,
    status,
    startNewRequest,
    setCloudStreamingContent,
    appendCloudStreamingContent,
    updateSession,
    anonymizedHistory,
    entityMap,
    currentSessionId,
    setCurrentSessionId,
    setSessions,
    setPendingClarification,
    clearPendingClarification,
  } = useAppStore()

  // Capture anonymized message and new entity entries mid-stream
  const anonymizedMsgRef = useRef<string>("")
  const newEntriesRef = useRef<Record<string, string>>({})
  const anonymizedResponseRef = useRef<string>("")
  const assistantMessageStartedRef = useRef<boolean>(false)

  const { connect, disconnect } = useSSE((data: unknown) => {
    const event = data as Record<string, unknown>

    switch (event.type) {
      case 'detection':
      case 'detection_reasoning':
      case 'step':
        addTraceEvent({
          id: crypto.randomUUID(),
          type: event.type as string,
          content: event,
          timestamp: new Date().toISOString()
        })
        if (event.type === 'step') {
          setStatus('processing', event.content as string)
        }
        break

      case 'heartbeat':
        setStatus('processing', event.content as string)
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
      case 'cloud_prompt':
        addTraceEvent({
          id: crypto.randomUUID(),
          type: event.type as string,
          content: event,
          timestamp: new Date().toISOString()
        })
        break

      case 'cloud_chunk':
        anonymizedResponseRef.current += event.content as string
        if (!assistantMessageStartedRef.current) {
          startAssistantMessage({
            role: 'assistant',
            content: event.content as string,
            timestamp: new Date().toISOString()
          })
          assistantMessageStartedRef.current = true
        } else {
          appendToLastAssistantMessage(event.content as string)
        }
        appendCloudStreamingContent(event.content as string)
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'cloud_chunk',
          content: event.content,
          timestamp: new Date().toISOString()
        })
        break

      case 'cloud_reasoning_chunk':
        setStatus('processing', 'Model is reasoning...')
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'cloud_reasoning_chunk',
          content: event,
          timestamp: new Date().toISOString()
        })
        break

      case 'reconstruction':
        if (assistantMessageStartedRef.current) {
          replaceLastAssistantMessage(event.text as string)
        } else {
          addMessage({
            role: 'assistant',
            content: event.text as string,
            timestamp: new Date().toISOString()
          })
        }
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'reconstruction',
          content: event,
          timestamp: new Date().toISOString()
        })
        break

      case 'reconstruction_verification':
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'reconstruction_verification',
          content: event,
          timestamp: new Date().toISOString()
        })
        break

      case 'entity_map_update':
        newEntriesRef.current = (event.new_entries as Record<string, string>) ?? {}
        break

      case 'clarification_required': {
        const store = useAppStore.getState()
        const currentGroup = store.traceGroups.find(g => g.id === store.currentRequestId)
        const rawItems = Array.isArray(event.clarifications)
          ? event.clarifications as Record<string, unknown>[]
          : [event]
        const items: ClarificationItem[] = rawItems.map((item) => ({
          entity: item.entity as string,
          entityType: item.entity_type as string,
          reason: item.reason as string | undefined,
          question: item.question as string,
          suggestedReplacement: item.suggested_replacement as string | undefined,
          options: (item.options as ClarificationItem["options"]) ?? [],
        }))
        const first = items[0]
        setPendingClarification({
          requestId: store.currentRequestId ?? crypto.randomUUID(),
          message: currentGroup?.userMessage || "",
          ...first,
          items,
        })
        setStatus(
          'awaiting_clarification',
          items.length > 1
            ? `Waiting for ${items.length} clarifications`
            : `Waiting for clarification about ${first.entity}`
        )
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'clarification_required',
          content: event,
          timestamp: new Date().toISOString()
        })
        // Clarification is a terminal event for this stream; stop SSE cleanly.
        disconnect()
        break
      }

      case 'playbook_updated':
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'playbook_updated',
          content: event,
          timestamp: new Date().toISOString()
        })
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
        assistantMessageStartedRef.current = false

        clearPendingClarification()
        setStatus('ready')
        addTraceEvent({
          id: crypto.randomUUID(),
          type: 'done',
          content: null,
          timestamp: new Date().toISOString()
        })

        // Auto-save session — read fresh state from store to avoid stale closures
        const store = useAppStore.getState()
        let sid = store.currentSessionId
        if (!sid) {
          sid = crypto.randomUUID()
          setCurrentSessionId(sid)
        }
        const msgs = store.messages
        const title = msgs.length > 0
          ? msgs[0].content.slice(0, 40)
          : "New Session"
        const sessionData = {
          id: sid,
          title,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          messages: msgs,
          anonymizedHistory: store.anonymizedHistory,
          entityMap: store.entityMap,
          traceGroups: store.traceGroups,
        }
        console.log("[auto-save] sending session", sid, title)
        fetch("/api/sessions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(sessionData),
          keepalive: true,
        }).then(async res => {
          if (!res.ok) {
            const text = await res.text()
            throw new Error(`HTTP ${res.status}: ${text}`)
          }
          const saved = await res.json()
          console.log("[auto-save] success", saved.id)
          const currentSessions = useAppStore.getState().sessions
          const summary = { id: saved.id, title: saved.title, createdAt: saved.createdAt, updatedAt: saved.updatedAt }
          const exists = currentSessions.some(s => s.id === saved.id)
          if (!exists) {
            setSessions([...currentSessions, summary])
          } else {
            setSessions(currentSessions.map(s => s.id === saved.id ? summary : s))
          }
        }).catch(err => {
          console.error("[auto-save] failed", err)
        })
        break

      case 'error':
        assistantMessageStartedRef.current = false
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
    if (status === 'processing' || status === 'awaiting_clarification') return

    // Ensure we have a session ID
    if (!currentSessionId) {
      setCurrentSessionId(crypto.randomUUID())
    }

    const requestId = crypto.randomUUID()
    startNewRequest(requestId, content)
    setCloudStreamingContent("")
    assistantMessageStartedRef.current = false

    addMessage({
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    })

    setStatus('processing')
    connect('/api/chat', {
      request_id: requestId,
      message: content,
      history: anonymizedHistory,
      entity_map: entityMap,
    })
  }

  const submitClarification = (answers: ClarificationSelection[], remember: boolean) => {
    const store = useAppStore.getState()
    const clarification = store.pendingClarification
    if (!clarification) return

    clearPendingClarification()
    setStatus('processing', answers.length > 1 ? "Applying clarifications" : `Applying clarification for ${answers[0]?.item.entity}`)
    setCloudStreamingContent("")

    connect('/api/chat/clarify', {
      request_id: clarification.requestId,
      message: clarification.message,
      history: store.anonymizedHistory,
      entity_map: store.entityMap,
      clarifications: answers.map(({ item, option }) => ({
        original: item.entity,
        entity_type: item.entityType,
        action: option.action,
        resolution: option.resolution,
        replacement: item.suggestedReplacement || "",
        remember,
      })),
    })
  }

  const stopGeneration = () => {
    disconnect()
    setStatus('ready')

    // Reset turn-local refs since this turn is abandoned
    anonymizedMsgRef.current = ""
    anonymizedResponseRef.current = ""
    newEntriesRef.current = {}
    assistantMessageStartedRef.current = false
    setCloudStreamingContent("")
    clearPendingClarification()
  }

  const saveSession = () => {
    const store = useAppStore.getState()
    let sid = store.currentSessionId
    if (!sid) {
      sid = crypto.randomUUID()
      setCurrentSessionId(sid)
    }
    const msgs = store.messages
    const title = msgs.length > 0
      ? msgs[0].content.slice(0, 40)
      : "New Session"
    const sessionData = {
      id: sid,
      title,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages: store.messages,
      anonymizedHistory: store.anonymizedHistory,
      entityMap: store.entityMap,
      traceGroups: store.traceGroups,
    }
    fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sessionData),
    }).then(async res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const saved = await res.json()
      const currentSessions = useAppStore.getState().sessions
      const summary = { id: saved.id, title: saved.title, createdAt: saved.createdAt, updatedAt: saved.updatedAt }
      const exists = currentSessions.some(s => s.id === saved.id)
      if (!exists) {
        setSessions([...currentSessions, summary])
      } else {
        setSessions(currentSessions.map(s => s.id === saved.id ? summary : s))
      }
    }).catch(console.error)
  }

  return { sendMessage, stopGeneration, saveSession, submitClarification }
}
