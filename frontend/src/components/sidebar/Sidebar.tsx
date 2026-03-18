import { StatusIndicator } from "./StatusIndicator"
import { ConfigPanel } from "./ConfigPanel"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Button } from "@/components/ui/button"
import { Settings, ChevronDown, ChevronUp } from "lucide-react"
import { useState } from "react"
import type { AppConfig } from "@/types"

interface SidebarProps {
  status: "ready" | "processing" | "error"
  config: AppConfig
  onConfigChange: (config: AppConfig) => void
}

export function Sidebar({ status, config, onConfigChange }: SidebarProps) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <div className="w-80 border-r border-[var(--color-base-200)] dark:border-[var(--color-base-800)] bg-[var(--color-base-50)] dark:bg-[var(--color-base-900)] flex flex-col h-full">
      <div className="p-4 border-b border-[var(--color-base-200)] dark:border-[var(--color-base-800)]">
        <h1 className="text-xl font-bold mb-2">CloakChat</h1>
        <StatusIndicator status={status} />
      </div>
      
      <div className="flex-1 overflow-hidden">
        <Collapsible open={isOpen} onOpenChange={setIsOpen} className="h-full flex flex-col">
          <div className="flex items-center justify-between p-4 pb-2">
            <h2 className="font-semibold flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Settings
            </h2>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="p-0 h-8 w-8">
                {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
            </CollapsibleTrigger>
          </div>
          
          <CollapsibleContent className="flex-1 overflow-hidden">
            <ConfigPanel config={config} onConfigChange={onConfigChange} />
          </CollapsibleContent>
        </Collapsible>
      </div>
    </div>
  )
}
