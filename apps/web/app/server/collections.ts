import { createServerFn } from '@tanstack/react-start'
import { createServerSupabaseClient } from '~/lib/supabase.server'
import { z } from 'zod'

export const getCollections = createServerFn({ method: 'GET' }).handler(async () => {
  const supabase = createServerSupabaseClient()
  const { data, error } = await supabase
    .from('collections')
    .select('*')
    .order('created_at', { ascending: false })
  if (error) throw error
  return data
})

const GetCollectionData = z.string()

export const getCollection = createServerFn({ method: 'POST' })
  .handler(async ({ data: id }) => {
    const collectionId = GetCollectionData.parse(id)
    const supabase = createServerSupabaseClient()
    const { data, error } = await supabase
      .from('collections')
      .select('*, sources(*), indexing_jobs(*)')
      .eq('id', collectionId)
      .single()
    if (error) throw error
    return data
  })

const CreateCollectionData = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
})

export const createCollection = createServerFn({ method: 'POST' })
  .handler(async ({ data }) => {
    const validated = CreateCollectionData.parse(data)
    const supabase = createServerSupabaseClient()
    const { data: collection, error } = await supabase
      .from('collections')
      .insert({
        name: validated.name,
        description: validated.description ?? null,
        status: 'ready',
        chunk_count: 0,
        user_id: '',
      })
      .select()
      .single()
    if (error) throw error
    return collection
  })

const DeleteCollectionData = z.string()

export const deleteCollection = createServerFn({ method: 'POST' })
  .handler(async ({ data: id }) => {
    const collectionId = DeleteCollectionData.parse(id)
    const supabase = createServerSupabaseClient()
    const { error } = await supabase.from('collections').delete().eq('id', collectionId)
    if (error) throw error
    return { success: true }
  })
