import { ScrollArea } from "@/components/ui/scroll-area"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import type { TraceGroup } from "@/types"
import { useAppStore } from "@/stores/appStore"
import { ChevronDown, ChevronRight, Loader2, ArrowRight } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

// --- Pipeline step renderers ---

function InputStep({ group }: { group: TraceGroup }) {
  if (!group.userMessage) return null
  return (
    <StepCard label="Input" color="base">
      <pre className="whitespace-pre-wrap font-mono text-xs">{group.userMessage}</pre>
    </StepCard>
  )
}

function AnonymiseStep({ group }: { group: TraceGroup }) {
  const detection = group.events.find(e => e.type === 'detection')
  const anonymized = group.events.find(e => e.type === 'anonymized')

  const replacements = detection
    ? ((detection.content as Record<string, unknown>)?.replacements as Array<{original: string; placeholder: string; entity_type: string}> ?? [])
    : []
  const anonymizedText = anonymized
    ? ((anonymized.content as Record<string, unknown>)?.text as string)
    : null

  if (!detection && !anonymized) return null

  return (
    <StepCard label="Anonymise" color="blue">
      {replacements.length > 0 ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {replacements.map((r, i) => (
              <span key={i} className="inline-flex items-center gap-1 text-xs">
                <Badge variant="outline" className="text-[10px] border-[var(--color-base-400)] text-[var(--color-base-500)]">{r.entity_type}</Badge>
                <span className="font-mono text-[var(--color-red-400)]">{r.original}</span>
                <ArrowRight className="h-3 w-3 text-[var(--color-base-400)]" />
                <span className="font-mono text-[var(--color-blue-400)]">{r.placeholder}</span>
              </span>
            ))}
          </div>
          {anonymizedText && (
            <pre className="mt-2 whitespace-pre-wrap font-mono text-xs text-[var(--color-base-500)] dark:text-[var(--color-base-400)] bg-[var(--color-base-100)] dark:bg-[var(--color-base-800)] rounded p-2">
              {anonymizedText}
            </pre>
          )}
        </div>
      ) : (
        <span className="text-xs text-[var(--color-base-400)]">No PII detected — message sent as-is</span>
      )}
    </StepCard>
  )
}

function CloudStep({ group, cloudContent, isActive }: { group: TraceGroup; cloudContent: string; isActive: boolean }) {
  const hasCloud = group.events.some(e => e.type === 'cloud_chunk') || (isActive)
  if (!hasCloud && !cloudContent) return null

  return (
    <StepCard label="Cloud" color="purple">
      <div className="flex items-center justify-between mb-2">
        {isActive && (
          <Badge variant="outline" className="text-xs border-[var(--color-purple-400)] text-[var(--color-purple-400)]">
            <Loader2 className="h-3 w-3 animate-spin mr-1" />
            Streaming
          </Badge>
        )}
        {cloudContent && (
          <span className="text-xs text-[var(--color-base-400)] ml-auto">
            {cloudContent.split(/\s+/).filter(Boolean).length} words
          </span>
        )}
      </div>
      <div className="max-h-40 overflow-y-auto rounded bg-white dark:bg-[var(--color-base-950)] p-2 text-xs text-[var(--color-base-700)] dark:text-[var(--color-base-300)] whitespace-pre-wrap">
        {cloudContent || "Waiting..."}
      </div>
    </StepCard>
  )
}

function DeanonymiseStep({ group }: { group: TraceGroup }) {
  const reconstruction = group.events.find(e => e.type === 'reconstruction')
  if (!reconstruction) return null
  const text = (reconstruction.content as Record<string, unknown>)?.text as string
  return (
    <StepCard label="Deanonymise" color="green">
      <pre className="whitespace-pre-wrap font-mono text-xs">{text}</pre>
    </StepCard>
  )
}

// --- Generic step card wrapper ---

type StepColor = "base" | "blue" | "orange" | "purple" | "green" | "red"

const colorMap: Record<StepColor, string> = {
  base:   "border-[var(--color-base-300)] dark:border-[var(--color-base-700)]",
  blue:   "border-[var(--color-blue-400)]",
  orange: "border-[var(--color-orange-400)]",
  purple: "border-[var(--color-purple-400)]",
  green:  "border-[var(--color-green-400)]",
  red:    "border-[var(--color-red-400)]",
}

const labelColorMap: Record<StepColor, string> = {
  base:   "text-[var(--color-base-500)]",
  blue:   "text-[var(--color-blue-400)]",
  orange: "text-[var(--color-orange-400)]",
  purple: "text-[var(--color-purple-400)]",
  green:  "text-[var(--color-green-400)]",
  red:    "text-[var(--color-red-400)]",
}

function StepCard({ label, color, children }: { label: string; color: StepColor; children: React.ReactNode }) {
  return (
    <div className={cn(
      "rounded-md border-l-4 bg-[var(--color-base-50)] dark:bg-[var(--color-base-900)] p-3 text-sm",
      colorMap[color]
    )}>
      <div className={cn("font-mono text-xs font-bold uppercase mb-2", labelColorMap[color])}>
        {label}
      </div>
      <div className="text-[var(--color-base-600)] dark:text-[var(--color-base-300)]">
        {children}
      </div>
    </div>
  )
}

// --- Trace group ---

function TraceGroupDisplay({ group }: { group: TraceGroup }) {
  const { toggleTraceGroup, cloudStreamingContent, status } = useAppStore()

  const isActive = status === 'processing' && !group.isCollapsed

  return (
    <Collapsible
      open={!group.isCollapsed}
      onOpenChange={() => toggleTraceGroup(group.id)}
      className="border border-[var(--color-base-200)] dark:border-[var(--color-base-800)] rounded-lg overflow-hidden"
    >
      <CollapsibleTrigger className="w-full">
        <div className="flex items-center justify-between p-3 hover:bg-[var(--color-base-100)] dark:hover:bg-[var(--color-base-800)] transition-colors">
          <div className="flex items-center gap-2">
            {group.isCollapsed
              ? <ChevronRight className="h-4 w-4 text-[var(--color-base-400)]" />
              : <ChevronDown className="h-4 w-4 text-[var(--color-base-400)]" />
            }
            <span className="font-semibold text-sm">Request</span>
            <span className="text-xs text-[var(--color-base-400)]">
              {new Date(group.timestamp).toLocaleTimeString()}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={cn("text-xs", group.summary.piiCount > 0 && "border-[var(--color-blue-400)] text-[var(--color-blue-400)]")}
            >
              {group.summary.piiCount} PII
            </Badge>
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                group.summary.status === 'processing' && "border-[var(--color-yellow-400)] text-[var(--color-yellow-400)]",
                group.summary.status === 'completed'  && "border-[var(--color-green-400)] text-[var(--color-green-400)]",
                group.summary.status === 'error'      && "border-[var(--color-red-400)] text-[var(--color-red-400)]",
              )}
            >
              {group.summary.status}
            </Badge>
          </div>
        </div>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="flex flex-col gap-2 p-3 pt-0 border-t border-[var(--color-base-200)] dark:border-[var(--color-base-800)]">
          <InputStep group={group} />
          <AnonymiseStep group={group} />
          <CloudStep group={group} cloudContent={isActive ? cloudStreamingContent : group.events.filter(e => e.type === 'cloud_chunk').map(e => e.content as string).join('')} isActive={isActive} />
          <DeanonymiseStep group={group} />

          {group.events.length === 0 && (
            <div className="text-center text-sm text-[var(--color-base-400)] py-4">Processing...</div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

// --- Root ---

export function TraceLog() {
  const { traceGroups } = useAppStore()

  if (traceGroups.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-sm text-[var(--color-base-400)] py-8 px-4">
          No trace events yet. Start a conversation to see the pipeline in action.
        </div>
      </div>
    )
  }

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-3 p-4">
        {traceGroups.slice().reverse().map((group) => (
          <TraceGroupDisplay key={group.id} group={group} />
        ))}
      </div>
    </ScrollArea>
  )
}
