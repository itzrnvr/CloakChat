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

function ReasoningStep({ group }: { group: TraceGroup }) {
  const reasoning = group.events.find(e => e.type === 'detection_reasoning')
  const content = reasoning
    ? ((reasoning.content as Record<string, unknown>)?.content as string)
    : ""
  if (!content) return null

  return (
    <StepCard label="Reasoning" color="orange">
      <div className="max-h-40 overflow-y-auto rounded bg-[var(--color-base-100)] dark:bg-[var(--color-base-800)] p-2 text-xs whitespace-pre-wrap">
        {content}
      </div>
    </StepCard>
  )
}

function ClarificationStep({ group }: { group: TraceGroup }) {
  const clarification = group.events.find(e => e.type === 'clarification_required')
  const playbookUpdate = group.events.find(e => e.type === 'playbook_updated')

  if (!clarification && !playbookUpdate) return null

  return (
    <StepCard label="Clarification" color="orange">
      <div className="space-y-2 text-xs">
        {clarification && (
          <div className="rounded bg-[var(--color-base-100)] dark:bg-[var(--color-base-800)] p-2">
            <div className="font-semibold">Prompted user</div>
            <div className="mt-1">
              {((clarification.content as Record<string, unknown>)?.question as string) || "Clarification required"}
            </div>
          </div>
        )}
        {playbookUpdate && (
          <div className="rounded bg-[var(--color-base-100)] dark:bg-[var(--color-base-800)] p-2">
            <div className="font-semibold">Applied rule</div>
            <div className="mt-1">
              {(() => {
                const content = playbookUpdate.content as Record<string, unknown>
                const entry = content.entry as Record<string, unknown> | undefined
                const action = entry?.action as string | undefined
                const original = entry?.original as string | undefined
                const remembered = content.remembered ? "and saved to playbook" : "for this request only"
                return original ? `"${original}" -> ${action} (${remembered})` : "Playbook updated"
              })()}
            </div>
          </div>
        )}
      </div>
    </StepCard>
  )
}

function CloudStep({ group, cloudContent, isActive }: { group: TraceGroup; cloudContent: string; isActive: boolean }) {
  const cloudPrompt = group.events.find(e => e.type === 'cloud_prompt')
  const cloudReasoning = group.events
    .filter(e => e.type === 'cloud_reasoning_chunk')
    .map((e) => ((e.content as Record<string, unknown>)?.content as string) || "")
    .join("")
  const hasCloud = group.events.some(e => e.type === 'cloud_chunk' || e.type === 'cloud_reasoning_chunk') || Boolean(cloudPrompt) || (isActive)
  if (!hasCloud && !cloudContent && !cloudReasoning) return null
  const entityMap = getEntityMap(group)
  const placeholders = Object.values(entityMap)
  const promptContent = cloudPrompt?.content as Record<string, unknown> | undefined
  const messages = (promptContent?.messages as Array<{role: string; content: string}> | undefined) ?? []

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
      {messages.length > 0 && (
        <div className="mb-2 rounded bg-[var(--color-base-100)] dark:bg-[var(--color-base-800)] p-2">
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="font-mono text-[10px] font-bold uppercase text-[var(--color-purple-400)]">
              Sent to cloud
            </span>
            <span className="text-[10px] text-[var(--color-base-400)]">
              {messages.length} messages
            </span>
          </div>
          <div className="max-h-44 overflow-y-auto space-y-2">
            {messages.map((message, index) => (
              <div key={index} className="rounded border border-[var(--color-base-200)] dark:border-[var(--color-base-700)] bg-white dark:bg-[var(--color-base-950)] p-2">
                <div className="mb-1 font-mono text-[10px] uppercase text-[var(--color-base-400)]">
                  {message.role}
                </div>
                <pre className="whitespace-pre-wrap font-mono text-xs text-[var(--color-base-700)] dark:text-[var(--color-base-300)]">
                  <HighlightedText text={message.content || ""} terms={placeholders} variant="placeholder" />
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
      {cloudReasoning && (
        <div className="mb-2 rounded bg-[var(--color-base-100)] dark:bg-[var(--color-base-800)] p-2">
          <div className="mb-1 font-mono text-[10px] font-bold uppercase text-[var(--color-orange-400)]">
            Model reasoning
          </div>
          <div className="max-h-32 overflow-y-auto whitespace-pre-wrap text-xs text-[var(--color-base-600)] dark:text-[var(--color-base-300)]">
            {cloudReasoning}
          </div>
        </div>
      )}
      <div className="max-h-40 overflow-y-auto rounded bg-white dark:bg-[var(--color-base-950)] p-2 text-xs text-[var(--color-base-700)] dark:text-[var(--color-base-300)] whitespace-pre-wrap">
        {cloudContent ? (
          <HighlightedText text={cloudContent} terms={placeholders} variant="placeholder" />
        ) : "Waiting..."}
      </div>
    </StepCard>
  )
}

function DeanonymiseStep({ group }: { group: TraceGroup }) {
  const reconstruction = group.events.find(e => e.type === 'reconstruction')
  if (!reconstruction) return null
  const text = (reconstruction.content as Record<string, unknown>)?.text as string
  const entityMap = getEntityMap(group)
  const originals = Object.keys(entityMap)
  return (
    <StepCard label="Deanonymise" color="green">
      <pre className="whitespace-pre-wrap font-mono text-xs">
        <HighlightedText text={text} terms={originals} variant="pii" />
      </pre>
    </StepCard>
  )
}

function VerificationStep({ group }: { group: TraceGroup }) {
  const verification = group.events.find(e => e.type === 'reconstruction_verification')
  if (!verification) return null
  const content = verification.content as Record<string, unknown>
  const valid = Boolean(content.valid)
  const leaks = (content.leaks as string[] | undefined) ?? []
  const notes = (content.notes as string | undefined) ?? ""
  const reasoning = (content.reasoning as string | undefined) ?? ""

  return (
    <StepCard label="Verification" color={valid ? "green" : "red"}>
      <div className="space-y-2 text-xs">
        <Badge variant="outline" className={cn(valid ? "border-[var(--color-green-400)] text-[var(--color-green-400)]" : "border-[var(--color-red-400)] text-[var(--color-red-400)]")}>
          {valid ? "No leaks detected" : "Needs attention"}
        </Badge>
        {notes && <div>{notes}</div>}
        {leaks.length > 0 && (
          <div className="rounded bg-[var(--color-base-100)] dark:bg-[var(--color-base-800)] p-2">
            <div className="font-semibold">Leaks</div>
            <div className="mt-1 font-mono">{leaks.join(", ")}</div>
          </div>
        )}
        {reasoning && (
          <div className="max-h-32 overflow-y-auto rounded bg-[var(--color-base-100)] dark:bg-[var(--color-base-800)] p-2 whitespace-pre-wrap">
            {reasoning}
          </div>
        )}
      </div>
    </StepCard>
  )
}

function HighlightedText({ text, terms, variant }: { text: string; terms: string[]; variant: "pii" | "placeholder" }) {
  const cleanTerms = terms.filter(Boolean).sort((a, b) => b.length - a.length)
  if (!text || cleanTerms.length === 0) return <>{text}</>

  const pattern = new RegExp(`(${cleanTerms.map(escapeRegExp).join("|")})`, "gi")
  const parts = text.split(pattern)
  return (
    <>
      {parts.map((part, index) => {
        const matched = cleanTerms.some(term => term.toLowerCase() === part.toLowerCase())
        if (!matched) return <span key={index}>{part}</span>
        return (
          <mark
            key={index}
            className={cn(
              "rounded px-1 py-0.5 font-semibold",
              variant === "pii"
                ? "bg-[var(--color-green-100)] text-[var(--color-green-700)] dark:bg-[var(--color-green-900)] dark:text-[var(--color-green-200)]"
                : "bg-[var(--color-purple-100)] text-[var(--color-purple-700)] dark:bg-[var(--color-purple-900)] dark:text-[var(--color-purple-200)]"
            )}
          >
            {part}
          </mark>
        )
      })}
    </>
  )
}

function getEntityMap(group: TraceGroup): Record<string, string> {
  const reconstruction = group.events.find(e => e.type === 'reconstruction')
  const fromReconstruction = (reconstruction?.content as Record<string, unknown> | undefined)?.entity_map as Record<string, string> | undefined
  if (fromReconstruction) return fromReconstruction

  const detection = group.events.find(e => e.type === 'detection')
  const replacements = ((detection?.content as Record<string, unknown> | undefined)?.replacements as Array<{original: string; placeholder: string}> | undefined) ?? []
  return Object.fromEntries(replacements.map(item => [item.original, item.placeholder]))
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
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

  const isActive = (status === 'processing' || status === 'awaiting_clarification') && !group.isCollapsed

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
                group.summary.status === 'awaiting_clarification' && "border-[var(--color-orange-400)] text-[var(--color-orange-400)]",
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
          <ReasoningStep group={group} />
          <AnonymiseStep group={group} />
          <ClarificationStep group={group} />
          <CloudStep group={group} cloudContent={isActive ? cloudStreamingContent : group.events.filter(e => e.type === 'cloud_chunk').map(e => e.content as string).join('')} isActive={isActive} />
          <DeanonymiseStep group={group} />
          <VerificationStep group={group} />

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
