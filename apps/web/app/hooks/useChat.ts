import { useState, useCallback, useRef } from 'react'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Chunk[]
  isStreaming?: boolean
  thinking?: string
}

export interface Chunk {
  id: string
  content: string
  metadata?: Record<string, unknown>
}

interface UseChatOptions {
  collectionIds: string[]
  conversationId?: string
  onThinking?: (node: string, message: string) => void
}

interface UseChatReturn {
  messages: ChatMessage[]
  isLoading: boolean
  sendMessage: (content: string) => Promise<void>
  error: Error | null
  thinkingMessage: string | null
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [thinkingMessage, setThinkingMessage] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (content: string) => {
      setIsLoading(true)
      setError(null)
      setThinkingMessage(null)

      const userMessageId = generateId()
      const userMessage: ChatMessage = { 
        id: userMessageId,
        role: 'user', 
        content 
      }
      
      setMessages((prev) => [...prev, userMessage])

      const assistantMessageId = generateId()
      const assistantMessage: ChatMessage = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        isStreaming: true,
      }
      setMessages((prev) => [...prev, assistantMessage])

      abortControllerRef.current = new AbortController()

      try {
        const response = await fetch('/api/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: content,
            collection_ids: options.collectionIds,
            conversation_id: options.conversationId,
          }),
          signal: abortControllerRef.current.signal,
        })

        if (!response.ok) {
          throw new Error(`Chat failed: ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) throw new Error('No response body')

        const decoder = new TextDecoder()
        let assistantContent = ''
        let sources: Chunk[] = []

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const data = line.slice(6)

            if (data === '[DONE]') {
              break
            }

            try {
              const event = JSON.parse(data)

              if (event.node && event.message) {
                const thinkingText = event.message
                setThinkingMessage(thinkingText)
                options.onThinking?.(event.node, thinkingText)
                
                setMessages((prev) => 
                  prev.map((msg) => 
                    msg.id === assistantMessageId 
                      ? { ...msg, thinking: thinkingText }
                      : msg
                  )
                )
              }

              if (event.text) {
                assistantContent += event.text
                setThinkingMessage(null)
                setMessages((prev) => 
                  prev.map((msg) => 
                    msg.id === assistantMessageId 
                      ? { ...msg, content: assistantContent, isStreaming: true }
                      : msg
                  )
                )
              }

              if (event.chunks && Array.isArray(event.chunks)) {
                sources = event.chunks
                setMessages((prev) => 
                  prev.map((msg) => 
                    msg.id === assistantMessageId 
                      ? { ...msg, sources }
                      : msg
                  )
                )
              }
            } catch {
            }
          }
        }

        setMessages((prev) => 
          prev.map((msg) => 
            msg.id === assistantMessageId 
              ? { ...msg, content: assistantContent, sources, isStreaming: false }
              : msg
          )
        )
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setError(err)
          
          setMessages((prev) => 
            prev.map((msg) => 
              msg.id === assistantMessageId 
                ? { ...msg, content: 'Sorry, something went wrong. Please try again.', isStreaming: false }
                : msg
            )
          )
        }
      } finally {
        setIsLoading(false)
        setThinkingMessage(null)
        abortControllerRef.current = null
      }
    },
    [options]
  )

  return { messages, isLoading, sendMessage, error, thinkingMessage }
}