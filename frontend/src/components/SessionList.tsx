import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Trash2, MessageSquarePlus } from "lucide-react"
import type { SessionSummary } from "@/types"

interface SessionListProps {
  sessions: SessionSummary[]
  currentSessionId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onNew: () => void
}

export function SessionList({ sessions, currentSessionId, onSelect, onDelete, onNew }: SessionListProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-[var(--color-base-200)] dark:border-[var(--color-base-800)]">
        <Button className="w-full" onClick={onNew}>
          <MessageSquarePlus className="h-4 w-4 mr-2" />
          New Session
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-1 p-2">
          {sessions.length === 0 && (
            <div className="text-center text-sm text-[var(--color-base-400)] py-8 px-4">
              No saved sessions yet.
            </div>
          )}

          {sessions.slice().reverse().map((session) => (
            <div
              key={session.id}
              onClick={() => onSelect(session.id)}
              className={[
                "group flex items-center justify-between rounded-md px-3 py-2 cursor-pointer",
                session.id === currentSessionId
                  ? "bg-[var(--color-blue-400)]/10 text-[var(--color-blue-400)]"
                  : "hover:bg-[var(--color-base-100)] dark:hover:bg-[var(--color-base-800)]"
              ].join(" ")}
            >
              <div className="flex flex-col min-w-0">
                <span className="text-sm font-medium truncate">{session.title}</span>
                <span className="text-xs text-[var(--color-base-400)]">
                  {new Date(session.updatedAt).toLocaleString()}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="opacity-0 group-hover:opacity-100 h-8 w-8 p-0"
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(session.id)
                }}
              >
                <Trash2 className="h-4 w-4 text-[var(--color-red-400)]" />
              </Button>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
