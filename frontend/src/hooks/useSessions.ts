import { useCallback } from "react"
import type { Session, SessionSummary } from "@/types"

export function useSessions() {
  const listSessions = useCallback(async (): Promise<SessionSummary[]> => {
    const res = await fetch("/api/sessions")
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
    return res.json()
  }, [])

  const getSession = useCallback(async (id: string): Promise<Session | null> => {
    const res = await fetch(`/api/sessions/${id}`)
    if (res.status === 404) return null
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
    return res.json()
  }, [])

  const saveSession = useCallback(async (session: Session): Promise<Session> => {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(session),
    })
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
    return res.json()
  }, [])

  const deleteSession = useCallback(async (id: string): Promise<void> => {
    const res = await fetch(`/api/sessions/${id}`, { method: "DELETE" })
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
  }, [])

  return { listSessions, getSession, saveSession, deleteSession }
}
