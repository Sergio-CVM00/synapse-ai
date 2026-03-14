import { useMemo } from 'react'
import type { ChatMessage } from '../../hooks/useChat'

interface MessageBubbleProps {
  message: ChatMessage
}

function formatContent(content: string): string {
  return content
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  
  const formattedContent = useMemo(() => 
    formatContent(message.content), 
    [message.content]
  )

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} w-full`}>
      <div
        className={`max-w-[85%] px-5 py-3 rounded-2xl ${
          isUser 
            ? 'bg-blue-600 text-white' 
            : 'bg-white border border-gray-200 text-gray-900'
        }`}
      >
        {!isUser && message.thinking && (
          <div className="flex items-center gap-2 mb-2 text-sm text-gray-500">
            <span className="inline-flex gap-1">
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </span>
            <span className="text-xs">{message.thinking}</span>
          </div>
        )}
        
        <div className={`whitespace-pre-wrap break-words ${isUser ? '' : 'prose prose-sm max-w-none'}`}>
          {formattedContent}
          {message.isStreaming && (
            <span className="inline-flex ml-1">
              <span className="w-0.5 h-4 bg-blue-500 animate-pulse" />
            </span>
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-medium text-gray-500">Sources:</span>
              {message.sources.map((source, index) => (
                <span 
                  key={source.id}
                  className="inline-flex items-center px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-md font-mono"
                >
                  [{source.id.slice(0, 8)}]
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
