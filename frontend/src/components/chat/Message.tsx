import { cn } from "@/lib/utils"

interface MessageProps {
  role: "user" | "assistant" | "system"
  content: string
  timestamp?: string
}

export function Message({ role, content, timestamp }: MessageProps) {
  return (
    <div
      className={cn(
        "flex w-full flex-col gap-2 py-4",
        role === "user" ? "items-end" : "items-start"
      )}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-4 py-3 text-sm",
          role === "user"
            ? "bg-[var(--color-base-200)] text-[var(--color-black)] dark:bg-[var(--color-base-800)] dark:text-[var(--color-base-50)]"
            : "bg-[var(--color-paper)] border border-[var(--color-base-200)] text-[var(--color-black)] dark:bg-[var(--color-base-950)] dark:border-[var(--color-base-800)] dark:text-[var(--color-base-50)]"
        )}
      >
        <div className="whitespace-pre-wrap">{content}</div>
      </div>
      {timestamp && (
        <span className="text-xs text-[var(--color-base-400)]">
          {new Date(timestamp).toLocaleTimeString()}
        </span>
      )}
    </div>
  )
}
