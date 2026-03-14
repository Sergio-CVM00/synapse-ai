import { useState } from 'react'
import type { Chunk } from '../../hooks/useChat'

interface SourcesPanelProps {
  chunks: Chunk[]
  isOpen: boolean
  onToggle: () => void
}

export function SourcesPanel({ chunks, isOpen, onToggle }: SourcesPanelProps) {
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set())

  const toggleChunk = (chunkId: string) => {
    setExpandedChunks((prev) => {
      const next = new Set(prev)
      if (next.has(chunkId)) {
        next.delete(chunkId)
      } else {
        next.add(chunkId)
      }
      return next
    })
  }

  const getSourceName = (chunk: Chunk): string => {
    if (chunk.metadata?.file_path) {
      const path = chunk.metadata.file_path as string
      return path.split('/').pop() || path
    }
    if (chunk.metadata?.url) {
      const url = chunk.metadata.url as string
      try {
        return new URL(url).pathname || url
      } catch {
        return url
      }
    }
    return chunk.id.slice(0, 8)
  }

  return (
    <>
      {/* Toggle Button */}
      <button
        onClick={onToggle}
        className={`fixed right-4 top-1/2 -translate-y-1/2 z-40 flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg shadow-sm hover:bg-gray-50 transition-all duration-200 ${
          isOpen ? 'right-[320px]' : 'right-4'
        }`}
        aria-label={isOpen ? 'Close sources panel' : 'Open sources panel'}
      >
        <svg className="w-4 h-4 text-gray-600" viewBox="0 0 20 20" fill="currentColor">
          <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
        </svg>
        <span className="text-sm font-medium text-gray-700">
          {chunks.length}
        </span>
        <svg 
          className={`w-4 h-4 text-gray-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} 
          viewBox="0 0 20 20" 
          fill="currentColor"
        >
          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
        </svg>
      </button>

      {/* Panel */}
      <div
        className={`fixed right-0 top-0 h-full w-80 bg-white border-l border-gray-200 shadow-xl z-30 transform transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-gray-500" viewBox="0 0 20 20" fill="currentColor">
                <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
              </svg>
              <h2 className="text-base font-semibold text-gray-900">Sources</h2>
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs font-medium rounded-full">
                {chunks.length}
              </span>
            </div>
            <button 
              onClick={onToggle}
              className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              aria-label="Close panel"
            >
              <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chunks.map((chunk, index) => {
              const isExpanded = expandedChunks.has(chunk.id)
              return (
                <div 
                  key={chunk.id} 
                  className="group bg-gray-50 rounded-xl overflow-hidden border border-gray-100 hover:border-gray-200 transition-colors duration-200"
                >
                  <button
                    onClick={() => toggleChunk(chunk.id)}
                    className="w-full flex items-start gap-3 p-3 text-left"
                  >
                    <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center bg-blue-100 text-blue-600 text-xs font-semibold rounded-md">
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {getSourceName(chunk)}
                      </p>
                      {chunk.metadata?.heading && (
                        <p className="text-xs text-gray-500 truncate mt-0.5">
                          {chunk.metadata.heading as string}
                        </p>
                      )}
                    </div>
                    <svg 
                      className={`w-4 h-4 text-gray-400 flex-shrink-0 mt-1 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                      viewBox="0 0 20 20" 
                      fill="currentColor"
                    >
                      <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </button>
                  
                  <div 
                    className={`overflow-hidden transition-all duration-200 ease-in-out ${
                      isExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
                    }`}
                  >
                    <div className="px-3 pb-3 pt-0">
                      <div className="pl-9">
                        <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                          {chunk.content}
                        </p>
                        <p className="text-xs text-gray-400 mt-2 font-mono">
                          ID: {chunk.id.slice(0, 12)}...
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/5 z-20"
          onClick={onToggle}
          aria-hidden="true"
        />
      )}
    </>
  )
}
