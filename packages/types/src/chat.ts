export interface Conversation {
  id: string
  user_id: string
  collection_ids: string[]
  title: string | null
  summary: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  sources: Array<{
    chunk_id: string
    score: number
  }>
  created_at: string
}

export interface SSEEvent {
  type: 'thinking' | 'token' | 'sources' | 'done'
  node?: string
  message?: string
  text?: string
  chunks?: Array<{
    id: string
    content: string
    metadata: Record<string, unknown>
  }>
}

export interface ChatRequest {
  message: string
  collection_ids: string[]
  conversation_id?: string
}

export interface ChatResponse {
  content: string
  sources: Array<{
    id: string
    content: string
    metadata: Record<string, unknown>
  }>
}