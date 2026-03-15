import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

interface IndexingJob {
  id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

interface UseIngestOptions {
  jobId?: string
  onComplete?: () => void
  onError?: (error: Error) => void
}

interface UseIngestReturn {
  job: IndexingJob | null
  isPolling: boolean
  progress: number
  status: IndexingJob['status'] | null
  error: string | null
}

export function useIngest(options: UseIngestOptions = {}): UseIngestReturn {
  const queryClient = useQueryClient()
  const [isPolling, setIsPolling] = useState(false)

  const { data: job, isLoading } = useQuery({
    queryKey: ['indexingJob', options.jobId],
    queryFn: async () => {
      if (!options.jobId) return null
      const response = await fetch(`/api/ingest/status?jobId=${options.jobId}`)
      if (!response.ok) throw new Error('Failed to fetch job status')
      return response.json() as Promise<IndexingJob>
    },
    enabled: !!options.jobId,
    refetchInterval: (query) => {
      const job = query.state.data
      if (!job || job.status === 'done' || job.status === 'failed') {
        return false
      }
      return 1000
    },
  })

  useEffect(() => {
    if (!job) return
    if (job.status === 'queued' || job.status === 'running') {
      setIsPolling(true)
    } else if (job.status === 'done') {
      setIsPolling(false)
      options.onComplete?.()
    } else if (job.status === 'failed') {
      setIsPolling(false)
      options.onError?.(new Error(job.error_message || 'Indexing failed'))
    }
  }, [job, options])

  const currentJob: IndexingJob | null = job ?? null
  
  return {
    job: currentJob,
    isPolling: isPolling || isLoading,
    progress: job?.progress ?? 0,
    status: job?.status ?? null,
    error: job?.error_message ?? null,
  }
}