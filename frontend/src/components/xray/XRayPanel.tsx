import { useState } from "react"
import { TraceLog } from "./TraceLog"
import { TraceExport } from "./TraceExport"
import { SessionList } from "@/components/SessionList"
import { useAppStore } from "@/stores/appStore"
import { Activity, MessageSquare } from "lucide-react"
import type { TraceEvent } from "@/types"

interface XRayPanelProps {
  events: TraceEvent[]
}

export function XRayPanel({ events }: XRayPanelProps) {
  const [tab, setTab] = useState<"xray" | "sessions">("xray")
  const { sessions, currentSessionId, setCurrentSessionId, clearHistory, loadSessionData, setSessions } = useAppStore()

  const handleNewSession = () => {
    clearHistory()
    setCurrentSessionId(null)
  }

  const handleSelectSession = async (id: string) => {
    const res = await fetch(`/api/sessions/${id}`)
    if (!res.ok) return
    const session = await res.json()
    if (session) {
      loadSessionData(session)
    }
  }

  const handleDeleteSession = async (id: string) => {
    await fetch(`/api/sessions/${id}`, { method: "DELETE" })
    const updated = sessions.filter(s => s.id !== id)
    setSessions(updated)
    if (currentSessionId === id) {
      clearHistory()
    }
  }

  return (
    <div className="flex flex-col h-full bg-[var(--color-base-50)] dark:bg-[var(--color-base-900)] border-l border-[var(--color-base-200)] dark:border-[var(--color-base-800)] w-96">
      <div className="flex items-center justify-between p-4 border-b border-[var(--color-base-200)] dark:border-[var(--color-base-800)]">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setTab("xray")}
            className={[
              "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-semibold",
              tab === "xray"
                ? "bg-[var(--color-base-200)] dark:bg-[var(--color-base-800)]"
                : "text-[var(--color-base-400)] hover:text-[var(--color-base-600)]"
            ].join(" ")}
          >
            <Activity className="h-4 w-4" />
            X-Ray
          </button>
          <button
            onClick={() => setTab("sessions")}
            className={[
              "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-semibold",
              tab === "sessions"
                ? "bg-[var(--color-base-200)] dark:bg-[var(--color-base-800)]"
                : "text-[var(--color-base-400)] hover:text-[var(--color-base-600)]"
            ].join(" ")}
          >
            <MessageSquare className="h-4 w-4" />
            Sessions
          </button>
        </div>
        {tab === "xray" && <TraceExport events={events} />}
      </div>

      <div className="flex-1 overflow-hidden">
        {tab === "xray" ? (
          <TraceLog />
        ) : (
          <SessionList
            sessions={sessions}
            currentSessionId={currentSessionId}
            onSelect={handleSelectSession}
            onDelete={handleDeleteSession}
            onNew={handleNewSession}
          />
        )}
      </div>
    </div>
  )
}
