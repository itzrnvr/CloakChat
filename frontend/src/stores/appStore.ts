import { create } from 'zustand'
import type { AppState, TraceGroup, AppConfig, Session, SessionSummary } from '@/types'

const DEFAULT_CONFIG: AppConfig = {
  detection: {
    provider_type: "openai",
    base_url: "http://moonhowler.local:8000/v1",
    model_id: "Qwen3.5-2B-Q6_K.gguf",
    api_key: "",
    temperature: 0.1,
    timeout: 30,
    max_tokens: 1024,
    output_mode: "tool"
  },
  cloud: {
    provider_type: "openai",
    base_url: "http://moonhowler.local:8000/v1",
    model_id: "Qwen3.5-2B-Q6_K.gguf",
    api_key: "",
    temperature: 0.7,
    timeout: 45,
    max_tokens: 1024
  },
  testing: {
    simulate_cloud_with_detection: false
  }
}

export const useAppStore = create<AppState>((set) => ({
  messages: [],
  traceEvents: [],
  traceGroups: [],
  currentRequestId: null,
  currentSessionId: null,
  cloudStreamingContent: "",
  config: DEFAULT_CONFIG,
  status: "ready",
  statusMessage: undefined,
  anonymizedHistory: [],
  entityMap: {},
  sessions: [],
  pendingClarification: null,

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),

  startAssistantMessage: (message) => set((state) => {
    const last = state.messages[state.messages.length - 1]
    if (last?.role === "assistant") {
      return {
        messages: [
          ...state.messages.slice(0, -1),
          { ...last, ...message, role: "assistant" },
        ],
      }
    }
    return {
      messages: [...state.messages, message],
    }
  }),

  appendToLastAssistantMessage: (chunk) => set((state) => {
    const last = state.messages[state.messages.length - 1]
    if (last?.role !== "assistant") {
      return state
    }
    return {
      messages: [
        ...state.messages.slice(0, -1),
        { ...last, content: last.content + chunk },
      ],
    }
  }),

  replaceLastAssistantMessage: (content) => set((state) => {
    const last = state.messages[state.messages.length - 1]
    if (last?.role !== "assistant") {
      return state
    }
    return {
      messages: [
        ...state.messages.slice(0, -1),
        { ...last, content },
      ],
    }
  }),

  addTraceEvent: (event) => set((state) => {
    const newEvent = {
      ...event,
      requestId: event.requestId || state.currentRequestId || undefined
    }

    const updatedGroups = [...state.traceGroups]
    const currentGroupIndex = updatedGroups.findIndex(g => g.id === state.currentRequestId)

    if (currentGroupIndex !== -1) {
      const group = updatedGroups[currentGroupIndex]
      group.events = [...group.events, newEvent]

      if (event.type === 'detection') {
        const ev = event.content as { replacements?: unknown[] }
        group.summary.piiCount = ev?.replacements?.length ?? 0
      }

      if (event.type === 'clarification_required') group.summary.status = 'awaiting_clarification'
      if (event.type === 'error') group.summary.status = 'error'
      if (event.type === 'done') group.summary.status = 'completed'
    }

    return {
      traceEvents: [...state.traceEvents, newEvent],
      traceGroups: updatedGroups
    }
  }),

  updateTraceEvent: (id, content) => set((state) => ({
    traceEvents: state.traceEvents.map(event =>
      event.id === id ? { ...event, content } : event
    )
  })),

  startNewRequest: (requestId, userMessage = "") => set((state) => {
    const newGroup: TraceGroup = {
      id: requestId,
      timestamp: new Date().toISOString(),
      userMessage,
      events: [],
      isCollapsed: false,
      summary: { piiCount: 0, status: 'processing' }
    }

    const updatedGroups = state.traceGroups.map(g => ({ ...g, isCollapsed: true }))

    return {
      currentRequestId: requestId,
      traceGroups: [...updatedGroups, newGroup],
      cloudStreamingContent: ""
    }
  }),

  toggleTraceGroup: (groupId) => set((state) => ({
    traceGroups: state.traceGroups.map(group =>
      group.id === groupId ? { ...group, isCollapsed: !group.isCollapsed } : group
    )
  })),

  setCloudStreamingContent: (content) => set({ cloudStreamingContent: content }),

  appendCloudStreamingContent: (chunk) => set((state) => ({
    cloudStreamingContent: state.cloudStreamingContent + chunk
  })),

  setConfig: (config) => set({ config }),

  setStatus: (status, message) => set({ status, statusMessage: message }),

  setPendingClarification: (pendingClarification) => set({ pendingClarification }),

  clearPendingClarification: () => set({ pendingClarification: null }),

  updateSession: (anonymizedMsg, anonymizedResponse, newEntries) => set((state) => ({
    anonymizedHistory: [
      ...state.anonymizedHistory,
      { role: "user",      content: anonymizedMsg },
      { role: "assistant", content: anonymizedResponse },
    ],
    entityMap: { ...state.entityMap, ...newEntries },
  })),

  clearHistory: () => set({
    messages: [],
    traceEvents: [],
    traceGroups: [],
    currentRequestId: null,
    currentSessionId: null,
    status: "ready",
    statusMessage: undefined,
    cloudStreamingContent: "",
    anonymizedHistory: [],
    entityMap: {},
    pendingClarification: null,
  }),

  setSessions: (sessions: SessionSummary[]) => set({ sessions }),

  loadSessionData: (session: Session) => set({
    messages: session.messages,
    traceEvents: [],
    traceGroups: session.traceGroups,
    currentRequestId: null,
    status: "ready",
    statusMessage: undefined,
    cloudStreamingContent: "",
    anonymizedHistory: session.anonymizedHistory,
    entityMap: session.entityMap,
    pendingClarification: null,
  }),

  updateSessionTitle: (title: string) => set((state) => {
    const updated = state.sessions.map(s =>
      s.id === state.currentSessionId ? { ...s, title } : s
    )
    return { sessions: updated }
  }),

  setCurrentSessionId: (id: string | null) => set({ currentSessionId: id }),
}))
