export interface Collection {
  id: string
  user_id: string
  name: string
  description: string | null
  status: 'ready' | 'indexing' | 'error'
  chunk_count: number
  created_at: string
}

export interface Source {
  id: string
  collection_id: string
  type: 'file' | 'url'
  name: string
  original_path: string | null
  url: string | null
  file_size: number | null
  status: 'pending' | 'indexing' | 'done' | 'error'
  indexed_at: string | null
}

export interface Chunk {
  id: string
  source_id: string
  collection_id: string
  content: string
  embedding: number[]
  search_vec: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface IndexingJob {
  id: string
  collection_id: string
  source_id: string | null
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

export type Database = {
  public: {
    Tables: {
      collections: {
        Row: Collection
        Insert: Omit<Collection, 'id' | 'created_at'>
        Update: Partial<Omit<Collection, 'id' | 'created_at'>>
      }
      sources: {
        Row: Source
        Insert: Omit<Source, 'id' | 'indexed_at'>
        Update: Partial<Omit<Source, 'id' | 'indexed_at'>>
      }
      chunks: {
        Row: Chunk
        Insert: Omit<Chunk, 'id' | 'created_at'>
        Update: Partial<Omit<Chunk, 'id' | 'created_at'>>
      }
      indexing_jobs: {
        Row: IndexingJob
        Insert: Omit<IndexingJob, 'id'>
        Update: Partial<Omit<IndexingJob, 'id'>>
      }
    }
  }
}