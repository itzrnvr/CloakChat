import { useAppStore } from "@/stores/appStore"
import { useEffect, useState, useCallback } from "react"
import type { AppConfig } from "@/types"

export function useConfig() {
  const { config, setConfig } = useAppStore()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/config')
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`)
      }
      const data = await res.json()
      
      // The backend now returns the nested structure that matches our AppConfig type
      if (data) {
        setConfig(data as AppConfig)
      }
      setIsLoading(false)
    } catch (err: any) {
      console.error("Failed to load config", err)
      setError(err.message)
      setIsLoading(false)
    }
  }, [setConfig])

  useEffect(() => {
    fetchConfig()
  }, [fetchConfig])

  const updateConfig = async (newConfig: AppConfig) => {
    // Update local state immediately for snappy UI
    setConfig(newConfig)
    
    try {
      // Sync with backend (mostly mock for now, but good practice)
      await fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      })
    } catch (err) {
      console.error("Failed to sync config with backend", err)
    }
  }

  return { config, updateConfig, isLoading, error, refreshConfig: fetchConfig }
}
