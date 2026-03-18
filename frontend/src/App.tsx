import { Sidebar } from "@/components/sidebar/Sidebar"
import { ChatContainer } from "@/components/chat/ChatContainer"
import { XRayPanel } from "@/components/xray/XRayPanel"
import { useAppStore } from "@/stores/appStore"
import { useChat } from "@/hooks/useChat"
import { useConfig } from "@/hooks/useConfig"
import { Loader2 } from "lucide-react"

function App() {
  const { messages, traceEvents, status } = useAppStore()
  const { sendMessage } = useChat()
  const { config, updateConfig, isLoading, error } = useConfig()

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[var(--color-paper)] dark:bg-[var(--color-base-950)]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-[var(--color-blue-400)]" />
          <p className="text-sm text-[var(--color-base-600)] dark:text-[var(--color-base-400)]">
            Loading configuration...
          </p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[var(--color-paper)] dark:bg-[var(--color-base-950)]">
        <div className="max-w-md space-y-4 text-center">
          <h1 className="text-xl font-bold text-[var(--color-red-400)]">
            Failed to load configuration
          </h1>
          <p className="text-sm text-[var(--color-base-600)] dark:text-[var(--color-base-400)]">
            {error}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-md bg-[var(--color-blue-400)] px-4 py-2 text-sm text-white hover:bg-[var(--color-blue-400)]/90"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[var(--color-paper)] dark:bg-[var(--color-base-950)] text-[var(--color-black)] dark:text-[var(--color-base-50)]">
      <Sidebar
        status={status}
        config={config}
        onConfigChange={updateConfig}
      />

      <main className="flex-1 overflow-hidden border-r border-[var(--color-base-200)] dark:border-[var(--color-base-800)]">
        <ChatContainer
          messages={messages}
          onSendMessage={sendMessage}
          isProcessing={status === "processing"}
        />
      </main>

      <XRayPanel events={traceEvents} />
    </div>
  )
}

export default App
