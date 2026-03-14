import { useState, useRef, useEffect } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { ChatInput } from '../../components/chat/ChatInput'
import { MessageBubble } from '../../components/chat/MessageBubble'
import { SourcesPanel } from '../../components/chat/SourcesPanel'
import { useChat, type ChatMessage, type Chunk } from '../../hooks/useChat'

function ChatIndex() {
  const navigate = useNavigate()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [collectionIds] = useState<string[]>([])

  const { messages, isLoading, sendMessage, error, thinkingMessage } = useChat({
    collectionIds,
    onThinking: () => {},
  })

  const allChunks: Chunk[] = messages
    .filter((msg): msg is ChatMessage & { sources: Chunk[] } => 
      msg.role === 'assistant' && !!msg.sources && msg.sources.length > 0
    )
    .flatMap((msg) => msg.sources)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinkingMessage])

  useEffect(() => {
    if (allChunks.length > 0 && !sourcesOpen) {
      setSourcesOpen(true)
    }
  }, [allChunks.length])

  const handleSend = async (content: string) => {
    await sendMessage(content)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-gray-50 rounded-2xl overflow-hidden shadow-sm border border-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 flex items-center justify-center bg-blue-100 rounded-xl">
            <svg className="w-5 h-5 text-blue-600" viewBox="0 0 20 20" fill="currentColor">
              <path d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-gray-900">New Chat</h1>
            <p className="text-sm text-gray-500">Ask anything about your knowledge base</p>
          </div>
        </div>
        {allChunks.length > 0 && (
          <button
            onClick={() => setSourcesOpen(!sourcesOpen)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
            </svg>
            {allChunks.length} sources
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 flex items-center justify-center bg-blue-50 rounded-2xl mb-4">
              <svg className="w-8 h-8 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Start a conversation</h2>
            <p className="text-gray-500 max-w-md">
              Ask questions about your knowledge base and get answers with citations from your documents.
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))
        )}
        
        {isLoading && !thinkingMessage && messages.length > 0 && messages[messages.length - 1]?.role !== 'assistant' && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl px-5 py-3">
              <span className="inline-flex items-center gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Error */}
      {error && (
        <div className="mx-6 mb-4 p-4 bg-red-50 border border-red-100 rounded-xl">
          <p className="text-sm text-red-600">{error.message}</p>
        </div>
      )}

      {/* Input */}
      <ChatInput 
        onSend={handleSend} 
        disabled={isLoading}
        placeholder="Ask a question about your documents..."
      />

      {/* Sources Panel */}
      <SourcesPanel 
        chunks={allChunks} 
        isOpen={sourcesOpen} 
        onToggle={() => setSourcesOpen(!sourcesOpen)} 
      />
    </div>
  )
}

export const Route = createFileRoute('/dashboard/chat/')({
  component: ChatIndex,
})
