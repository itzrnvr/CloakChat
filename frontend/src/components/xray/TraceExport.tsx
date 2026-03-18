import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Download, Copy, ChevronDown } from "lucide-react"
import { useState } from "react"
import { useAppStore } from "@/stores/appStore"

/**
 * Builds a clean, consolidated export payload from trace groups.
 * - Filters out raw `cloud_chunk` events (streaming fragments).
 * - Collates all cloud chunks into a single `cloud_response` string per group.
 * - Removes internal implementation details, keeping only meaningful pipeline steps.
 */
function buildExportPayload() {
  const { traceGroups, cloudStreamingContent } = useAppStore.getState()

  return traceGroups.map((group) => {
    // Separate chunk events from meaningful pipeline events
    const chunkEvents = group.events.filter((e) => e.type === "cloud_chunk")
    const meaningfulEvents = group.events.filter((e) => e.type !== "cloud_chunk" && e.type !== "done")

    // Reconstruct the full cloud response from chunks.
    // cloud_chunk events store `content` as a plain string (the chunk text).
    const cloudResponse = chunkEvents.length > 0
      ? chunkEvents.map((e) => (e.content as string) ?? "").join("")
      : cloudStreamingContent || undefined

    const exportGroup: Record<string, unknown> = {
      request_id: group.id,
      timestamp: group.timestamp,
      summary: group.summary,
      pipeline_steps: meaningfulEvents.map((e) => ({
        type: e.type,
        timestamp: e.timestamp,
        content: e.content,
      })),
    }

    if (cloudResponse) {
      exportGroup.cloud_response = cloudResponse
    }

    return exportGroup
  })
}

interface TraceExportProps {
  // kept for API compatibility — we now pull data directly from the store
  events?: unknown[]
}

export function TraceExport(_props: TraceExportProps) {
  const [copySuccess, setCopySuccess] = useState(false)
  const traceGroups = useAppStore((s) => s.traceGroups)
  const hasData = traceGroups.length > 0

  const handleExport = () => {
    const payload = buildExportPayload()
    const dataStr = JSON.stringify(payload, null, 2)
    const dataUri = "data:application/json;charset=utf-8," + encodeURIComponent(dataStr)

    const exportFileDefaultName = `trace_${new Date().toISOString()}.json`

    const linkElement = document.createElement("a")
    linkElement.setAttribute("href", dataUri)
    linkElement.setAttribute("download", exportFileDefaultName)
    linkElement.click()
  }

  const handleCopy = async () => {
    try {
      const payload = buildExportPayload()
      const dataStr = JSON.stringify(payload, null, 2)
      await navigator.clipboard.writeText(dataStr)
      setCopySuccess(true)
      setTimeout(() => setCopySuccess(false), 2000)
    } catch (err) {
      console.error("Failed to copy:", err)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={!hasData}>
          <Download className="h-4 w-4 mr-2" />
          Export
          <ChevronDown className="h-4 w-4 ml-2" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={handleExport}>
          <Download className="h-4 w-4 mr-2" />
          Export as JSON
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleCopy}>
          <Copy className="h-4 w-4 mr-2" />
          {copySuccess ? "Copied!" : "Copy to Clipboard"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
