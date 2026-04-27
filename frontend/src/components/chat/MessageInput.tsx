import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Send, Square } from "lucide-react"
import { useState } from "react"

interface MessageInputProps {
  onSend: (message: string) => void
  onStop?: () => void
  disabled?: boolean
  isProcessing?: boolean
}

export function MessageInput({ onSend, onStop, disabled, isProcessing }: MessageInputProps) {
  const [input, setInput] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !disabled) {
      onSend(input)
      setInput("")
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-4 border-t border-[var(--color-base-200)] dark:border-[var(--color-base-800)]">
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type a message..."
        disabled={disabled}
        className="flex-1"
      />
      {isProcessing ? (
        <Button type="button" size="icon" variant="destructive" onClick={onStop}>
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button type="submit" size="icon" disabled={disabled || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      )}
    </form>
  )
}
