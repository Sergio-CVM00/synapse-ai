import { createServerFn } from '@tanstack/react-start'
import { createServerSupabaseClient } from '~/lib/supabase.server'

export const getCollections = createServerFn({ method: 'GET' }).handler(async () => {
  const supabase = createServerSupabaseClient()
  const { data, error } = await supabase
    .from('collections')
    .select('*')
    .order('created_at', { ascending: false })
  if (error) throw error
  return data
})

export const getCollection = createServerFn({ method: 'GET' })
  .validator((id: string) => id)
  .handler(async ({ data: id }) => {
    const supabase = createServerSupabaseClient()
    const { data, error } = await supabase
      .from('collections')
      .select('*, sources(*), indexing_jobs(*)')
      .eq('id', id)
      .single()
    if (error) throw error
    return data
  })

export const createCollection = createServerFn({ method: 'POST' })
  .validator((data: { name: string; description?: string }) => data)
  .handler(async ({ data }) => {
    const supabase = createServerSupabaseClient()
    const { data: collection, error } = await supabase
      .from('collections')
      .insert({
        name: data.name,
        description: data.description,
        status: 'ready',
        chunk_count: 0,
      })
      .select()
      .single()
    if (error) throw error
    return collection
  })

export const deleteCollection = createServerFn({ method: 'POST' })
  .validator((id: string) => id)
  .handler(async ({ data: id }) => {
    const supabase = createServerSupabaseClient()
    const { error } = await supabase.from('collections').delete().eq('id', id)
    if (error) throw error
    return { success: true }
  })