interface StreamingIndicatorProps {
  message?: string
}

export function StreamingIndicator({ message = 'Thinking...' }: StreamingIndicatorProps) {
  return (
    <div className="flex items-center gap-3 px-5 py-3">
      <span className="inline-flex items-center gap-1">
        <span 
          className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" 
          style={{ animationDelay: '0ms', animationDuration: '600ms' }} 
        />
        <span 
          className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" 
          style={{ animationDelay: '150ms', animationDuration: '600ms' }} 
        />
        <span 
          className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" 
          style={{ animationDelay: '300ms', animationDuration: '600ms' }} 
        />
      </span>
      <span className="text-sm text-gray-500 font-medium">{message}</span>
    </div>
  )
}
