export interface Message {
  role: "user" | "assistant" | "system"
  content: string
  timestamp?: string
}

export interface TraceEvent {
  id: string
  type: string
  content: unknown
  timestamp: string
  requestId?: string
}

export interface TraceGroup {
  id: string
  timestamp: string
  userMessage: string
  events: TraceEvent[]
  isCollapsed: boolean
  summary: {
    piiCount: number
    duration?: number
    status: "processing" | "completed" | "error"
  }
}

export interface ModelConfig {
  base_url: string
  model_id: string
  api_key: string
  temperature: number
  max_tokens: number
  tool_mode: "native" | "text_json" | "mistral_tags" | "none"
}

export interface DetectionConfig extends ModelConfig {}
export interface CloudConfig extends ModelConfig {}

export interface AppConfig {
  detection: DetectionConfig
  cloud: CloudConfig
  testing: {
    simulate_cloud_with_detection: boolean
  }
  system_prompt?: string
}

export interface AppState {
  messages: Message[]
  traceEvents: TraceEvent[]
  traceGroups: TraceGroup[]
  currentRequestId: string | null
  config: AppConfig
  status: "ready" | "processing" | "error"
  statusMessage?: string
  cloudStreamingContent: string

  // Conversation session state (sent to backend each turn)
  anonymizedHistory: Array<{role: string, content: string}>
  entityMap: Record<string, string>  // original -> placeholder

  addMessage: (message: Message) => void
  addTraceEvent: (event: TraceEvent) => void
  updateTraceEvent: (id: string, content: unknown) => void
  startNewRequest: (requestId: string, userMessage?: string) => void
  toggleTraceGroup: (groupId: string) => void
  setCloudStreamingContent: (content: string) => void
  appendCloudStreamingContent: (chunk: string) => void
  setConfig: (config: AppConfig) => void
  setStatus: (status: "ready" | "processing" | "error", message?: string) => void
  updateSession: (anonymizedMsg: string, anonymizedResponse: string, newEntries: Record<string, string>) => void
  clearHistory: () => void
}
