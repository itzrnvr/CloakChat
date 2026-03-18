import { ScrollArea } from "@/components/ui/scroll-area"
import { Message } from "./Message"
import { useEffect, useRef } from "react"

interface MessageListProps {
  messages: Array<{
    role: "user" | "assistant" | "system"
    content: string
    timestamp?: string
  }>
}

export function MessageList({ messages }: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [messages])

  return (
    <ScrollArea className="h-full p-4">
      <div className="flex flex-col gap-4">
        {messages.map((msg, index) => (
          <Message
            key={index}
            role={msg.role}
            content={msg.content}
            timestamp={msg.timestamp}
          />
        ))}
        <div ref={scrollRef} />
      </div>
    </ScrollArea>
  )
}
