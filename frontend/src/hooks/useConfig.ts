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
    try {
      const res = await fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      })
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`)
      }
      const saved = await res.json()
      setConfig(saved as AppConfig)
    } catch (err: any) {
      console.error("Failed to sync config with backend", err)
      setError(err.message)
    }
  }

  return { config, updateConfig, isLoading, error, refreshConfig: fetchConfig }
}
