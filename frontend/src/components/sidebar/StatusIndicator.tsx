import { cn } from "@/lib/utils"

interface StatusIndicatorProps {
  status: "ready" | "processing" | "error"
  message?: string
}

export function StatusIndicator({ status, message }: StatusIndicatorProps) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <div
        className={cn(
          "h-2.5 w-2.5 rounded-full",
          status === "ready" && "bg-[var(--color-green-400)]",
          status === "processing" && "bg-[var(--color-yellow-400)] animate-pulse",
          status === "error" && "bg-[var(--color-red-400)]"
        )}
      />
      <span className="text-[var(--color-base-600)] dark:text-[var(--color-base-400)]">
        {message || (status === "ready" ? "System Ready" : status === "processing" ? "Processing..." : "Error")}
      </span>
    </div>
  )
}
