import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
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
    prompts: false,
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
            <ProviderSelect
              value={localConfig.detection.provider_type}
              onChange={(provider_type) => updateDetection({ provider_type })}
            />
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
            <div className="space-y-2">
              <Label className="text-xs">Timeout (seconds)</Label>
              <Input
                type="number"
                min={1}
                value={localConfig.detection.timeout ?? ""}
                onChange={(e) => updateDetection({ timeout: e.target.value ? Number(e.target.value) : undefined })}
                placeholder="30"
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
            <ProviderSelect
              value={localConfig.cloud.provider_type}
              onChange={(provider_type) => updateCloud({ provider_type })}
            />
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
                placeholder="your-cloud-model"
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
            <div className="space-y-2">
              <Label className="text-xs">Timeout (seconds)</Label>
              <Input
                type="number"
                min={1}
                value={localConfig.cloud.timeout ?? ""}
                onChange={(e) => updateCloud({ timeout: e.target.value ? Number(e.target.value) : undefined })}
                placeholder="45"
                className="h-8 text-xs font-mono"
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Prompts */}
        <Collapsible open={openSections.prompts} onOpenChange={() => toggleSection("prompts")}>
          <CollapsibleTrigger className="flex w-full items-center justify-between py-2 font-semibold border-b">
            <div className="flex items-center gap-2">
              <ChevronDown className={cn("h-4 w-4 transition-transform", !openSections.prompts && "-rotate-90")} />
              📝 Prompts & Context
            </div>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-4 space-y-4">
            <div className="space-y-2">
              <Label className="text-xs">User Corrections / Context</Label>
              <p className="text-[10px] text-[var(--color-base-400)]">
                Added to every detection call. Use for correcting misidentified entities (e.g. "Tom Cruise is always an actor name, not a person").
              </p>
              <textarea
                value={localConfig.user_context || ""}
                onChange={(e) => setLocalConfig(prev => ({ ...prev, user_context: e.target.value }))}
                placeholder="e.g. Always treat 'Tom Cruise' as ACTOR not PERSON..."
                className="w-full h-24 rounded-md border border-[var(--color-base-200)] dark:border-[var(--color-base-800)] bg-[var(--color-base-50)] dark:bg-[var(--color-base-900)] px-3 py-2 text-xs font-mono resize-y focus:outline-none focus:ring-1 focus:ring-[var(--color-blue-400)]"
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

interface ProviderSelectProps {
  value: "genai" | "openai" | "other"
  onChange: (value: "genai" | "openai" | "other") => void
}

function ProviderSelect({ value, onChange }: ProviderSelectProps) {
  return (
    <div className="space-y-2">
      <Label className="text-xs">Provider Type</Label>
      <Select value={value || "openai"} onValueChange={(next) => onChange(next as "genai" | "openai" | "other")}>
        <SelectTrigger className="h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="openai">OpenAI-compatible</SelectItem>
          <SelectItem value="genai">Google GenAI</SelectItem>
          <SelectItem value="other">Other LiteLLM provider</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}
