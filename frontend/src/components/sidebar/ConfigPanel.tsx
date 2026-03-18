import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChevronDown, Save, RefreshCw } from "lucide-react"
import { useState } from "react"
import { cn } from "@/lib/utils"
import type { AppConfig } from "@/types"

interface ConfigPanelProps {
  config: AppConfig
  onConfigChange: (config: AppConfig) => void
}

export function ConfigPanel({ config, onConfigChange }: ConfigPanelProps) {
  const [localConfig, setLocalConfig] = useState<AppConfig>(config)
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    detection: true,
    cloud: true,
    testing: false,
  })

  const toggleSection = (section: string) =>
    setOpenSections(prev => ({ ...prev, [section]: !prev[section] }))

  const updateDetection = (updates: Partial<typeof localConfig.detection>) =>
    setLocalConfig(prev => ({ ...prev, detection: { ...prev.detection, ...updates } }))

  const updateCloud = (updates: Partial<typeof localConfig.cloud>) =>
    setLocalConfig(prev => ({ ...prev, cloud: { ...prev.cloud, ...updates } }))

  const updateTesting = (updates: Partial<typeof localConfig.testing>) =>
    setLocalConfig(prev => ({ ...prev, testing: { ...prev.testing, ...updates } }))

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4 pb-20">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-bold">Configuration</h2>
          <Button size="sm" variant="ghost" onClick={() => setLocalConfig(config)} title="Reset">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>

        {/* Detection Model */}
        <Collapsible open={openSections.detection} onOpenChange={() => toggleSection("detection")}>
          <CollapsibleTrigger className="flex w-full items-center justify-between py-2 font-semibold border-b">
            <div className="flex items-center gap-2">
              <ChevronDown className={cn("h-4 w-4 transition-transform", !openSections.detection && "-rotate-90")} />
              🔍 Detection Model (PII)
            </div>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-4 space-y-4">
            <div className="space-y-2">
              <Label className="text-xs">Base URL</Label>
              <Input
                value={localConfig.detection.base_url}
                onChange={(e) => updateDetection({ base_url: e.target.value })}
                placeholder="http://localhost:8000/v1"
                className="h-8 text-xs font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs">Model ID</Label>
              <Input
                value={localConfig.detection.model_id}
                onChange={(e) => updateDetection({ model_id: e.target.value })}
                placeholder="model-name"
                className="h-8 text-xs font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs">API Key</Label>
              <Input
                type="password"
                value={localConfig.detection.api_key}
                onChange={(e) => updateDetection({ api_key: e.target.value })}
                placeholder="Optional API Key"
                className="h-8 text-xs font-mono"
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Cloud Model */}
        <Collapsible open={openSections.cloud} onOpenChange={() => toggleSection("cloud")}>
          <CollapsibleTrigger className="flex w-full items-center justify-between py-2 font-semibold border-b">
            <div className="flex items-center gap-2">
              <ChevronDown className={cn("h-4 w-4 transition-transform", !openSections.cloud && "-rotate-90")} />
              ☁️ Cloud Model (Chat)
            </div>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-4 space-y-4">
            <div className="space-y-2">
              <Label className="text-xs">Base URL</Label>
              <Input
                value={localConfig.cloud.base_url}
                onChange={(e) => updateCloud({ base_url: e.target.value })}
                placeholder="https://api.openai.com/v1"
                className="h-8 text-xs font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs">Model ID</Label>
              <Input
                value={localConfig.cloud.model_id}
                onChange={(e) => updateCloud({ model_id: e.target.value })}
                placeholder="gpt-4o or gemini/gemini-pro"
                className="h-8 text-xs font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs">API Key</Label>
              <Input
                type="password"
                value={localConfig.cloud.api_key}
                onChange={(e) => updateCloud({ api_key: e.target.value })}
                placeholder="Enter API Key"
                className="h-8 text-xs font-mono"
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Testing */}
        <Collapsible open={openSections.testing} onOpenChange={() => toggleSection("testing")}>
          <CollapsibleTrigger className="flex w-full items-center justify-between py-2 font-semibold border-b">
            <div className="flex items-center gap-2">
              <ChevronDown className={cn("h-4 w-4 transition-transform", !openSections.testing && "-rotate-90")} />
              🧪 Testing
            </div>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-4 space-y-4">
            <div className="flex items-center gap-2">
              <Checkbox
                id="simulate"
                checked={localConfig.testing.simulate_cloud_with_detection}
                onCheckedChange={(checked) => updateTesting({ simulate_cloud_with_detection: !!checked })}
              />
              <Label htmlFor="simulate" className="text-xs cursor-pointer">
                Simulate cloud with detection model
              </Label>
            </div>
          </CollapsibleContent>
        </Collapsible>

        <div className="pt-6">
          <Button className="w-full shadow-sm" onClick={() => onConfigChange(localConfig)}>
            <Save className="h-4 w-4 mr-2" />
            Apply Settings
          </Button>
        </div>
      </div>
    </ScrollArea>
  )
}
