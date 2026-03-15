import { createServerFn } from '@tanstack/react-start'
import { createServerSupabaseClient } from '~/lib/supabase.server'
import { z } from 'zod'

const TriggerIngestData = z.object({
  collectionId: z.string().min(1),
  sourceType: z.enum(['file', 'url']),
  sourceData: z.string().min(1),
})

export const triggerIngest = createServerFn({ method: 'POST' })
  .handler(async ({ data }) => {
    const validated = TriggerIngestData.parse(data)
    const supabase = createServerSupabaseClient()
    const agentUrl = process.env.AGENT_URL || 'http://localhost:8000'

    const { data: source, error: sourceError } = await supabase
      .from('sources')
      .insert({
        collection_id: validated.collectionId,
        type: validated.sourceType,
        name: validated.sourceType === 'url' ? validated.sourceData : 'file',
        original_path: null,
        url: validated.sourceType === 'url' ? validated.sourceData : null,
        file_size: null,
        status: 'pending',
      })
      .select()
      .single()

    if (sourceError) throw sourceError
    if (!source) throw new Error('Failed to create source')

    const { data: job, error: jobError } = await supabase
      .from('indexing_jobs')
      .insert({
        collection_id: validated.collectionId,
        source_id: source.id,
        status: 'queued',
        progress: 0,
        error_message: null,
        started_at: null,
        completed_at: null,
      })
      .select()
      .single()

    if (jobError) throw jobError
    if (!job) throw new Error('Failed to create indexing job')

    await fetch(`${agentUrl}/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        collection_id: validated.collectionId,
        source_id: source.id,
        source_type: validated.sourceType,
        source_data: validated.sourceData,
      }),
    })

    return { jobId: job.id, sourceId: source.id }
  })

const GetIngestStatusData = z.string()

export const getIngestStatus = createServerFn({ method: 'POST' })
  .handler(async ({ data: jobId }) => {
    const validatedJobId = GetIngestStatusData.parse(jobId)
    const supabase = createServerSupabaseClient()
    const { data, error } = await supabase
      .from('indexing_jobs')
      .select('*')
      .eq('id', validatedJobId)
      .single()
    if (error) throw error
    return data
  })
