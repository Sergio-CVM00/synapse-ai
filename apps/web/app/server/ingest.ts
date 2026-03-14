import { createServerFn } from '@tanstack/react-start'
import { createServerSupabaseClient } from '~/lib/supabase.server'

export const triggerIngest = createServerFn({ method: 'POST' })
  .validator((data: { collectionId: string; sourceType: 'file' | 'url'; sourceData: string }) => data)
  .handler(async ({ data }) => {
    const supabase = createServerSupabaseClient()
    const agentUrl = process.env.AGENT_URL || 'http://localhost:8000'

    const { data: source, error: sourceError } = await supabase
      .from('sources')
      .insert({
        collection_id: data.collectionId,
        type: data.sourceType,
        name: data.sourceType === 'url' ? data.sourceData : 'file',
        status: 'pending',
      })
      .select()
      .single()

    if (sourceError) throw sourceError

    const { data: job, error: jobError } = await supabase
      .from('indexing_jobs')
      .insert({
        collection_id: data.collectionId,
        source_id: source.id,
        status: 'queued',
        progress: 0,
      })
      .select()
      .single()

    if (jobError) throw jobError

    await fetch(`${agentUrl}/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        collection_id: data.collectionId,
        source_id: source.id,
        source_type: data.sourceType,
        source_data: data.sourceData,
      }),
    })

    return { jobId: job.id, sourceId: source.id }
  })

export const getIngestStatus = createServerFn({ method: 'GET' })
  .validator((jobId: string) => jobId)
  .handler(async ({ data: jobId }) => {
    const supabase = createServerSupabaseClient()
    const { data, error } = await supabase
      .from('indexing_jobs')
      .select('*')
      .eq('id', jobId)
      .single()
    if (error) throw error
    return data
  })