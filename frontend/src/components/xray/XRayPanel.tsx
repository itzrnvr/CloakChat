import { TraceLog } from "./TraceLog"
import { TraceExport } from "./TraceExport"
import { Activity } from "lucide-react"
import type { TraceEvent } from "@/types"

interface XRayPanelProps {
  events: TraceEvent[]
}

export function XRayPanel({ events }: XRayPanelProps) {
  return (
    <div className="flex flex-col h-full bg-[var(--color-base-50)] dark:bg-[var(--color-base-900)] border-l border-[var(--color-base-200)] dark:border-[var(--color-base-800)] w-96">
      <div className="flex items-center justify-between p-4 border-b border-[var(--color-base-200)] dark:border-[var(--color-base-800)]">
        <h2 className="font-semibold flex items-center gap-2">
          <Activity className="h-4 w-4" />
          X-Ray View
        </h2>
        <TraceExport events={events} />
      </div>
      <div className="flex-1 overflow-hidden">
        <TraceLog />
      </div>
    </div>
  )
}
