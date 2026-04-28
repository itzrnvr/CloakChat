import { MessageList } from "./MessageList"
import { MessageInput } from "./MessageInput"
import { ClarificationPrompt } from "./ClarificationPrompt"
import { useAppStore } from "@/stores/appStore"
import { Loader2 } from "lucide-react"
import type { ClarificationOption } from "@/types"

interface ChatContainerProps {
  messages: Array<{
    role: "user" | "assistant" | "system"
    content: string
    timestamp?: string
  }>
  onSendMessage: (message: string) => void
  onSubmitClarification: (option: ClarificationOption, remember: boolean) => void
  onStopGeneration?: () => void
  status: "ready" | "processing" | "awaiting_clarification" | "error"
}

export function ChatContainer({ messages, onSendMessage, onSubmitClarification, onStopGeneration, status }: ChatContainerProps) {
  const { traceGroups, currentRequestId, pendingClarification } = useAppStore()
  const isProcessing = status === "processing"
  const isBlocked = status === "processing" || status === "awaiting_clarification"

  // Get the current step message from the active trace group
  const currentGroup = traceGroups.find(g => g.id === currentRequestId)
  const latestStepEvent = currentGroup?.events
    .filter(e => e.type === 'step')
    .slice(-1)[0]

  return (
    <div className="flex flex-col h-full bg-[var(--color-paper)] dark:bg-[var(--color-base-950)]">
      <div className="flex-1 overflow-hidden">
        <MessageList messages={messages} />
      </div>

      {isProcessing && (
        <div className="border-t border-[var(--color-base-200)] dark:border-[var(--color-base-800)] px-4 py-3 bg-[var(--color-base-50)] dark:bg-[var(--color-base-900)]">
          <div className="flex items-center gap-3 text-sm text-[var(--color-base-600)] dark:text-[var(--color-base-400)]">
            <Loader2 className="h-4 w-4 animate-spin text-[var(--color-blue-400)]" />
            <span>
              {latestStepEvent?.content as string || "Processing your message..."}
            </span>
          </div>
        </div>
      )}

      {pendingClarification && (
        <ClarificationPrompt
          clarification={pendingClarification}
          onSubmit={onSubmitClarification}
        />
      )}

      <MessageInput
        onSend={onSendMessage}
        onStop={onStopGeneration}
        disabled={isBlocked}
        isProcessing={isProcessing}
      />
    </div>
  )
}
